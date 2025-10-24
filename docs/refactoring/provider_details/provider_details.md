# Provider Registry Refactoring

## Overview

This document outlines the refactoring of the provider registry system to separate LLM, BasicAgents, and DeepAgents configurations. The current unified approach creates unnecessary dependencies and configuration conflicts.

## Current Problems

### 1. **Unified Provider Registry Issues**
- **Single Point of Failure**: One registry manages all configurations
- **Dependency Complexity**: BasicAgents depends on LLM Manager
- **Configuration Conflicts**: LLM and Agent configurations mixed together
- **Extension Difficulty**: Adding DeepAgents requires modifying existing architecture

### 2. **Configuration Mixing Problems**
- **Base URL Conflicts**: Agents need base_url but LLM config doesn't provide it
- **Parameter Overlap**: Same parameters used differently across modules
- **Security Issues**: API keys and endpoints mixed in single configuration

## Refactoring Solution

### 1. **Provider Registry Separation**

#### Directory Structure
```
src/core/providers/
├── llm_provider_registry.py          # Pure LLM configuration
├── basicagents_provider_registry.py  # BasicAgents configuration
└── deepagents_provider_registry.py  # DeepAgents configuration
```

#### Configuration Structure
```
config/
├── llm/models/provider.json          # Pure LLM parameters
├── agents/basic/models/provider.json # BasicAgents parameters
└── agents/deep/models/provider.json  # DeepAgents parameters
```

### 2. **Configuration Separation**

#### LLM Configuration (Pure Parameters)
```json
{
  "providers": {
    "anthropic": {
      "models": {
        "claude-4.5-sonnet": {
          "temperature": 0.1,
          "max_tokens": 8000,
          "context_window": 128000,
          "supports_tools": true
        }
      }
    },
    "tongyi": {
      "models": {
        "qwen3-coder": {
          "temperature": 0.1,
          "max_tokens": 4000,
          "context_window": 32000,
          "supports_tools": true
        }
      }
    },
    "zhipu": {
      "models": {
        "glm-4.6": {
          "temperature": 0.1,
          "max_tokens": 6000,
          "context_window": 128000,
          "supports_tools": true
        }
      }
    }
  }
}
```

#### BasicAgents Configuration (Complete API Config)
```json
{
  "providers": {
    "anthropic": {
      "base_url": "https://api.anthropic.com/v1",
      "api_key_env": "ANTHROPIC_API_KEY",
      "models": {
        "claude-4.5-sonnet": {
          "agent_type": "react",
          "max_iterations": 8,
          "max_execution_time": 300,
          "temperature": 0.1,
          "max_tokens": 8000,
          "tools": ["internet_search", "calculator"]
        }
      }
    },
    "tongyi": {
      "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
      "api_key_env": "TONGYI_API_KEY",
      "models": {
        "qwen3-coder": {
          "agent_type": "function_calling",
          "max_iterations": 6,
          "max_execution_time": 180,
          "temperature": 0.2,
          "max_tokens": 4000,
          "tools": ["code_analysis", "file_edit"]
        }
      }
    }
  }
}
```

#### DeepAgents Configuration (Complete API Config)
```json
{
  "providers": {
    "anthropic": {
      "base_url": "https://api.anthropic.com/v1",
      "api_key_env": "ANTHROPIC_API_KEY",
      "models": {
        "claude-4.5-sonnet": {
          "middleware": ["filesystem", "subagents"],
          "subagents": ["research", "coding", "analysis"],
          "temperature": 0.1,
          "max_tokens": 8000,
          "security": {
            "filesystem_mode": "read_only",
            "allowed_paths": ["/workspace/", "/data/"]
          }
        }
      }
    },
    "zhipu": {
      "base_url": "https://open.bigmodel.cn/api/paas/v4",
      "api_key_env": "ZHIPU_API_KEY",
      "models": {
        "glm-4.6": {
          "middleware": ["filesystem", "subagents"],
          "subagents": ["research", "analysis"],
          "temperature": 0.1,
          "max_tokens": 6000,
          "security": {
            "filesystem_mode": "ask_before_edit",
            "allowed_paths": ["/workspace/"]
          }
        }
      }
    }
  }
}
```

