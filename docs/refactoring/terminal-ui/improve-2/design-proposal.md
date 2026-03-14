# Terminal UI Improve-2：设计方案

## 1. 设计目标与约束

### 目标
1. 修复历史导航草稿丢失（P0）
2. 实现跨会话历史持久化（P1）
3. 实现 engine-aware Tab 命令补全 + 参数 ghost text（P1/P2）
4. 支持 Shift+Enter 多行输入（P2）
5. 消除 `asyncio.to_thread` 包装（P3）

### 约束
- **最小侵入**：不修改 `commands/`、`state.py` 业务逻辑
- **单一职责**：输入关注点完全内聚到新增的 `input/` 包
- **路径一致性**：历史文件路径遵循已有的三层配置体系（`ProjectContext`）
- **优雅降级**：`prompt_toolkit` 不可用时自动回退 `console.input()`

---

## 2. 新增模块结构

```
src/application/cli/
  input/                        ← 新增 package（输入层全部关注点）
    __init__.py                 ← 对外只暴露: create_input_session()
    session.py                  ← PromptSession 工厂（核心组装器）
    history.py                  ← HistoryPathResolver（路径策略）
    completer.py                ← CommandCompleter（engine-aware 补全）
    suggest.py                  ← CommandAutoSuggest（inline ghost text）
    keybindings.py              ← 自定义键绑定（Shift+Enter 等）
```

**设计原则说明**：
- 每个文件单一职责，可独立测试
- `session.py` 是唯一依赖 `AppState` 的文件，其余文件无应用层依赖
- `main.py` 只调用 `create_input_session(ctx)` 一个函数，无需了解内部

---

## 3. 模块详细设计

### 3.1 `history.py` — 历史路径策略

**设计决策**：历史文件应跟随项目（project-scoped），而非全局共享。原因：
- 不同项目与不同 agent/engine 交互，历史语境不同
- 与现有 `ProjectContext.iris_dir` 路径体系完全一致
- 全局 fallback 保证初始化阶段（`ProjectContext` 未就绪时）可用

```
路径优先级（高 → 低）：
  1. <project>/.iris/input_history    ← 项目级，ProjectContext.iris_dir
  2. ~/.iris/input_history            ← 用户级 fallback（IrisShareDir）
  3. InMemoryHistory                  ← 最终 fallback（无文件访问权限时）
```

实现接口：
```python
class HistoryPathResolver:
    def resolve(self, ctx: AppState) -> BaseHistory:
        # 优先使用 project-level，不可用则 fallback
        ...
```

**历史文件格式**：`prompt_toolkit.history.FileHistory` 原生格式（每条记录以 `+` 开头，`#` 注释行，条目间空行分隔），无需自定义序列化。

---

### 3.2 `completer.py` — Engine-Aware 命令补全

**补全策略**：

```
用户输入         触发条件           补全内容
─────────────────────────────────────────────────────
(空)             按 Tab             当前 engine 可用命令列表
/                按 Tab             全部可用命令
/mo              按 Tab             /mode, /model（过滤前缀）
/mode            按 Tab             basic, deep（参数值）
/mode b          按 Tab             basic
/switch          按 Tab             llm, agent, agentflow, dify
/mcp st          按 Tab             status（子命令）
/skills          按 Tab             list, create, info, reload
/skills c        按 Tab             create
/stream          按 Tab             on, off, enable, disable
```

**Engine 过滤规则**（直接读 `ctx.current_engine`，实时动态）：

| Engine | 可用命令（除 `all` 外追加） |
|---|---|
| `all`（全局） | `/switch`, `/help`, `/info`, `/exit`, `/quit` |
| `llm` | `/model <provider> [model]`, `/llms`, `/reload`, `/stream [on\|off]` |
| `agent` | `/mode [basic\|deep]`, `/model`, `/use [research\|coding\|analysis]`, `/deep`, `/tools`, `/mcp`, `/connector`, `/skills` |
| `agent`+`llm`+`agentflow` | `/new`, `/clear`, `/sessions`, `/restore`, `/delete_session`, `/cleanup` |
| `agentflow` | `/graph`, `/graph-model`, `/nodes`, `/visualize` |
| `dify` | `/upload`, `/files`, `/reset`, `/reconnect` |

