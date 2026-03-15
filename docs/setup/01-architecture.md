# Setup 模块总体架构设计

## 1. 概述

本文档定义 IRIS CLI 的 Setup 模块架构。该模块解决首次安装时用户无法快速上手的问题，
提供交互式配置向导（Setup Wizard）和配置健康检查（Config Validator），
覆盖 LLM、Agent、工具、Dify 四类配置。

## 2. 设计目标

- 首次安装自动触发交互式向导，引导用户完成最小可用配置
- 支持按功能模块独立配置（`/iris setup --llm` 等）
- 支持配置健康检查（`/iris doctor`）
- 所有敏感信息（API key）统一写入 `~/.iris/.env`
- 非必要配置均可跳过（skip），不阻塞启动

## 3. 模块结构

```
src/core/config/
  setup/
    __init__.py          # public API: SetupWizard, ConfigValidator
    wizard.py            # SetupWizard -- orchestrator
    writer.py            # EnvWriter -- .env read/write with format preservation
    validator.py         # ConfigValidator -- health check (iris doctor)
    widgets.py           # SelectOne / SelectMany -- keyboard-driven selectors
    steps/
      __init__.py
      base.py            # SetupStep abstract base, StepResult, SetupContext
      llm.py             # LLM provider + API key configuration
      agent.py           # Agent (basic / deep) configuration
      tools.py           # SDK + MCP tool API key configuration
      dify.py            # Dify engine configuration
```

## 4. 职责矩阵

| 模块 | 职责 | 输入 | 输出 |
|------|------|------|------|
| `wizard.py` | 编排 steps 执行顺序，管理 `[setup]` 标记，处理首次/手动/升级三条路径 | config.toml, pyproject version | config.toml `[setup]` section |
| `writer.py` | 读取/追加/更新 `~/.iris/.env` 中的键值对，保持注释和格式 | .env file | .env file (updated) |
| `validator.py` | 检查所有配置项健康状态，输出 pass/fail/warn 报告 | .env, config.toml, JSON configs | CheckResult list |
| `widgets.py` | 提供键盘驱动的单选/多选交互控件 | options list | user selection |
| `steps/base.py` | 定义 SetupStep 抽象基类、SetupContext 数据类、StepResult | - | - |
| `steps/llm.py` | LLM provider 选择 + API key 输入 + 默认 provider/model 写入 | user input | .env keys |
| `steps/agent.py` | Basic 确认 + Deep mainagents/subagents 配置检查 | llm step result, JSON configs | .env keys (optional) |
| `steps/tools.py` | SDK 工具 + MCP 工具的 API key 配置 | user input | .env keys |
| `steps/dify.py` | Dify API key + base_url 配置 | user input | .env keys |

## 5. 依赖关系

```
wizard.py
  |-- steps/base.py (SetupStep, SetupContext, StepResult)
  |-- steps/llm.py
  |-- steps/agent.py  (depends on llm step result)
  |-- steps/tools.py
  |-- steps/dify.py
  |-- writer.py (EnvWriter)
  |-- widgets.py (SelectOne, SelectMany)
  |-- validator.py (ConfigValidator, for post-setup check)

writer.py
  |-- (standalone, no internal dependencies)

validator.py
  |-- src/core/config/settings.py (has_api_key, get_api_key)
  |-- src/core/config/loader.py (load config.toml, load JSON)
  |-- os.getenv() (for MCP/Dify keys not in Settings)

widgets.py
  |-- prompt_toolkit (keyboard event handling + interactive rendering)
  |-- rich (static output: Panel, Table, Rule, banners)
```

**重要约束：widgets.py 中 prompt_toolkit 和 Rich 的职责分离**

- `SelectOne` / `SelectMany` 交互期间使用 prompt_toolkit 原生渲染（`FormattedText`），
  不使用 Rich `Live`，避免两个库同时管理终端状态导致冲突。
- Rich 仅用于静态输出（步骤标题、表格、Banner、结果摘要），在交互控件运行前后调用。
- 文本输入（API key）和确认输入（y/N/skip）使用 Rich `Prompt.ask()`，
  此时没有 prompt_toolkit 并发运行。

### 分层约束

