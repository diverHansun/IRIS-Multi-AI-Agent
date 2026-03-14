# Terminal UI Improve-2：实施计划

## 概览

| 阶段 | 内容 | 触及文件 | 风险 |
|---|---|---|---|
| Phase 1 | 依赖声明 + 基础脚手架 | `pyproject.toml`, `input/__init__.py` | 极低 |
| Phase 2 | 历史模块 | `input/history.py` | 低 |
| Phase 3 | 补全模块 | `input/completer.py` | 中（需准确映射命令数据） |
| Phase 4 | Ghost text 模块 | `input/suggest.py` | 低 |
| Phase 5 | 键绑定模块 | `input/keybindings.py` | 低 |
| Phase 6 | Session 工厂 + 降级 | `input/session.py` | 中 |
| Phase 7 | main.py 集成 | `main.py`（约 10 行改动） | 低（改动极小） |
| Phase 8 | pyproject.toml 声明 | `pyproject.toml` | 极低 |

---

## Phase 1：基础脚手架

### 1.1 创建 `src/application/cli/input/__init__.py`

```python
"""
CLI 输入层 — 基于 prompt_toolkit 的行编辑、历史、补全和 ghost text。
对外暴露唯一入口: create_input_session()
"""
from .session import create_input_session

__all__ = ["create_input_session"]
```

---

## Phase 2：历史模块

### 新建 `src/application/cli/input/history.py`

```python
"""历史路径策略：项目级优先，用户级 fallback，最终 InMemoryHistory。"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from prompt_toolkit.history import BaseHistory, FileHistory, InMemoryHistory

if TYPE_CHECKING:
    from src.application.cli.state import AppState

logger = logging.getLogger(__name__)

_HISTORY_FILENAME = "input_history"


class HistoryPathResolver:
    """将 AppState 中的 ProjectContext / 用户目录映射为 prompt_toolkit History 实例。"""

    def resolve(self, ctx: "AppState") -> BaseHistory:
        # 1. 优先：project-level  <project>/.iris/input_history
        if ctx.project_context is not None:
            path = ctx.project_context.iris_dir / _HISTORY_FILENAME
            hist = self._try_file_history(path)
            if hist is not None:
                return hist

        # 2. fallback：user-level  ~/.iris/input_history
        user_path = Path.home() / ".iris" / _HISTORY_FILENAME
        hist = self._try_file_history(user_path)
        if hist is not None:
            return hist

        # 3. 最终 fallback：内存（当前会话有效）
        logger.warning("Cannot write input history to disk; using in-memory history.")
        return InMemoryHistory()

    @staticmethod
    def _try_file_history(path: Path) -> FileHistory | None:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            return FileHistory(str(path))
        except OSError as exc:
            logger.debug("Cannot use history file %s: %s", path, exc)
            return None
```

---

## Phase 3：补全模块

### 新建 `src/application/cli/input/completer.py`

