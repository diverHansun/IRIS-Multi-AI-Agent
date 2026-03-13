# DeepAgents 配置参数说明

> 兼容性说明:
> 目前 canonical bundled 路径已经迁移到 `config/agents/deep/` 根层。
> `models/` 目录保留为 legacy 兼容镜像。新的代码、文档和配置初始化逻辑
> 应优先使用 `config/agents/deep/mainagents*.json` 与
> `config/agents/deep/subagents*.json`。

本文档详细说明 MainAgent 和 SubAgent 的各项配置参数及其作用。

---

## 配置文件

### Models 配置 (models/)
- `mainagents.json` - 主 Agent 配置
- `mainagents.example.json` - 主 Agent 配置示例
- `subagents.json` - 子 Agent 配置 (包含所有 SubAgent 定义)
- `subagents.example.json` - 子 Agent 配置示例

### Middleware 配置 (middleware/)
- `filesystem.json` - 文件系统中间件配置 (安全路径、文件限制等)

---

## MainAgent 配置参数

### 结构概览

```json
{
  "provider_name": {
    "description": "...",
    "default_model": "...",
    "api_config": {...},
    "models": {
      "model_name": {
        "llm_params": {...},
        "runtime_config": {...},
        "middleware_config": {...},
        "display_config": {...},
        "safety_config": {...},
        "metadata": {...}
      }
    }
  }
}
```

### 1. Provider 级别配置

#### `description`
- **类型**: String
- **说明**: Provider 的描述信息
- **示例**: `"Anthropic Claude models configured for deep agents"`

#### `default_model`
- **类型**: String
- **说明**: 该 Provider 默认使用的模型名称
- **示例**: `"claude-4.5-sonnet"`

#### `api_config`
- **类型**: Object
- **说明**: API 连接配置

参数:
- `base_url` (String): API 基础 URL
- `api_key_env` (String): API Key 对应的环境变量名

示例:
```json
"api_config": {
  "base_url": "https://api.openai-proxy.org/v1",
  "api_key_env": "ANTHROPIC_API_KEY"
}
```

---

### 2. Model 级别配置

#### `llm_params` - LLM 调用参数
控制模型的生成行为。

参数:
- `temperature` (Float, 0-1): 生成随机性,越高越随机
  - 推荐: `0.6` (平衡创造性和稳定性)
- `max_tokens` (Integer): 单次生成的最大 token 数
  - 推荐: `4096`
- `streaming` (Boolean): 是否启用流式输出
  - 推荐: `false` (非流式更稳定)

示例:
```json
"llm_params": {
  "temperature": 0.6,
  "max_tokens": 4096,
  "streaming": false
}
```

---

#### `runtime_config` - 运行时配置
控制 Agent 运行时行为。

参数:
- `recursion_limit` (Integer): 最大递归深度
  - **含义**: Agent 可以执行的最大步骤数
  - **推荐**: `300` (MainAgent 通常需要较多步骤)
  - **注意**: 过小会导致复杂任务中断,过大可能导致无限循环

- `step_timeout` (Integer, 秒): 单步超时时间
  - **含义**: 单个步骤(包括模型调用和工具执行)的最大执行时间
  - **推荐**: `120` (2分钟,足够大多数操作)
  - **触发**: LangGraph 在步骤级别超时时终止

- `stream_mode` (String): 流式输出模式
  - **可选值**: `"updates"`, `"values"`, `"messages"`
  - **推荐**: `"updates"` (仅输出更新)

示例:
```json
"runtime_config": {
  "recursion_limit": 300,
  "step_timeout": 120,
  "stream_mode": "updates"
}
```

---

#### `middleware_config` - 中间件配置
配置 Agent 使用的中间件。

参数:
- `filesystem` (String/Object): 文件系统中间件配置
  - 值为 `"default"` 时使用默认配置
  - 值为对象时使用自定义配置

- `subagents` (String/Object): 子 Agent 中间件配置
  - 值为 `"default"` 时使用默认配置
  - 值为对象时使用自定义配置

示例:
```json
"middleware_config": {
  "filesystem": "default",
  "subagents": "default"
}
```

---

#### `display_config` - 显示配置
控制执行过程中的信息显示。

参数:
- `streaming_enabled` (Boolean): 是否启用流式显示
- `show_reasoning_steps` (Boolean): 是否显示推理步骤
- `show_tool_calls` (Boolean): 是否显示工具调用
- `show_tool_results` (Boolean): 是否显示工具结果
- `show_subagent_delegations` (Boolean): 是否显示子 Agent 委托
- `show_elapsed_time` (Boolean): 是否显示执行时间

