# 启动流程与 Wizard 编排设计

## 1. 概述

本文档定义 IRIS CLI 的启动流程改造方案和 SetupWizard 的编排逻辑，
包含两层判断机制、版本检测、三条触发路径。

## 2. 两层判断机制

### 2.1 第一层：结构初始化

由现有 `ConfigInitializer.ensure_initialized()` 负责。

判断条件：`~/.iris/config.toml` 是否存在。

- 不存在：创建 `~/.iris/` 目录结构，复制模板文件，写入默认 `config.toml`
- 存在：仅补齐缺失文件（`sync_missing=True`）

此层不涉及用户交互，纯文件操作。

### 2.2 第二层：Setup 完成检测

由 `SetupWizard.check_and_run()` 负责。

判断条件：`config.toml` 中 `[setup]` 节的状态。

```toml
[setup]
completed = true
completed_at = "2026-03-15T10:30:00"
version = "0.1.3"
```

| 状态 | 行为 |
|------|------|
| `[setup]` 节不存在 | 视为未完成，运行完整向导 |
| `completed = false` | 上次中断，运行完整向导 |
| `completed = true` 且 `version` = 当前版本 | 正常启动，不触发向导 |
| `completed = true` 且 `version` < 当前版本 | 正常启动，打印提示信息（非阻塞） |

### 2.3 版本号来源

```python
def get_package_version() -> str:
    """Get version from installed package metadata or pyproject.toml."""
    try:
        from importlib.metadata import version
        return version("iris-muti-ai-agent")
    except Exception:
        # Fallback: read pyproject.toml directly (dev mode)
        ...
```

版本号与 `pyproject.toml` 中的 `version` 字段保持一致。

## 3. 启动流程改造

### 3.1 改造前（当前）

```
main.py:run()
  1. ensure_initialized(quiet=True)
  2. AppState()
  3. display_logo()
  4. _initialize_memory()
  5. service.initialize()
  6. _cli_loop()
```

### 3.2 改造后

```
main.py:run()
  1. ensure_initialized(quiet=True)       # existing: dir/file creation
  2. SetupWizard.check_and_run()          # NEW: interactive setup if needed
  3. AppState()
  4. display_logo()
  5. _initialize_memory()
  6. service.initialize()
  7. _cli_loop()
```

关键变化：
- `SetupWizard.check_and_run()` 插入在 `ensure_initialized()` 之后、`AppState()` 之前
- 确保 `.env` 已写入后，后续的 `_initialize_memory()` -> `reload_settings()` 能读到新值
- Logo 显示移到 setup 之后，避免 setup 界面与 logo 混在一起

### 3.3 首次启动时序

```
ensure_initialized()
  |-- Create ~/.iris/ directory tree
  |-- Write config.toml (with DEFAULT_CONFIG_TOML, no [setup] section)
  |-- Write .env.example
  |-- Copy bundled config files (example -> actual)
  |
SetupWizard.check_and_run()
  |-- Read config.toml -> [setup] section missing -> first_time = true
  |-- wizard.run_first_time()
  |     |-- Display welcome banner
  |     |-- LLMSetupStep.run()        (required)
  |     |-- AgentSetupStep.run()      (skippable)
  |     |-- ToolsSetupStep.run()      (skippable)
  |     |-- DifySetupStep.run()       (skippable)
  |     |-- Display summary
  |     |-- _mark_completed()         (write [setup] to config.toml)
  |
AppState()                             (reads updated .env via settings)
display_logo()
_initialize_memory()
_cli_loop()
```

## 4. 三条触发路径

### 4.1 路径一：首次安装

触发条件：`[setup].completed` 不存在或为 `false`。

行为：运行完整向导（4 个 steps 依次执行）。

### 4.2 路径二：版本升级

触发条件：`[setup].completed = true` 且 `[setup].version < current_version`。

