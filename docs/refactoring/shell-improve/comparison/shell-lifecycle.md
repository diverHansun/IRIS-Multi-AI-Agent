# Shell 进程的本质与生命周期

## 一、Shell 的本质

agent 使用 shell 工具，本质上是在 **agent 自身所在的宿主进程内**，通过 Python 标准库的 `subprocess.Popen` 启动了一个子进程。这个子进程就是真实的 shell 程序：

- Windows 默认：`cmd.exe /Q`
- Windows 可选：`powershell.exe -NoLogo -NoProfile`
- Linux / macOS：`/bin/bash --norc --noprofile`

它不是虚拟的、也不是模拟的，而是操作系统级别的真实 shell 进程，和你在终端手动打开一个命令行窗口，效果完全一致。

```
Python 进程（agent harness）
    │
    └─ subprocess.Popen → cmd.exe（子进程，PID 独立）
                              │
                              ├─ 通过 stdin pipe 接收命令
                              ├─ 通过 stdout pipe 输出结果
                              └─ 通过 stderr pipe 输出错误
```

agent harness 与 shell 子进程之间通过三条管道（stdin / stdout / stderr）通信。agent 把命令字符串写入 stdin，再从 stdout/stderr 读取执行结果。

---

## 二、为什么叫"持久化"Shell

区别于每次调用都 fork 一个新进程的做法，本项目采用的是"持久化"方式：shell 子进程在 agent 开始工作时启动，在 agent 本次工作结束时关闭。中间所有的 `shell` 工具调用，全部复用同一个子进程。

这带来两个关键好处：

1. **状态保持**：shell 的工作目录（`cd /some/dir` 之后的位置）、环境变量（`export FOO=bar` 之后的值）在多次命令调用之间自动保留。agent 不需要每次都重新 `cd` 到目标目录。

2. **性能更好**：省去了每次命令调用时启动新 shell 的开销，对于需要执行几十条命令的复杂任务，效果明显。

---

## 三、命令完成如何检测

由于 agent 是把命令写入 stdin 的一个持续运行的进程，没有"命令结束"这个信号，所以需要一个特殊机制来判断当前命令什么时候执行完了。

本项目使用的方式叫做 **唯一标记（marker）**：

每次发送命令时，在命令末尾追加一行 echo，输出一个含随机 UUID 的字符串，同时附上命令的退出码：

```
# Windows
<用户命令>
echo __SHELL_CMD_DONE__<uuid> %ERRORLEVEL%

# Unix
<用户命令>
echo __SHELL_CMD_DONE__<uuid> $?
```

读输出时，一直读到看见这个标记为止，标记后面的数字就是退出码。这样就能准确判断命令结束，并获得退出状态。

---

## 四、Shell 什么时候关闭（释放）

这是一个很关键的问题，答案是：**shell 子进程的生命周期与一次 agent"轮次"（turn）绑定，而不是与整个 Python 进程绑定**。

### 本项目的绑定点

生命周期由中间件（`ShellToolMiddleware`）的两个钩子控制：

| 钩子 | 调用时机 | 动作 |
|---|---|---|
| `before_agent()` | agent 开始处理一条消息前 | 创建（或复用）shell 子进程，`session.start()` |
| `after_agent()` | agent 本次输出完成后 | 关闭子进程，`session.stop()` |

具体源码位置：[middleware.py](../../../src/components/deepagents/runtime_middlewares/shell/middleware.py)

```python
def before_agent(self, state, runtime):
    # 用户发来一条消息，agent 准备工作 → 在这里创建 shell 子进程
    session = self._get_or_create_session(state)
    return {"shell_session": session}

def after_agent(self, state, runtime):
    # agent 本次回复结束 → 在这里关闭 shell 子进程
    session = state.get("shell_session")
    if session:
        session.stop(timeout=self.config.termination_timeout)
```

### 更准确的说法

一次"agent 轮次"是指：用户发送一条消息，agent 思考、调用工具（可能多次）、最终输出回复，这整个过程算一个轮次。

- shell 子进程在轮次开始时启动
- shell 子进程在轮次结束时关闭
- 下一次用户发消息时，会重新启动一个新的子进程

这意味着 **跨轮次不保留 shell 状态**。在第一条消息里 `cd /workspace/foo` 了，在第二条消息里，工作目录会重置回初始的 workspace root。

### HITL 中断时的特殊情况

当 HITL（人工审批）中断发生时，agent 暂停执行，等待用户决定。此时：

- 如果 agent 在等待中意外断开，shell 子进程也会一起消失
- 恢复执行（resume）时，`before_agent()` 会重新调用，检查 session 是否存活：
  - 如果还在（进程没有意外退出）→ 复用
  - 如果已经消失 → 创建新的

```python
def _get_or_create_session(self, state):
    session = state.get("shell_session")
    # 检查是否存活，不存活就重建
    if session and isinstance(session, PersistentShellSession) and session.is_alive():
        return session
    # 重新创建
    new_session = PersistentShellSession(...)
    new_session.start()
    return new_session
```

这是代码里明确注释的设计意图："This supports HITL resume by recreating the session if it doesn't exist."

### Python 进程退出时

当用户杀掉整个 agent 进程（Ctrl+C、kill 命令、关闭终端），Python 进程退出，子进程因为父进程消失也会随之终止（stdout/stderr 管道关闭，读线程退出）。这是操作系统的默认行为，不需要特殊清理。

---

## 五、生命周期图示

```
用户发消息 A
    │
    ▼
before_agent() → 启动 cmd.exe（PID: 1234）
    │
    ├── agent 思考
    ├── 调用 shell("git status")       → 复用 PID 1234
    ├── 调用 shell("npm install")      → 复用 PID 1234（工作目录保留）
    ├── 调用 shell("npm run build")    → 复用 PID 1234
    └── agent 输出回复
    │
after_agent() → 终止 PID 1234
    │
用户发消息 B
    │
    ▼
before_agent() → 启动新的 cmd.exe（PID: 5678）
    │
    ├── agent 思考
    ├── 调用 shell("ls")               → 复用 PID 5678（工作目录已重置）
    └── agent 输出回复
    │
after_agent() → 终止 PID 5678
```

---

## 六、小结

| 问题 | 答案 |
|---|---|
| shell 是什么 | 宿主进程内通过 subprocess.Popen 启动的真实系统 shell 子进程 |
| 何时启动 | agent 开始处理每条用户消息前（before_agent 钩子） |
| 何时关闭 | agent 本次回复结束后（after_agent 钩子） |
| 跨轮次保留状态吗 | 不保留，每轮重新启动 |
| 用户 kill 进程 | 子进程随父进程一起终止，无需特殊清理 |
| HITL 后能复用吗 | 能，只要子进程还存活；否则自动重建 |
