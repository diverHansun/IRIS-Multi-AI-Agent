# 服务层重构指南

## 模块概述

服务层是业务逻辑的核心，负责：
- 实现各引擎的具体功能
- 提供统一的服务接口
- 管理引擎状态和生命周期

**核心原则**：按引擎分包，每个引擎独立服务，实现 BaseEngineService 接口

## 目录结构

```
application/services/
├── __init__.py          # 引擎服务路由器
├── base.py              # BaseEngineService 抽象基类
│
├── langchain/           # LangChain 引擎服务
│   ├── __init__.py
│   ├── service.py           # 主服务（实现 BaseEngineService）
│   ├── conversation.py      # 对话处理（LLM/Agent 模式）
│   ├── streaming.py         # 流式输出管理
│   └── agent_lifecycle.py   # Agent 创建/切换/销毁
│
├── langgraph/           # LangGraph 引擎服务（预留）
│   ├── __init__.py
│   ├── service.py           # 主服务
│   ├── graph_executor.py    # Graph 执行器
│   ├── graph_builder.py     # Graph 构建器
│   └── workflow_manager.py  # 工作流管理
│
└── dify/                # Dify 引擎服务
    ├── __init__.py
    ├── service.py           # 主服务（原 control.py 重构）
    ├── client.py            # Dify API 客户端
    ├── streaming.py         # 流式处理
    └── upload.py            # 文件上传
```

## 关键模块说明

### 1. base.py - BaseEngineService 抽象基类

**职责**：
- 定义引擎服务标准接口
- 保证各引擎实现一致性

**关键接口**：

```python
class BaseEngineService(ABC):
    """引擎服务抽象基类"""
    
    @abstractmethod
    async def initialize(self, ctx) -> dict:
        """初始化引擎
        
        Returns:
            {"type": "success"|"error", "message": str, "payload": dict}
        """
        pass
    
    @abstractmethod
    async def handle_query(self, ctx, query: str) -> str:
        """处理用户对话
        
        Returns:
            对话响应文本
        """
        pass
    
    @abstractmethod
    async def switch_model(self, ctx, provider: str, model: str = None) -> dict:
        """切换模型（如果支持）
        
        Returns:
            {"type": "success"|"error", "message": str}
        """
        pass
    
    @abstractmethod
    def get_info(self, ctx) -> dict:
        """获取引擎信息
        
        Returns:
            引擎详细信息字典
        """
        pass
    
    @abstractmethod
    def supports_command(self, command_name: str) -> bool:
        """判断命令是否可用
        
        Returns:
            True if command is supported
        """
        pass
```

### 2. __init__.py - 引擎服务路由器

**职责**：
- 提供统一的服务获取接口

**关键接口**：

```python
from .langchain.service import LangChainService
from .langgraph.service import LangGraphService
from .dify.service import DifyService

ENGINE_SERVICES = {
    "langchain": LangChainService,
    "langgraph": LangGraphService,
    "dify": DifyService,
}

def get_current_service(ctx):
    """获取当前引擎的服务实例"""
    service_class = ENGINE_SERVICES.get(ctx.current_engine)
    if not service_class:
        raise ValueError(f"Unknown engine: {ctx.current_engine}")
    return service_class()
```

## LangChain 引擎服务

### 3. langchain/conversation.py - 对话处理

**职责**：
- 处理 LLM 和 Agent 两种模式的对话
- 构建上下文历史
- 保存对话记忆

**关键接口**：

