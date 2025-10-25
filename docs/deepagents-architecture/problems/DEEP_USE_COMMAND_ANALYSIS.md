# Deep Agent `/use` 命令分析报告

## 问题描述

用户执行 `/use coding` 后发现:
- ✅ Prompt 切换了 (从 `prompts/subagents/research.md` → `prompts/subagents/coding.md`)
- ❌ SubAgent 对应的 LLM 模型没有切换

## 架构分析

### 核心概念区分

#### 1. Function Type (功能类型)
这是**主代理(Main Agent)**的功能类型:

```
Function Type → 决定创建哪个 Main Agent 类
├─ research  → ResearchAgent (主代理)
├─ coding    → CodingAgent (主代理)
└─ analysis  → AnalysisAgent (主代理)
```

**配置文件**: `config/agents/deep/models/providers.json`
- 定义主代理使用的 LLM 模型
- 例如: ANTHROPIC/claude-4.5-sonnet, TONGYI/qwen3-coder

#### 2. SubAgent (子代理)
这是**被主代理调用的专家助手**:

```
SubAgent Types → 主代理可以委托的专家
├─ research  → 研究子代理
├─ coding    → 编码子代理
└─ analysis  → 分析子代理
```

**配置文件**: `config/agents/deep/models/subagents.json`
- 定义子代理使用的 LLM 模型
- research: ANTHROPIC/claude-haiku-4-5 或 ZHIPU/glm-4.6
- coding: TONGYI/qwen3-coder-plus
- analysis: ANTHROPIC/claude-4.5-sonnet

### 当前 `/use` 命令的实际行为

**文件**: `src/application/commands/agent/deep/use_commands.py:42-48`

```python
agent, info = await switch_deep_agent(
    ctx,
    provider=config.get("provider"),  # ← 使用当前的 provider
    model=config.get("model"),        # ← 使用当前的 model
    function_type=target,             # ← 只切换 function_type
    target="deep",
)
```

**执行流程**:

```
/use coding
    ↓
switch_deep_agent(function_type="coding", provider=当前provider, model=当前model)
    ↓
创建新的 CodingAgent
    ├─ 主代理模型: 保持不变 (使用当前 provider/model)
    ├─ 主代理prompt: ✅ 切换到 coding 相关
    └─ 子代理配置: 从 subagents.json 读取
        ├─ research subagent: ANTHROPIC/claude-haiku-4-5
        ├─ coding subagent: TONGYI/qwen3-coder-plus  ← 正确配置
        └─ analysis subagent: ANTHROPIC/claude-4.5-sonnet
```

### 问题根源

**误解**: `/use` 命令切换的是**主代理的功能类型**,而不是切换使用哪个子代理。

**实际情况**:
1. `/use coding` 创建一个 `CodingAgent` 作为主代理
2. 这个主代理使用你当前配置的 provider/model
3. 子代理的模型在 `subagents.json` 中已经预定义
4. 主代理可以调用任何子代理 (research, coding, analysis)

## 配置文件对比

### providers.json (主代理配置)
```json
{
  "ANTHROPIC": {
    "models": {
      "claude-4.5-sonnet": { ... }  ← 主代理可用模型
    }
  },
  "TONGYI": {
    "models": {
      "qwen3-coder": { ... }  ← 主代理可用模型
    }
  }
}
```

### subagents.json (子代理配置)
```json
{
  "research": {
    "providers": {
      "ANTHROPIC": { "models": { "claude-haiku-4-5": { ... } } }
    }
  },
  "coding": {
    "providers": {
      "TONGYI": { "models": { "qwen3-coder-plus": { ... } } }
    }
  }
}
```

## 当前行为示例

假设你当前使用 ANTHROPIC/claude-4.5-sonnet:

```
初始状态: /mode deep
  Main Agent: ResearchAgent
  └─ LLM: ANTHROPIC/claude-4.5-sonnet

执行: /use coding
  Main Agent: CodingAgent  ← 切换了类型
  └─ LLM: ANTHROPIC/claude-4.5-sonnet  ← 模型没变!

主代理可以调用的子代理:
  ├─ research: ANTHROPIC/claude-haiku-4-5
  ├─ coding: TONGYI/qwen3-coder-plus  ← 这个模型是预配置的
  └─ analysis: ANTHROPIC/claude-4.5-sonnet
```

## 用户期望 vs 实际行为

### 用户期望
```
/use coding
  ↓
主代理切换为: CodingAgent
主代理LLM切换为: TONGYI/qwen3-coder (适合编码)
子代理不变: 保持 subagents.json 配置
```

### 实际行为
```
/use coding
  ↓
主代理切换为: CodingAgent  ✅
主代理LLM: 保持当前 provider/model  ❌
子代理不变: 保持 subagents.json 配置  ✅
```

## 解决方案选项

### 选项 1: 自动切换主代理模型 (推荐)
修改 `/use` 命令,根据 function_type 自动选择最佳的主代理模型:

```python
# 定义每个 function type 的推荐 provider/model
FUNCTION_TYPE_DEFAULTS = {
    "research": ("ZHIPU", "glm-4.6"),      # 研究任务用 GLM
    "coding": ("TONGYI", "qwen3-coder"),   # 编码任务用 Qwen
    "analysis": ("ANTHROPIC", "claude-4.5-sonnet"),  # 分析用 Claude
}
```

### 选项 2: 提示用户手动切换
保持当前行为,但提供清晰的提示:

```
/use coding
→ "Deep agent function switched to coding (ANTHROPIC/claude-4.5-sonnet).
   Tip: Use '/agent TONGYI qwen3-coder' for optimal coding performance."
```

### 选项 3: 添加配置选项
在 providers.json 中为每个模型标记推荐的 function_type:

```json
{
  "TONGYI": {
    "models": {
      "qwen3-coder": {
        "recommended_for": ["coding"],  ← 新增
        ...
      }
    }
  }
}
```

## 推荐实施方案

**方案**: 选项 1 + 选项 2 的组合

1. **自动切换** (方便快捷)
   - `/use coding` → 自动切换到 TONGYI/qwen3-coder
   - `/use research` → 自动切换到 ZHIPU/glm-4.6
   - `/use analysis` → 自动切换到 ANTHROPIC/claude-4.5-sonnet

2. **保留手动覆盖** (灵活性)
   - `/use coding --provider ANTHROPIC` → 使用 ANTHROPIC 做编码
   - 用户仍可用 `/agent` 命令独立切换模型

3. **清晰提示** (用户体验)
   - 显示切换后的 provider/model
   - 提示用户可以手动覆盖

## 实施细节

### 修改文件
1. `src/application/commands/agent/deep/use_commands.py`
   - 添加 function_type 默认模型映射
   - 修改 execute() 方法

2. 可选: 添加配置文件
   - `config/agents/deep/function_type_defaults.json`
   - 定义每个 function_type 的推荐 provider/model

### 向后兼容性
- ✅ 现有配置文件无需修改
- ✅ 用户可以继续手动切换模型
- ✅ 如果推荐模型不可用,回退到当前模型

---

## 总结

**问题**: `/use` 命令只切换主代理类型,不切换主代理使用的 LLM 模型
**原因**: 设计上 function_type 和 provider/model 是独立配置
**期望**: 切换 function_type 时自动选择最佳模型
**解决**: 实施智能默认值 + 保留手动覆盖选项