## Implementation Details

### 1. **LLM Provider Registry**

```python
# src/core/providers/llm_provider_registry.py
class LLMProviderRegistry:
    def __init__(self):
        self._providers = {}
        self._load_from_config("config/llm/models/provider.json")
    
    def get_llm_config(self, provider: str, model: str) -> Dict[str, Any]:
        """Get pure LLM configuration"""
        provider_config = self._providers.get(provider.upper())
        if not provider_config:
            raise ValueError(f"Provider {provider} not found")
        
        model_config = provider_config.get("models", {}).get(model)
        if not model_config:
            raise ValueError(f"Model {model} not found in provider {provider}")
        
        return {
            "temperature": model_config.get("temperature", 0.1),
            "max_tokens": model_config.get("max_tokens", 4000),
            "context_window": model_config.get("context_window", 32000),
            "supports_tools": model_config.get("supports_tools", False)
        }
    
    def validate_llm_config(self, provider: str, model: str) -> bool:
        """Validate LLM configuration"""
        try:
            self.get_llm_config(provider, model)
            return True
        except ValueError:
            return False
```

### 2. **BasicAgents Provider Registry**

```python
# src/core/providers/basicagents_provider_registry.py
class BasicAgentsProviderRegistry:
    def __init__(self):
        self._providers = {}
        self._load_from_config("config/agents/basic/models/provider.json")
    
    def get_agent_config(self, provider: str, model: str) -> Dict[str, Any]:
        """Get complete BasicAgents configuration"""
        provider_config = self._providers.get(provider.upper())
        if not provider_config:
            raise ValueError(f"Provider {provider} not found")
        
        model_config = provider_config.get("models", {}).get(model)
        if not model_config:
            raise ValueError(f"Model {model} not found in provider {provider}")
        
        return {
            "base_url": provider_config["base_url"],
            "api_key_env": provider_config["api_key_env"],
            "agent_type": model_config.get("agent_type", "react"),
            "max_iterations": model_config.get("max_iterations", 8),
            "max_execution_time": model_config.get("max_execution_time", 300),
            "temperature": model_config.get("temperature", 0.1),
            "max_tokens": model_config.get("max_tokens", 4000),
            "tools": model_config.get("tools", [])
        }
    
    def create_llm(self, provider: str, model: str):
        """Create LLM using BasicAgents configuration"""
        config = self.get_agent_config(provider, model)
        return ChatOpenAI(
            base_url=config["base_url"],
            api_key=os.getenv(config["api_key_env"]),
            model_name=model,
            temperature=config["temperature"],
            max_tokens=config["max_tokens"]
        )
```

### 3. **DeepAgents Provider Registry**

```python
# src/core/providers/deepagents_provider_registry.py
class DeepAgentsProviderRegistry:
    def __init__(self):
        self._providers = {}
        self._load_from_config("config/agents/deep/models/provider.json")
    
    def get_deep_agent_config(self, provider: str, model: str) -> Dict[str, Any]:
        """Get complete DeepAgents configuration"""
        provider_config = self._providers.get(provider.upper())
        if not provider_config:
            raise ValueError(f"Provider {provider} not found")
        
        model_config = provider_config.get("models", {}).get(model)
        if not model_config:
            raise ValueError(f"Model {model} not found in provider {provider}")
        
        return {
            "base_url": provider_config["base_url"],
            "api_key_env": provider_config["api_key_env"],
            "middleware": model_config.get("middleware", []),
            "subagents": model_config.get("subagents", []),
            "temperature": model_config.get("temperature", 0.1),
            "max_tokens": model_config.get("max_tokens", 4000),
            "security": model_config.get("security", {})
        }
    
    def create_llm(self, provider: str, model: str):
        """Create LLM using DeepAgents configuration"""
        config = self.get_deep_agent_config(provider, model)
        return ChatOpenAI(
            base_url=config["base_url"],
            api_key=os.getenv(config["api_key_env"]),
            model_name=model,
            temperature=config["temperature"],
            max_tokens=config["max_tokens"]
        )
```

