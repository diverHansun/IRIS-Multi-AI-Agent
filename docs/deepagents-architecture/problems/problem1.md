# Problem Report: Deep Agent Initialization and Configuration Issues

## Issue Summary

Four critical bugs were identified in the deep agent mode implementation that prevent proper initialization and runtime execution:

1. API authentication failures (401 errors) during LLM invocation
2. Missing provider/model information in `/info` command output
3. Tool count shows 0 in `/info` command before agent initialization
4. Incorrect architecture for SubAgent instantiation

## Problem Details

### Problem 1: API Key Not Passed to LLM Runtime

**Location**: `src/components/deepagents/runtime.py:48-49`

**Symptom**:
```
Deep Agent Error: Deep agent execution failed: Error code: 401 -
{'error': {'code': '401', 'message': 'Token expired or verification failed'}}
```

**Root Cause**:

When `init_chat_model()` is called in the runtime builder, the API key is not explicitly passed even though it exists in the environment:

```python
# Current implementation (BROKEN)
if isinstance(model, str) and model_settings:
    model = init_chat_model(model, **model_settings)
```

The `model_settings` dict only contains parameters from `adapter.get_model_parameters()` which excludes `api_key_env`. While environment variables are loaded correctly via `src.config.env_loader`, the LangChain OpenAI-compatible wrapper for ZhipuAI requires explicit API key parameter.

**Evidence**:
- `.env` file loads successfully with UTF-16 encoding
- Environment variable `ZHIPU_API_KEY` is accessible when importing `src.config`
- The adapter has `api_key_env` property but doesn't extract the actual key value
- `init_chat_model()` receives no `api_key` in `model_settings`

**Solution**:

Modify `BaseDeepAgentFactory.create_agent()` in `src/agents/deepagents/factories/base.py:64-66`:

```python
model_settings = adapter.get_model_parameters()
if adapter.base_url:
    model_settings["base_url"] = adapter.base_url

# Add API key extraction
if adapter.api_key_env:
    import os
    api_key = os.getenv(adapter.api_key_env)
    if api_key:
        model_settings["api_key"] = api_key
```

---

### Problem 2: `/info` Command Shows Unknown Provider/Model

**Location**: `src/application/commands/agent/mode_commands.py:25-28`

**Symptom**:
```
After executing /mode deep:
- Provider: unknown
- Model: unknown
- Function: research
- Tool Count: 0
```

**Root Cause**:

The `/mode deep` command does not load default configuration from `providers.json`:

```python
# Current implementation (INCOMPLETE)
config["agent_type"] = target
config["agent_instance"] = None
if target == "deep":
    config.setdefault("function_type", "research")
    # Missing: No default provider/model assignment
```

When `DeepAgentService.get_info()` is called before the first query, `agent_instance` is `None`, resulting in empty metadata.

**Solution**:

Enhance `ModeCommand.execute()` to initialize default configuration:

```python
if target == "deep":
    from src.core.providers import deepagents_provider_registry
    config.setdefault("function_type", "research")

    # Load default provider and model from providers.json
    providers = deepagents_provider_registry.list_providers()
    if "ZHIPU" in providers:
        models = providers["ZHIPU"].get("models", {})
        if "glm-4.6" in models:
            config.setdefault("provider", "ZHIPU")
            config.setdefault("model", "glm-4.6")
```

---

### Problem 3: Tool Count Shows Zero Before Agent Initialization

**Location**: `src/application/services/agent/deep/service.py:115-129`

**Symptom**:
```
After executing /mode deep and /info:
- Tool Count: 0
```

**Root Cause**:

The `get_info()` method in `DeepAgentService` returns agent information before the agent instance is created:

```python
def get_info(self, ctx) -> Dict[str, Any]:
    config = self._config(ctx)
    agent = config.get("agent_instance")
    agent_info = agent.get_info() if agent and hasattr(agent, "get_info") else {}
    # If agent_instance is None, agent_info is empty dict
    return {
        "agent": agent_info,  # Empty when agent not yet created
        "mode": {...}
    }
```

When the user runs `/mode deep` followed by `/info`, the agent instance hasn't been created yet (it's only created on the first query). The `agent_info` dict is empty, which means `tool_count` and `tools` metadata are missing.

**Related Code Flow**:

1. `/mode deep` sets `config["agent_instance"] = None`
2. User runs `/info` immediately
3. `DeepAgentService.get_info()` tries to call `agent.get_info()` on `None`
4. Returns empty `agent_info`, showing Tool Count: 0

**Solution**:

Modify `DeepAgentService.get_info()` to return configuration-based metadata when agent is not yet initialized:

```python
def get_info(self, ctx) -> Dict[str, Any]:
    config = self._config(ctx)
    agent = config.get("agent_instance")

    if agent and hasattr(agent, "get_info"):
        agent_info = agent.get_info()
    else:
        # Agent not yet created, return config-based metadata
        from src.core.providers import deepagents_provider_registry
        agent_info = {
            "provider": config.get("provider", "unknown"),
            "model": config.get("model", "unknown"),
            "function_type": config.get("function_type", "research"),
            "tool_count": 0,
            "tools": [],
            "status": "not_initialized"
        }

    return {
        "agent": agent_info,
        "mode": {
            "mode": "agent",
            "agent_type": "deep",
            "streaming": False,
            "middleware": agent_info.get("middleware"),
            "function_type": config.get("function_type"),
            "session_id": ctx.session_id,
        },
    }
```

Alternatively, trigger agent creation immediately when switching to deep mode in `DeepAgentService.initialize()`.

---

### Problem 4: SubAgent Uses Incompatible BasicAgent Manager

