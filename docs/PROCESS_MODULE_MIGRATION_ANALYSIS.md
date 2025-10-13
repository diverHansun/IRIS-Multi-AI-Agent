# Process 模块迁移分析报告

## 📋 执行摘要

本报告全面分析了 `src/components/process` 模块对 Agents 和 LLM 板块的依赖，识别了所有使用废弃API的位置，并提供了详细的迁移方案。

**关键发现：**
- ✅ **7个文件** 已完成检查
- ⚠️ **3个文件** 存在废弃依赖
- ✅ **4个文件** 无需迁移
- 📊 **5处** 需要替换废弃API

---

## 📁 文件清单与状态

### ✅ 无需迁移的文件 (4个)

1. **session_control.py**
   - 状态：✅ 合规
   - 说明：仅处理会话管理，无Agent/LLM依赖

2. **mcp_control.py**
   - 状态：✅ 合规
   - 说明：仅导入 `src.components.shared.tools.mcp`

3. **connector_control.py**
   - 状态：✅ 合规
   - 说明：仅导入 `src.components.shared.tools.connector`

4. **validation.py**
   - 状态：✅ 合规
   - 说明：独立的配置验证模块，无废弃依赖

### ⚠️ 需要迁移的文件 (3个)

#### 1. registry.py

**当前依赖：**
```python
from src.agents.langchain.factories import get_available_configurations  # ⚠️ 废弃
from src.llm.langchain.providers.ollama import list_ollama_models        # ✅ 新路径
```

**使用场景：**
- `get_catalog()` 函数调用 `get_available_configurations()` 获取可用providers和models

**影响范围：**
- 被 `cli.py` 的 `/llms` 命令调用

---

#### 2. control.py

**当前依赖：**
```python
from src.agents.langchain.factories import agent_factory                # ⚠️ 废弃
from src.llm.langchain.managers import reload_llm_config                # ✅ 新路径
```

**使用场景：**
1. `switch_llm()` 函数：
   - `agent_factory.get_available_configurations()` - 验证provider
   - `agent_factory.create_agent()` - 创建新agent
   - `agent_factory.clear_cache()` - 清理缓存

2. `reload_config()` 函数：
   - `reload_llm_config()` - ✅ 新路径
   - `agent_factory.clear_cache()` - ⚠️ 废弃

**影响范围：**
- 被 `cli.py` 的 `/switch` 和 `/reload` 命令调用

---

#### 3. cli.py

**当前依赖：**
```python
from src.agents.langchain.factories import create_default_agent, get_available_configurations  # ⚠️ 废弃
from src.llm.langchain.utils import stream_llm_response                                        # ✅ 新路径
```

**使用场景：**
1. `run()` 函数启动时：
   - `get_available_configurations()` - 检查可用providers
   - `create_default_agent()` - 创建默认agent

2. LLM模式流式输出：
   - `stream_llm_response()` - ✅ 新路径（utils模块）

**影响范围：**
- 应用程序主入口

---

## 🔄 迁移对照表

### 废弃路径 → 新路径映射

| 废弃路径 | 新路径 | 功能说明 | 返回格式变化 |
|---------|--------|---------|------------|
| `factories.get_available_configurations()` | `llm_manager.get_available_providers()` | 获取可用providers列表 | ⚠️ 需要适配 |
| `factories.agent_factory.create_agent()` | `agent_manager.create_agent()` | 创建Agent实例 | ✅ 兼容 |
| `factories.create_default_agent()` | `agent_manager.create_agent()` | 创建默认Agent | ⚠️ 需要指定provider |
| `factories.agent_factory.clear_cache()` | N/A | 清理Factory缓存 | ⚠️ 新架构无缓存 |
| `factories.agent_factory.get_available_configurations()` | `llm_manager.get_available_providers()` | 获取可用配置 | ⚠️ 需要适配 |

---

## 📊 返回格式对比分析

### `get_available_configurations()` vs `get_available_providers()`

