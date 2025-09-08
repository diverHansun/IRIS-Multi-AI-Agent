# 智谱AI Function Calling 实现方案（走 zhipuai SDK）

## 1. 概述

为智谱 AI 的 `glm-4.5` 模型提供原生 Function Calling 支持，与现有基于 ReAct 的 `ZhipuAgent` 并存。用户通过命令 `switch zhipu glm-4.5` 切换至 FC 模式；默认仍为 ReAct（`glm-4-plus`）。

## 2. 设计目标

- 保持现有 ReAct 实现不变，新增 FC 实现并可随时切换。
- 仅在 `glm-4.5` 上启用 FC 路线，其余模型走 ReAct。
- 复用现有 `src/tools` 下的 LangChain `BaseTool`，通过适配器转换为 Zhipu `tools`。
- 错误信息结构化，便于 LLM 决策（重试/询问/降级）。
- 与 `GlobalMemoryManager` 会话/记忆完全兼容；接口与 CLI 现有显示保持一致。
- 完整支持 MCP 工具集成。

## 3. 实现方案

### 3.1 整体架构

新增一个 FC Agent，并在工厂里按模型路由：
```
src/
└── agents/
    ├── zhipu_agent.py              # 现有 ReAct 实现
    ├── zhipu_fcall_agent.py        # 新增 Function Calling 实现（zhipuai SDK）
    ├── functioncalling_adapter.py  # 工具适配器：BaseTool -> Zhipu functions
    └── agent_factory.py            # 工厂：glm-4.5 路由到 FC Agent
```

不新增文件夹，保持最小侵入。后续若 FC 扩展复杂，再考虑拆分子包。

### 3.2 核心组件

#### 3.2.1 ZhipuFunctionCallingAgent
职责：
- 组织会话消息，调用 zhipuai Chat Completions（携带 `tools`）。
- 解析返回的 `tool_calls`，执行本地工具，构造 `role:"tool"` 回填消息，再次请求，直至得到最终回答。
- 集成 `GlobalMemoryManager`：读取历史、在完成后保存当前轮对话。
- 对外接口与 `ZhipuAgent` 一致：`initialize() / invoke() / ainvoke() / get_info()`；返回字段保持一致（见 3.5）。
- 完整支持 MCP 工具集成。

#### 3.2.2 工具适配器（functioncalling_adapter.py）
将 LangChain BaseTool 转为 Zhipu 工具定义：
```python
from langchain_core.tools import BaseTool

def convert_tool_to_function(tool: BaseTool) -> dict:
    """转换 BaseTool 为 Zhipu Function 定义。"""
    schema = {}
    try:
        if hasattr(tool, "args_schema") and tool.args_schema is not None:
            # 检查args_schema是否为字典（MCP工具的情况）
            if isinstance(tool.args_schema, dict):
                schema = tool.args_schema
            # 检查args_schema是否有schema()方法（标准LangChain工具的情况）
            elif hasattr(tool.args_schema, "schema") and callable(getattr(tool.args_schema, "schema")):
                schema = tool.args_schema.schema()
            else:
                # 单参数回退：统一使用 input 字段
                schema = {
                    "type": "object",
                    "properties": {"input": {"type": "string", "description": tool.description or ""}},
                    "required": ["input"],
                }
        else:
            # 单参数回退：统一使用 input 字段
            schema = {
                "type": "object",
                "properties": {"input": {"type": "string", "description": tool.description or ""}},
                "required": ["input"],
            }
    except Exception as e:
        logger.warning(f"工具 {tool.name} 参数schema提取失败: {e}")
        schema = {"type": "object", "properties": {}, "additionalProperties": True}

    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description or tool.name,
            "parameters": schema or {"type": "object", "properties": {}},
        },
    }
```

执行工具时的入参策略（避免参数名不匹配）：
- 特别处理字符串参数：尝试解析为JSON，失败则创建包含input字段的字典
- 对于 MCP 工具：确保传递正确的字典格式参数，避免 "String tool inputs are not allowed" 错误
- 对于 BaseTool 实例：根据 args_schema 类型正确处理参数
- 对于使用 @tool 装饰器的函数：优先调用 tool.func，失败则降级为 tool.run/tool.arun

#### 3.2.3 交互流程（循环直到无 tool_calls）
1) 组装消息（含历史）：`system`（可选）+ 历史（user/assistant）+ 当前 `user`。
2) 附带 `tools=[...converted functions...]` 调用 zhipuai Chat Completions。
3) 如返回 `tool_calls`：逐个执行 -> 以 `role:"tool"` + `tool_call_id` 回填消息 -> 再次请求。
4) 无 `tool_calls` 时，返回 `assistant` 最终回答；保存到记忆；回传 CLI 所需字段。

