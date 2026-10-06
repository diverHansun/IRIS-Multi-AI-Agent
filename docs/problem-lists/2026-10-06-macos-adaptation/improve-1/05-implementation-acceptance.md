# 实施验收

验收日期：2026-10-06。基线为 6c32e00，实施范围为当前工作区的 macOS 适配改动。

结论：本机环境安装、平台适配、ZenMux 流式请求及 BasicAgent/DeepAgent 真实对话验证通过。全量测试有 6 项基线失败，没有发现新增失败。

## 实际安装与配置

- macOS 26.6.2，Apple Silicon arm64。
- 项目 `.venv` 使用 CPython 3.11.15；按现有 `uv.lock` 安装 147 个包，无依赖版本升级。
- `~/.iris/` 配置已初始化，DeepAgent 两个文件系统配置均存在。
- 用户指定 ZenMux；默认提供商为 `openai`，模型为 `openai/gpt-6-luna`，Base URL 为 `https://zenmux.ai/api/v1`。LLM、BasicAgent、DeepAgent 和 subagents 的用户配置均已更新。
- `~/.iris/.env` 权限为 `600`；按用户明确授权复用指定本机 .env 的 ZENMUX_API_KEY，写入 IRIS 的 OPENAI_API_KEY，未输出密钥。连接验证后将 setup 标记为已完成。尚未配置的 MCP 服务在本机配置中关闭，后续可通过 /setup --tools 配置。

## 规划与实施对照

| 范围 | 结果 | 说明 |
| --- | --- | --- |
| Stage 1：环境、Shell 与配置初始化 | 完成 | auto 在运行时解析平台默认值；service 复用 ShellConfig |
| Stage 2：路径与启动 | 完成 | POSIX 上传语法、~ 展开、Windows 配置分隔符迁移；main.py 复用正式入口 |
| Stage 3：脚本与文档 | 完成 | 安装脚本执行成功，重复执行不覆盖用户配置，README/IRIS_SETUP 已更新 |
| 远程模型 | 完成 | ZenMux 流式请求、BasicAgent 和 DeepAgent 对话均成功 |
| MCP/Crawl4AI | 未验证 | 仍需独立服务及对应密钥 |

实施调整：文件系统配置通过 `initializer.py` 增加旧模板名回退，而不是把 defaults.py 的来源强制改成 example，以保留已有源码配置的优先级；本机安装了 `rg`，测试发现其 JSON 分支丢弃上下文，新增 `real_filesystem/tools.py` 的小范围回退，context_lines > 0 时使用原有 Python 扫描器。该行为用原有失败测试验证，代价是上下文搜索不走 rg 快速分支。

用户补充 ZenMux 配置后，实际 `/mode deep` 测试暴露了写死选择 zhipu/glm-4.6 的旧逻辑。`mode_commands.py` 现按 config.toml 的 deep_agent 默认值选择提供商和模型，缺失时按 provider.default_model、首个配置模型逐级回退；新增 3 个先失败后通过的回归用例。此为确保用户指定的模型在模式切换时仍被使用而增加的小范围修复。

本轮没有引擎接口、会话存储协议、依赖版本或目录层级变更。用户配置文件均位于 ~/.iris，不随 Git 提交。

## 验收证据

| ID | 结果 | 证据 |
| --- | --- | --- |
| A1 | 通过 | `uv sync --python 3.11 --locked` 安装成功；Python 输出 3.11.15/arm64 与项目 .venv；`uv pip check` 检查 147 个包无冲突 |
| A2 | 通过 | auto 的 POSIX/Windows 分支测试；真实 bash 保持状态、输出中文、返回非零退出码并正常停止 |
| A3 | 通过 | Windows 配置引用、POSIX 引号/空格/中文/转义/~ 上传路径回归 |
| A4 | 通过 | 首次复制两种模板；重复初始化保留用户修改；真实源码配置优先于模板 |
| A5 | 通过 | 实际 PTY 启动首次向导；配置完成后进入 CLI，BasicAgent 回复「Mac 适配成功。」；切换 DeepAgent 使用指定模型并回复 DEEP_MAC_OK；`python main.py --help` 正常 |
| A6 | 通过 | `bash -n scripts/setup-macos.sh`；实际安装与再次安装成功，已有 .env/config.toml 内容逐字节保持不变 |

相关回归命令：

```bash
.venv/bin/python -m pytest tests/unit/core/config tests/unit/core/project tests/unit/deepagents/middleware tests/unit/application/services/test_upload_paths.py tests/unit/deepagents/test_real_filesystem.py tests/unit/application/commands/agent/test_mode_command.py tests/unit/application/services/test_deep_agent_service_contract.py tests/integration/test_cli_init.py tests/integration/test_shell_posix.py -q -k 'not test_llm_step_fails_when_default_provider_key_is_empty'
```

结果：267 passed，2 skipped，1 deselected。跳过项包含 Windows 真进程测试和现有跳过用例。

全量命令：

```bash
.venv/bin/python -m pytest tests/ --import-mode=importlib -q -k 'not test_llm_step_fails_when_default_provider_key_is_empty'
```