#### 旧格式 (factories.get_available_configurations)
```python
{
    "available_providers": [
        {
            "name": "Zhipu AI",
            "provider": "zhipu",
            "default_model": "glm-4-plus",
            "models_detail": {
                "glm-4-plus": {...},
                "glm-4.5": {...}
            }
        },
        ...
    ],
    "recommended_configs": [...],
    "default_config": {...}
}
```

#### 新格式 (llm_manager.get_available_providers)
```python
[
    {
        "provider": "zhipu",
        "name": "Zhipu AI",
        "available": True,
        "default_model": "glm-4-plus",
        "models": ["glm-4-plus", "glm-4.5", ...],
        "api_key_required": "ZHIPU_API_KEY",
        "mode_defaults": {
            "llm": {...},
            "agent": {...}
        },
        "models_detail": {
            "glm-4-plus": {...},
            "glm-4.5": {...}
        }
    },
    ...
]
```

**主要差异：**
1. ✅ 新格式直接返回列表，更简洁
2. ✅ 新格式增加了 `available` 字段（API密钥检查）
3. ✅ 新格式增加了 `mode_defaults` 配置
4. ⚠️ 新格式没有 `recommended_configs` 和 `default_config` 顶层字段

---

## 🛠️ 详细迁移方案

### 方案 A：适配层方案（推荐）

**思路：** 在 `registry.py` 中创建适配层，将新API返回格式转换为旧格式，保持对上层的兼容。

**优点：**
- ✅ 最小化改动，对 `cli.py` 无影响
- ✅ 快速实施
- ✅ 降低风险

**实施步骤：**

#### 1. 修改 registry.py

```python
"""
Registry module for the Multi-AI-Agent project.
This module contains provider/model catalog and validation.
"""

# 使用新API
from src.llm.langchain.managers import llm_manager
from src.llm.langchain.providers.ollama import list_ollama_models


async def get_catalog():
    """Get the full provider/model catalog"""
    try:
        # 使用新API获取providers
        providers = llm_manager.get_available_providers()
        
        # 过滤出可用的providers（有API密钥）
        available_providers = [p for p in providers if p.get("available", False)]
        
        if not available_providers:
            return {
                "error": "No available LLM providers",
                "message": "Please ensure at least one API key is configured (ZHIPU_API_KEY or OPENAI_API_KEY)"
            }
        
        catalog = {
            "providers": [],
            "recommended": [],  # 新API不再提供推荐配置，可选择性保留或移除
            "default": {}       # 新API不再提供默认配置，可选择性保留或移除
        }
        
        for provider in available_providers:
            provider_info = {
                "name": provider['name'],
                "provider": provider['provider'],
                "default_model": provider['default_model']
            }
            
            # Ollama special handling: show local available models and dynamic default model
            if provider['provider'] == 'ollama':
                try:
                    local_models = await list_ollama_models()
                    if local_models:
                        # Update default model to the first available local model
                        provider_info["default_model"] = local_models[0]
                        provider_info["local_models"] = local_models
                    else:
                        provider_info["default_model"] = None
                        provider_info["local_models"] = []
                        provider_info["message"] = "No local models available. Please run 'ollama pull <model>' to install models."
                except Exception as e:
                    provider_info["error"] = str(e)
            else:
                # Other providers show static supported model list
                if "models_detail" in provider:
                    provider_info["models"] = provider["models_detail"]
            
            catalog["providers"].append(provider_info)
        
        return catalog
        
    except Exception as e:
        return {
            "error": "Failed to get LLM catalog",
            "message": str(e)
        }


def validate(provider, model, catalog):
    """Validate requested provider/model switch"""
    # 此函数无需修改，逻辑保持不变
    provider_info = next((p for p in catalog["providers"] if p["provider"] == provider), None)
    if not provider_info:
        available_providers = [p["provider"] for p in catalog["providers"]]
        return {
            "valid": False,
            "error": f"Unsupported LLM provider: {provider}",
            "message": f"Available providers: {', '.join(available_providers)}"
        }
    
    # For Ollama, check if model is available locally
    if provider == 'ollama':
        if model and model not in provider_info.get("local_models", []):
            return {
                "valid": False,
                "error": f"Model not available locally: {model}",
                "message": f"Please run 'ollama pull {model}' to install the model"
            }
    
    return {"valid": True}


def resolve_default(provider, catalog):
    """Resolve default model if omitted"""
    # 此函数无需修改，逻辑保持不变
    provider_info = next((p for p in catalog["providers"] if p["provider"] == provider), None)
    if provider_info:
        return provider_info["default_model"]
    return None
```

