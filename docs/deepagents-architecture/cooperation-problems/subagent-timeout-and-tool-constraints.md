# Subagent 超时与工具限制问题 ⚠️

## 问题概述

当 main agent 使用 `task` 工具将任务委托给 subagent 时，subagent 的执行经常超过 `step_timeout` 限制，导致 `asyncio.TimeoutError` 和任务失败。

**根本原因**: Subagent 能力、工具选择和超时约束之间的不匹配。

---

## 问题详情

### 问题 1: 任务范围不匹配 📦

**症状**: Main agent 一次性将整个复杂任务委托给 subagent。

**错误示例**:
```
Main agent: "搜索9个城市的活动：上海、北京、南京..."
  ↓ (一次性全部委托)
Subagent: 开始逐个搜索所有城市
  → 耗时 120+ 秒
  → 触发 step_timeout
  → 任务失败 ❌
```

**正确流程**:
```
Main agent: 自己规划任务分解
  ↓ "搜索上海"
  Subagent: 30秒内返回 ✅
  ↓ "搜索北京"
  Subagent: 30秒内返回 ✅
  ↓ 继续...
```

**已应用的解决方案**:
- 修改了 `src/components/deepagents/prompts/subagents/research.md`
- 添加了明确的约束条件：
  - 范围限制: 一次只处理一个聚焦任务
  - 时间限制: 最多 60-90 秒
  - 工具调用限制: 2-5 次调用
  - 指示拒绝过大的任务

**效果**: Subagent 现在会返回"任务范围过大"消息，强制 main agent 拆分任务。

---

### 问题 2: 工具选择问题 🔧

**症状**: Subagent 选择了慢速工具（如 `tavily-search-advanced`），超出时间限制。

**时间线**:
```
18:32:51 - Subagent 开始执行
18:33:21 - 使用快速搜索（快速）
18:33:38 - 切换到 tavily-search-advanced
            ↓ (等待 API 响应 + 处理大量数据)
18:34:51 - step_timeout (120秒) 触发 ⏰
```

**问题分析**:

| 工具 | 速度 | 数据质量 | 数据量 | 超时风险 |
|------|-------|----------|--------|---------|
| `search` (DuckDuckGo) | 快 (5-10秒) | 中等 | 小 | 低 ✅ |
| `web_fetch` | 快 (3-8秒) | 中等 | 小 | 低 ✅ |
| `tavily-search-advanced` | 慢 (30-60秒) | 高 | 大 | **高** ⚠️ |

**为什么 tavily-search-advanced 很慢**:
- `depth=advanced` - 深度爬取模式
- `max_results=10` - 抓取 10 个完整页面
- 返回大量结构化数据
- API 处理时间 30-60 秒
- LLM 需要时间处理大量响应数据

**当前配置** (`config/agents/deep/models/subagents.json`):
```json
"research": {
  "agent_config": {
    "tools": [],  // 空数组 = 使用所有可用工具
  }
}
```

这意味着 subagent 可以访问所有 125 个工具，包括慢速工具。

---

## 超时配置分析 ⏱️

### Main Agent 超时设置

**文件**: `config/agents/deep/models/mainagents.json`

```json
"runtime_config": {
  "recursion_limit": 300,
  "step_timeout": 120,        // 每步最多 120 秒
  "stream_mode": "updates"
},
"safety_config": {
  "max_execution_time": 600   // 总计最多 600 秒
}
```

**关键点**: `step_timeout: 120` 适用于**每个单独的步骤**，包括等待工具调用。

当 main agent 调用 `task` 工具时：
1. Main agent 进入"步骤"状态，等待工具响应
2. Subagent 开始执行（发生在步骤内部）
3. 如果 subagent 执行 >120 秒，main agent 的步骤超时
4. 任务失败，抛出 `asyncio.TimeoutError`

### Subagent 超时设置

**文件**: `config/agents/deep/models/subagents.json`

```json
"runtime_limits": {
  "max_execution_time": 300,  // 总执行时间限制
  "recursion_limit": 80,
  "step_timeout": 120         // 每步限制
}
```

**问题**: Subagent 有自己的超时设置，但 main agent 的 `step_timeout` 先触发。

**约束链**:
```
Main agent step_timeout: 120秒
  └─ 包含: Subagent 执行
       └─ 包含: 工具调用（如 tavily-search-advanced: 60秒）
            └─ 包含: LLM 处理大量响应: 20-40秒
```

**结果**: 即使 subagent 在自己的限制内完成，main agent 也会超时。

---

## 解决方案选项 💡

### 方案 1: 限制 Subagent 可用工具（推荐短期方案）⭐