适配后：637 passed，6 failed，6 skipped，1 deselected。用 `git archive HEAD` 导出未修改代码，以同一虚拟环境和本机用户配置运行相同命令：622 passed，7 failed，6 skipped，1 deselected。对比失败用例 ID 集合，新增失败为 0，原有文件系统上下文搜索失败已修复。

## 已知测试基线问题

以下 6 项在 HEAD 中也失败，本轮保留：

- `test_deepagents_provider_registry.py::TestDeepAgentsProviderRegistry::test_model_not_found`
- `test_manager.py::test_create_deep_agent_builds_runtime`
- `test_subagent_parameter_flow.py::TestFactoryParameterPassing::test_factory_passes_agent_config_to_subagent`
- `test_subagent_parameter_flow.py::TestMiddlewareParameterUsage::test_middleware_uses_configured_tools`
- `test_subagent_parameter_flow.py::TestMiddlewareParameterUsage::test_tools_merging_consistency`
- `test_timeout_recovery.py::test_system_notification_detection`

`test_setup_flow_logic.py::test_llm_step_fails_when_default_provider_key_is_empty` 的旧 mock 仍替换 `Prompt.ask`，实际配置输入已改用 `text_input`。堆栈显示它等待真实终端输入，因此排除该用例；相关源文件与测试文件在本轮均未修改。没有将其记作通过。

默认 pytest 导入模式遇到两份同名 `test_session_commands.py` 的收集冲突，使用 `--import-mode=importlib` 后可完成全量运行。依赖产生 Pydantic/LangGraph 弃用警告，尚未升级。

## 改动质量与边界

改动集中在现有配置、路径和执行边界，没有新增平台架构层，符合 KISS 与复杂度管理原则。Shell 平台默认值由组件层统一解析，避免 service 重复维护平台判断；模板初始化保留用户文件和源码配置优先级。带上下文的文件搜索复用既有回退实现，避免在本轮重写解析器。

Windows 仅验证了配置分支与旧显式配置兼容，实际 Windows 进程需在 Windows 机器上验证。macOS 上传路径已验证，Dify 网络上传需要实际服务。

## ZenMux 连接验证

按照用户提供的 [模型页面](https://zenmux.ai/openai/gpt-6-luna) 与 [API Quickstart](https://zenmux.ai/docs/guide/quickstart) 核对接口和模型标识。通过项目 create_llm 进行流式请求，返回 IRIS_MAC_OK；实际 CLI 的 BasicAgent 回复「Mac 适配成功。」；DeepAgent 回复 DEEP_MAC_OK（约 5.3 秒）。`/doctor` 返回 9 passed、0 failed、13 warnings，警告均为未配置的可选服务或提供商。密钥只发送到用户指定的 ZenMux 接口。

再次执行安装脚本，验证 .env、config.toml 与 4 份用户模型 JSON 配置逐字节不变；检查仓库 diff 与所有非忽略新文件不包含复用密钥。

## 主要文件

- `scripts/setup-macos.sh`：可重复的本机虚拟环境安装与用户配置初始化。
- `src/components/deepagents/runtime_middlewares/shell/config.py`、`src/application/services/agent/deep/middleware/shell_service.py`：平台默认 Shell。
- `src/core/config/initializer.py`、`src/core/config/paths.py`：模板回退与路径迁移。
- `src/application/services/dify/upload.py`：上传路径解析。
- `src/components/deepagents/runtime_middlewares/real_filesystem/tools.py`：上下文搜索回退。
- `main.py`：统一首次配置与启动流程。
- `src/application/commands/agent/mode_commands.py`：Deep 模式遵循已配置的模型默认值。
- `README.md`、`IRIS_SETUP.md`：macOS 使用说明。
- `tests/unit/core/config/test_platform_migration.py`、`tests/unit/application/services/test_upload_paths.py`、`tests/unit/deepagents/middleware/test_shell_middleware.py`、`tests/integration/test_shell_posix.py`、`tests/unit/application/commands/agent/test_mode_command.py`：本轮回归。

## 补充：Windows / macOS 兼容提示检查

2026-10-06，按用户要求检查代码和文档中的双平台说明。这次只补充说明与工具描述，没有改变平台选择或路径解析逻辑。

README 首页新增平台表和验证范围，源码安装增加 Windows PowerShell 的最短流程；IRIS_SETUP 补齐双平台安装、激活、检查命令、跨系统重建 .venv 和迁移路径注意事项。DeepAgent 配置 README 与 ShellConfig、配置路径、Dify 上传代码说明统一 Windows/macOS 用语。

修正旧 Dify 文档中固定 posix=False 的描述，以及文件系统文档中 macOS 一定区分大小写的说法。两份旧 Shell 规划文档保留 cmd 配置快照，但明确其历史语境和当前 auto 默认值。

验证：平台相关回归 31 passed、1 skipped；bash -n 通过。模拟配置层的 os.name，确认 Windows auto 返回 cmd.exe /Q、Windows powershell 返回对应启动参数，POSIX auto 返回 /bin/bash --norc --noprofile。这是启动参数分支检查，不等于 Windows 实机进程验收。
