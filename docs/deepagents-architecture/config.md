# DeepAgents Configuration

## Overview

DeepAgents configuration system extends the existing configuration architecture to support middleware settings, subagent management, and security controls. Configuration is managed through JSON files with validation and reload capabilities.

## Configuration Structure

### Directory Layout
```
config/agents/deep/
├── models/
│   ├── subagents.json          # Subagent LLM configurations
│   └── main_agent.json         # Main agent LLM configuration (optional)
└── middleware/
    ├── filesystem.json         # Filesystem middleware configuration
    └── subagents.json          # Subagent middleware configuration
```

### Configuration Files

#### Main Agent Configuration
```json
{
  "providers": {
    "anthropic": {
      "base_url": "https://api.anthropic.com/v1",
      "api_key_env": "ANTHROPIC_API_KEY",
      "models": {
        "claude-4.5-sonnet": {
          "name": "Claude 4.5 Sonnet",
          "temperature": 0.1,
          "max_tokens": 8000
        }
      }
    },
    "tongyi": {
      "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
      "api_key_env": "TONGYI_API_KEY",
      "models": {
        "qwen3-coder": {
          "name": "Qwen3 Coder",
          "temperature": 0.1,
          "max_tokens": 4000
        }
      }
    },
    "zhipu": {
      "base_url": "https://open.bigmodel.cn/api/paas/v4",
      "api_key_env": "ZHIPU_API_KEY",
      "models": {
        "glm-4.6": {
          "name": "GLM-4.6",
          "temperature": 0.1,
          "max_tokens": 6000
        }
      }
    }
  }
}
```

#### Subagent Models Configuration
```json
{
  "research": {
    "anthropic": {
      "claude-4.5-sonnet": {
        "name": "Claude Research",
        "temperature": 0.1,
        "max_tokens": 4000
      }
    },
    "zhipu": {
      "glm-4.6": {
        "name": "GLM Research",
        "temperature": 0.1,
        "max_tokens": 3000
      }
    }
  },
  "coding": {
    "tongyi": {
      "qwen3-coder": {
        "name": "Qwen3 Coder",
        "temperature": 0.2,
        "max_tokens": 2000
      }
    }
  },
  "analysis": {
    "anthropic": {
      "claude-4.5-sonnet": {
        "name": "Claude Analysis",
        "temperature": 0.1,
        "max_tokens": 3000
      }
    }
  }
}
```

#### Filesystem Middleware Configuration
```json
{
  "enabled": true,
  "mode": "read_only",
  "security": {
    "allowed_paths": [
      "/workspace/",
      "/data/",
      "/tmp/"
    ],
    "excluded_paths": [
      "/etc/",
      "/root/",
      "/home/"
    ],
    "max_file_size": 10485760,
    "excluded_extensions": [".exe", ".bat", ".sh", ".pyc"]
  },
  "modes": {
    "read_only": {
      "enabled": true,
      "description": "Only allows file reading operations"
    },
    "ask_before_edits": {
      "enabled": true,
      "description": "Prompts user before file modifications"
    },
    "edit_automatically": {
      "enabled": false,
      "description": "Allows automatic file editing (high risk)"
    }
  }
}
```

#### Subagent Middleware Configuration
```json
{
  "enabled": true,
  "max_concurrent": 3,
  "default_timeout": 300,
  "subagents": {
    "research": {
      "description": "Conducts thorough research on complex topics",
      "system_prompt": "You are a dedicated researcher...",
      "tools": ["internet_search", "file_read"],
      "timeout": 300
    },
    "coding": {
      "description": "Handles programming and code analysis tasks",
      "system_prompt": "You are a skilled programmer...",
      "tools": ["code_analysis", "file_edit"],
      "timeout": 180
    },
    "analysis": {
      "description": "Performs data analysis and reporting",
      "system_prompt": "You are an analytical expert...",
      "tools": ["data_analysis", "report_generation"],
      "timeout": 240
    }
  }
}
```

## Configuration Loading

### DeepConfigLoader Implementation
```python
# src/config/deep_loader.py
class DeepConfigLoader:
    def __init__(self, config_dir: str = "config/agents/deep"):
        self.config_dir = Path(config_dir)
        self._cached_config = None
        self._cache_timestamp = None
    
    def load_middleware_config(self) -> Dict[str, Any]:
        """Load middleware configuration"""
        filesystem_config = self._load_json("middleware/filesystem.json")
        subagents_config = self._load_json("middleware/subagents.json")
        
        return {
            "filesystem": filesystem_config,
            "subagents": subagents_config
        }
    
    def load_models_config(self) -> Dict[str, Any]:
        """Load models configuration"""
        subagents_config = self._load_json("models/subagents.json")
        return {"subagents": subagents_config}
    
    def _load_json(self, file_path: str) -> Dict[str, Any]:
        """Load and validate JSON configuration"""
        full_path = self.config_dir / file_path
        with open(full_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        self._validate_config(config, file_path)
        return config
```

