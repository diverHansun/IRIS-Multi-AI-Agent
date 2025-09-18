# LLM配置系统文档

## 概述

本项目使用JSON文件来管理LLM模型配置，替代了原来硬编码在代码中的配置方式。这使得添加新模型和修改配置变得更加灵活和便捷。

## 文件结构

```
config/llms/
├── schema.json           # JSON Schema定义
├── providers.json        # 主配置文件
├── example_new_provider.json  # 新增Provider示例
└── README.md            # 本文档
```

## 配置文件说明

### 1. schema.json
定义了配置文件的JSON Schema，用于验证配置文件的格式正确性。

### 2. providers.json
主配置文件，包含所有LLM提供商和模型的配置信息。

### 3. example_new_provider.json
演示如何添加新的LLM提供商的示例文件。

## 配置文件格式

### 基本结构

```json
{
  "schema_version": "1.0",
  "providers": {
    "PROVIDER_KEY": {
      "name": "Provider显示名称",
      "default_model": "默认模型名称",
      "api_key_env": "API_KEY_环境变量名",
      "class": "LLM类名（可选）",
      "mode_defaults": {
        "llm": {
          "temperature": 0.1,
          "streaming": true
        },
        "agent": {
          "temperature": 0.1,
          "memory_enabled": true,
          "max_iterations": 10,
          "max_execution_time": 300,
          "streaming": false
        }
      },
      "models": {
        "model_key": {
          "name": "模型显示名称",
          "description": "模型描述",
          "recommended": true,
          "model_features": ["特性1", "特性2"],
          "supports_tools": true,
          "mode_overrides": {
            "llm": {},
            "agent": {}
          }
        }
      }
    }
  }
}
```

### 字段说明

#### Provider级别字段

- `name`: Provider的显示名称
- `default_model`: 默认使用的模型名称
- `api_key_env`: API密钥的环境变量名（可选，Ollama不需要）
- `class`: LLM类名，用于代码中的类引用（可选）
- `mode_defaults`: 默认模式配置
  - `llm`: LLM模式默认参数
  - `agent`: Agent模式默认参数

#### Model级别字段

- `name`: 模型的显示名称
- `description`: 模型描述
- `recommended`: 是否推荐使用（布尔值）
- `model_features`: 模型特性列表
- `supports_tools`: 是否支持工具调用（布尔值）
- `default_temperature`: 默认温度参数（可选）
- `temperature_fixed`: 温度是否固定（可选）
- `mode_overrides`: 模式参数覆盖（可选）

## 如何添加新的LLM Provider

### 1. 编辑providers.json文件

在`providers`对象中添加新的Provider配置：

```json
{
  "schema_version": "1.0",
  "providers": {
    "NEW_PROVIDER": {
      "name": "新Provider名称",
      "default_model": "default-model",
      "api_key_env": "NEW_PROVIDER_API_KEY",
      "mode_defaults": {
        "llm": {
          "temperature": 0.1,
          "streaming": true
        },
        "agent": {
          "temperature": 0.1,
          "memory_enabled": true,
          "max_iterations": 10,
          "max_execution_time": 300,
          "streaming": false
        }
      },
      "models": {
        "model-1": {
          "name": "Model 1",
          "description": "第一个模型",
          "recommended": true,
          "model_features": ["特性A", "特性B"],
          "supports_tools": true
        }
      }
    }
  }
}
```

### 2. 实现对应的LLM类（如需要）

如果是全新的Provider，需要在代码中实现相应的LLM类：

```python
# src/llm/new_provider_llm.py
class NewProviderLLM:
    def __init__(self, api_key: str, model: str, **kwargs):
        # 实现初始化逻辑
        pass
    
    def create_llm(self):
        # 实现LLM创建逻辑
        pass
```

### 3. 更新LLM管理器

在`src/llm/llm_manager.py`的`_convert_json_config`方法中添加新Provider的处理逻辑：

```python
elif provider_enum == LLMProvider.NEW_PROVIDER:
    if "class" in config_copy and config_copy["class"] == "NewProviderLLM":
        config_copy["class"] = NewProviderLLM
```

### 4. 重新加载配置

使用CLI命令重新加载配置：

```bash
reload
```

## 如何添加新模型

在现有Provider中添加新模型只需编辑`providers.json`文件：

```json
"models": {
  "existing-model": {
    // 现有模型配置
  },
  "new-model": {
    "name": "新模型名称",
    "description": "新模型描述",
    "recommended": false,
    "model_features": ["新特性"],
    "supports_tools": true,
    "mode_overrides": {
      "agent": {
        "max_iterations": 15
      }
    }
  }
}
```

## 配置验证

系统会自动验证配置文件的格式：

1. **JSON Schema验证**: 检查配置文件是否符合定义的Schema
2. **业务逻辑验证**: 检查业务相关的逻辑一致性
3. **自动修复**: 尝试修复常见的配置问题

如果验证失败，系统会：
1. 显示详细的错误信息
2. 尝试自动修复
3. 如果无法修复，回退到硬编码的备用配置

## 最佳实践

### 1. 配置文件管理

- 修改配置前先备份原文件
- 使用`reload`命令测试配置是否正确
- 遵循JSON格式规范，注意逗号和引号

### 2. 模型配置

- 为新模型设置合适的`recommended`标志
- 提供详细和准确的`description`
- 根据模型能力设置`supports_tools`
- 为特殊模型设置适当的`mode_overrides`

### 3. 开发时配置

- 使用`reload`命令动态重载配置，无需重启程序
- 通过`llms`命令查看当前加载的配置
- 使用示例配置文件作为参考

## 故障排除

### 常见问题

1. **配置文件格式错误**
   - 检查JSON语法是否正确
   - 确保所有必需字段都存在
   - 查看错误日志获取详细信息

2. **新Provider无法加载**
   - 确保Provider key在LLMProvider枚举中定义
   - 检查是否实现了对应的LLM类
   - 验证API密钥环境变量是否正确设置

3. **模型切换失败**
   - 使用`reload`命令重新加载配置
   - 检查模型名称是否正确
   - 验证Provider是否可用

### 调试命令

```bash
# 查看当前配置
llms

# 重新加载配置
reload

# 查看系统信息
info

# 查看帮助
help
```

## 未来扩展

系统设计为支持未来扩展到SQLite数据库：

1. 当前的JSON配置系统作为轻量级解决方案
2. 可以轻松迁移到数据库存储
3. 保持相同的配置格式和验证逻辑
4. 支持更复杂的查询和管理功能

## 示例

参考`example_new_provider.json`文件，了解如何配置一个完整的新Provider（Anthropic Claude）。