```python
"""
Engine-aware Tab 补全。
读取 COMMAND_REGISTRY 的元数据 + 静态参数表，按当前 engine 过滤返回补全项。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Iterable

from prompt_toolkit.completion import Completer, Completion

if TYPE_CHECKING:
    from prompt_toolkit.document import Document
    from prompt_toolkit.completion import CompleteEvent
    from src.application.cli.state import AppState


# ── 参数补全值表 ──────────────────────────────────────────────────────────────
# key: 命令名（不含 /）, value: 第一层参数可选值列表
_ARG_VALUES: dict[str, list[str]] = {
    "switch":         ["llm", "agent", "agentflow", "dify"],
    "mode":           ["basic", "deep"],
    "stream":         ["on", "off", "enable", "disable"],
    "use":            ["research", "coding", "analysis"],
    "mcp":            ["status", "status -v", "tools", "tools --json", "reload"],
    "connector":      ["status", "status -v", "tools", "tools --json", "reload"],
    "skills":         ["list", "create", "info", "reload"],
    "deep":           ["status", "config reload", "filesystem status", "filesystem reload"],
    "files":          ["clear", "remove"],
    "tools":          ["--list"],
    "sessions":       ["all"],
}

# ── Engine → 可用命令名集合 ────────────────────────────────────────────────────
_GLOBAL = {"switch", "help", "info", "exit", "quit"}
_SESSION_SHARED = {"new", "clear", "sessions", "restore", "delete_session", "cleanup"}

_ENGINE_COMMANDS: dict[str, set[str]] = {
    "llm":       _GLOBAL | _SESSION_SHARED | {"model", "llms", "reload", "stream"},
    "agent":     _GLOBAL | _SESSION_SHARED | {
                     "mode", "model", "use", "deep",
                     "tools", "mcp", "connector", "skills",
                 },
    "agentflow": _GLOBAL | _SESSION_SHARED | {"graph", "graph-model", "nodes", "visualize"},
    "dify":      _GLOBAL | {"upload", "files", "reset", "reconnect"},
}


def _get_command_meta() -> dict[str, str]:
    """从 COMMAND_REGISTRY 中提取命令 → help_text 映射。"""
    try:
        from src.application.commands import COMMAND_REGISTRY
        meta: dict[str, str] = {}
        for name, cmds in COMMAND_REGISTRY.items():
            if cmds:
                meta[name] = cmds[0].help_text
        return meta
    except Exception:
        return {}


class CommandCompleter(Completer):
    """
    按 engine 过滤命令，支持命令名补全和一级参数值补全。
    complete_while_typing=False 时只在按 Tab 时触发。
    """

    def __init__(self, ctx: "AppState") -> None:
        self._ctx = ctx
        self._meta: dict[str, str] = _get_command_meta()

    def get_completions(
        self,
        document: "Document",
        complete_event: "CompleteEvent",
    ) -> Iterable[Completion]:
        text = document.text_before_cursor.lstrip()

        if not text.startswith("/"):
            return

        parts = text[1:].split(" ", 1)
        cmd_fragment = parts[0]
        has_space = len(parts) > 1

        available = _ENGINE_COMMANDS.get(self._ctx.current_engine, _GLOBAL)

        # ── Case 1: 命令名未输完，补全命令名 ─────────────────────────────────
        if not has_space:
            for cmd_name in sorted(available):
                if cmd_name.startswith(cmd_fragment):
                    meta = self._meta.get(cmd_name, "")
                    yield Completion(
                        text=cmd_name[len(cmd_fragment):],
                        start_position=0,
                        display=f"/{cmd_name}",
                        display_meta=meta,
                    )
            return

        # ── Case 2: 命令名已完整，补全参数值 ─────────────────────────────────
        if cmd_fragment not in available:
            return

        arg_fragment = parts[1]
        for value in _ARG_VALUES.get(cmd_fragment, []):
            if value.startswith(arg_fragment):
                yield Completion(
                    text=value[len(arg_fragment):],
                    start_position=0,
                    display=value,
                )
```

---

## Phase 4：Ghost Text 模块

### 新建 `src/application/cli/input/suggest.py`

