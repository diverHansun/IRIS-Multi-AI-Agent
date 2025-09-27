# 智谱AI函数调用(Function Calling)开发与使用指南 🚀

## 1. 概述 📚

智谱AI函数调用(Function Calling)是专为 `glm-4.5` 模型设计的智能代理系统，通过原生函数调用API实现AI与工具的无缝交互。该系统将LangChain工具转换为函数调用格式，使AI能够自主决定何时以及如何调用特定工具来完成任务。

### 核心特性 ✨
- **原生函数调用支持**：直接与智谱AI的函数调用API交互
- **工具适配机制**：自动将LangChain BaseTool转换为函数调用格式
- **异步执行**：支持异步工具调用，提高执行效率
- **错误处理**：结构化错误处理和重试机制
- **记忆管理**：与全局记忆管理器完全兼容
- **MCP集成**：支持MCP工具的完整集成

## 2. 架构设计 🏗️

### 2.1 文件结构
```
src/agents/
├── zhipu_fcall_agent.py      # 智谱AI函数调用代理主实现
├── functioncalling_adapter.py # 工具适配器：BaseTool → 函数调用格式
├── agent_factory.py          # 代理工厂：按模型路由到不同实现
└── ...
```

### 2.2 模块职责

#### 2.2.1 智谱AI函数调用代理 (`zhipu_fcall_agent.py`)
- **初始化管理**：创建智谱AI客户端、加载工具、初始化记忆管理器
- **消息处理**：组装对话历史消息，调用函数调用API
- **循环执行**：实现工具调用循环，直到AI生成最终回答
- **记忆管理**：与 `GlobalMemoryManager` 集成，处理会话历史
- **工具集成**：支持SDK工具、连接器工具、MCP工具的自动加载

#### 2.2.2 函数调用适配器 (`functioncalling_adapter.py`)
- **工具转换**：将LangChain BaseTool转换为智谱AI函数调用格式
- **参数处理**：智能处理工具参数，支持多种参数格式
- **异步执行**：提供异步和同步工具执行接口
- **错误处理**：统一结构化错误处理机制

#### 2.2.3 代理工厂 (`agent_factory.py`)
- **路由逻辑**：根据模型名称路由到不同实现（`glm-4.5` → 函数调用，其他 → ReAct）
- **实例管理**：创建和管理不同类型的代理实例

## 3. API 接口 🌐

### 3.1 智谱AI函数调用代理接口

#### 3.1.1 初始化接口
```python
def __init__(
    self,
    model: str = "glm-4.5",
    temperature: float = 0.1,
    verbose: bool = False,
    max_iterations: int = 10,
    enable_memory: bool = True,
    global_memory_manager=None,
    **kwargs
)
```

**参数说明**：
- `model`: 模型名称，仅支持 `glm-4.5`
- `temperature`: 温度参数，控制输出随机性
- `verbose`: 是否显示详细日志
- `max_iterations`: 最大迭代次数，防止无限循环
- `enable_memory`: 是否启用记忆功能
- `global_memory_manager`: 全局记忆管理器实例

#### 3.1.2 执行接口
```python
async def invoke(self, query: str, session_id: str = "default", **kwargs) -> Dict[str, Any]
```

**返回值结构**：
```json
{
  "output": "最终回答",
  "tool_calls": 2,
  "tool_names": ["search", "calculator"],
  "intermediate_steps": [
    {
      "tool": "search", 
      "args": {"query": "AI发展历史"}, 
      "result": "...", 
      "error": null
    }
  ],
  "error": null,
  "success": true
}
```

#### 3.1.3 信息接口
```python
def get_agent_info(self) -> Dict[str, Any]
```

**返回信息**：
- `provider`: "zhipu"
- `model`: 模型名称
- `mode`: "function_calling"
- `tool_count`: 工具数量
- `memory_enabled`: 记忆是否启用

### 3.2 工具适配器接口

#### 3.2.1 工具转换接口
```python
def convert_tool_to_function(tool: BaseTool) -> Dict[str, Any]
```

**转换结果格式**：
```json
{
  "type": "function",
  "function": {
    "name": "tool_name",
    "description": "tool_description",
    "parameters": {
      "type": "object",
      "properties": {},
      "required": []
    }
  }
}
```

#### 3.2.2 工具执行接口
```python
def execute_tool_with_arguments(tool: BaseTool, arguments: Dict[str, Any]) -> Any
async def execute_tool_with_arguments_async(tool: BaseTool, arguments: Dict[str, Any]) -> Any
```

## 4. 配置系统 ⚙️

### 4.1 代理配置参数
- `model`: 模型名称（固定为 `glm-4.5`）
- `temperature`: 温度参数（0.0-1.0）
- `max_iterations`: 最大迭代次数（默认10次）
- `verbose`: 详细日志开关
- `enable_memory`: 记忆功能开关

