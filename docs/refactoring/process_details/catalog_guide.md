# 目录服务重构指南

## 模块概述

目录服务负责提供模型和工作流的信息查询，支持：
- 按引擎分包管理目录服务
- LangChain: 模型目录（从 provider_registry 获取）
- LangGraph: 工作流目录（预留）
- Dify: 云端 agentflow（暂不实现）

**核心原则**：按引擎独立管理目录，依赖底层配置接口

## 目录结构

```
application/services/catalog/
├── __init__.py                  # 统一导出接口
│
├── langchain/                   # LangChain 目录服务
│   ├── __init__.py
│   └── catalog.py              # LangChainCatalogService
│
├── langgraph/                   # LangGraph 目录服务（预留）
│   ├── __init__.py
│   └── catalog.py              # LangGraphCatalogService
│
└── dify/                        # Dify 目录服务（暂不实现）
    ├── __init__.py
    └── catalog.py              # DifyCatalogService
```

## 依赖关系

### LangChain 目录服务依赖链

```
config/llms/providers.json
    ↓
src/core/langchain/providers/provider_registry.py
    ↓
application/services/catalog/langchain/catalog.py
    ↓
application/commands/langchain/llm_commands.py (LLMsCommand)
```

### 设计理念

- `provider_registry` - 底层配置读取（框架基础设施）
- `catalog` - 高层目录服务（应用层）
- 目录服务负责整合配置 + 动态查询（如 Ollama）

## 关键模块说明

### 1. __init__.py - 统一导出接口

**职责**：
- 提供统一的目录服务获取接口

**关键接口**：

```python
from .langchain.catalog import LangChainCatalogService
from .langgraph.catalog import LangGraphCatalogService
from .dify.catalog import DifyCatalogService

CATALOG_SERVICES = {
    "langchain": LangChainCatalogService,
    "langgraph": LangGraphCatalogService,
    "dify": DifyCatalogService,
}

def get_catalog_service(engine: str):
    """获取指定引擎的目录服务"""
    service_class = CATALOG_SERVICES.get(engine)
    if not service_class:
        raise ValueError(f"Unknown engine: {engine}")
    return service_class()

async def get_engine_catalog(engine: str) -> dict:
    """获取指定引擎的目录（便捷函数）"""
    service = get_catalog_service(engine)
    return await service.get_catalog()
```

### 2. langchain/catalog.py - LangChain 目录服务

**职责**：
- 从 provider_registry 读取配置
- 动态查询 Ollama 本地模型
- 提供模型验证和信息查询

**关键接口**：

```python
from src.core.langchain.providers import provider_registry
from src.core.langchain.providers.utils import list_ollama_models

class LangChainCatalogService:
    """LangChain 模型目录服务"""
    
    async def get_catalog(self) -> dict:
        """获取 LangChain 模型目录
        
        Returns:
            {
                "providers": [
                    {
                        "name": "Zhipu AI",
                        "provider": "zhipu",
                        "default_model": "glm-4-plus",
                        "models": {...}
                    },
                    ...
                ],
                "recommended": [...],
                "default": {...}
            }
        """
        # 从 provider_registry 读取配置
        providers_config = provider_registry.list_providers()
        
        catalog = {
            "providers": [],
            "recommended": [],
            "default": {}
        }
        
        # 遍历所有 provider
        for provider_key, config in providers_config.items():
            provider_name = provider_key.lower()
            
            provider_info = {
                "name": config.get("name"),
                "provider": provider_name,
                "default_model": config.get("default_model"),
                "models": config.get("models", {})
            }
            
            # Ollama 特殊处理：动态查询本地模型
            if provider_name == "ollama":
                try:
                    local_models = await list_ollama_models()
                    provider_info["local_models"] = local_models
                    
                    if local_models:
                        provider_info["default_model"] = local_models[0]
                    else:
                        provider_info["message"] = "No local models. Run 'ollama pull <model>'"
                except Exception as e:
                    provider_info["error"] = str(e)
            
            catalog["providers"].append(provider_info)
        
        return catalog
    
    def validate_model(self, provider: str, model: str) -> dict:
        """验证模型是否可用
        
        Returns:
            {"valid": bool, "error": str, "message": str}
        """
        is_valid = provider_registry.validate_model(provider, model)
        
        if not is_valid:
            return {
                "valid": False,
                "error": f"Model {model} not found in provider {provider}",
                "message": "Please check available models with /llms"
            }
        
        return {"valid": True}
    
    def get_model_info(self, provider: str, model: str = None) -> dict:
        """获取模型详细信息
        
        Returns:
            {
                "provider": "zhipu",
                "model": "glm-4-plus",
                "name": "GLM-4-Plus",
                "description": "...",
                "supports_tools": True,
                "mode_defaults": {...}
            }
        """
        return provider_registry.get_model_info(provider, model)
    
    def reload_config(self) -> bool:
        """重载配置"""
        return provider_registry.reload_config()
```