```python
"""
参数 Ghost Text（内联暗示）。
在已输入命令名 + 空格后，以浅灰色自动显示剩余参数格式提示。
"""

from __future__ import annotations

from typing import Optional
from prompt_toolkit.auto_suggest import AutoSuggest, Suggestion


# 命令名 → 参数格式提示字符串（按已输入参数数量分层）
# key: 命令名, value: list[str] 对应已输入 0、1、2… 个参数后的提示
_PARAM_HINTS: dict[str, list[str]] = {
    "model":         ["<provider> [model]", "[model]"],
    "switch":        ["llm | agent | agentflow | dify"],
    "mode":          ["basic | deep"],
    "stream":        ["on | off"],
    "use":           ["research | coding | analysis"],
    "restore":       ["<session_id>"],
    "delete_session":["<session_id>"],
    "skills":        ["list | create <name> | info <name> | reload", "<name> [--project]"],
    "mcp":           ["status [-v] | tools [--json] | reload"],
    "connector":     ["status [-v] | tools [--json] | reload"],
    "deep":          ["status | config reload | filesystem status | filesystem reload"],
    "files":         ["clear | remove <index>"],
    "upload":        ["<file_path>"],
    "sessions":      ["[all]"],
}


class CommandAutoSuggest(AutoSuggest):
    """
    在用户输入命令名并加上空格后，显示参数格式 ghost text。
    仅对 / 开头的命令行有效，自由文本查询不受影响。
    """

    def get_suggestion(self, buffer, document) -> Optional[Suggestion]:
        text = document.text_before_cursor.lstrip()
        if not text.startswith("/"):
            return None

        # 按空格拆分，不含前导 /
        parts = text[1:].split(" ")
        cmd_name = parts[0]

        hints = _PARAM_HINTS.get(cmd_name)
        if hints is None:
            return None

        # 已输入的参数个数（不含命令名本身）
        # 只在当前末尾是空格（空参数槽）时显示，避免覆盖正在输入的内容
        if not text.endswith(" "):
            return None

        # 已输入的参数数量 = len(parts) - 1 - 1（命令名占一个，最后一个是空的）
        filled = len(parts) - 2  # 已填写的参数数量
        hint_index = max(0, min(filled, len(hints) - 1))
        hint = hints[hint_index]

        return Suggestion(hint)
```

---

## Phase 5：键绑定模块

### 新建 `src/application/cli/input/keybindings.py`

```python
"""自定义键绑定：Shift+Enter 换行，Ctrl+L 清屏。"""

from __future__ import annotations

from prompt_toolkit.key_binding import KeyBindings


def build_key_bindings() -> KeyBindings:
    kb = KeyBindings()

    @kb.add("shift+enter")
    def _insert_newline(event) -> None:
        """Shift+Enter：插入换行符，不提交输入（Windows 兼容）。"""
        event.app.current_buffer.insert_text("\n")

    @kb.add("c-l")
    def _clear_screen(event) -> None:
        """Ctrl+L：清屏并重绘 prompt。"""
        event.app.renderer.clear()

    return kb
```

---

## Phase 6：Session 工厂

### 新建 `src/application/cli/input/session.py`

```python
"""
PromptSession 工厂。
组装 history / completer / suggest / keybindings，返回可 await prompt_async 的对象。
若 prompt_toolkit 不可用，返回 _FallbackSession（透明降级）。
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from src.application.cli.state import AppState

logger = logging.getLogger(__name__)


@runtime_checkable
class InputSession(Protocol):
    async def prompt_async(self, message: str, **kwargs) -> str: ...


def create_input_session(ctx: "AppState") -> InputSession:
    """
    创建输入会话。调用方只需 await session.prompt_async(prompt_str)。
    若 prompt_toolkit 初始化失败，自动降级为 _FallbackSession。
    """
    try:
        return _build_prompt_session(ctx)
    except Exception as exc:
        logger.warning("prompt_toolkit init failed (%s); falling back to console.input.", exc)
        return _FallbackSession(ctx)


def _build_prompt_session(ctx: "AppState"):
    from prompt_toolkit import PromptSession
    from .history import HistoryPathResolver
    from .completer import CommandCompleter
    from .suggest import CommandAutoSuggest
    from .keybindings import build_key_bindings

    return PromptSession(
        history=HistoryPathResolver().resolve(ctx),
        completer=CommandCompleter(ctx),
        auto_suggest=CommandAutoSuggest(),
        key_bindings=build_key_bindings(),
        complete_while_typing=False,   # 仅 Tab 触发，不影响自由文本
        enable_history_search=True,    # Ctrl+R 反向历史搜索
        reserve_space_for_menu=4,      # 补全菜单最多显示 4 行
    )


class _FallbackSession:
    """降级方案：包装 rich.Console.input()，接口与 PromptSession 兼容。"""

    def __init__(self, ctx: "AppState") -> None:
        self._console = ctx.console

    async def prompt_async(self, message: str, **_) -> str:
        return await asyncio.to_thread(self._console.input, message)
```