- `src/core/config/setup/` 属于 core 层，不依赖 application 层
- `/iris setup` 和 `/iris doctor` 命令在 `src/application/commands/` 中实现，
  作为 core 层 SetupWizard / ConfigValidator 的薄壳调用
- `main.py` 在启动时直接调用 `SetupWizard.check_and_run()`，无需经过 command dispatch

## 6. 与现有模块的关系

| 现有模块 | 关系 |
|---------|------|
| `src/core/config/initializer.py` | setup 模块在 `ensure_initialized()` 之后运行；initializer 负责目录和文件创建，setup 负责交互式配置 |
| `src/core/config/loader.py` | setup 写入 `.env` 后，后续的 `ConfigLoader.load()` 自然读取到新值 |
| `src/core/config/settings.py` | validator 使用 `Settings.has_api_key()` 检查 LLM key 状态；MCP/Dify 等 key 通过 `os.getenv()` 直接检查（不扩展 Settings） |
| `src/core/config/defaults.py` | setup 的 `.env` 模板内容与 `DEFAULT_ENV_TEMPLATE` 保持一致 |
| `src/core/project/` | setup 不直接依赖 project 模块；project context 的创建在 setup 之后 |
| `src/application/commands/` | `/iris setup` 和 `/iris doctor` 命令调用 core 层的 SetupWizard / ConfigValidator |
| `src/application/cli/main.py` | 启动流程中插入 `SetupWizard.check_and_run()` 调用点 |

## 7. 数据流

```
                    pyproject.toml (version)
                           |
                           v
main.py --> ensure_initialized() --> SetupWizard.check_and_run()
                                          |
                          +---------+-----+-----+---------+
                          |         |           |         |
                     LLMStep   AgentStep   ToolsStep  DifyStep
                          |         |           |         |
                          v         v           v         v
                      EnvWriter (read/write ~/.iris/.env)
                          |
                          v
                    config.toml [setup] section updated
                          |
                          v
                    ConfigLoader.load() reads updated .env
                          |
                          v
                    Settings / IrisConfig populated
```

## 8. 设计原则

- **Single Responsibility**: 每个 step 只关注一类配置，writer 只关注 .env 读写
- **Open/Closed**: 新增配置类型只需添加新 step 文件，不修改 wizard 编排器
- **Dependency Inversion**: steps 通过 SetupContext 通信，不直接互相引用
- **Fail-Safe**: 所有可选步骤支持 skip，setup 中断后下次启动重新引导

## 9. [setup] 节与 IrisConfig 的关系

`config.toml` 中的 `[setup]` 节是 wizard 内部管理的元数据，不纳入 `IrisConfig` Pydantic 模型。
原因：`[setup]` 包含的是安装状态信息（completed、version），不是运行时配置参数。

- **读取方式**：`SetupWizard._read_setup_info()` 通过 `tomlkit` 直接解析 `config.toml`，
  绕过 `ConfigLoader.load()` -> `IrisConfig` 的路径。
- **写入方式**：`SetupWizard._mark_completed()` 通过 `tomlkit` 直接修改 `config.toml`，
  保持文件中的注释和其他 section 不变。
- **IrisConfig 兼容**：Pydantic v2 的 `BaseModel` 默认行为是忽略未定义字段（`extra` 默认
  为 `"ignore"`），因此 `[setup]` 节不会导致解析报错。当前 `IrisConfig` 未显式设置
  `model_config`，依赖的是 Pydantic v2 默认行为。

## 10. Settings 扩展策略

`Settings` 类（`src/core/config/settings.py`）目前只覆盖 LLM provider 的 API key
（zhipu/openai/anthropic/tongyi/tavily/amap/notion）。

**不扩展 Settings 的范围**：MCP 工具 key（CONTEXT7_API_KEY、FIRECRAWL_API_KEY、
AMAP_MAPS_API_KEY）和 Dify key（DIFY_API_KEY）通过 `os.getenv()` 直接检查。
理由：这些 key 只在特定组件加载时使用，不需要全局 Settings 管理。

`ConfigValidator` 的 check 方法对不同类别使用不同策略：
- LLM/Agent key -> `Settings.has_api_key(provider)`
- MCP/SDK tool key -> `os.getenv(key_name)` 直接检查
- Dify key -> `os.getenv("DIFY_API_KEY")` 直接检查
