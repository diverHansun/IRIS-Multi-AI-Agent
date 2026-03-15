# 命令设计：/iris setup 与 /iris doctor

## 1. 概述

本文档定义两个新增 CLI 命令的接口规格、参数解析和执行逻辑。
命令层作为 core 层 `SetupWizard` / `ConfigValidator` 的薄壳调用，
不包含业务逻辑。

## 2. 命令注册

```python
# src/application/commands/__init__.py
# Added to register_default_commands():

from src.application.commands.shared.setup_commands import SetupCommand, DoctorCommand

commands: list[BaseCommand] = [
    ...
    SetupCommand(),
    DoctorCommand(),
]
```

文件位置：`src/application/commands/shared/setup_commands.py`

## 3. /iris setup

### 3.1 命令定义

```python
class SetupCommand(BaseCommand):
    name = "setup"
    help_text = "Run configuration wizard (LLM, agents, tools, dify)"
    aliases = ()
    engine_scope = ("all",)  # available in all engines
```

### 3.2 参数格式

```
/iris setup                    # run all steps
/iris setup --llm              # LLM provider + API key only
/iris setup --agent basic      # basic agent config only
/iris setup --agent deep       # deep agent config only
/iris setup --tools sdk        # SDK tools only
/iris setup --tools mcp        # MCP tools only
/iris setup --dify             # Dify engine only
```

### 3.3 参数解析

```python
async def execute(self, ctx, args: str) -> CommandResult:
    """Parse args and delegate to SetupWizard."""
    parts = args.strip().split()

    if not parts:
        # No args: run all steps (sync wizard in thread to avoid blocking event loop)
        wizard = SetupWizard(console=ctx.console)
        success = await asyncio.to_thread(wizard.run_all)
        return (CommandResult.success("Setup completed.") if success
                else CommandResult.error("Setup failed."))

    flag = parts[0]  # e.g., "--llm", "--agent", "--tools", "--dify"
    sub_target = parts[1] if len(parts) > 1 else None

    target_map = {
        "--llm": ("llm", None),
        "--agent": ("agent", sub_target),     # sub_target: "basic" or "deep"
        "--tools": ("tools", sub_target),     # sub_target: "sdk" or "mcp"
        "--dify": ("dify", None),
    }

    if flag not in target_map:
        return CommandResult.error(f"Unknown setup target: {flag}")

    target, sub = target_map[flag]
    wizard = SetupWizard(console=ctx.console)
    success = await asyncio.to_thread(wizard.run_specific, target, sub)
    return (CommandResult.success(f"Setup ({target}) completed.") if success
            else CommandResult.error(f"Setup ({target}) failed."))
```

### 3.4 执行流程

```
/iris setup --agent deep
    |
    v
SetupCommand.execute(ctx, "--agent deep")
    |
    v
SetupWizard.run_specific(target="agent", sub_target="deep")
    |
    v
AgentSetupStep.run(context, sub_target="deep")
    |
    v
  Interactive deep agent configuration
    |
    v
CommandResult.success("Agent (deep) configuration completed.")
```

### 3.5 与启动时 wizard 的关系

| 触发方式 | 入口 | 行为 |
|---------|------|------|
| 首次启动 | `main.py` -> `SetupWizard.check_and_run()` | 自动，运行全部 steps |
| CLI 命令 | `/iris setup` -> `SetupCommand.execute()` | 手动，无视 completed 标记 |
| CLI 命令+参数 | `/iris setup --llm` -> `SetupCommand.execute()` | 手动，仅运行指定 step |

## 4. /iris doctor

### 4.1 命令定义

```python
class DoctorCommand(BaseCommand):
    name = "doctor"
    help_text = "Check configuration health status"
    aliases = ("check",)
    engine_scope = ("all",)
```

### 4.2 参数格式

```
/iris doctor                   # full health check
/iris doctor --llm             # LLM config check only
/iris doctor --agent           # agent config check only
/iris doctor --tools           # tools config check only
/iris doctor --dify            # dify config check only
```

### 4.3 执行逻辑

```python
async def execute(self, ctx, args: str) -> CommandResult:
    """Run configuration health check."""
    validator = ConfigValidator(console=ctx.console)
    parts = args.strip().split()

    valid_categories = {"llm", "agent", "tools", "dify"}

    if not parts:
        results = validator.check_all()
    else:
        category = parts[0].lstrip("-")
        if category not in valid_categories:
            return CommandResult.error(
                f"Unknown category '{category}'. "
                f"Valid options: {', '.join(sorted(valid_categories))}"
            )
        results = validator.check_category(category)

    validator.print_report(results)

    failed = [r for r in results if r.status == "fail"]
    if failed:
        return CommandResult.error(
            f"{len(failed)} configuration issue(s) found. "
            "Run /iris setup to fix."
        )
    return CommandResult.success("All configuration checks passed.")
```

### 4.4 输出格式

使用 Rich Table 渲染，详见 05-ui-widgets.md。

输出示例：

```
IRIS Configuration Health Check
=================================

LLM:
  [pass] ZHIPU_API_KEY configured
  [fail] DEFAULT_LLM_PROVIDER = openai, but OPENAI_API_KEY not configured

Agent:
  [pass] Basic agent: zhipu / glm-4.5-flash

Tools:
  [pass] DuckDuckGo: available
  [warn] Tavily: TAVILY_API_KEY not configured

---------------------------------
Summary: 3 passed, 1 failed, 1 warning

Run /iris setup to fix configuration issues.
```

## 5. Help 命令集成

现有的 `/help` 命令（`system_commands.py`）输出中需要追加：

```
Configuration:
  /setup          Run configuration wizard
  /setup --llm    Configure LLM providers
  /setup --agent  Configure agents (basic/deep)
  /setup --tools  Configure tools (sdk/mcp)
  /setup --dify   Configure Dify engine
  /doctor         Check configuration health
```

## 6. 命令层约束

- 命令层不包含配置业务逻辑，仅做参数解析和委托调用
- 命令层不直接读写 `.env` 或 JSON 文件
- 命令层通过 `ctx.console` 传递 Rich Console 给 core 层
- 命令执行结果统一通过 `CommandResult` 返回