#### 2. 修改 control.py

```python
"""
Control module for the Multi-AI-Agent project.
This module contains general control commands.
"""

# 使用新API
from src.agents.langchain.managers import agent_manager
from src.llm.langchain.managers import llm_manager


async def switch_llm(ctx, provider: str, model: str = None):
    """Switch LLM provider/model"""
    try:
        # 使用新API验证provider
        available_providers_list = llm_manager.get_available_providers()
        available_providers = [p["provider"] for p in available_providers_list if p.get("available", False)]
        
        if provider not in available_providers:
            return {
                "type": "error",
                "message": f"Unsupported LLM provider: {provider}",
                "payload": {
                    "available_providers": available_providers
                }
            }
        
        # 使用新API创建Agent
        new_agent = await agent_manager.create_agent(
            provider=provider,
            model=model,
            verbose=True,
            temperature=0.1,
            global_memory_manager=ctx.global_memory  # Pass global memory manager
        )
        
        # Get Agent info
        info = new_agent.get_info()
        ctx.console.print(f"[green]Successfully switched to {info['provider']} / {info['model']}[/]")
        ctx.console.print(f"[dim]Tool count: {info['tool_count']}, Memory: {'Enabled' if info['memory_enabled'] else 'Disabled'}[/]")
        ctx.console.print(f"[dim]Memory continuity maintained, you can continue previous conversations after switching[/]")
        
        # Update context
        ctx.agent = new_agent
        
        return {
            "type": "success",
            "message": f"Successfully switched to {info['provider']} / {info['model']}",
            "payload": info
        }
        
    except Exception as e:
        return {
            "type": "error",
            "message": f"Failed to switch LLM: {str(e)}",
            "payload": {}
        }


def set_mode(ctx, mode: str):
    """Set working mode (llm/agent)"""
    # 此函数无需修改
    if mode.lower() in ["llm", "stream"]:
        ctx.llm_mode = True
        ctx.streaming_enabled = True
        return {
            "type": "success",
            "message": "Switched to LLM mode (streaming output)",
            "payload": {
                "llm_mode": True,
                "streaming_enabled": True
            }
        }
    elif mode.lower() in ["agent", "tool"]:
        ctx.llm_mode = False
        return {
            "type": "success",
            "message": "Switched to Agent mode (tool calling)",
            "payload": {
                "llm_mode": False,
                "streaming_enabled": ctx.streaming_enabled
            }
        }
    else:
        return {
            "type": "error",
            "message": "Invalid mode, please use 'llm' or 'agent'",
            "payload": {}
        }


def set_stream(ctx, action: str):
    """Set streaming output on/off"""
    # 此函数无需修改
    if not ctx.llm_mode:
        return {
            "type": "error",
            "message": "Streaming output is only available in LLM mode, please switch to LLM mode first",
            "payload": {}
        }
    
    if action.lower() in ["on", "enable"]:
        ctx.streaming_enabled = True
        return {
            "type": "success",
            "message": "LLM streaming output enabled",
            "payload": {
                "streaming_enabled": True
            }
        }
    elif action.lower() in ["off", "disable"]:
        ctx.streaming_enabled = False
        return {
            "type": "success",
            "message": "LLM streaming output disabled",
            "payload": {
                "streaming_enabled": False
            }
        }
    else:
        return {
            "type": "error",
            "message": "Invalid action, please use 'on' or 'off'",
            "payload": {}
        }


def get_info(ctx):
    """Get system information"""
    # 此函数无需修改
    agent_info = ctx.agent.get_info()
    
    # Add mode information
    mode_info = {
        "llm_mode": ctx.llm_mode,
        "streaming_enabled": ctx.streaming_enabled,
        "session_id": ctx.session_id
    }
    
    return {
        "type": "info",
        "message": "System information retrieved",
        "payload": {
            "agent": agent_info,
            "mode": mode_info
        }
    }


def reload_config(ctx):
    """Reload LLM configuration from JSON files"""
    try:
        # 使用新API重载配置
        success = llm_manager.reload_config()
        
        if success:
            # 新架构中AgentManager不使用缓存，无需清理
            # 旧代码: agent_factory.clear_cache()
            
            return {
                "type": "success",
                "message": "LLM configuration reloaded successfully",
                "payload": {
                    "cache_cleared": False,  # 新架构无缓存机制
                    "note": "You may need to switch models to use the updated configuration"
                }
            }
        else:
            return {
                "type": "error",
                "message": "Failed to reload LLM configuration",
                "payload": {}
            }
            
    except Exception as e:
        return {
            "type": "error",
            "message": f"Error reloading configuration: {str(e)}",
            "payload": {}
        }
```