**迁移映射**：
- `components/process/registry.py` → `catalog/langchain/catalog.py`
  - 保留：`get_catalog()` 逻辑
  - 依赖：`provider_registry` 替代直接读取 JSON
  - 增强：Ollama 动态查询

### 3. langgraph/catalog.py - LangGraph 目录服务（预留）

**职责**：
- 提供 Graph 工作流目录
- 列出可用的 Graph 模板
- 显示 Graph 节点信息

**预留接口**：

```python
class LangGraphCatalogService:
    """LangGraph 工作流目录服务（预留）"""
    
    async def get_catalog(self) -> dict:
        """获取 LangGraph 工作流目录
        
        未来实现：
        - 读取 Graph 配置文件
        - 列出可用的 Graph 模板
        - 显示每个 Graph 的节点信息
        
        Returns:
            {
                "graphs": [
                    {
                        "name": "deep_agent",
                        "description": "Deep reasoning agent",
                        "nodes": ["planner", "executor", "reviewer"],
                        "supported_providers": ["openai", "zhipu"]
                    },
                    ...
                ],
                "default": "deep_agent"
            }
        """
        # 未来实现：可能依赖 src/core/langgraph/graphs/graph_registry.py
        return {
            "graphs": [],
            "default": None,
            "message": "LangGraph catalog not implemented yet"
        }
    
    def validate_graph(self, graph_name: str) -> bool:
        """验证 Graph 是否存在"""
        # 未来实现
        return False
    
    def get_graph_info(self, graph_name: str) -> dict:
        """获取 Graph 详细信息"""
        # 未来实现
        return {}
```

**未来实现建议**：
```python
# 可能的依赖结构（参考 LangChain）

# 1. 创建底层配置读取
src/core/langgraph/graphs/
├── graph_registry.py      # 类似 provider_registry
└── graph_loader.py        # 从配置加载 Graph 定义

# 2. 配置文件
config/graphs/
├── graphs.json            # Graph 配置
└── templates/             # Graph 模板定义
    ├── deep_agent.json
    └── writer_agent.json

# 3. 在 catalog 层调用
from src.core.langgraph.graphs import graph_registry

async def get_catalog(self):
    graphs = graph_registry.list_graphs()
    # ...
```

### 4. dify/catalog.py - Dify 目录服务（暂不实现）

**说明**：
- Dify agentflow 由云端 API key 决定
- 无法本地列举
- 多 agentflow 支持后续考虑

**预留接口**：

```python
class DifyCatalogService:
    """Dify 目录服务（暂不实现）"""
    
    async def get_catalog(self) -> dict:
        """获取 Dify agentflow 目录
        
        说明：
        - Dify agentflow 由不同的 API key 决定
        - 在云端管理，无法本地列举
        - 后续考虑支持多 agentflow 配置
        
        Returns:
            {
                "message": "Dify uses cloud agentflow, no local catalog",
                "current_agentflow": "...",
                "api_key": "app-xxx..."
            }
        """
        return {
            "message": "Dify uses cloud agentflow",
            "note": "Multi-agentflow support to be considered in future"
        }
```

## 使用示例

### 在 LLMsCommand 中使用