行为：
```
IRIS has been updated to v0.2.0 (was v0.1.3).
New configuration options may be available.
Run /iris setup to configure.
```
仅打印提示，不强制运行向导。不阻塞启动。

### 4.3 路径三：手动触发

触发条件：用户在 CLI 中执行 `/iris setup` 或 `/iris setup --llm` 等。

行为：
- 无参数：运行全部 steps（等同首次向导，但已配置的项会显示当前值）
- 有参数：运行指定 step

手动触发时无视 `[setup].completed` 状态，始终运行。

## 5. SetupWizard 编排器设计

```python
class SetupWizard:
    """Main orchestrator for the setup wizard."""

    def __init__(self, share_dir: Path = None, console: Console = None):
        self._share_dir = share_dir or Path.home() / ".iris"
        self._console = console or Console()
        self._env_writer = EnvWriter(self._share_dir / ".env")

    def check_and_run(self) -> bool:
        """Auto-check at startup, run wizard if needed."""
        setup_info = self._read_setup_info()

        if not setup_info.get("completed", False):
            return self.run_first_time()

        installed_ver = setup_info.get("version", "0.0.0")
        current_ver = get_package_version()
        if _version_lt(installed_ver, current_ver):
            self._print_upgrade_hint(installed_ver, current_ver)

        return True

    def run_first_time(self) -> bool:
        """Full wizard for first-time setup."""
        context = self._build_context()
        self._print_welcome_banner(context.version)

        steps = [
            LLMSetupStep(),
            AgentSetupStep(),
            ToolsSetupStep(),
            DifySetupStep(),
        ]

        for i, step in enumerate(steps, 1):
            self._print_step_header(i, len(steps), step.title)
            result = step.run(context)

            if result.skipped:
                self._print_skip_message(step.name)
            elif result.error:
                self._print_error(result.error)
                if not step.skippable:
                    return False

        self._print_summary(context)
        self._mark_completed(context.version)
        return True

    def run_specific(self, target: str, sub_target: str = None) -> bool:
        """Run a specific step: e.g., target='llm', target='tools', sub_target='mcp'."""
        step = self._resolve_step(target)
        context = self._build_context()
        result = step.run(context, sub_target=sub_target)
        return not result.error

    def run_all(self) -> bool:
        """Manual /iris setup with no args: run all steps.

        Unlike run_first_time(), this does NOT update the [setup].completed_at
        timestamp, preserving the original first-time setup record.
        It does update [setup].version to the current version.
        """
        context = self._build_context()
        self._print_welcome_banner(context.version)

        steps = [
            LLMSetupStep(),
            AgentSetupStep(),
            ToolsSetupStep(),
            DifySetupStep(),
        ]

        for i, step in enumerate(steps, 1):
            self._print_step_header(i, len(steps), step.title)
            result = step.run(context)

            if result.skipped:
                self._print_skip_message(step.name)
            elif result.error:
                self._print_error(result.error)
                if not step.skippable:
                    return False

        self._print_summary(context)
        self._update_version(context.version)  # only update version, not completed_at
        return True
```

## 6. SetupContext 传递机制

```python
@dataclass
class SetupContext:
    """Shared context passed between setup steps."""

    share_dir: Path              # ~/.iris/
    env_writer: EnvWriter        # .env reader/writer
    configured_providers: Set[str]    # provider names with valid API keys (e.g., {"zhipu", "openai"})
    console: Console             # Rich console instance
    version: str                 # Current package version
```

`configured_keys` 的作用：

- LLMStep 配置了 `ZHIPU_API_KEY` -> `configured_providers.add("zhipu")`
- AgentStep 读取 `configured_providers` 判断哪些 provider 可用
- ToolsStep 读取判断 zhipu search/crawl 是否已经可用（复用 LLM 的 key）

步骤间通过 `SetupContext` 传递状态，不直接互相引用。

`configured_providers` 在 `_build_context()` 时从 `.env` 预加载已有的 key：

