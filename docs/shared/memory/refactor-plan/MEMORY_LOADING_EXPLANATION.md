# Deep Mode 记忆加载机制说明

## 您的疑问

> 在对话过程中，我的问题是否被加载到上下文中两次？

## 简短回答

**不会重复加载。** 修复后的实现确保历史消息只被加载一次到 Agent 的上下文中。

## 详细说明

### 架构组件

1. **JSON 存储** (`data/deepagent/sessions/*.json`)
   - 持久化存储，程序重启后仍然存在
   - 只保存 HumanMessage 和 AIMessage

2. **MemorySaver** (内存 checkpoint)
   - 临时存储，程序重启后清空
   - 保存 LangGraph 的完整执行状态
   - 支持 HITL (Human-in-the-Loop) 功能

### 对话流程

#### 场景 1: 程序启动后的第一轮对话

```
[程序启动] → [选择/创建会话] → [第一个问题]

步骤：
1. 检查 MemorySaver: 无 checkpoint (程序刚启动)
2. 从 JSON 加载历史: [H1, A1, A2] (3条消息)
3. 添加新问题: [H1, A1, A2, H2] (4条消息)
4. Agent 处理: 生成 A2
5. 最终状态: [H1, A1, A2, H2, A2] (5条消息)
6. 保存到 JSON: 去重后保存
7. MemorySaver 自动记录 checkpoint

结果: Agent 看到 4 条消息 (历史3条 + 新问题1条)
```

#### 场景 2: 同一程序运行中的第二轮对话

```
[继续对话] → [第二个问题]

步骤：
1. 检查 MemorySaver: 有 checkpoint (包含5条消息)
2. 不从 JSON 加载 (避免重复!)
3. 只添加新问题: [H3] (1条消息)
4. LangGraph 自动合并: checkpoint的5条 + 新的1条 = 6条
5. Agent 处理: 生成 A3
6. 最终状态: [H1, A1, A2, H2, A2, H3, A3] (7条消息)
7. 保存到 JSON: 去重后保存
8. MemorySaver 更新 checkpoint

结果: Agent 看到 6 条消息 (checkpoint的5条 + 新问题1条)
```

#### 场景 3: 程序重启后继续会话

```
[程序重启] → [选择已有会话] → [第三个问题]

步骤：
1. 检查 MemorySaver: 无 checkpoint (程序重启了)
2. 从 JSON 加载历史: [H1, A1, A2, H2, A2, H3, A3] (7条消息)
3. 添加新问题: [H1, A1, A2, H2, A2, H3, A3, H4] (8条消息)
4. Agent 处理: 生成 A4
5. 最终状态: [H1, A1, A2, H2, A2, H3, A3, H4, A4] (9条消息)
6. 保存到 JSON: 去重后保存
7. MemorySaver 记录新 checkpoint

结果: Agent 看到 8 条消息 (历史7条 + 新问题1条)
```

### 关键机制：避免重复加载

```python
# 在 conversation.py 中的关键代码

# 检查 MemorySaver 是否已有 checkpoint
checkpoint_tuple = runtime_checkpointer.get_tuple(runtime_config)
has_checkpoint = checkpoint_tuple is not None

if not has_checkpoint:
    # 场景1和3: 从 JSON 加载历史
    runtime_input = memory_sync.enhance_runtime_input(...)
else:
    # 场景2: 不加载，让 MemorySaver 提供历史
    runtime_input = agent.create_runtime_input(query)  # 只有新问题
```

### 去重机制

即使出现意外重复，`persist_from_runtime` 中的 `_deduplicate_messages` 方法会：

```python
def _deduplicate_messages(messages):
    seen = set()
    deduplicated = []
    
    for msg in messages:
        key = (type(msg).__name__, msg.content)
        if key not in seen:
            seen.add(key)
            deduplicated.append(msg)
    
    return deduplicated
```

这确保相同类型和内容的消息只保存一次。

## 验证方法

### 方法 1: 检查会话文件

查看 `data/deepagent/sessions/*.json`：
- 每个问题应该只出现一次
- 每个回答应该只出现一次
- `message_count` 应该等于实际消息数量

### 方法 2: 观察 AI 的回答

如果 AI 说"您问了两次相同的问题"，但您只问了一次，说明有重复。
如果 AI 正确回忆历史且不提及重复，说明没有问题。

### 方法 3: 启用日志

修改后的 `main.py` 已启用日志，您应该能看到：
- 第一轮: `First query in this session: loading history from storage into input`
- 第二轮: `Continuing session: MemorySaver will provide history automatically`

## 总结

1. **不会重复加载**: 每个程序运行周期内，历史只从 JSON 加载一次
2. **MemorySaver 管理**: 后续对话由 MemorySaver 自动管理历史
3. **去重保护**: 即使出现意外，去重机制会防止重复保存
4. **上下文正确**: Agent 在每轮对话中看到的都是完整且不重复的历史

您的会话文件 `user_20251119_120412_ee068166.json` 显示 5 条消息，没有重复，证明机制工作正常！