```python
async def handle_llm_query(ctx, query: str, streaming: bool = True) -> str:
    """LLM 模式对话
    
    流程：
    1. 获取 LLM 实例
    2. 构建上下文历史
    3. 流式/非流式输出
    4. 保存记忆
    """
    config = ctx.engine_configs["langchain"]
    agent = config["agent"]
    llm = agent.get_llm()
    
    # 构建上下文
    history = ctx.global_memory.get_session_history(ctx.session_id)
    messages = build_context_messages(history, query)
    
    if streaming:
        from .streaming import stream_response
        answer = await stream_response(config["provider"], messages, llm)
    else:
        response = await llm.ainvoke(messages)
        answer = response.content
    
    # 保存记忆
    ctx.global_memory.add_llm_conversation(ctx.session_id, query, answer)
    return answer

async def handle_agent_query(ctx, query: str) -> dict:
    """Agent 模式对话"""
    config = ctx.engine_configs["langchain"]
    agent = config["agent"]
    
    result = await agent.ainvoke(query, session_id=ctx.session_id)
    return result

def build_context_messages(history, query: str, max_messages: int = 10):
    """构建上下文消息"""
    # 从历史中提取最近的消息
    recent_messages = history.messages[-max_messages:] if history.messages else []
    # 添加当前查询
    # ...
    return messages
```

**迁移映射**：
- `components/process/cli.py` L198-234 (LLM 对话) → `langchain/conversation.py:handle_llm_query()`
- `components/process/cli.py` L239-260 (非流式 LLM) → `langchain/conversation.py:handle_llm_query(streaming=False)`
- `components/process/cli.py` L266-283 (Agent 对话) → `langchain/conversation.py:handle_agent_query()`

### 4. langchain/streaming.py - 流式服务

> **📌 模块定位说明**：
> 
> 系统中存在两个 streaming 模块，各有不同职责：
> 
> 1. **底层工具** - `src/llm/langchain/utils/streaming.py`
>    - 通用流式工具库，提供 `StreamingLLM` 抽象基类
>    - 实现各提供商流式策略（Zhipu, OpenAI, Ollama）
>    - 提供 `StreamingManager` 和 `StreamingDisplay`
>    - **无业务依赖，可被多个引擎复用**
> 
> 2. **应用服务** - `application/services/langchain/streaming.py`（本模块）
>    - 应用层流式服务封装
>    - 处理 LLM 注册逻辑（从 cli.py 迁移而来）
>    - 与 AppState 协调，提供业务接口
>    - **调用底层工具，处理应用级逻辑**
> 
> 这符合分层架构原则：底层工具可复用，应用服务处理业务。

**职责**：
- 统一管理流式 LLM 注册
- 避免重复注册
- 提供流式输出封装

**关键接口**：

```python
class StreamingService:
    """流式服务（单例模式）"""
    
    _registry = {}  # {provider: llm_instance}
    
    @classmethod
    def register_llm(cls, provider: str, llm):
        """注册 LLM 实例（去重）"""
        if provider not in cls._registry:
            cls._registry[provider] = llm
            logger.debug(f"Registered streaming LLM: {provider}")
    
    @classmethod
    async def stream_response(cls, provider: str, messages, llm=None):
        """流式输出响应"""
        llm_instance = llm or cls._registry.get(provider)
        if not llm_instance:
            raise ValueError(f"No LLM registered for {provider}")
        
        from src.llm.langchain.utils import stream_llm_response
        return await stream_llm_response(provider, messages, llm_instance)

# 便捷函数
async def stream_response(provider: str, messages, llm):
    """流式输出响应"""
    return await StreamingService.stream_response(provider, messages, llm)

def register_streaming_llm(agent):
    """注册 Agent 的流式 LLM"""
    info = agent.get_info()
    llm = agent.get_llm()
    if llm:
        StreamingService.register_llm(info['provider'], llm)
```

**迁移映射**：
- `components/process/cli.py` L150-159 (初始化时注册) → `langchain/streaming.py:register_streaming_llm()`
- `components/process/control.py` L42-54 (切换时注册) → `langchain/streaming.py:register_streaming_llm()`
- 统一为单例注册，避免重复

### 5. langchain/agent_lifecycle.py - Agent 生命周期

**职责**：
- Agent 创建、切换、销毁
- 自动注册流式 LLM

**关键接口**：

