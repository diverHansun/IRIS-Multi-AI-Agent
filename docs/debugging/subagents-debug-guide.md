# SubAgents 调试指南

## 概述
本文档说明在 Deep Agent 模式下使用 task 工具调用 subagents 时需要添加的调试点，以便快速定位问题。

## SubAgents 执行流程

```
用户查询
  ↓
Main Agent (DeepAgent)
  ↓
调用 task 工具
  ↓
SubAgentMiddleware.invoke_task()
  ↓
Subagent.ainvoke()
  ↓
返回结果给 Main Agent
```

## 关键调试点及其含义

### 1. 错误捕获点 - Main Loop
**文件**: `src/application/cli/main.py:132-133`

**当前代码**:
```python
except Exception as exc:
    ctx.console.print(f"[bold red]Conversation error: {exc}")
```

**问题**: 只显示异常消息，缺少：
- 异常类型
- 完整堆栈跟踪
- 错误上下文

**此处错误表示**:
- 整个对话流程中的任何未捕获异常
- 包括 subagent 执行失败、超时、API 错误等

**建议添加**:
```python
except Exception as exc:
    import traceback
    ctx.console.print(f"[bold red]Conversation error ({type(exc).__name__}): {exc}")
    logger.error("Conversation error details:", exc_info=True)
    if ctx.debug:
        ctx.console.print(f"[dim]{traceback.format_exc()}[/dim]")
```

---

### 2. Subagent 创建阶段
**文件**: `src/components/deepagents/runtime_middlewares/__init__.py:162-236`

**方法**: `SubAgentMiddleware._create_subagent_runnables()`

**此阶段问题表示**:
- Subagent 配置错误（模型、工具、中间件配置）
- LLM 模型初始化失败
- 工具过滤逻辑错误
- Middleware 构建失败

**当前日志**:
```python
logger.debug(f"SubAgent '{subagent_spec.name}' configuration: ...")
```

**建议添加**:
```python
# 在 for subagent_spec in self.subagents: 循环开始
logger.info(f"[SubAgent Init] Creating subagent: {subagent_spec.name}")

# 在 create_agent 之前
logger.debug(f"[SubAgent Init] {subagent_spec.name} - Model: {subagent_model}, Tools: {len(subagent_tools)}")

# 在 create_agent 之后
logger.info(f"[SubAgent Init] {subagent_spec.name} created successfully")

# 在 except 块中添加
except Exception as e:
    logger.error(f"[SubAgent Init] Failed to create {subagent_spec.name}: {e}", exc_info=True)
    raise
```

---

### 3. Task 工具创建
**文件**: `src/components/deepagents/runtime.py:105-109`

**此阶段问题表示**:
- SubAgentMiddleware 没有创建任何 subagent
- Task 工具未被添加到主 agent 的工具列表

**建议添加**:
```python
task_tool = subagent_middleware.get_task_tool()
if task_tool:
    logger.info(f"[Runtime] Task tool created with {len(subagent_middleware._subagent_runnables)} subagents")
    logger.debug(f"[Runtime] Available subagents: {list(subagent_middleware._subagent_runnables.keys())}")
    tools = list(tools) if tools else []
    tools.append(task_tool)
else:
    logger.warning("[Runtime] No task tool created - no subagents available")
```

---

### 4. Subagent 调用入口
**文件**: `src/components/deepagents/runtime_middlewares/__init__.py:254-259`

**方法**: `invoke_task()` 开始

**此阶段问题表示**:
- Main agent 传递的 subagent_type 不存在
- 参数验证失败

**当前日志**:
```python
logger.info(f"[SubAgent] Main agent delegating task to '{subagent_type}' subagent")
logger.debug(f"[SubAgent] Task description: {description[:100]}...")
```