推荐:
```json
"display_config": {
  "streaming_enabled": true,
  "show_reasoning_steps": true,
  "show_tool_calls": true,
  "show_tool_results": true,
  "show_subagent_delegations": true,
  "show_elapsed_time": true
}
```

---

#### `safety_config` - 安全配置
控制 Agent 的安全限制和人工介入。

参数:

**`max_execution_time` (Integer, 秒): 总执行时间限制**
- **含义**: Agent 从开始到结束的最大总执行时间
- **推荐**: `600` (10分钟)
- **触发**: ExecutionTimeoutMiddleware 在超时时优雅终止 Agent
- **区别于 `step_timeout`**:
  - `step_timeout` 限制单个步骤
  - `max_execution_time` 限制整个 Agent 执行

**`hitl_config` (Object): Human-in-the-Loop 配置**

子参数:
- `dangerous_tools` (Array): 需要人工确认的危险工具列表
  - 示例: `["delete_file", "execute_shell", "rm", "sudo"]`

- `tools` (Object): 工具级别的详细配置
  - 每个工具可配置:
    - `allow_auto_approve` (Boolean): 是否允许自动批准
    - `warning_message` (String): 警告消息

示例:
```json
"safety_config": {
  "max_execution_time": 600,
  "hitl_config": {
    "dangerous_tools": ["delete_file", "execute_shell", "rm", "sudo"],
    "tools": {
      "delete_file": {
        "allow_auto_approve": false,
        "warning_message": "This operation cannot be undone!"
      }
    }
  }
}
```

---

#### `metadata` - 元数据
模型的能力信息(仅供参考,不影响运行时行为)。

参数:
- `context_window` (Integer): 上下文窗口大小(tokens)
- `supports_tools` (Boolean): 是否支持工具调用
- `max_input_tokens` (Integer): 最大输入 tokens
- `max_output_tokens` (Integer): 最大输出 tokens

示例:
```json
"metadata": {
  "context_window": 200000,
  "supports_tools": true,
  "max_input_tokens": 100000,
  "max_output_tokens": 50000
}
```

---

## SubAgent 配置参数

### 结构概览

```json
{
  "subagent_type": {
    "name": "...",
    "description": "...",
    "llm_config": {...},
    "agent_config": {...},
    "runtime_limits": {...},
    "display_config": {...},
    "metadata": {...}
  }
}
```

### 1. 基本信息

#### `name`
- **类型**: String
- **说明**: SubAgent 的唯一标识符
- **示例**: `"research"`, `"coding"`, `"analysis"`

#### `description`
- **类型**: String
- **说明**: SubAgent 的功能描述
- **示例**: `"Research specialist for deep information gathering and analysis"`

---

### 2. LLM 配置

#### `llm_config` - LLM 配置
配置 SubAgent 使用的语言模型。

参数:
- `provider` (String): 模型提供商
  - 可选: `"zhipu"`, `"tongyi"`, `"anthropic"`, `"openai"`

- `model` (String): 具体模型名称
  - 示例: `"glm-4.6"`, `"qwen3-coder-plus"`, `"claude-haiku-4-5"`

- `api_config` (Object): API 配置(同 MainAgent)

- `model_params` (Object): 模型参数(同 MainAgent 的 `llm_params`)

示例:
```json
"llm_config": {
  "provider": "zhipu",
  "model": "glm-4.6",
  "api_config": {
    "base_url": "https://open.bigmodel.cn/api/paas/v4",
    "api_key_env": "ZHIPU_API_KEY"
  },
  "model_params": {
    "temperature": 0.6,
    "max_tokens": 4096,
    "streaming": false
  }
}
```

---

### 3. Agent 配置

#### `agent_config` - Agent 行为配置

参数:
- `tools` (Array): 该 SubAgent 可用的工具列表
  - 示例: `[]` (空数组表示使用默认工具)

- `middleware` (Array): 自定义中间件列表
  - 示例: `[]` (空数组表示使用默认中间件)

- `checkpointer` (Boolean): 是否启用检查点(状态持久化)
  - 推荐: `false` (SubAgent 通常不需要持久化状态)

示例:
```json
"agent_config": {
  "tools": [],
  "middleware": [],
  "checkpointer": false
}
```

---

### 4. 运行时限制

#### `runtime_limits` - 运行时限制配置

**重要参数说明**:

**`max_execution_time` (Integer, 秒): 总执行时间限制**
- **含义**: SubAgent 从被调用到完成的最大总时间
- **推荐**: `90` (1.5分钟,SubAgent 任务通常较简单)
- **触发**: ExecutionTimeoutMiddleware 在超时时终止 SubAgent

