# LangChain 1.0.0 迁移文档

## 文档概述

本目录包含将项目从旧版 LangChain Agent API 迁移到 LangChain 1.0.0 新版 API 的完整文档。

## 文档结构

1. **migration_overview.md** - 迁移概述
   - 版本信息和迁移范围
   - 核心 API 变化对比
   - 迁移策略和风险评估
   - 主要挑战和解决方案

2. **api_analysis.md** - API 详细分析
   - `create_agent()` 函数详解
   - `CompiledStateGraph` 接口说明
   - `AgentState` 结构详解
   - Message 类型和工具调用流程
   - 与旧版 API 的映射关系

3. **architecture_design.md** - 架构设计方案
   - 当前架构 vs 目标架构
   - BaseAgent 重构设计
   - AgentAdapter 重构设计
   - Memory 集成方案
   - 配置参数处理
   - 迁移路径和检查清单

## 核心变化总结

### API 变化

| 方面 | 旧版 | 新版 |
|------|------|------|
| 创建方式 | `create_react_agent()` / `create_tool_calling_agent()` | 统一的 `create_agent()` |
| 返回类型 | `AgentExecutor` | `CompiledStateGraph` |
| 输入格式 | `{"input": str}` | `{"messages": [Message, ...]}` |
| 输出格式 | `{"output": str, "intermediate_steps": [...]}` | `{"messages": [Message, ...]}` |
| Prompt | 复杂的 PromptTemplate | 简单的 system_prompt 字符串 |
| Memory | RunnableWithMessageHistory | 原生 checkpointer |

### 迁移策略

我们采用**直接重构**方案：
1. 更新 Adapter 层使用新的 `create_agent()` API
2. 重构 BaseAgent 添加输入输出转换层
3. 保持对外接口不变
4. 可选：迁移到新的 checkpointer 系统

### 文件改动范围

需要修改的核心文件：
- `src/agents/basicagents/adapters/base.py`
- `src/agents/basicagents/adapters/zhipu_agent_adapter.py`
- `src/agents/basicagents/adapters/openai_agent_adapter.py`
- `src/agents/basicagents/adapters/ollama_agent_adapter.py`
- `src/agents/basicagents/instances/base_agent.py`
- `src/components/shared/memory/` (可选)

## 快速开始

1. 阅读 [migration_overview.md](./migration_overview.md) 了解整体变化
2. 阅读 [api_analysis.md](./api_analysis.md) 深入理解新 API
3. 阅读 [architecture_design.md](./architecture_design.md) 查看具体设计方案
4. 按照迁移检查清单逐步实施

## 关键代码片段

### 新版 Agent 创建

```python
from langchain.agents import create_agent

graph = create_agent(
    model=llm,                    # LLM 实例
    tools=tools,                  # 工具列表
    system_prompt="...",          # 系统提示词
    checkpointer=checkpointer,    # 可选：用于 memory
    debug=False                   # 替代 verbose
)
```

### 新版执行方式

```python
# 输入格式
input_data = {
    "messages": [HumanMessage(content="user query")]
}

# 执行
result = await graph.ainvoke(
    input_data,
    config={"configurable": {"thread_id": "session_id"}}
)

# 输出格式
# result = {
#     "messages": [HumanMessage(...), AIMessage(...), ...]
# }
```

### 输出转换

```python
# 从 messages 中提取最终输出
output = ""
for msg in reversed(result["messages"]):
    if isinstance(msg, AIMessage):
        output = msg.content
        break

# 从 messages 中提取工具调用信息
for msg in result["messages"]:
    if isinstance(msg, AIMessage) and msg.tool_calls:
        # 处理 tool_calls
        pass
```

## 注意事项

1. **不兼容变化**: 新旧 API 输入输出格式完全不同，需要转换层
2. **Memory 系统**: 建议迁移到新的 checkpointer，但也可以保持兼容旧系统
3. **配置参数**: `max_iterations` 等参数需要通过 config 或 middleware 实现
4. **测试覆盖**: 务必充分测试，确保输出格式兼容

## 参考资源

- LangChain 官方文档: https://docs.langchain.com/oss/python/langchain/agents
- LangGraph 文档: https://langchain-ai.github.io/langgraph/
- Agent State 文档: https://docs.langchain.com/oss/python/langchain/agents#agent-state

## 问题反馈

迁移过程中遇到问题，请：
1. 查阅文档中的"主要挑战"部分
2. 检查示例代码
3. 查看错误处理和回退策略