**建议添加**:
```python
# 在函数开始
logger.info(f"[SubAgent Call] Received task delegation - Type: {subagent_type}")
logger.debug(f"[SubAgent Call] Task: {description[:200]}...")
logger.debug(f"[SubAgent Call] Available: {list(self._subagent_runnables.keys())}")

# 在验证失败时
if subagent_type not in self._subagent_runnables:
    error_msg = f"Error: Unknown subagent type '{subagent_type}'. Available: {list(self._subagent_runnables.keys())}"
    logger.error(f"[SubAgent Call] {error_msg}")
    return error_msg
```

---

### 5. Subagent 执行阶段
**文件**: `src/components/deepagents/runtime_middlewares/__init__.py:265-279`

**方法**: `subagent.ainvoke()` 调用

**此阶段问题表示**:
- Subagent 内部执行错误（工具调用失败、推理错误）
- API 调用失败（网络、认证、限流）
- 超时（超过 max_execution_time）
- 消息格式不匹配
- Recursion limit 达到上限

**当前日志**:
```python
logger.info(f"[SubAgent] '{subagent_type}' completed successfully")
logger.warning(f"[SubAgent] '{subagent_type}' completed but returned no response")
logger.error(f"[SubAgent] '{subagent_type}' failed: {exc}")
```

**建议添加**:
```python
import time

subagent = self._subagent_runnables[subagent_type]
try:
    logger.info(f"[SubAgent Exec] Starting '{subagent_type}' execution")
    start_time = time.time()

    # 显示传递给 subagent 的消息格式
    input_messages = {"messages": [{"role": "user", "content": description}]}
    logger.debug(f"[SubAgent Exec] Input format: {type(input_messages)}")

    result = await subagent.ainvoke(input_messages)

    elapsed = time.time() - start_time
    logger.info(f"[SubAgent Exec] '{subagent_type}' completed in {elapsed:.2f}s")

    # 显示返回的结果结构
    logger.debug(f"[SubAgent Exec] Result keys: {result.keys() if isinstance(result, dict) else type(result)}")

    messages = result.get("messages", [])
    if messages:
        response = messages[-1].content if hasattr(messages[-1], 'content') else str(messages[-1])
        logger.info(f"[SubAgent Exec] Response length: {len(response)} chars")
        logger.debug(f"[SubAgent Exec] Response preview: {response[:200]}...")
        return response
    logger.warning(f"[SubAgent Exec] '{subagent_type}' returned empty messages")
    return "SubAgent completed but returned no response."

except TimeoutError as exc:
    elapsed = time.time() - start_time
    error_msg = f"SubAgent '{subagent_type}' timed out after {elapsed:.2f}s: {exc}"
    logger.error(f"[SubAgent Exec] {error_msg}")
    return error_msg

except Exception as exc:
    elapsed = time.time() - start_time
    error_msg = f"SubAgent '{subagent_type}' failed after {elapsed:.2f}s: {exc}"
    logger.error(f"[SubAgent Exec] {error_msg}", exc_info=True)
    return error_msg
```

---

### 6. Event Handler - Task 工具调用跟踪
**文件**: `src/application/services/agent/deep/event_handler.py:150-163`

**方法**: `_track_tool_usage()` 和 `_record_subagent_call()`

**此阶段问题表示**:
- Main agent 调用了 task 工具但没有记录
- 无法追踪哪些 subagent 被调用

**当前实现**: 已经在记录，但可以增强

**建议添加**:
```python
def _track_tool_usage(self, messages: Sequence[BaseMessage]) -> None:
    for message in messages:
        if isinstance(message, AIMessage) and message.tool_calls:
            self._tool_call_count += len(message.tool_calls)
            for call in message.tool_calls:
                name = call.get("name")
                if name:
                    self._tool_names.add(name)

                    # 特别记录 task 工具调用
                    if name == "task":
                        logger.info(f"[EventHandler] Detected task tool call: {call.get('id')}")

                    if self.show_subagent_delegations and name == "task":
                        args = call.get("args", {}) if isinstance(call, dict) else {}
                        self._record_subagent_call(call, args)
```

---