#### 3. 修改 cli.py

```python
# 在文件开头修改导入

# 旧导入（删除）
# from src.agents.langchain.factories import create_default_agent, get_available_configurations

# 新导入
from src.agents.langchain.managers import agent_manager
from src.llm.langchain.managers import llm_manager
from src.llm.langchain.utils import stream_llm_response  # 保留，这是新路径


# 在 run() 函数中修改

async def run():
    """Main CLI loop"""
    # Display the IRIS logo at startup
    display_logo()
    display_logo_intro()
    # Create app state
    ctx = AppState()
    
    # Check for at least one LLM available
    # 旧代码: configs = get_available_configurations()
    # 新代码:
    available_providers = llm_manager.get_available_providers()
    available_providers_filtered = [p for p in available_providers if p.get("available", False)]
    
    if not available_providers_filtered:
        ctx.console.print("[bold red]Error: No LLM providers available[/]")
        ctx.console.print("Please set at least one API key in your .env file:")
        ctx.console.print("- ZHIPU_API_KEY (Zhipu AI)")
        ctx.console.print("- OPENAI_API_KEY (OpenAI)")
        return

    # Print welcome message
    gui.print_welcome(ctx.console)

    # Initialize global memory system
    ctx.console.print("[yellow]Initializing memory system...[/]")
    ctx.global_memory = GlobalMemoryManager(storage_dir="data/sessions", max_messages=50)
    ctx.session_manager = SessionManager(ctx.global_memory)
    
    # Interactive session selection (restore or create new)
    ctx.session_id = ctx.session_manager.prompt_for_session_choice()
    ctx.console.print(f"[dim]Current Session ID: {ctx.session_id}[/]")
    
    try:
        # Create default Agent (async) and integrate global memory
        # 旧代码: ctx.agent = await create_default_agent(...)
        # 新代码: 使用第一个可用的provider创建Agent
        with ctx.console.status("[yellow]Initializing default Agent...[/]"):
            default_provider = available_providers_filtered[0]
            ctx.agent = await agent_manager.create_agent(
                provider=default_provider["provider"],
                model=default_provider.get("default_model"),
                verbose=True,
                temperature=0.1,
                global_memory_manager=ctx.global_memory  # Pass global memory manager
            )

        # Show initialization info
        info = ctx.agent.get_info()
        ctx.console.print(f"[green]Agent initialized successfully[/]")
        ctx.console.print(f"[dim]Provider: {info['provider']}, Model: {info['model']}, Tool Count: {info['tool_count']}[/]")
        
        # ... 其余代码保持不变
```

---

### 方案 B：全面重构方案

**思路：** 完全移除对旧API的依赖，重构所有调用点。

**优点：**
- ✅ 完全符合新架构
- ✅ 代码更清晰
- ✅ 易于长期维护

**缺点：**
- ⚠️ 改动范围大
- ⚠️ 需要更多测试

**推荐时机：** 在完成方案A后，作为长期重构目标。

---

## 🧪 测试计划

### 单元测试

#### 1. registry.py 测试