---

## Phase 7：`main.py` 集成

### 改动范围：仅 `_cli_loop` 函数，净改动约 8 行

**修改前**（第 145-149 行）：
```python
async def _cli_loop(ctx: AppState) -> None:
    while True:
        try:
            prompt = _build_prompt(ctx)
            query = await asyncio.to_thread(ctx.console.input, prompt)
```

**修改后**：
```python
from src.application.cli.input import create_input_session
from prompt_toolkit.patch_stdout import patch_stdout

async def _cli_loop(ctx: AppState) -> None:
    input_session = create_input_session(ctx)          # ← 新增，只初始化一次
    while True:
        try:
            plain_prompt = _build_plain_prompt(ctx)    # ← 新增函数（见下方）
            with patch_stdout(raw=True):               # ← 新增，保护 rich 输出
                query = await input_session.prompt_async(plain_prompt)
```

同时在 `main.py` 中新增 `_build_plain_prompt` 函数（紧跟在现有 `_build_prompt` 之后）：

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

---

## Phase 8：`pyproject.toml` 依赖声明

在 `pyproject.toml` 的 `dependencies` 列表中追加：

```toml
"prompt_toolkit>=3.0.0,<4.0.0",
```

---

## 文件改动汇总

| 操作 | 文件 | 说明 |
|---|---|---|
| **新建** | `src/application/cli/input/__init__.py` | 包入口 |
| **新建** | `src/application/cli/input/session.py` | PromptSession 工厂 + 降级 |
| **新建** | `src/application/cli/input/history.py` | 历史路径策略 |
| **新建** | `src/application/cli/input/completer.py` | Engine-aware 命令补全 |
| **新建** | `src/application/cli/input/suggest.py` | 参数 ghost text |
| **新建** | `src/application/cli/input/keybindings.py` | 键绑定 |
| **修改** | `src/application/cli/main.py` | `_cli_loop` 约 8 行 + 新增 `_build_plain_prompt` |
| **修改** | `pyproject.toml` | 追加 `prompt_toolkit` 依赖声明 |
| **已修改** | `requirements.txt` | 追加 `prompt_toolkit==3.0.52` ✓ |

**不修改**：`state.py`、`gui/interact.py`、`commands/`（全部保持原样）

---

## 手动验证清单

实施完成后，按以下步骤验证：

```
□ 1. 启动 iris，界面正常显示（无报错）
□ 2. 输入半段文字 → 按 ↑ 谁知道有没有历史（第一次启动跳过）→ 按 ↓ → 草稿恢复 ✓
□ 3. 输入一条消息发送 → 退出重启 → 按 ↑ → 上次输入可见（跨会话历史）✓
□ 4. 输入 / → 按 Tab → 显示当前 engine 可用命令列表 ✓
□ 5. 输入 /mo → 按 Tab → 显示 /mode 和 /model（前缀过滤）✓
□ 6. 输入 /mode → 按 Tab → 显示 basic / deep ✓
□ 7. 输入 /mode  （加空格）→ 不按 Tab → ghost text 显示 "basic | deep" ✓
□ 8. 输入 /switch  → ghost text 显示引擎选项 ✓
□ 9. 按 Shift+Enter → 插入换行，界面扩展为多行，Enter 正常提交 ✓
□ 10. 按 Ctrl+L → 清屏，prompt 重绘到顶部 ✓
□ 11. 按 Ctrl+R → 反向历史搜索激活 ✓
□ 12. 流式输出期间无 prompt 行撕裂（patch_stdout 生效）✓
□ 13. 在无写权限目录运行 → 降级为内存历史，无报错 ✓
```

---

## 实施顺序建议

建议按 **Phase 2 → 5 → 3 → 4 → 6 → 7 → 8** 顺序实施（先建独立模块，最后集成）；每个 Phase 约 30-60 行代码，可独立完成和审查。

Phase 7（main.py 集成）是唯一对用户有直接影响的改动，在所有模块单元测试通过后最后执行。
