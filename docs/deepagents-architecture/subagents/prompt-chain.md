## Prompt 装配链概览

本文描述当前 Deep 模式中 main agent 与 subagent 的系统提示（prompt）如何从模板落地到运行时，以及涉及的核心模块。

- **Prompt 模板仓库**  
  `src/components/deepagents/prompts/registry.py` 负责加载 `main_agent.md` 及 `subagents/*.md` 模板。  
  - `get_main_agent_prompt()` 使用模板渲染主代理的系统提示。  
  - `get_subagent_prompt()` 以子代理类型为 key 读取模板，生成专属系统提示。

- **配置解析**  
  `src/core/providers/subagents_provider_registry.py` 调用上述注册表：  
  - 主代理：在 `DeepAgentFactory` 中直接调用 `adapter.get_system_prompt()`，其中 `BaseDeepAgentAdapter` 使用 registry 渲染主代理提示。  
  - 子代理：`SubAgentsProviderRegistry.get_subagent_config()` 获取模板并合并配置，返回完整的子代理规格。

- **工厂组装**  
  `src/agents/deepagents/factories/base.py` 负责将提示植入可执行规格：  
  - 主代理：在 `create_agent()` 中将渲染好的系统提示写入 `metadata["system_prompt"]`，随后实例化 `BaseDeepAgent`。  
  - 子代理：`_build_subagent_specs()` 读取配置返回的 `system_prompt`，构造 `SubAgent` 数据类。

- **运行时注入**  
  `src/components/deepagents/runtime.py` 与 `runtime_middlewares/subagents/middleware.py` 共同完成最终装配：  
  - 主代理：`create_deep_agent_runtime()` 调用 `langchain.agents.create_agent()`，将主代理系统提示传入 LangChain agent。  
  - 子代理：`SubAgentMiddleware` 遍历 `SubAgent` 列表，使用 `create_agent()` 编译子代理 runnable，并在调度 `task` 工具时载入各自系统提示。

整条链路确保配置文件与模板文件分离，提示文案统一由 `DeepAgentPromptRegistry` 管理，在工厂阶段注入，并在运行时通过 LangChain agent 机制落地执行。