```python
# application/commands/langchain/llm_commands.py

from ...services.catalog import get_catalog_service

class LLMsCommand(BaseCommand):
    """显示 LangChain 模型目录"""
    
    async def execute(self, ctx, args):
        # 获取 LangChain 目录服务
        catalog_service = get_catalog_service("langchain")
        catalog = await catalog_service.get_catalog()
        
        # 渲染
        from ...cli.gui.render import render_llms_catalog
        render_llms_catalog(ctx.console, catalog)
        
        return CommandResult(type="success", message="", payload={})
```

### 在 ModelCommand 中验证模型

```python
# application/commands/langchain/model_commands.py

from ...services.catalog import get_catalog_service

class LangChainModelCommand(BaseCommand):
    
    async def execute(self, ctx, args):
        provider, model = parse_args(args)
        
        # 验证模型
        catalog_service = get_catalog_service("langchain")
        validation = catalog_service.validate_model(provider, model)
        
        if not validation["valid"]:
            return CommandResult(
                type="error",
                message=validation["error"],
                payload={}
            )
        
        # 切换模型
        # ...
```

### 在 ReloadCommand 中重载配置

```python
# application/commands/langchain/llm_commands.py

class ReloadCommand(BaseCommand):
    
    async def execute(self, ctx, args):
        catalog_service = get_catalog_service("langchain")
        success = catalog_service.reload_config()
        
        if success:
            # 清理 agent_manager 缓存
            from src.agents.langchain.factories.registry import get_global_registry
            registry = get_global_registry()
            registry.clear_cache()
            
            return CommandResult(
                type="success",
                message="Config reloaded successfully",
                payload={}
            )
        else:
            return CommandResult(
                type="error",
                message="Failed to reload config",
                payload={}
            )
```

## 与底层 provider_registry 的关系

### 职责划分

**provider_registry（底层）**：
- 读取 JSON 配置
- 提供基础查询接口
- 验证模型配置
- 位置：`src/core/langchain/providers/provider_registry.py`

**catalog（应用层）**：
- 整合配置数据
- 动态查询（Ollama）
- 提供应用级接口
- 位置：`application/services/catalog/langchain/catalog.py`

### 调用示例

```python
# catalog 调用 provider_registry

from src.core.langchain.providers import provider_registry

# 1. 获取配置
providers_config = provider_registry.list_providers()

# 2. 获取模型信息
model_info = provider_registry.get_model_info("zhipu", "glm-4-plus")

# 3. 验证模型
is_valid = provider_registry.validate_model("openai", "gpt-4o")

# 4. 重载配置
success = provider_registry.reload_config()
```

## 风险点

### 1. 配置同步

**风险**：provider_registry 配置更新后，catalog 缓存未刷新

**应对**：
- catalog 不缓存数据，每次从 provider_registry 读取
- reload_config() 直接调用 provider_registry.reload_config()

### 2. Ollama 查询失败

**风险**：Ollama 服务未启动，导致目录查询失败

**应对**：
- 捕获异常，返回错误信息
- 不影响其他 provider 的显示

### 3. 循环导入

**风险**：catalog 和 commands 相互导入

**应对**：
- catalog 不导入 commands
- commands 导入 catalog（单向依赖）

## 迁移检查清单

- [ ] 创建 `catalog/__init__.py`，实现统一接口
- [ ] 创建 `catalog/langchain/catalog.py`
  - [ ] 实现 `get_catalog()`
  - [ ] 依赖 `provider_registry`
  - [ ] 支持 Ollama 动态查询
  - [ ] 实现模型验证
  - [ ] 实现配置重载
- [ ] 预留 `catalog/langgraph/catalog.py` 结构
- [ ] 预留 `catalog/dify/catalog.py` 结构
- [ ] 更新 LLMsCommand 使用 catalog 服务
- [ ] 更新 ModelCommand 使用 catalog 验证
- [ ] 更新 ReloadCommand 使用 catalog 重载
- [ ] 删除旧的 `components/process/registry.py`
- [ ] 测试目录查询和模型验证