### 7. Conversation Handler - 超时检测
**文件**: `src/application/services/agent/deep/conversation.py:104-106`

**此阶段问题表示**:
- Subagent 执行时间超过 max_execution_time
- 整体流程超时

**当前实现**:
```python
if deadline is not None and time.perf_counter() > deadline:
    timed_out = True
    break
```

**建议添加**:
```python
if deadline is not None and time.perf_counter() > deadline:
    elapsed = time.perf_counter() - (deadline - max_execution_time)
    logger.error(f"[Conversation] Execution timed out after {elapsed:.2f}s (limit: {max_execution_time}s)")
    logger.debug(f"[Conversation] Last event: {event}")
    timed_out = True
    break
```

---

## 调试流程决策树

```
运行时出现 "Conversation error"
    ↓
检查日志中是否有 "[SubAgent Call] Received task delegation"
    ↓
    ├─ 没有 → Main agent 没有调用 task 工具
    │           检查: Task 工具是否创建成功 (Runtime 日志)
    │                 Main agent 的 system prompt 是否包含 subagent 说明
    │
    └─ 有 → 继续检查
        ↓
    检查 "[SubAgent Exec] Starting" 日志
        ↓
        ├─ 没有 → subagent_type 验证失败或找不到 subagent
        │           检查: 可用的 subagent 列表
        │                 Subagent 创建日志
        │
        └─ 有 → 继续检查
            ↓
        检查是否有 "[SubAgent Exec] completed" 日志
            ↓
            ├─ 没有 → Subagent 执行中出错
            │           检查完整异常堆栈
            │           可能原因:
            │           - API 调用失败 (网络/认证)
            │           - 工具执行错误
            │           - 超时
            │           - Recursion limit
            │           - 消息格式错误
            │
            └─ 有 → Subagent 执行成功
                    检查返回结果格式
                    检查 Main agent 如何处理返回结果
```

---

## 快速诊断命令

### 1. 检查 Subagent 配置
```bash
# 查看 subagent 配置文件
cat config/agents/deep/models/subagents.json
```

### 2. 启用调试日志
```python
# 在运行前设置环境变量
export PYTHONUNBUFFERED=1
export LOG_LEVEL=DEBUG
```

### 3. 检查日志文件
```bash
# 过滤 subagent 相关日志
grep -i "subagent" logs/app.log | tail -100

# 查看错误日志
grep -i "error" logs/app.log | grep -i "subagent"
```

---

## 常见问题模式

### Pattern 1: Subagent 未创建
**症状**: 没有 "[SubAgent Init]" 日志
**原因**:
- config/agents/deep/models/subagents.json 文件不存在或为空
- SubagentManager 初始化失败
- 配置文件格式错误

### Pattern 2: Task 工具未添加
**症状**: 有 "[SubAgent Init]" 但没有 "[Runtime] Task tool created"
**原因**:
- `get_task_tool()` 返回 None
- `_subagent_runnables` 为空

### Pattern 3: Subagent 调用失败
**症状**: 有 "[SubAgent Call]" 但没有 "[SubAgent Exec] completed"
**原因**:
- API 调用失败（最常见）
- 超时
- 工具执行错误
- 消息格式不匹配

### Pattern 4: 长时间等待后超时
**症状**: 从 "Calling tools [task]" 到 "Conversation error" 之间等待很久
**原因**:
- Subagent 内部递归执行
- 工具调用链过长
- API 响应慢
- 达到 max_execution_time (300s)

---

## 总结

**最关键的 3 个调试点**:
1. **Main Loop 异常捕获** - 显示完整错误信息和堆栈
2. **Subagent 执行阶段** - 记录开始、结束、耗时、异常详情
3. **消息格式和返回值** - 确保数据流转正确

**调试优先级**:
1. 先确保看到完整的错误信息（修改 main.py:133）
2. 再添加 subagent 执行阶段的详细日志
3. 最后根据具体错误添加其他调试点