**实现接口**：
```python
class CommandCompleter(Completer):
    def __init__(self, ctx: AppState): ...

    def get_completions(self, document: Document, complete_event: CompleteEvent):
        # 解析当前输入，返回 Completion 对象列表
        # 每个 Completion 携带 display_meta（命令 help_text）
        ...
```

每个补全项附带 `display_meta` 展示命令简介（从 `BaseCommand.help_text` 获取），效果：

```
> /m[Tab]
  /mode          Switch between basic and deep agent modes.
  /mcp           Manage MCP tools.
  /model         Switch provider/model for the agent engine.
```

---

### 3.3 `suggest.py` — 参数 Ghost Text（内联暗示）

**Ghost text** = 用户已输入部分命令后，右侧以**浅灰色**自动显示剩余参数提示（类似 fish shell）。

**实现方式**：继承 `prompt_toolkit.auto_suggest.AutoSuggest`，重写 `get_suggestion()`：

```python
class CommandAutoSuggest(AutoSuggest):
    def get_suggestion(self, buffer, document) -> Optional[Suggestion]:
        text = document.text_before_cursor
        # 解析已输入的命令名和已有参数
        # 返回剩余参数的 hint 字符串
        ...
```

**参数 ghost text 规格表**：

| 已输入 | Ghost text 显示（浅灰） |
|---|---|
| `/model ` | `<provider> [model]` |
| `/model openai ` | `[model]` |
| `/mode ` | `basic\|deep` |
| `/switch ` | `llm \| agent \| agentflow \| dify` |
| `/restore ` | `<session_id>` |
| `/delete_session ` | `<session_id>` |
| `/use ` | `research \| coding \| analysis` |
| `/stream ` | `on \| off` |
| `/skills ` | `list \| create <name> \| info <name> \| reload` |
| `/skills create ` | `<name> [--project]` |
| `/mcp ` | `status [-v] \| tools [--json] \| reload` |
| `/connector ` | `status [-v] \| tools [--json] \| reload` |
| `/deep ` | `status \| config reload \| filesystem status\|reload` |
| `/files ` | `[clear \| remove <index>]` |
| `/upload ` | `<file_path>` |

**注意**：Ghost text 和 Tab 补全**互补而非互斥**：
- Ghost text：已知命令后提示参数格式（无需按 Tab，实时显示）
- Tab 补全：命令名未输入完整时，枚举可选项

---

### 3.4 `keybindings.py` — 自定义键绑定

**Shift+Enter 多行输入**（Windows 下 Meta 键 = Alt，但 Alt+Enter 在 Windows Terminal 可能被系统拦截，故改用 Shift+Enter）：

```python
from prompt_toolkit.key_binding import KeyBindings

def build_key_bindings() -> KeyBindings:
    kb = KeyBindings()

    @kb.add('shift+enter')
    def insert_newline(event):
        """Shift+Enter 插入换行（不提交）"""
        event.app.current_buffer.insert_text('\n')

    @kb.add('c-l')
    def clear_screen(event):
        """Ctrl+L 清屏"""
        event.app.renderer.clear()

    return kb
```

**多行显示机制**：
- `PromptSession` 使用 `multiline=False`（Enter 提交）
- 用户按 Shift+Enter 向 buffer 插入 `\n`
- `prompt_toolkit` 的 `BufferControl` **自动将 buffer 中的换行渲染为多行显示**（无需设置 `multiline=True`）
- Enter 提交后，`_cli_loop` 收到含 `\n` 的完整字符串，正常处理

---

### 3.5 `session.py` — PromptSession 工厂

核心组装器，将上述组件拼装为一个 `PromptSession` 实例：

```python
from prompt_toolkit import PromptSession
from prompt_toolkit.patch_stdout import patch_stdout

def create_input_session(ctx: AppState) -> PromptSession:
    history = HistoryPathResolver().resolve(ctx)
    completer = CommandCompleter(ctx)
    suggest = CommandAutoSuggest()
    kb = build_key_bindings()

    return PromptSession(
        history=history,
        completer=completer,
        auto_suggest=suggest,
        key_bindings=kb,
        complete_while_typing=False,   # 仅 Tab 触发，不影响自由文本输入
        enable_history_search=True,    # Ctrl+R 反向搜索历史
    )
```

**`create_input_session` 的调用时机**：在 `_cli_loop` 启动时调用一次（非每次循环），`PromptSession` 贯穿整个 CLI 生命周期，history 对象保持状态连续性。