```python
def _build_context(self) -> SetupContext:
    env_writer = EnvWriter(self._share_dir / ".env")
    pre_configured = set(env_writer.get_configured_providers())
    return SetupContext(
        share_dir=self._share_dir,
        env_writer=env_writer,
        configured_providers=pre_configured,
        console=self._console,
        version=get_package_version(),
    )
```

这样手动重跑 `/iris setup` 时，已配置的项自动标注 `configured`，用户可快速跳过。

## 7. [setup] 标记管理

### 写入

```python
def _mark_completed(self, version: str) -> None:
    """Write [setup] section to config.toml."""
    config_path = self._share_dir / "config.toml"
    # Use tomlkit to preserve existing content and comments
    # Append or update [setup] section:
    # [setup]
    # completed = true
    # completed_at = "2026-03-15T10:30:00"
    # version = "0.1.3"
```

### 读取

```python
def _read_setup_info(self) -> dict:
    """Read [setup] section from config.toml."""
    config_path = self._share_dir / "config.toml"
    # Parse TOML, return setup section or empty dict
```

使用 `tomlkit` 库读写以保持文件中的注释和格式不被破坏。

## 8. 中断恢复策略

如果 setup 向导在运行中被中断（Ctrl+C、程序崩溃等），`_mark_completed()` 尚未执行，
`[setup].completed` 保持 `false`。下次启动时会重新运行完整向导。

**设计选择：不跟踪单步完成状态。**

理由：
- 每个 step 在 `run()` 时会通过 `EnvWriter` 和 `configured_providers` 检测已配置的项，
  自动标注 `configured` 状态。已配置的项用户只需按 Enter/N 快速跳过。
- 增加单步跟踪（如 `steps_completed = ["llm", "agent"]`）会增加复杂度，
  但收益很小（重跑一遍的体验已经足够流畅）。

**KeyboardInterrupt 处理：**

```python
def run_first_time(self) -> bool:
    try:
        ...  # step execution loop
    except KeyboardInterrupt:
        self._console.print(
            "\nSetup interrupted. Run /iris setup to continue.",
            style=COLORS["warning"],
        )
        return False
```

## 9. Async/Sync 策略

### 问题

`BaseCommand.execute()` 是 `async def`，但 SetupWizard 的交互式 prompt
（Rich `Prompt.ask()`、prompt_toolkit 键盘控件）是同步阻塞的。

### 解决方案

**启动路径**（`main.py`）：`SetupWizard.check_and_run()` 在 async 事件循环建立前调用，
直接同步执行，无冲突。

**命令路径**（`/iris setup`）：在 `SetupCommand.execute()` 中使用 `asyncio.to_thread()`
将同步 wizard 调用移到线程池：

```python
async def execute(self, ctx, args: str) -> CommandResult:
    wizard = SetupWizard(console=ctx.console)
    success = await asyncio.to_thread(wizard.run_all)
    ...
```

这样不会阻塞主 async 事件循环。

### main.py 调用位置

```python
async def run() -> None:
    ensure_initialized(quiet=True)

    # Setup wizard runs synchronously BEFORE async loop is busy
    wizard = SetupWizard()
    if not wizard.check_and_run():
        # Setup failed (LLM step mandatory but not configured)
        print("Setup incomplete. At least one LLM API key is required.")
        print("Run 'iris' again to restart setup.")
        return

    ctx = AppState()
    ...
```

如果 `check_and_run()` 返回 `False`（LLM 未配置），程序打印提示后退出，
不进入 `_cli_loop()`。

## 10. 版本比较

使用 `packaging.version.Version` 进行语义版本比较，该库是 pip/setuptools 的
传递依赖，无需额外安装：

```python
from packaging.version import Version

def _version_lt(installed: str, current: str) -> bool:
    """Compare semantic versions safely."""
    try:
        return Version(installed) < Version(current)
    except Exception:
        return installed != current
```