### 3.3 错误处理（结构化）
统一以如下结构在工具回填与最终结果中体现：
```json
{ "error": "错误信息", "type": "invalid_arguments|tool_runtime|tool_not_found|internal", "retryable": true/false }
```
模型可据此选择：
- retry（如偶发/超时）
- ask-user（参数缺失/无效）
- degrade（工具失败时给出通用回答）

### 3.4 与现有系统集成

#### 3.4.1 会话管理
与 `GlobalMemoryManager` 兼容：
- 读取：`get_session_history(session_id)` -> 转换为 zhipuai 消息结构。
- 保存：`add_conversation(session_id, user_input, final_answer)`。

#### 3.4.2 MCP 工具集成
与 `GlobalMCPManager` 完全兼容：
- 加载：在 `_initialize_tools()` 中通过 `GlobalMCPManager.get_tools()` 获取 MCP 工具
- 转换：通过 `convert_tool_to_function()` 将 MCP 工具转换为 Function Calling 格式
- 执行：通过 `execute_tool_with_arguments_async()` 正确执行 MCP 工具
- 参数处理：特别处理 MCP 工具的 JSON schema 参数，确保传递正确的字典格式

#### 3.4.3 Agent 工厂路由
`agent_factory.py` 在 `provider=="zhipu" and model=="glm-4.5"` 时创建 FC Agent；其余走 ReAct。
```python
if provider == LLMProvider.ZHIPU:
    if model == "glm-4.5":
        from .zhipu_fcall_agent import build_zhipu_fcall_agent
        agent = await build_zhipu_fcall_agent(...)
    else:
        from .zhipu_agent import build_zhipu_agent
        agent = await build_zhipu_agent(...)
```

### 3.5 返回结构（与 ZhipuAgent 保持一致）
```json
{
  "output": "最终回答",
  "tool_calls": 2,
  "intermediate_steps": [
    {"tool": "xxx", "args": {"query": "..."}, "result": "...", "error": null}
  ],
  "error": null
}
```
`get_info()` 额外包含 `{"mode": "function_calling"}`。

## 4. 开发计划

### 4.1 第一阶段：基础实现（已完成）
- [x] 新增 `src/agents/functioncalling_adapter.py`（工具到 FC 的适配）。
- [x] 新增 `src/agents/zhipu_fcall_agent.py`（基础框架 + 单轮/多轮 FC 循环）。
- [x] 使用 `zhipuai` SDK 直调 Chat Completions（附 `tools`）。
- [x] 集成 `GlobalMemoryManager`（读取历史 + 保存本轮）。
- [x] 最小化接入现有工具：数学/搜索（确保 E2E 通）。

### 4.2 第二阶段：功能完善（部分完成）
- [x] 错误处理与重试机制完善（细化错误类型）。
- [x] AgentFactory 路由完成并稳定缓存策略。
- [x] 支持 MCP 工具集成。
- [ ] 支持更多工具（Tavily、Notion、地图、OKX）。
- [ ] CLI 文案/信息优化（区分 FC/React 模式）。
- [ ] 编写单元测试（工具适配器、工具执行器、FC 循环 mock）。

### 4.3 第三阶段：测试与优化（待完成）
- [ ] 全面功能测试（多工具、多轮、异常分支）。
- [ ] 性能和用户体验优化（必要时并行工具执行）。
- [ ] 文档更新（README/本指南同步最终实现）。

## 5. 注意事项

1. 仅 `glm-4.5` 启用 FC，默认仍走 ReAct（`glm-4-plus`）。
2. 工具无需修改，全部通过适配器转换为 Zhipu `tools`。
3. 错误需结构化，禁止暴露敏感信息；必要时截断工具输出。
4. 与记忆系统保持完全兼容，接口与返回结构对齐现有 CLI 使用方式。
5. 首版以正确性为先；流式输出与并行工具执行可在后续迭代。
6. MCP 工具已完整集成，支持所有 MCP 服务器（Filesystem、Notion、Context7等）。

## 6. MCP 工具支持详情

### 6.1 支持的 MCP 服务器
- Filesystem MCP：文件系统操作（读取、写入、目录浏览等）
- Notion MCP：Notion 页面和数据库操作
- Context7 MCP：文档搜索和检索

### 6.2 MCP 工具参数处理
MCP 工具使用 JSON schema 的 args_schema，需要特别处理：
- 确保传递字典格式参数
- 避免传递字符串参数导致 "String tool inputs are not allowed" 错误
- 自动转换单值参数为正确的字典格式

### 6.3 MCP 工具执行
MCP 工具通过 `execute_tool_with_arguments_async()` 函数执行，支持异步调用和错误重试机制。