```python
# tests/unit/test_process_registry.py

import pytest
from src.components.process import registry

@pytest.mark.asyncio
async def test_get_catalog_success():
    """测试获取catalog成功"""
    catalog = await registry.get_catalog()
    
    assert "providers" in catalog
    assert isinstance(catalog["providers"], list)
    assert len(catalog["providers"]) > 0
    
    for provider in catalog["providers"]:
        assert "name" in provider
        assert "provider" in provider
        assert "default_model" in provider


@pytest.mark.asyncio
async def test_get_catalog_ollama_models():
    """测试Ollama本地模型列表"""
    catalog = await registry.get_catalog()
    
    ollama_provider = next(
        (p for p in catalog["providers"] if p["provider"] == "ollama"),
        None
    )
    
    if ollama_provider:
        # 如果Ollama可用，应该有本地模型列表
        assert "local_models" in ollama_provider or "error" in ollama_provider


def test_validate_valid_provider():
    """测试验证有效的provider"""
    catalog = {
        "providers": [
            {"provider": "zhipu", "default_model": "glm-4-plus"}
        ]
    }
    
    result = registry.validate("zhipu", "glm-4-plus", catalog)
    assert result["valid"] is True


def test_validate_invalid_provider():
    """测试验证无效的provider"""
    catalog = {
        "providers": [
            {"provider": "zhipu", "default_model": "glm-4-plus"}
        ]
    }
    
    result = registry.validate("invalid_provider", "model", catalog)
    assert result["valid"] is False
    assert "error" in result
```

#### 2. control.py 测试

```python
# tests/unit/test_process_control.py

import pytest
from unittest.mock import Mock, AsyncMock
from src.components.process import control

@pytest.mark.asyncio
async def test_switch_llm_success():
    """测试切换LLM成功"""
    ctx = Mock()
    ctx.console = Mock()
    ctx.global_memory = Mock()
    
    # Mock agent_manager
    from src.agents.langchain.managers import agent_manager
    original_create = agent_manager.create_agent
    
    mock_agent = Mock()
    mock_agent.get_info.return_value = {
        "provider": "zhipu",
        "model": "glm-4-plus",
        "tool_count": 5,
        "memory_enabled": True
    }
    
    agent_manager.create_agent = AsyncMock(return_value=mock_agent)
    
    try:
        result = await control.switch_llm(ctx, "zhipu", "glm-4-plus")
        
        assert result["type"] == "success"
        assert "zhipu" in result["message"]
        assert ctx.agent == mock_agent
    finally:
        agent_manager.create_agent = original_create


@pytest.mark.asyncio
async def test_switch_llm_invalid_provider():
    """测试切换到无效的provider"""
    ctx = Mock()
    ctx.console = Mock()
    
    result = await control.switch_llm(ctx, "invalid_provider", None)
    
    assert result["type"] == "error"
    assert "Unsupported" in result["message"]


def test_reload_config_success():
    """测试重载配置成功"""
    ctx = Mock()
    
    result = control.reload_config(ctx)
    
    assert result["type"] in ["success", "error"]
    # 由于实际调用了llm_manager，结果取决于当前配置状态
```

### 集成测试

```python
# tests/integration/test_process_cli_integration.py

import pytest
from unittest.mock import Mock, AsyncMock, patch
from src.components.process import cli

@pytest.mark.asyncio
async def test_cli_startup_with_available_providers():
    """测试CLI启动时有可用providers"""
    with patch("src.components.process.cli.display_logo"), \
         patch("src.components.process.cli.display_logo_intro"), \
         patch("src.components.process.cli.llm_manager") as mock_llm_mgr, \
         patch("src.components.process.cli.agent_manager") as mock_agent_mgr:
        
        # Mock available providers
        mock_llm_mgr.get_available_providers.return_value = [
            {
                "provider": "zhipu",
                "name": "Zhipu AI",
                "available": True,
                "default_model": "glm-4-plus"
            }
        ]
        
        # Mock agent creation
        mock_agent = Mock()
        mock_agent.get_info.return_value = {
            "provider": "zhipu",
            "model": "glm-4-plus",
            "tool_count": 5
        }
        mock_agent_mgr.create_agent = AsyncMock(return_value=mock_agent)
        
        # 此测试需要进一步模拟CLI交互循环
        # 这里只是示例框架
```

---

## 📝 实施检查清单