**实施**: 修改 `config/agents/deep/models/subagents.json`

```json
"research": {
  "agent_config": {
    "tools": ["search", "web_fetch"]  // 只允许快速工具
  }
}
```

**优点**:
- ✅ 简单直接，立即生效
- ✅ 强制使用快速工具
- ✅ 不依赖 LLM 遵守规则

**缺点**:
- ❌ 失去访问高质量 Tavily 数据的能力
- ❌ 降低研究能力

---

### 方案 2: 在 System Prompt 中规定工具使用规则

**实施**: 修改 `src/components/deepagents/prompts/subagents/research.md`

```markdown
## 工具使用规则
- **仅使用**: `search`, `web_fetch`
- **禁止使用**: `tavily-search-advanced`（对 subagent 任务太慢）
- 原因: Subagent 必须在 60-90 秒内完成
```

**优点**:
- ✅ 灵活，可以提供推理原因
- ✅ 工具在技术上仍可用
- ✅ 易于调整规则

**缺点**:
- ❌ 依赖 LLM 遵守规则（不可靠）
- ❌ LLM 可能仍会选择慢速工具
- ❌ 没有硬性约束

**不推荐**: 观察到的行为显示，即使 prompt 中有时间约束，LLM 仍会调用 `tavily-search-advanced`。

---

### 方案 3: 创建 Tavily 工具的快速版本 🚀

**实施**: 创建 `tavily_search_quick` 工具

```python
def tavily_search_quick(query: str) -> str:
    """为 subagent 优化的快速 Tavily 搜索。"""
    return tavily_search(
        query=query,
        depth="basic",        # 不是 "advanced"
        max_results=3,        # 不是 10
        timeout=20            # 硬性限制
    )
```

**优点**:
- ✅ 平衡速度和质量
- ✅ 利用 Tavily 优势（去广告、结构化数据）
- ✅ 可预测的执行时间

**缺点**:
- ❌ 需要开发新工具
- ❌ 增加复杂性
- ⚠️ 仍比 DuckDuckGo 慢

---

### 方案 4: 多种类型的研究 Subagent 🎯

**实施**: 创建专门化的 subagent

```json
"research-quick": {
  "name": "research-quick",
  "description": "快速研究，用于聚焦查询 (30-60秒)",
  "tools": ["search", "web_fetch"],
  "runtime_limits": {
    "max_execution_time": 90
  }
},
"research-deep": {
  "name": "research-deep",
  "description": "全面研究，使用高质量来源 (2-5分钟)",
  "tools": ["tavily-search-advanced", "web_fetch"],
  "runtime_limits": {
    "max_execution_time": 300
  }
}
```

**使用方式**:
- Main agent 调用 `research-quick` 处理子任务
- Main agent 直接使用 `research-deep` 工具进行全面研究
- 用户明确请求深度研究时使用

**优点**:
- ✅ 清晰的关注点分离
- ✅ 为正确的工作选择正确的工具
- ✅ 可扩展的模式

**缺点**:
- ❌ 配置更复杂
- ❌ Main agent 需要选择正确的 subagent 类型
- ❌ 维护开销更高

---

### 方案 5: 调整 step_timeout（不推荐）❌

**为什么不推荐**:
- 将 main agent 的 `step_timeout` 增加到 300 秒会让整个系统变慢
- 掩盖了真正的问题（任务/工具范围）
- 如果 subagent 需要 3+ 分钟，说明任务太大
- 违反 subagent 设计原则（小型、聚焦任务）

---

## 推荐实施计划 📋

### 阶段 1: 立即修复（当前会话）
✅ **已完成**:
- 修改了 `research.md` prompt，添加范围约束
- Subagent 现在会拒绝过大的任务

🔧 **下一步**:
- 应用**方案 1**: 限制 subagent 工具为仅快速工具
  ```json
  "tools": ["search", "web_fetch"]
  ```

### 阶段 2: 测试和验证
- 测试限制工具后 subagent 的性能
- 测量响应时间和质量
- 记录与 Tavily Advanced 的质量差异

### 阶段 3: 质量改进（未来）
根据阶段 2 结果选择:
- 如果质量可接受: 保持阶段 1 方案
- 如果质量不足: 实施**方案 3**（tavily_search_quick）
- 如果出现更多场景: 实施**方案 4**（多种 subagent 类型）

---

## 相关文件 📁

**配置文件**:
- `config/agents/deep/models/mainagents.json` - Main agent 配置
- `config/agents/deep/models/subagents.json` - Subagent 配置

**System Prompt**:
- `src/components/deepagents/prompts/subagents/research.md` - 研究型 subagent
- `src/components/deepagents/prompts/subagents/coding.md` - 编码型 subagent
- `src/components/deepagents/prompts/subagents/analysis.md` - 分析型 subagent