```python
async def create_agent(ctx, provider: str, model: str = None):
    """创建 Agent 并注册流式 LLM"""
    from src.agents.langchain.managers import agent_manager
    
    agent = await agent_manager.create_agent(
        provider=provider,
        model=model,
        global_memory_manager=ctx.global_memory
    )
    
    # 自动注册流式 LLM
    from .streaming import register_streaming_llm
    register_streaming_llm(agent)
    
    return agent

async def switch_agent(ctx, provider: str, model: str = None):
    """切换 Agent"""
    config = ctx.engine_configs["langchain"]
    
    # 创建新 Agent
    new_agent = await create_agent(ctx, provider, model)
    
    # 更新配置
    config["agent"] = new_agent
    config["provider"] = provider
    config["model"] = new_agent.get_info()["model"]
    
    return new_agent
```

**迁移映射**：
- `components/process/cli.py` L131-143 (初始化 Agent) → `langchain/agent_lifecycle.py:create_agent()`
- `components/process/control.py` L10-70 (切换 Agent) → `langchain/agent_lifecycle.py:switch_agent()`

### 6. langchain/service.py - LangChain 主服务

**职责**：
- 实现 BaseEngineService 接口
- 协调各子模块

**关键接口**：

```python
class LangChainService(BaseEngineService):
    """LangChain 引擎主服务"""
    
    async def initialize(self, ctx) -> dict:
        """初始化 LangChain 引擎"""
        from .agent_lifecycle import create_agent
        
        config = ctx.engine_configs["langchain"]
        agent = await create_agent(
            ctx,
            provider=config["provider"],
            model=config.get("model")
        )
        
        config["agent"] = agent
        
        return {
            "type": "success",
            "message": "LangChain initialized",
            "payload": agent.get_info()
        }
    
    async def handle_query(self, ctx, query: str) -> str:
        """处理对话"""
        from .conversation import handle_llm_query, handle_agent_query
        
        config = ctx.engine_configs["langchain"]
        
        if config["mode"] == "llm":
            return await handle_llm_query(ctx, query, config["streaming"])
        else:
            result = await handle_agent_query(ctx, query)
            return result.get("output", "")
    
    async def switch_model(self, ctx, provider: str, model: str = None) -> dict:
        """切换模型"""
        from .agent_lifecycle import switch_agent
        
        agent = await switch_agent(ctx, provider, model)
        info = agent.get_info()
        
        return {
            "type": "success",
            "message": f"Switched to {info['provider']}/{info['model']}",
            "payload": info
        }
    
    def get_info(self, ctx) -> dict:
        """获取引擎信息"""
        config = ctx.engine_configs["langchain"]
        agent = config["agent"]
        
        info = agent.get_info()
        info.update({
            "mode": config["mode"],
            "streaming": config["streaming"]
        })
        return info
    
    def supports_command(self, command_name: str) -> bool:
        """判断命令可用性"""
        return command_name in ["model", "mode", "stream", "llms", "reload", "mcp", "connector"]
```

## Dify 引擎服务

### 7. dify/service.py - Dify 主服务

**职责**：
- 实现 BaseEngineService 接口
- 封装 DifyControl 逻辑

**关键接口**：

```python
class DifyService(BaseEngineService):
    """Dify 引擎主服务"""
    
    async def initialize(self, ctx) -> dict:
        """初始化 Dify 客户端"""
        from .client import DifyClient
        from .streaming import DifyStreaming
        
        config = ctx.engine_configs["dify"]
        
        # 加载配置
        dify_config = self._load_config()
        
        # 创建客户端
        client = DifyClient(
            api_key=dify_config['api_key'],
            base_url=dify_config['base_url']
        )
        
        # 创建流式处理器
        streaming = DifyStreaming(ctx.console)
        
        config["client"] = client
        config["streaming"] = streaming
        
        return {
            "type": "success",
            "message": "Dify initialized",
            "payload": {}
        }
    
    async def handle_query(self, ctx, query: str) -> str:
        """处理对话"""
        config = ctx.engine_configs["dify"]
        client = config["client"]
        streaming_handler = config["streaming"]
        
        # 发送查询
        stream = client.chat_message(
            query=query,
            user_id=ctx.session_id,
            streaming=True,
            conversation_id=config.get("conversation_id"),
            files=config.get("files")
        )
        
        # 显示流式响应
        new_conversation_id = await streaming_handler.display_stream(stream)
        
        # 更新会话 ID
        if new_conversation_id:
            config["conversation_id"] = new_conversation_id
        
        # 清空文件列表（一次性使用）
        if config.get("files"):
            config["files"] = []
        
        return ""  # 流式显示已处理
    
    async def switch_model(self, ctx, provider: str, model: str = None) -> dict:
        """Dify 不支持切换模型"""
        return {
            "type": "error",
            "message": "Dify uses cloud model, cannot switch",
            "payload": {}
        }
    
    def get_info(self, ctx) -> dict:
        """获取 Dify 信息"""
        config = ctx.engine_configs["dify"]
        return {
            "provider": "Dify",
            "model": "Cloud AI",
            "conversation_id": config.get("conversation_id"),
            "files_count": len(config.get("files", []))
        }
    
    def supports_command(self, command_name: str) -> bool:
        """判断命令可用性"""
        return command_name in ["upload", "files", "reset", "reconnect"]
```

