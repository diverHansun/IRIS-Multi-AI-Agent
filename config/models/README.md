# LLM配置系统文档

## 概述

本项目使用JSON文件来管理LLM模型配置，替代了原来硬编码在代码中的配置方式。这使得添加新模型和修改配置变得更加灵活和便捷。

## 文件结构

```
config/llms/
├── schema.json           # JSON Schema定义
├── providers.json        # 主配置文件
├── example_provider.json # 新增Provider示例
└── README.md            # 本文档
```

## 配置文件说明

### 1. schema.json
定义了配置文件的JSON Schema，用于验证配置文件的格式正确性。

### 2. providers.json
主配置文件，包含所有LLM提供商和模型的配置信息。

### 3. example_provider.json
演示如何添加新的LLM提供商的示例文件，包含最新的配置字段。

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
          "max_tokens": 4096,
          "context_window": 131072,
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
- `max_tokens`: 最大输出token数（整数，可选）
- `context_window`: 上下文窗口大小（整数，可选）
- `default_temperature`: 默认温度参数（可选）
- `temperature_fixed`: 温度是否固定（可选）
- `mode_overrides`: 模式参数覆盖（可选）

### 新增字段说明

#### max_tokens
- **类型**: 整数
- **说明**: 模型的最大输出token数
- **示例**: 4096, 8192, 16384
- **用途**: 控制模型单次输出的最大长度

#### context_window
- **类型**: 整数  
- **说明**: 模型的上下文窗口大小
- **示例**: 131072, 200000, 32768
- **用途**: 控制模型可以处理的输入+输出总长度

### 字段配置建议

| 模型类型 | max_tokens | context_window | 说明 |
|---------|------------|----------------|------|
| 小型模型 (1-7B) | 2048-4096 | 8192-16384 | 适合快速响应 |
| 中型模型 (8-20B) | 4096-8192 | 16384-32768 | 平衡性能和成本 |
| 大型模型 (70B+) | 8192-16384 | 32768-131072 | 最强能力 |
| 长上下文模型 | 4096-8192 | 131072-200000 | 支持长文档处理 |

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
          "supports_tools": true,
          "max_tokens": 4096,
          "context_window": 131072
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
    "max_tokens": 8192,
    "context_window": 131072,
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
- **重要**: 正确设置`max_tokens`和`context_window`参数
- 为特殊模型设置适当的`mode_overrides`

#### 新字段配置建议

1. **max_tokens配置**:
   - 根据模型实际能力设置，不要过高或过低
   - 考虑成本因素：更大的输出意味着更高的API费用
   - 参考官方文档或实际测试确定最佳值

2. **context_window配置**:
   - 设置为模型实际支持的上下文长度
   - 注意：这是输入+输出的总长度限制
   - 长上下文模型可以设置更大的值（如131072+）

3. **配置验证**:
   - 使用`reload`命令测试配置是否正确
   - 检查模型是否能正常加载和运行
   - 验证输出长度是否符合预期

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

参考`example_provider.json`文件，了解如何配置一个完整的新Provider（Anthropic Claude），包含最新的`max_tokens`和`context_window`字段配置。

### 完整配置示例

```json
{
  "schema_version": "1.0",
  "providers": {
    "ANTHROPIC": {
      "name": "Anthropic",
      "default_model": "claude-3-sonnet",
      "api_key_env": "ANTHROPIC_API_KEY",
      "models": {
        "claude-3-sonnet": {
          "name": "Claude 3 Sonnet",
          "description": "平衡性能和速度的Claude 3模型",
          "recommended": true,
          "model_features": ["高质量推理", "快速响应", "工具调用", "长上下文"],
          "supports_tools": true,
          "max_tokens": 4096,
          "context_window": 200000
        }
      }
    }
  }
}
```

这个示例展示了如何正确配置新字段，确保模型能够按照预期的方式工作。