**实现代码**:
- `src/components/deepagents/runtime_middlewares/__init__.py` - Subagent 中间件和 task 工具
- `src/components/deepagents/runtime.py` - 运行时创建和超时设置
- `src/core/providers/subagents_provider_registry.py` - Subagent 配置加载器

**工具实现**:
- `src/components/shared/tools/sdk/tavily_search/tavily_search_tool.py` - Tavily 工具
- `src/components/shared/tools/sdk/search/search_tools.py` - DuckDuckGo 和其他搜索工具

---

## 核心要点 🎯

1. **Subagent 用于小任务** - 不是多步骤工作流
2. **工具速度很重要** - 快速工具防止超时
3. **范围约束有效** - Prompt 修改成功引导行为
4. **硬限制优于软指导** - 工具限制 > prompt 指令
5. **设计原则** - Main agent 编排，subagent 执行聚焦工作

---

## 未来考虑 🔮

### Tavily Advanced 使用场景

**应该使用的场景**:
- ✅ Main agent 直接调用（无 subagent 包装）
- ✅ 用户明确请求全面研究
- ✅ 质量 > 速度的任务
- ✅ 批量操作，用户预期较长等待时间

**不应该使用的场景**:
- ❌ 在有严格时间约束的 subagent 内
- ❌ 需要快速响应的迭代循环
- ❌ 实时或交互式场景

### 监控建议 📊

建议添加指标跟踪:
- Subagent 执行时间分布
- Subagent 的工具使用模式
- 按工具类型的超时频率
- 按工具类型的质量指标（用户反馈）

这些数据将为未来的工具选择和超时配置决策提供依据。

---

## 删除调试信息的便利性评估 🔧

### 修改文件清单

根据 `git status`，当前修改的文件：

**核心修改** (7个文件):
1. `main.py` - 添加 logging 配置
2. `src/application/cli/main.py` - 增强错误处理
3. `src/application/services/agent/deep/conversation.py` - 超时日志
4. `src/application/services/agent/deep/event_handler.py` - Task tool 追踪
5. `src/components/deepagents/runtime.py` - Task tool 创建日志
6. `src/components/deepagents/runtime_middlewares/__init__.py` - Subagent 详细日志
7. `src/components/deepagents/prompts/subagents/research.md` - Prompt 改进

**新增文档** (2个目录):
- `docs/debugging/` - 调试指南和实施总结
- `deepagents/` - （外部示例代码，可删除）

### 删除调试代码的便利性

**容易删除** ✅:
- 所有日志调用都有明确的前缀标记：`[SubAgent Init]`, `[SubAgent Exec]`, `[Runtime]` 等
- 可以通过搜索快速定位所有调试代码
- Git 可以快速恢复到修改前的状态

**删除方案**:

**选项 A: 完全恢复** (5分钟)
```bash
git checkout HEAD -- src/components/deepagents/runtime_middlewares/__init__.py
git checkout HEAD -- src/application/services/agent/deep/conversation.py
git checkout HEAD -- src/application/services/agent/deep/event_handler.py
git checkout HEAD -- src/components/deepagents/runtime.py
```

**选项 B: 保留关键日志** (10分钟)
- 保留所有 ERROR 级别日志（生产环境有用）
- 保留 main.py 的错误详情输出
- 删除 INFO 和 DEBUG 日志
- 保留 `research.md` 的改进（这是业务逻辑，不是调试）

**选项 C: 使用日志级别控制** (10分钟，推荐)
- 将所有调试日志改为 DEBUG 级别
- 生产环境设置 `level=logging.WARNING`
- 需要调试时改为 `level=logging.DEBUG`
- 优点：不需要删除代码，通过配置控制

### 便利性评分

| 删除方式 | 难度 | 风险 | 时间成本 | 推荐度 |
|---------|------|------|---------|--------|
| Git checkout | ⭐ 简单 | 低 | 5分钟 | ⭐⭐⭐ |
| 手动删除 | ⭐⭐ 中等 | 中 | 30分钟 | ⭐⭐ |
| 日志级别控制 | ⭐ 简单 | 低 | 10分钟 | ⭐⭐⭐⭐⭐ |

**结论**:
- ✅ **删除非常方便** - 有完整文档记录所有修改位置
- ✅ **Git 可快速恢复** - 每个文件都有清晰的修改历史
- 💡 **建议保留部分** - ERROR 日志和 main.py 的改进对生产环境有益
- 🎯 **最佳方案**: 使用日志级别控制，保留代码，通过配置切换