**`step_timeout` (Integer, 秒): 单步超时时间**
- **含义**: SubAgent 单个步骤的最大执行时间
- **推荐**: `30` (30秒,SubAgent 的单步操作应该快速)
- **触发**: LangGraph 在步骤级别超时时终止

**`recursion_limit` (Integer): 最大递归深度**
- **含义**: SubAgent 可以执行的最大步骤数
- **推荐**: `60` (SubAgent 步骤应该较少)

**参数区别**:
```
recursion_limit: 最多执行多少个步骤
step_timeout: 每个步骤最多执行多长时间
max_execution_time: 所有步骤加起来最多执行多长时间
```

示例:
```json
"runtime_limits": {
  "max_execution_time": 90,
  "step_timeout": 30,
  "recursion_limit": 60
}
```

---

### 5. 显示和元数据配置

#### `display_config`
同 MainAgent,但 SubAgent 通常设置较简洁:
```json
"display_config": {
  "streaming_enabled": false,
  "show_reasoning_steps": false,
  "show_tool_calls": false
}
```

#### `metadata`
同 MainAgent,记录模型能力信息。

---

## 超时参数对比表

| 参数名 | 层级 | 作用范围 | MainAgent 推荐值 | SubAgent 推荐值 | 触发机制 |
|--------|------|----------|------------------|-----------------|----------|
| `step_timeout` | 步骤级 | 单个步骤 | 120秒 | 30秒 | LangGraph |
| `max_execution_time` | Agent级 | 整个执行 | 600秒 | 90秒 | ExecutionTimeoutMiddleware |
| `recursion_limit` | 步骤数 | 最大步数 | 300 | 60 | LangGraph |

---

## 参数调优建议

### MainAgent (复杂长时任务)
```json
{
  "recursion_limit": 300,        // 允许较多步骤
  "step_timeout": 120,           // 单步时间充裕
  "max_execution_time": 600      // 总时间10分钟
}
```

### SubAgent (快速专项任务)
```json
{
  "recursion_limit": 60,         // 限制步骤数
  "step_timeout": 30,            // 单步快速响应
  "max_execution_time": 90       // 总时间1.5分钟
}
```

---

## 常见问题

### Q1: `step_timeout` 和 `max_execution_time` 的区别?

**A**:
- `step_timeout`: 限制**单个步骤**的时间(如一次工具调用)
- `max_execution_time`: 限制**整个 Agent 执行**的总时间(所有步骤加起来)

示例:
```
假设 step_timeout=30, max_execution_time=90
- 如果某个工具调用超过30秒 → step_timeout 触发
- 如果总共执行了4步,每步25秒,总共100秒 → max_execution_time 触发
```

### Q2: 为什么 SubAgent 的限制比 MainAgent 小?

**A**: SubAgent 被设计为处理**专项的简单任务**,应该快速完成。MainAgent 负责**复杂的长时任务**,需要更多时间和步骤。

### Q3: 如何调整这些参数?

**A**:
1. 监控实际执行情况
2. 如果经常超时但任务合理 → 增加限制
3. 如果任务陷入循环 → 减少 `recursion_limit`
4. 如果单步操作慢(如大文件处理) → 增加 `step_timeout`

---

## 配置最佳实践

1. **保持示例文件更新**: 修改配置后同步更新 `.example.json` 文件
2. **不要过度限制**: 限制太严会导致正常任务被终止
3. **不要过度放松**: 限制太松会导致异常任务长时间运行
4. **根据任务类型调整**: 不同类型的 Agent 使用不同的限制值
5. **监控和迭代**: 根据实际使用情况调整参数

---

## 配置架构说明

### 配置文件职责划分

**models/ 目录**: Agent 的基础定义
- 定义 Agent 的 LLM 配置、工具、参数等核心配置
- `mainagents.json`: 主 Agent 的完整定义
- `subagents.json`: 所有 SubAgent 的完整定义

**middleware/ 目录**: 运行时中间件配置
- 配置 Agent 运行时使用的中间件行为
- `filesystem.json`: 文件系统访问控制、安全限制等

**注意**: 旧版本中存在 `middleware/subagents.json` 文件,该文件已废弃。所有 SubAgent 的配置统一在 `models/subagents.json` 中管理。

---

## 版本历史

- **2025-10-27**:
  - 添加 `max_execution_time` 参数(MainAgent 和 SubAgent)
  - 添加 `step_timeout` 参数(SubAgent)
  - 区分 `step_timeout` 和 `max_execution_time`
  - 实现 ExecutionTimeoutMiddleware
  - 废弃 `middleware/subagents.json`,统一使用 `models/subagents.json`