## Dependency Optimization

### 1. **Before Refactoring (Complex Dependencies)**
```
BasicAgents -> LLM Manager -> LLM Provider Registry
DeepAgents -> LLM Manager -> LLM Provider Registry
```

**Problems:**
- BasicAgents needs base_url from LLM config
- Configuration conflicts between modules
- Single point of failure

### 2. **After Refactoring (Clear Dependencies)**
```
BasicAgents -> BasicAgents Provider Registry
DeepAgents -> DeepAgents Provider Registry
LLM -> LLM Provider Registry
```

**Benefits:**
- Each module manages its own complete configuration
- No cross-module dependencies
- Clear separation of concerns

## Adapter Implementation

### 1. **BasicAgents Adapter**
```python
# src/agents/basicagents/adapters/anthropic_adapter.py
class AnthropicAdapter:
    def __init__(self, provider: str, model: str):
        self.provider_registry = BasicAgentsProviderRegistry()
        self.config = self.provider_registry.get_agent_config(provider, model)
    
    def create_llm(self):
        """Create LLM with complete BasicAgents configuration"""
        return ChatOpenAI(
            base_url=self.config["base_url"],
            api_key=os.getenv(self.config["api_key_env"]),
            model_name=self.model,
            temperature=self.config["temperature"],
            max_tokens=self.config["max_tokens"]
        )
    
    def get_agent_params(self):
        """Get agent-specific parameters"""
        return {
            "agent_type": self.config["agent_type"],
            "max_iterations": self.config["max_iterations"],
            "max_execution_time": self.config["max_execution_time"],
            "tools": self.config["tools"]
        }
```

### 2. **DeepAgents Adapter**
```python
# src/agents/deepagents/adapters/research_adapter.py
class ResearchAdapter:
    def __init__(self, provider: str, model: str):
        self.provider_registry = DeepAgentsProviderRegistry()
        self.config = self.provider_registry.get_deep_agent_config(provider, model)
    
    def create_llm(self):
        """Create LLM with complete DeepAgents configuration"""
        return ChatOpenAI(
            base_url=self.config["base_url"],
            api_key=os.getenv(self.config["api_key_env"]),
            model_name=self.model,
            temperature=self.config["temperature"],
            max_tokens=self.config["max_tokens"]
        )
    
    def get_middleware_config(self):
        """Get middleware configuration"""
        return {
            "middleware": self.config["middleware"],
            "subagents": self.config["subagents"],
            "security": self.config["security"]
        }
```

## Migration Strategy

### 1. **Phase 1: Create New Provider Registries**
- Create separate provider registry classes
- Implement configuration loading for each module
- Add validation and error handling

### 2. **Phase 2: Update Adapters**
- Update BasicAgents adapters to use BasicAgents Provider Registry
- Update DeepAgents adapters to use DeepAgents Provider Registry
- Remove dependencies on LLM Manager

### 3. **Phase 3: Configuration Migration**
- Create separate configuration files
- Migrate existing configurations
- Update configuration loading logic

### 4. **Phase 4: Testing and Validation**
- Test each module independently
- Validate configuration loading
- Ensure no cross-module dependencies

## Benefits

### 1. **Architecture Benefits**
- **Clear Separation**: Each module manages its own configuration
- **Reduced Dependencies**: No cross-module dependencies
- **Better Maintainability**: Easier to modify and extend
- **Improved Testing**: Each module can be tested independently

### 2. **Configuration Benefits**
- **Complete Configurations**: Each module has all necessary parameters
- **No Conflicts**: No parameter conflicts between modules
- **Security**: API keys and endpoints properly isolated
- **Flexibility**: Easy to add new modules or modify existing ones

### 3. **Development Benefits**
- **Faster Development**: No need to modify existing code for new features
- **Easier Debugging**: Clear separation of concerns
- **Better Documentation**: Each module has clear responsibilities
- **Simplified Testing**: Independent module testing

## Conclusion

The provider registry refactoring provides a clean, maintainable architecture that separates concerns and eliminates unnecessary dependencies. Each module manages its own complete configuration, ensuring flexibility and ease of extension while maintaining security and performance.
