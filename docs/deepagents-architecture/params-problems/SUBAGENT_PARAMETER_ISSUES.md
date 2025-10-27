# SubAgent 参数传递问题文档

## 问题概述

SubAgent 在参数传递过程中存在一个**语义混淆**问题:

- `max_execution_time` (总执行时间) 被错误地赋值给了 `step_timeout` (单步超时时间)

## 问题位置

**文件**: `src/agents/deepagents/factories/base.py`

**代码行**: [base.py:244-286](../src/agents/deepagents/factories/base.py#L244-L286)

```python
# base.py:244-246
runtime_limits = config["runtime_limits"]
recursion_limit = runtime_limits.get("recursion_limit")
max_execution_time = runtime_limits.get("max_execution_time")  # ← 获取 max_execution_time

# base.py:278-286
subagent_spec = SubAgent(
    name=config["name"],
    description=description,
    system_prompt=system_prompt,
    tools=tools,
    model=subagent_llm,
    recursion_limit=recursion_limit,
    step_timeout=max_execution_time,  # ← 错误!将总执行时间赋值给单步超时
    middleware=middleware_cfg,
    checkpointer=checkpointer,
    display_config=display_config,
    metadata=metadata_cfg,
)
```

## 配置来源

**文件**: `config/agents/deep/models/subagents.json`

```json
{
  "research": {
    "runtime_limits": {
      "max_execution_time": 90,  // 这应该是总执行时间,不是单步超时
      "recursion_limit": 60
    }
  }
}
```

## 问题分析

### 语义混淆

1. **`max_execution_time`** (在 `subagents.json` 中):
   - **预期语义**: SubAgent 的**总执行时间限制** (整个 subagent 从开始到结束的最大时长)
   - **当前用法**: 被错误地当作 `step_timeout` (单步超时)

2. **`step_timeout`** (在 `SubAgent` 类中):
   - **预期语义**: 单个步骤的超时时间
   - **当前接收**: 错误地接收了 `max_execution_time` 的值

### 影响

- SubAgent 的总执行时间限制未被正确应用
- SubAgent 的单步超时被错误地设置为总执行时间的值
- 例如: `research` subagent 的 `step_timeout` 被设置为 90 秒,但这个值实际上应该是总执行时间限制

## 修复方案

### 方案 1: 添加 `step_timeout` 参数 (推荐)

在 `subagents.json` 中添加明确的 `step_timeout` 参数:

```json
{
  "research": {
    "runtime_limits": {
      "max_execution_time": 90,    // 总执行时间限制
      "step_timeout": 30,           // 新增:单步超时
      "recursion_limit": 60
    }
  }
}
```

然后在代码中正确传递:

```python
runtime_limits = config["runtime_limits"]
recursion_limit = runtime_limits.get("recursion_limit")
max_execution_time = runtime_limits.get("max_execution_time")
step_timeout = runtime_limits.get("step_timeout")  # 新增

subagent_spec = SubAgent(
    ...
    recursion_limit=recursion_limit,
    step_timeout=step_timeout,              # 传递 step_timeout
    max_execution_time=max_execution_time,  # 新增: 传递 max_execution_time
    ...
)
```

### 方案 2: 重命名配置参数

如果 `max_execution_time` 的真实语义就是单步超时,则应该:

1. 在 `subagents.json` 中重命名为 `step_timeout`
2. 在代码中直接使用 `step_timeout`

## 相关修改

- **MainAgent** 的 `max_execution_time` 问题已在本次修复中解决
- **SubAgent** 的问题需要在后续单独修复

## SubAgent 数据结构

`SubAgent` dataclass 当前定义 ([runtime_middlewares/__init__.py:32-47](../src/components/deepagents/runtime_middlewares/__init__.py#L32-L47)):

```python
@dataclass(slots=True)
class SubAgent:
    """Lightweight spec used to describe a subagent to the orchestrator."""

    name: str
    description: str
    system_prompt: str
    tools: Sequence[Any] = field(default_factory=list)
    model: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    recursion_limit: Optional[int] = None
    step_timeout: Optional[float] = None  # ← 当前接收 max_execution_time 的值
    middleware: Sequence[Any] = field(default_factory=list)
    checkpointer: Optional[Any] = None
    display_config: Dict[str, Any] = field(default_factory=dict)
```

**建议添加**:
```python
max_execution_time: Optional[float] = None  # 新增字段
```

## 实施 SubAgent 的 max_execution_time

SubAgent 也需要使用 `ExecutionTimeoutMiddleware` 来实现总执行时间限制:

1. 在创建 subagent 时,将 `ExecutionTimeoutMiddleware` 添加到其 middleware 列表中
2. 位置: `runtime_middlewares/__init__.py` 的 `SubAgentMiddleware._create_subagent_runnables()` 方法

```python
# 在 _create_subagent_runnables 方法中添加:
if subagent_spec.max_execution_time:
    # 添加执行超时 middleware
    from .timeout import ExecutionTimeoutMiddleware
    timeout_middleware = ExecutionTimeoutMiddleware(
        max_execution_time=subagent_spec.max_execution_time
    )
    combined_middleware.insert(0, timeout_middleware)
```

## 待办事项

- [ ] 决定 `subagents.json` 中 `max_execution_time` 的真实语义
- [ ] 更新 `subagents.json` 配置结构
- [ ] 更新 `SubAgent` dataclass,添加 `max_execution_time` 字段
- [ ] 修改 `BaseDeepAgentFactory._build_subagent_specs()` 方法
- [ ] 在 `SubAgentMiddleware._create_subagent_runnables()` 中应用 ExecutionTimeoutMiddleware
- [ ] 添加测试验证修复

## 参考

- MainAgent max_execution_time 修复: [本次提交]
- ExecutionTimeoutMiddleware 实现: [runtime_middlewares/timeout.py](../src/components/deepagents/runtime_middlewares/timeout.py)