### Configuration Validation
```python
class ConfigValidator:
    def validate_filesystem_config(self, config: Dict[str, Any]):
        """Validate filesystem configuration"""
        required_fields = ["enabled", "mode", "security"]
        for field in required_fields:
            if field not in config:
                raise ValueError(f"Missing required field: {field}")
        
        # Validate security settings
        security = config.get("security", {})
        if not security.get("allowed_paths"):
            raise ValueError("allowed_paths must be specified")
        
        # Validate file size limit
        max_size = security.get("max_file_size", 0)
        if max_size <= 0 or max_size > 100 * 1024 * 1024:  # 100MB limit
            raise ValueError("Invalid max_file_size")
    
    def validate_subagents_config(self, config: Dict[str, Any]):
        """Validate subagents configuration"""
        if not config.get("enabled", False):
            return
        
        subagents = config.get("subagents", {})
        if not subagents:
            raise ValueError("No subagents configured")
        
        for name, subagent_config in subagents.items():
            self._validate_subagent_config(name, subagent_config)
```

## Integration with Existing System

### Provider Registry Integration
```python
# src/core/providers/provider_registry.py
class ProviderRegistry:
    def __init__(self):
        # Existing provider configuration
        self._providers = {}
        
        # Deep agents configuration
        self.deep_config_loader = DeepConfigLoader()
        self._deep_config = None
    
    def get_deep_agent_config(self) -> Dict[str, Any]:
        """Get deep agent configuration"""
        if self._deep_config is None:
            self._deep_config = self.deep_config_loader.load_middleware_config()
        return self._deep_config
```

### Agent Manager Integration
```python
# src/agents/deepagents/managers/deep_agent_manager.py
class DeepAgentManager:
    def __init__(self):
        from src.core.providers import provider_registry
        self.provider_registry = provider_registry
        self.deep_config = provider_registry.get_deep_agent_config()
        self.models_config = provider_registry.get_models_config()
    
    async def create_deep_agent(self, provider: str, model: str):
        # Load configuration
        filesystem_config = self.deep_config.get("filesystem", {})
        subagents_config = self.deep_config.get("subagents", {})
        
        # Create middleware with configuration
        middleware = self._create_middleware(filesystem_config, subagents_config)
        
        # Create deep agent
        return self._create_deep_agent_with_middleware(provider, model, middleware)
```

## Configuration Management

### Runtime Configuration Updates
```python
class ConfigManager:
    def __init__(self):
        self.config_loader = DeepConfigLoader()
        self.current_config = None
    
    def reload_config(self) -> bool:
        """Reload configuration from files"""
        try:
            new_config = self.config_loader.load_middleware_config()
            self._validate_config(new_config)
            self.current_config = new_config
            return True
        except Exception as e:
            logger.error(f"Failed to reload configuration: {e}")
            return False
    
    def get_config(self, section: str) -> Dict[str, Any]:
        """Get configuration section"""
        if self.current_config is None:
            self.current_config = self.config_loader.load_middleware_config()
        return self.current_config.get(section, {})
```

### Configuration Security
```python
class ConfigSecurity:
    def __init__(self):
        self.allowed_paths = []
        self.restricted_settings = ["api_keys", "secrets"]
    
    def validate_path_access(self, path: str) -> bool:
        """Validate if path is allowed"""
        for allowed_path in self.allowed_paths:
            if path.startswith(allowed_path):
                return True
        return False
    
    def sanitize_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Remove sensitive information from configuration"""
        sanitized = config.copy()
        for key in self.restricted_settings:
            if key in sanitized:
                sanitized[key] = "***REDACTED***"
        return sanitized
```

## Error Handling

### Configuration Error Recovery
```python
class ConfigErrorHandler:
    def handle_config_error(self, error: Exception, config_file: str):
        """Handle configuration errors"""
        logger.error(f"Configuration error in {config_file}: {error}")
        
        # Fallback to default configuration
        default_config = self._get_default_config(config_file)
        return default_config
    
    def _get_default_config(self, config_file: str) -> Dict[str, Any]:
        """Get default configuration for file"""
        defaults = {
            "middleware/filesystem.json": {
                "enabled": True,
                "mode": "read_only",
                "security": {
                    "allowed_paths": ["/workspace/"],
                    "max_file_size": 10485760
                }
            }
        }
        return defaults.get(config_file, {})
```

## Performance Considerations

### Configuration Caching
- **Memory Caching**: Configuration is cached in memory to avoid repeated file reads
- **Timestamp Validation**: Cache is invalidated when configuration files are modified
- **Lazy Loading**: Configuration is loaded only when needed

### Configuration Validation
- **Schema Validation**: Configuration is validated against JSON schemas
- **Security Validation**: Security settings are validated for safety
- **Performance Validation**: Configuration settings are validated for performance impact