**迁移映射**：
- `components/dify/control.py` (DifyControl 类) → `dify/service.py` (DifyService 类)
  - 重构：实现 BaseEngineService 接口
  - `initialize()` → `initialize()`
  - `handle_query()` → `handle_query()`

### 8. dify/ 其他模块迁移

**client.py, streaming.py, upload.py**：

```python
# 直接迁移，无需修改
components/dify/client.py    → services/dify/client.py
components/dify/streaming.py → services/dify/streaming.py
components/dify/upload.py    → services/dify/upload.py
```

## LangGraph 引擎服务（预留）

### 9. langgraph/service.py - LangGraph 主服务

**预留接口**：

```python
class LangGraphService(BaseEngineService):
    """LangGraph 引擎主服务（预留）"""
    
    async def initialize(self, ctx) -> dict:
        """初始化 LangGraph"""
        # 未来实现
        pass
    
    async def handle_query(self, ctx, query: str) -> str:
        """运行 Graph"""
        # 未来实现
        pass
    
    async def switch_model(self, ctx, provider: str, model: str = None) -> dict:
        """切换 Graph 使用的 LLM"""
        # 未来实现
        pass
    
    def supports_command(self, command_name: str) -> bool:
        return command_name in ["model", "graph", "nodes", "visualize"]
```

## 使用示例

### 在 CLI 中使用服务

```python
# application/cli/main.py

from ..services import get_current_service

async def run():
    # ...
    if not is_command(query):
        # 对话 - 通过服务处理
        service = get_current_service(ctx)
        answer = await service.handle_query(ctx, query)
        ctx.console.print(f"[bold blue]>[/] {answer}")
```

### 在命令中使用服务

```python
# application/commands/langchain/model_commands.py

from ...services.langchain import LangChainService

class LangChainModelCommand(BaseCommand):
    async def execute(self, ctx, args):
        service = LangChainService()
        result = await service.switch_model(ctx, provider, model)
        return result
```

## 风险点

### 1. 循环导入

**风险**：service 和 adapter 相互导入

**应对**：
- adapter 只导入 service（单向依赖）
- 必要时使用动态导入

### 2. 状态同步

**风险**：`engine_configs` 中的状态可能与实际不一致

**应对**：
- 所有状态修改通过 service 接口
- 提供验证方法确保状态一致

### 3. 资源清理

**风险**：引擎切换时资源未正确释放

**应对**：
- 实现 `cleanup()` 方法
- 在引擎切换时调用清理

## 迁移检查清单

- [ ] 创建 `base.py`，定义 BaseEngineService 接口
- [ ] 创建 `__init__.py`，实现服务路由
- [ ] 实现 LangChain 服务：
  - [ ] `conversation.py` - 抽取对话逻辑
  - [ ] `streaming.py` - 统一流式管理
  - [ ] `agent_lifecycle.py` - Agent 生命周期
  - [ ] `service.py` - 主服务
- [ ] 迁移 Dify 服务：
  - [ ] `control.py` → `service.py` 重构
  - [ ] 迁移 `client.py`, `streaming.py`, `upload.py`
- [ ] 预留 LangGraph 服务结构
- [ ] 测试服务接口和引擎切换