### 4.2 工具加载配置
自动加载以下类型工具：
1. **SDK工具**：通过 `SDKToolManager` 获取
2. **连接器工具**：通过 `ConnectorToolManager` 获取
3. **MCP工具**：通过 `GlobalMCPManager` 获取

### 4.3 记忆管理配置
- **本地记忆**：每个代理实例独立的记忆管理器
- **全局记忆**：共享的 `GlobalMemoryManager` 实例
- **历史限制**：最多保留10条历史消息

## 5. 错误处理 🛡️

### 5.1 错误分类
- `tool_runtime`: 工具运行时错误
- `invalid_arguments`: 参数无效错误
- `tool_not_found`: 工具未找到错误
- `internal`: 内部错误

### 5.2 错误结构
```json
{
  "error": "具体错误信息",
  "type": "错误类型",
  "retryable": true/false,
  "tool_name": "工具名称"
}
```

### 5.3 重试机制
- **最大重试次数**：3次
- **可重试错误**：超时、网络连接、临时性错误
- **重试间隔**：1秒

### 5.4 错误处理流程
1. 捕获工具执行异常
2. 判断错误是否可重试
3. 如果可重试且未达到最大重试次数，等待后重试
4. 否则将错误信息结构化返回

## 6. 与 AI 代理连接 🔗

### 6.1 代理工厂集成
通过 `agent_factory.py` 实现按模型路由：
```python
if provider == LLMProvider.ZHIPU:
    if model == "glm-4.5":
        from .zhipu_fcall_agent import build_zhipu_fcall_agent
        agent = await build_zhipu_fcall_agent(...)
    else:
        from .zhipu_agent import build_zhipu_agent
        agent = await build_zhipu_agent(...)
```

### 6.2 工具链集成
自动集成以下工具类型：
- **SDK工具**：标准LangChain工具
- **连接器工具**：HTTP API工具（如Crawl4AI）
- **MCP工具**：Model Context Protocol工具

### 6.3 记忆系统集成
- **历史读取**：从 `GlobalMemoryManager` 获取会话历史
- **结果保存**：将当前对话轮次保存到记忆系统
- **消息格式转换**：将LangChain消息格式转换为智谱AI格式

## 7. 使用方法 💡

### 7.1 基本用法
```python
from src.agents.zhipu_fcall_agent import build_zhipu_fcall_agent

# 创建函数调用代理
agent = await build_zhipu_fcall_agent(
    model="glm-4.5",
    temperature=0.1,
    verbose=True
)

# 执行查询
result = await agent.invoke("查询今天的天气情况")

# 获取结果
print(result["output"])
print(f"使用工具: {result['tool_names']}")
```

### 7.2 配置会话
```python
# 使用特定会话ID
result = await agent.invoke("继续之前的对话", session_id="user_123")
```

### 7.3 获取代理信息
```python
info = agent.get_agent_info()
print(f"模型: {info['model']}")
print(f"工具数量: {info['tool_count']}")
print(f"记忆启用: {info['memory_enabled']}")
```

## 8. 最佳实践 🎯

### 8.1 工具适配策略
- **参数转换**：智能处理JSON参数、字典参数和单值参数
- **错误处理**：提供结构化错误信息便于AI决策
- **异步优先**：优先使用异步执行提高性能

### 8.2 性能优化
- **最大迭代限制**：防止无限循环
- **历史消息限制**：避免消息过长
- **工具执行重试**：处理临时性错误

### 8.3 安全考虑
- **错误信息脱敏**：不向AI暴露敏感错误详情
- **参数验证**：验证工具调用参数的有效性
- **资源限制**：限制工具执行时间和资源使用

## 9. MCP工具支持 🛠️

### 9.1 支持的MCP服务器
- **Filesystem MCP**：文件系统操作（读取、写入、目录浏览等）
- **Notion MCP**：Notion页面和数据库操作
- **Context7 MCP**：文档搜索和检索

### 9.2 MCP工具参数处理
- **JSON Schema支持**：正确处理MCP工具的复杂参数结构
- **字典格式转换**：确保传递正确的字典格式参数
- **错误类型识别**：区分MCP工具特有的错误类型

## 10. 开发注意事项 ⚠️

### 10.1 模型限制
- 函数调用功能仅支持 `glm-4.5` 模型
- 其他模型继续使用ReAct模式

### 10.2 工具兼容性
- 所有现有工具无需修改，通过适配器自动转换
- 支持各种类型的LangChain工具（BaseTool、@tool装饰器等）

### 10.3 接口兼容性
- 保持与现有代理接口的一致性
- 返回结构与传统代理保持一致

---

本指南详细介绍了智谱AI函数调用系统的设计、实现和使用方法，为开发者提供了全面的技术参考。