**Location**: `src/agents/deepagents/managers/subagent_manager.py:48-56`

**Symptom**:

SubAgents are created using `basicagents.agent_manager.create_agent()`, which expects a different configuration schema than what deep agents provide.

**Root Cause**:

Configuration format mismatch between BasicAgents and DeepAgents:

**BasicAgents config** (`config/agents/basic/models/providers.json`):
```json
{
  "providers": {
    "ZHIPU": {
      "models": {
        "glm-4.5-flash": {
          "agent_type": "function_calling",    // BasicAgent-specific
          "max_iterations": 15,                 // BasicAgent-specific
          "memory_enabled": true                // BasicAgent-specific
        }
      }
    }
  }
}
```

**DeepAgents subagent config** (`config/agents/deep/models/subagents.json`):
```json
{
  "research": {
    "providers": {
      "ZHIPU": {
        "models": {
          "glm-4.6": {
            "temperature": 0.6,
            "supports_tools": true              // No agent_type or max_iterations
          }
        }
      }
    }
  }
}
```

The BasicAgent manager expects fields like `agent_type`, `max_iterations`, and `memory_enabled` which are not present in deep agent subagent configurations.

**Current problematic code**:
```python
from src.agents.basicagents.managers import agent_manager

agent = await agent_manager.create_agent(
    provider=provider,
    model=model,
    agent_type=agent_type,  // May be missing from deep config
    **params,
)
```

**Solution**:

Based on LangChain's official deep agent implementation (see `deepagents/examples/research/research_agent.py` and `deepagents/src/deepagents/middleware/subagents.py`), SubAgents should NOT use BasicAgent manager.

**LangChain Official Pattern**:

SubAgents are created using `langchain.agents.create_agent()` directly in the SubAgentMiddleware:

```python
# From deepagents/src/deepagents/middleware/subagents.py:271-277
agents[agent_["name"]] = create_agent(
    subagent_model,
    system_prompt=agent_["system_prompt"],
    tools=_tools,
    middleware=_middleware,
    checkpointer=False,
)
```

**Recommended Approach**:

1. Refactor `SubAgentManager.create_subagent()` to use `langchain.agents.create_agent()` directly
2. Remove dependency on `basicagents.agent_manager`
3. Use the SubAgent specification format from LangChain:

```python
# Example from official LangChain deepagents
research_sub_agent = {
    "name": "research-agent",
    "description": "Used to research in-depth questions",
    "system_prompt": "You are a dedicated researcher...",
    "tools": [internet_search],
    "model": "openai:glm-4.6",  # Optional, uses default if not specified
}
```

4. Update `config/agents/deep/models/subagents.json` to align with this format or transform it during loading

This ensures SubAgents are lightweight, stateless LangChain agents without BasicAgent's complex lifecycle management.

---

## Impact Assessment

| Problem | Severity | Impact |
|---------|----------|--------|
| API Key Not Passed | Critical | Deep mode completely non-functional - all LLM calls fail with 401 |
| Unknown Provider/Model | High | Poor user experience - cannot verify configuration before execution |
| Tool Count Shows Zero | Medium | Misleading information display - users cannot see what tools are available |
| SubAgent Manager Mismatch | Medium | Potential runtime errors when subagents are invoked, inconsistent behavior |

## Recommended Fix Priority

1. **Immediate**: Fix API key passing (Problem 1)
2. **High**: Fix `/mode deep` default config (Problem 2)
3. **Medium**: Fix `/info` to show config-based metadata when agent not initialized (Problem 3)
4. **Medium**: Refactor SubAgent instantiation to use LangChain's create_agent (Problem 4)

## Architecture Implications

### Current Misalignment

```
SubAgentManager (DeepAgents)
    --> basicagents.agent_manager.create_agent()
        --> Expects BasicAgent config schema
            --> INCOMPATIBLE with DeepAgent subagent config
```

### Proposed Alignment (LangChain Official Pattern)

```
SubAgentManager (DeepAgents)
    --> langchain.agents.create_agent()
        --> Uses SubAgent dict spec (name, description, system_prompt, tools, model)
            --> Creates lightweight stateless LangChain agent
```

This aligns with LangChain's official deep agent implementation where:
- SubAgents are created via `create_agent()` directly
- SubAgent specs are simple dicts (not complex BasicAgent configs)
- Middleware is applied during creation (no post-creation lifecycle)
- No checkpointer or state management (stateless execution)

**Reference**: `deepagents/src/deepagents/middleware/subagents.py:254-277`

---

## Testing Checklist

After implementing fixes:

- [ ] Deep agent can execute queries without 401 errors
- [ ] `/info` command displays correct provider/model after `/mode deep`
- [ ] `/info` shows tool count > 0 when tools are configured
- [ ] SubAgents can be invoked without config schema errors
- [ ] API keys from `.env` (UTF-16 encoded) are correctly read
- [ ] Default configuration loads from `providers.json` on mode switch

---

**Document Version**: 1.1
**Date**: 2025-01-24
**Last Updated**: 2025-01-24
**Status**: Active Issue

**Related Files**:
- `src/components/deepagents/runtime.py`
- `src/agents/deepagents/factories/base.py`
- `src/application/commands/agent/mode_commands.py`
- `src/application/services/agent/deep/service.py`
- `src/agents/deepagents/managers/subagent_manager.py`
- `config/agents/deep/models/providers.json`
- `config/agents/deep/models/subagents.json`

**Reference Implementations**:
- `deepagents/examples/research/research_agent.py` - LangChain official deep agent example
- `deepagents/src/deepagents/middleware/subagents.py` - SubAgent creation pattern
- `deepagents/src/deepagents/graph.py` - Deep agent runtime builder