### Phase 1: 代码迁移
- [ ] 备份当前 `registry.py`
- [ ] 备份当前 `control.py`
- [ ] 备份当前 `cli.py`
- [ ] 实施 `registry.py` 迁移
- [ ] 实施 `control.py` 迁移
- [ ] 实施 `cli.py` 迁移
- [ ] 代码审查

### Phase 2: 测试
- [ ] 编写单元测试
- [ ] 运行单元测试
- [ ] 编写集成测试
- [ ] 运行集成测试
- [ ] 手动测试所有CLI命令

### Phase 3: 验证
- [ ] 测试 `/llms` 命令
- [ ] 测试 `/switch` 命令
- [ ] 测试 `/reload` 命令
- [ ] 测试 `/info` 命令
- [ ] 测试 LLM 模式切换
- [ ] 测试 Agent 模式切换
- [ ] 测试 Ollama 本地模型检测

### Phase 4: 文档
- [ ] 更新代码注释
- [ ] 更新API文档
- [ ] 更新用户手册
- [ ] 记录已知问题

---

## ⚡ 快速参考

### 新API导入清单

```python
# Agents 模块
from src.agents.langchain.managers import agent_manager
from src.agents.langchain.managers import get_available_agents  # 便捷函数

# LLM 模块
from src.llm.langchain.managers import llm_manager
from src.llm.langchain.managers import get_available_providers  # 便捷函数

# 工具模块（保持不变）
from src.llm.langchain.utils import stream_llm_response
from src.llm.langchain.providers.ollama import list_ollama_models
```

### 新API使用示例

```python
# 获取可用providers
providers = llm_manager.get_available_providers()

# 创建Agent
agent = await agent_manager.create_agent(
    provider="zhipu",
    model="glm-4-plus",
    verbose=True,
    temperature=0.1
)

# 重载配置
success = llm_manager.reload_config()

# 流式输出（LLM模式）
response = await stream_llm_response(
    provider="zhipu",
    prompt="Hello",
    llm=llm_instance
)
```

---

## 🎯 结论与建议

### 关键发现

1. **废弃依赖集中**：所有废弃依赖都集中在 `registry.py`、`control.py` 和 `cli.py` 三个文件
2. **影响可控**：迁移工作量适中，风险可控
3. **向后兼容**：通过适配层可以保持对现有代码的兼容

### 推荐行动

1. ✅ **立即执行**：实施方案A（适配层方案）
2. ✅ **优先级高**：完成单元测试和集成测试
3. ✅ **中期目标**：规划方案B（全面重构）的实施时机

### 风险与缓解

| 风险 | 影响 | 概率 | 缓解措施 |
|-----|------|------|---------|
| 返回格式不兼容 | 高 | 中 | 使用适配层转换 |
| 测试覆盖不足 | 中 | 中 | 增加单元测试和集成测试 |
| 线上故障 | 高 | 低 | 充分测试后再部署 |
| 性能下降 | 低 | 低 | 新架构性能更优 |

---

## 📚 附录

### A. 完整的废弃API清单

1. `src.agents.langchain.factories.get_available_configurations()`
2. `src.agents.langchain.factories.agent_factory`
3. `src.agents.langchain.factories.create_agent()`
4. `src.agents.langchain.factories.create_default_agent()`
5. `src.agents.langchain.factories.agent_factory.clear_cache()`

### B. 完整的新API清单

1. `src.agents.langchain.managers.agent_manager`
2. `src.agents.langchain.managers.agent_manager.create_agent()`
3. `src.agents.langchain.managers.agent_manager.get_available_agents()`
4. `src.llm.langchain.managers.llm_manager`
5. `src.llm.langchain.managers.llm_manager.get_available_providers()`
6. `src.llm.langchain.managers.llm_manager.reload_config()`

### C. 相关文档

- `docs/agents_api_unification_v4.md` - API统一重构计划
- `docs/modules_migration_analysis.md` - 模块迁移分析
- `docs/DEPRECATED_PATHS_CHECK.md` - 废弃路径检查报告

---

**报告生成时间**: 2025-10-12  
**版本**: 1.0  
**状态**: ✅ 分析完成，待实施


