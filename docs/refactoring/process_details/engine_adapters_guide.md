# 引擎适配层重构指南

## 模块概述

引擎适配层是三大引擎的统一网关，负责：
- 提供统一的调用接口
- 根据当前引擎分流请求
- 调用转换（适配不同的服务接口）

**核心原则**：只做分流路由，不包含业务逻辑

## 目录结构

```
application/engine_adapters/
├── __init__.py              # 适配器路由
├── base.py                  # BaseEngineAdapter（可选）
├── langchain_adapter.py     # LangChain 适配器
├── langgraph_adapter.py     # LangGraph 适配器（预留）
└── dify_adapter.py          # Dify 适配器
```

## 设计理念

### Adapter 职责边界

Adapter 层的职责：
- **做什么**：接收请求 → 选择服务 → 调用服务 → 返回结果
- **不做什么**：不包含业务逻辑、不操作状态、不处理数据

**职责对比**：
```
Adapter（轻量）:
  - 分流路由
  - 接口转换
  - 异常包装

Service（重量）:
  - 业务逻辑
  - 状态管理
  - 数据处理
```

## 关键模块说明

### 1. __init__.py - 适配器路由

**职责**：
- 提供统一的适配器获取接口

**关键接口**：

```python
from .langchain_adapter import LangChainAdapter
from .langgraph_adapter import LangGraphAdapter
from .dify_adapter import DifyAdapter

ADAPTERS = {
    "langchain": LangChainAdapter,
    "langgraph": LangGraphAdapter,
    "dify": DifyAdapter,
}

def get_adapter(engine: str):
    """获取指定引擎的适配器"""
    adapter_class = ADAPTERS.get(engine)
    if not adapter_class:
        raise ValueError(f"Unknown engine: {engine}")
    return adapter_class()
```

### 2. langchain_adapter.py - LangChain 适配器

**职责**：
- 路由到 LangChain 服务
- 统一调用接口

**关键接口**：

```python
class LangChainAdapter:
    """LangChain 引擎适配器"""
    
    @staticmethod
    async def handle_query(ctx, query: str) -> str:
        """处理对话请求
        
        职责：
        1. 获取 LangChain 服务实例
        2. 调用服务的 handle_query() 方法
        3. 返回结果
        """
        from ..services.langchain import LangChainService
        
        service = LangChainService()
        return await service.handle_query(ctx, query)
    
    @staticmethod
    def get_service(ctx):
        """获取服务实例（辅助方法）"""
        from ..services.langchain import LangChainService
        return LangChainService()
```

**说明**：
- Adapter 不存储状态，只做路由
- 使用静态方法，避免实例化开销
- 动态导入 service，避免循环依赖

### 3. langgraph_adapter.py - LangGraph 适配器（预留）

**预留接口**：

```python
class LangGraphAdapter:
    """LangGraph 引擎适配器（预留）"""
    
    @staticmethod
    async def handle_query(ctx, query: str) -> str:
        """处理对话请求"""
        from ..services.langgraph import LangGraphService
        
        service = LangGraphService()
        return await service.handle_query(ctx, query)
    
    @staticmethod
    async def handle_graph_execution(ctx, graph_name: str, input_state: dict):
        """处理 Graph 执行请求（特定接口）"""
        from ..services.langgraph import LangGraphService
        
        service = LangGraphService()
        return await service.execute_graph(ctx, graph_name, input_state)
```

### 4. dify_adapter.py - Dify 适配器

**关键接口**：

```python
class DifyAdapter:
    """Dify 引擎适配器"""
    
    @staticmethod
    async def handle_query(ctx, query: str) -> str:
        """处理对话请求"""
        from ..services.dify import DifyService
        
        service = DifyService()
        return await service.handle_query(ctx, query)
    
    @staticmethod
    async def handle_file_upload(ctx, files: List[str]):
        """处理文件上传请求（Dify 特定接口）"""
        from ..services.dify import DifyService
        
        service = DifyService()
        return await service.upload_files(ctx, files)
```

## 使用示例

### 在 CLI 主循环中使用

```python
# application/cli/main.py

from ..engine_adapters import get_adapter

async def run():
    # ...
    
    while True:
        query = await asyncio.to_thread(ctx.console.input, prompt)
        
        if not is_command(query):
            # 对话处理 - 通过适配器路由
            adapter = get_adapter(ctx.current_engine)
            result = await adapter.handle_query(ctx, query)
            
            if result:  # 某些引擎可能已在内部显示
                ctx.console.print(f"[bold blue]>[/] {result}")
```

### 引擎切换流程

```python
# 1. 用户执行 /switch langgraph

# 2. SwitchEngineCommand 执行：
ctx.current_engine = "langgraph"

# 3. 初始化新引擎
from ..services import get_current_service
service = get_current_service(ctx)
await service.initialize(ctx)

# 4. 下次对话时，适配器自动路由到 LangGraph
adapter = get_adapter(ctx.current_engine)  # 返回 LangGraphAdapter
result = await adapter.handle_query(ctx, query)
```

## 数据流向

```
用户输入（非命令）
    ↓
cli/main.py
    ↓
get_adapter(ctx.current_engine)
    ↓
┌──────────┬──────────┬──────────┐
│LangChain │LangGraph │  Dify    │ (Adapter 选择)
│Adapter   │Adapter   │Adapter   │
└────┬─────┴────┬─────┴────┬─────┘
     ↓          ↓          ↓
┌──────────┬──────────┬──────────┐
│LangChain │LangGraph │  Dify    │ (Service 调用)
│Service   │Service   │Service   │
└──────────┴──────────┴──────────┘
```

## 可选：BaseEngineAdapter

如果需要更严格的接口约束，可以定义基类：

```python
# application/engine_adapters/base.py

class BaseEngineAdapter(ABC):
    """引擎适配器抽象基类（可选）"""
    
    @staticmethod
    @abstractmethod
    async def handle_query(ctx, query: str) -> str:
        """处理对话请求"""
        pass
    
    @staticmethod
    @abstractmethod
    def get_service(ctx):
        """获取服务实例"""
        pass
```

**使用场景**：
- 需要强制统一接口
- 需要类型检查和文档生成
- 团队协作需要明确规范

**不使用的理由**：
- Adapter 足够简单，接口清晰
- Python 的鸭子类型已足够
- 避免过度设计

## 风险点

### 1. 循环导入

**风险**：adapter 导入 service，service 可能导入 adapter

**应对**：
- adapter 只导入 service（单向依赖）
- 使用动态导入（在方法内部 import）
- service 层不导入 adapter

### 2. 接口不一致

**风险**：不同 adapter 提供的接口不一致

**应对**：
- 定义核心接口：`handle_query()`
- 引擎特定接口通过独立方法提供
- 使用 BaseEngineAdapter 强制约束（可选）

### 3. 错误处理

**风险**：adapter 层错误处理不统一

**应对**：
- adapter 只做简单的异常传递
- 复杂错误处理在 service 层
- 在 CLI 层统一捕获和显示

## 迁移检查清单

- [ ] 创建 `__init__.py`，实现适配器路由
- [ ] 创建 `langchain_adapter.py`
- [ ] 创建 `dify_adapter.py`
- [ ] 预留 `langgraph_adapter.py` 结构
- [ ] 可选：创建 `base.py` 定义基类
- [ ] 更新 CLI 主循环使用适配器
- [ ] 测试引擎切换和路由
- [ ] 验证无循环导入

