# Terminal UI Improve-2：问题分析

## 1. 背景

IRIS CLI 的用户输入层（`src/application/cli/main.py` `_cli_loop`）当前使用一行代码完成所有输入：

```python
query = await asyncio.to_thread(ctx.console.input, prompt)
```

`ctx.console` 是 `rich.console.Console`，其 `.input()` 是对 Python 内置 `input()` 的薄封装。在 Windows 平台上，`input()` 完全委托给 **Win32 Console API（ReadConsole + ENABLE_LINE_INPUT）**进行行编辑。这一设计导致了以下一系列已知和潜在问题。

---

## 2. 已确认的问题

### 2.1 历史导航时草稿丢失（P0）

**现象**：用户正在输入一段较长的 prompt，尚未按 Enter 发送，此时按 PgUp（或方向键上）浏览历史消息，再按 PgDn（或方向键下）返回，原先正在输入的内容**完全消失**，变为空行。

**根因**：
Win32 Console API 的内置历史导航（DoReadLine 历史缓冲）在向下翻出历史末尾时，**不恢复用户之前键入的草稿（draft）**，而是返回空缓冲区。这与 GNU readline（Linux/macOS）的行为不同——readline 会将当前草稿临时保存到"历史第0项（youngest slot）"，按下 ↓ 到底后恢复。

**影响**：Win32 Console 下任何 Python `input()` 调用均有此问题，与 IRIS 代码无关；但 IRIS 从未主动规避或修复它，应用层对此无任何保护机制。

---

### 2.2 无跨会话历史持久化（P1）

**现象**：每次启动 `iris` 命令，之前输入过的历史完全不可用，需要重新输入。

**根因**：
`AppState` 中没有任何历史存储字段；`_cli_loop` 不保存任何已提交的输入。Win32 Console 的内置历史仅在**同一进程生命周期**内有效，退出即清空。

**影响**：用户每次会话都要重复输入常用命令（如 `/switch agent`、`/mode deep` 等），降低效率。

---

### 2.3 无 Tab 命令补全（P1）

**现象**：输入 `/` 后按 Tab，终端无响应或插入制表符，无法看到可用命令列表。

**根因**：
CLI 层从未实现任何 `Completer`。项目虽然在 `render.py` 中静态定义了全部命令表（`GLOBAL_COMMANDS`、`AGENT_ENGINE_COMMANDS` 等），但这些数据仅用于渲染帮助面板，未与输入层打通。

**影响**：28 个跨 4 种 engine 的命令，用户必须记忆或频繁查阅 `/help`。

---

### 2.4 无参数提示/内联 ghost text（P2）

**现象**：输入 `/model ` 后，界面无任何提示，用户不知道参数格式是 `<provider> [model]` 还是其他。

**根因**：无 AutoSuggest 机制，无 bottom toolbar，无内联参数暗示。

**影响**：命令使用门槛高，出错时才能看到 "Usage: /model <provider> [model]" 错误提示。

---

### 2.5 无多行输入支持（P2）

**现象**：粘贴含换行符的代码片段或多行 prompt 时，换行符被识别为 Enter，导致消息提前截断发送。

**根因**：当前输入模式为单行（`input()` 在遇到 `\n` 时立即返回），没有 Shift+Enter 多行模式。

**影响**：涉及代码的 agent 使用场景（如 `/use coding`）受限。

---

### 2.6 `asyncio.to_thread` 包装（P3 / 架构债）

**现象**：无直接用户感知，但属于架构问题。

**根因**：`input()` 是同步阻塞调用，必须用 `asyncio.to_thread` 在线程池中运行，以免阻塞事件循环。这增加了线程开销，也使 Ctrl+C 等信号处理略显复杂。

**影响**：`prompt_toolkit` 提供原生 `prompt_async()`，可以完全消除此包装。

---

## 3. 问题影响矩阵

| 问题 | 影响用户频率 | 恢复成本 | 优先级 |
|---|---|---|---|
| 历史导航草稿丢失 | 每次浏览历史必现 | 重新输入，高 | P0 |
| 无跨会话历史 | 每次启动必现 | 重新输入，中 | P1 |
| 无 Tab 补全 | 每次输入命令时 | 查阅帮助，低 | P1 |
| 无参数 ghost text | 不熟悉命令时 | 试错，低 | P2 |
| 无多行输入 | 粘贴代码场景 | 分段发送，中 | P2 |
| to_thread 包装 | 无直接感知 | 无 | P3 |

---

## 4. 受影响的代码范围

| 文件 | 问题直接关联 |
|---|---|
| `src/application/cli/main.py` | `_cli_loop` 第 148-149 行：`asyncio.to_thread(ctx.console.input, prompt)` |
| `src/application/cli/state.py` | `AppState` 缺少输入历史 / PromptSession 字段 |
| `src/application/cli/gui/interact.py` | `prompt_confirm`、`prompt_select` 同样使用 `console.input()`，也缺少历史和中断保护 |
| `pyproject.toml` / `requirements.txt` | `prompt_toolkit` 仅为传递依赖，未显式声明 |

---

## 5. 为什么不用 readline / pyreadline3

| 方案 | 问题 |
|---|---|
| Python 内置 `readline`（GNU） | Windows 无内置，需额外安装 `pyreadline3`，且 `pyreadline3` 已停止维护（2022年）|
| `pyreadline3` | 未维护，Windows 11 兼容性差，不支持 asyncio native prompt |
| `rich.prompt.Prompt` | 基于 `input()`，无历史、无补全、无 async |
| `prompt_toolkit` | 纯 Python，跨平台，原生 asyncio，活跃维护，IPython 同款 ✓ |

---

## 6. 结论

所有问题均源于同一根因：**CLI 输入层将所有行编辑能力外包给了 OS / 终端，自身零控制权**。修复不需要重写业务逻辑，只需在 `_cli_loop` 的输入点替换底层驱动。`prompt_toolkit 3.0.52`（已安装）是唯一合适的解决方案。