`create_input_session` **不保存到 `AppState`**：其生命周期与 `_cli_loop` 函数完全绑定，无需跨层传递。

---

## 4. Rich + prompt_toolkit 共存方案

两者均向 stdout 写入，必须协调以避免输出撕裂。

### 问题场景

```
时序：
  T1  prompt_toolkit 绘制 prompt 行（光标在行末）
  T2  rich 输出流式 token（写入 stdout，光标跳位）
  T3  prompt_toolkit 重绘 prompt → 与 T2 的输出重叠
```

### 解决方案：`patch_stdout`

```python
# main.py _cli_loop 中
from prompt_toolkit.patch_stdout import patch_stdout

async def _cli_loop(ctx: AppState) -> None:
    input_session = create_input_session(ctx)
    while True:
        plain_prompt = _build_plain_prompt(ctx)     # 去掉 Rich markup 标记
        with patch_stdout(raw=True):                # ← 关键
            query = await input_session.prompt_async(plain_prompt)
```

`patch_stdout(raw=True)` 的作用：
1. 临时替换 `sys.stdout`，拦截所有写入
2. 在 prompt 行之前安全插入外部输出
3. 自动将 prompt 行重绘到最底部
4. `raw=True` 兼容 rich 的 ANSI 控制码，不做额外转义

---

## 5. `_build_plain_prompt` 设计

`prompt_toolkit` 的 `prompt_async(message)` 接受普通字符串或 `FormattedText`，不理解 Rich 的 `[bold][/bold]` markup。需要新增一个并行的 plain 版本：

```python
def _build_plain_prompt(ctx: AppState) -> str:
    """返回不含 Rich markup 的 prompt 字符串，供 prompt_toolkit 使用。"""
    engine = ctx.current_engine
    if engine == "agent":
        cfg = ctx.get_engine_config()
        agent_type = cfg.get("agent_type", "basic").upper()
        stream = "~" if cfg.get("streaming") else ""
        return f"\n{engine}:{agent_type}{stream} > "
    if engine == "llm":
        cfg = ctx.get_engine_config()
        stream = "~" if cfg.get("streaming") else ""
        return f"\n{engine}{stream} > "
    return f"\n{engine} > "
```

（原 `_build_prompt` 保留不动，仍用于 rich 的 `console.print` 之外的场景，如初始化时的状态显示。）

---

## 6. 降级策略

若 `prompt_toolkit` 导入失败或初始化异常，`create_input_session` 返回一个 `_FallbackSession` 包装：

```python
class _FallbackSession:
    """降级：使用原始 console.input()"""
    def __init__(self, console): self._console = console

    async def prompt_async(self, prompt: str, **_) -> str:
        return await asyncio.to_thread(self._console.input, prompt)
```

`_cli_loop` 无需感知降级，调用接口完全相同。

---

## 7. `interact.py` 的处理（P2 范围，本次不改）

`gui/interact.py` 中的 `prompt_confirm` 和 `prompt_select` 同样使用 `console.input()`，但：
- 它们是一次性交互（确认/选择），不需要历史
- HITL 场景下可能在 agent 执行中途调用，输入上下文不同

这部分改造推迟到 **improve-3**，本次不涉及，降低风险。

---

## 8. 依赖声明

`prompt_toolkit 3.0.52` 已在 `.venv` 中安装（传递依赖），需在 `pyproject.toml` 中显式声明以锁定版本：

```toml
# pyproject.toml dependencies 追加：
"prompt_toolkit>=3.0.0,<4.0.0",
```

`requirements.txt` 已更新为 `prompt_toolkit==3.0.52`。

---

## 9. 设计总结

| 关注点 | 负责模块 | 依赖 |
|---|---|---|
| Session 组装 | `input/session.py` | AppState, 其他 input/ 子模块 |
| 历史路径 | `input/history.py` | ProjectContext |
| 命令补全 | `input/completer.py` | AppState.current_engine, COMMAND_REGISTRY |
| 参数 ghost text | `input/suggest.py` | 无（纯文本解析） |
| 键绑定 | `input/keybindings.py` | 无（纯 prompt_toolkit） |
| 主循环集成 | `main.py` | input/session.py（单一依赖） |
| 降级 | `input/session.py` 内部 | rich.Console |
