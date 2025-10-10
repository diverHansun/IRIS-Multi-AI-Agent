# Memory Integration Guide

## 概述

本项目实现了基于LangChain 2025最佳实践的AI Agent记忆系统，使用`RunnableWithMessageHistory`标准模式，支持会话隔离和持久化存储。

## 架构设计

### 核心组件

```
ChatMemoryManager (统一管理器)
├── ConversationBuffer (对话缓冲区)
│   ├── 继承 BaseChatMessageHistory
│   ├── 智能消息修剪 (trim_messages)
│   └── 会话级别的消息管理
└── MemoryStorage (持久化存储)
    ├── JSON文件存储
    ├── 会话元数据管理
    └── 自动清理机制
```

### 文件职责

- **`conversation_buffer.py`**: 单个会话的消息历史管理
- **`memory_storage.py`**: 持久化存储和会话管理
- **`chat_memory.py`**: 统一的记忆管理器，Agent集成接口
- **`__init__.py`**: 模块导出接口

## 集成原理

### 1. LangChain标准集成模式

本项目使用`RunnableWithMessageHistory`包装器实现记忆功能，这是LangChain 2025推荐的标准方式：

```python
# src/memory/chat_memory.py:67-72
def create_runnable_with_history(self, runnable) -> RunnableWithMessageHistory:
    return RunnableWithMessageHistory(
        runnable,
        self.get_session_history,           # 关键：会话历史获取函数
        input_messages_key="input",
        history_messages_key="chat_history", # 提示模板中的占位符
        output_messages_key="output"
    )
```

### 2. 提示模板集成

Agent的提示模板包含`{chat_history}`占位符，会被自动填充：

```python
# src/agents/zhipu_agent.py:26-27
REACT_PROMPT_ZH = """你是一个功能强大的AI助手...

## 聊天历史
{chat_history}

## 可用工具列表
{tools}
...
```

### 3. 自动化流程

当用户调用`agent.invoke(query, session_id)`时：

1. **`RunnableWithMessageHistory`自动调用**：
   ```python
   # src/memory/chat_memory.py:39-57
   def get_session_history(self, session_id: str) -> BaseChatMessageHistory:
       # 返回对应session的ConversationBuffer实例
   ```

2. **历史消息格式化**：
   ```python
   # ConversationBuffer.messages 属性提供历史消息
   # RunnableWithMessageHistory 自动格式化为文本
   ```

3. **提示模板填充**：
   ```
   {chat_history} → "human: 我的名字是张三\nai: 你好张三！"
   ```

4. **Agent推理**：基于完整上下文（历史+当前输入）进行推理

5. **自动保存**：新的对话自动添加到历史中

## 关键实现细节

### 会话隔离

```python
# src/memory/chat_memory.py:28-29
# 每个session_id对应独立的ConversationBuffer实例
self._session_store: Dict[str, BaseChatMessageHistory] = {}
```

### 智能消息修剪

```python
# src/memory/conversation_buffer.py:120-134
def _trim_messages(self) -> None:
    if self.max_tokens:
        def token_counter(messages):
            return sum(len(str(msg.content)) for msg in messages)
        
        trimmed_messages = trim_messages(
            messages=self._messages,
            max_tokens=self.max_tokens,
            token_counter=token_counter,
            strategy="last",
            start_on="human",
            include_system=self.keep_system_message
        )
```

### 持久化存储

```python
# src/memory/memory_storage.py:33-54
def save_conversation(self, session_id: str, conversation_data: List[Dict]):
    save_data = {
        "session_id": session_id,
        "conversation": conversation_data,
        "metadata": metadata or {},
        "created_at": datetime.now(timezone.utc).isoformat(),
        "message_count": len(conversation_data)
    }
    
    file_path = self.storage_dir / f"{session_id}.json"
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(save_data, f, ensure_ascii=False, indent=2)
```

## Agent集成步骤

### 1. 初始化记忆管理器

```python
# src/agents/zhipu_agent.py:133-139
def _init_memory(self, config: Dict[str, Any]) -> None:
    self.chat_memory = ChatMemoryManager(
        storage_path=config.get("storage_path"),
        max_messages=config.get("max_messages", 20),
        max_tokens=config.get("max_tokens", 4000),
        auto_save=config.get("auto_save", True)
    )
```

### 2. 创建带记忆的Agent

```python
# src/agents/zhipu_agent.py:238-248
def _build_agent_with_memory(self):
    if not self.agent_executor:
        raise ValueError("基础Agent必须先初始化")
    
    # 使用ChatMemoryManager创建带记忆的Runnable
    self.agent_with_memory = self.chat_memory.create_runnable_with_history(
        self.agent_executor
    )
```

### 3. 执行带记忆的推理

```python
# src/agents/zhipu_agent.py:278-287
if self.enable_memory and self.agent_with_memory:
    # 使用RunnableWithMessageHistory标准接口
    result = self.agent_with_memory.invoke(
        {"input": query},
        config={"configurable": {"session_id": session_id}}
    )
    
    # 保存会话到存储
    if self.chat_memory:
        self.chat_memory.save_session(session_id)
```

## 使用示例

### 基本使用

```python
# 创建带记忆的Agent
agent = await build_zhipu_agent(
    enable_memory=True,
    memory_config={
        "max_messages": 20,
        "max_tokens": 4000,
        "auto_save": True
    }
)

# 使用记忆功能
result1 = agent.invoke("我的名字是张三", session_id="user_001")
result2 = agent.invoke("你记得我的名字吗？", session_id="user_001")  # 会记住
```

### 会话管理

```python
# 清空指定会话
agent.clear_memory("user_001")

# 列出所有会话
sessions = agent.list_sessions()

# 删除会话
agent.delete_session("user_001")

# 获取记忆统计
stats = agent.get_memory_stats()
```

## 关键优势

1. **标准化**：遵循LangChain 2025最佳实践
2. **透明性**：Agent无需感知记忆存在
3. **会话隔离**：多用户支持，会话完全隔离
4. **智能管理**：自动消息修剪，避免上下文过长
5. **持久化**：会话自动保存到磁盘
6. **可扩展**：支持自定义存储后端

## 性能考虑

- **内存使用**：每个活跃会话占用一个ConversationBuffer实例
- **存储开销**：JSON文件存储，每个会话一个文件
- **Token管理**：智能修剪避免超出模型限制
- **并发安全**：单进程多会话支持

## 故障排除

### 常见问题

1. **记忆不生效**：检查`enable_memory=True`和`agent_with_memory`是否正确初始化
2. **会话混淆**：确保使用不同的`session_id`
3. **存储权限**：确保`.memory`目录有写入权限
4. **编码问题**：JSON文件使用UTF-8编码

### 调试技巧

```python
# 检查记忆状态
memory_stats = agent.get_memory_stats()
print(f"活跃会话数: {memory_stats['active_sessions']}")

# 检查会话历史
sessions = agent.list_sessions()
for session in sessions:
    print(f"会话: {session['session_id']}, 消息数: {session['message_count']}")
```

## 扩展建议

1. **自定义存储后端**：可扩展为Redis、数据库等
2. **消息摘要**：对长对话进行智能摘要
3. **多模态支持**：支持图片、文件等多媒体消息
4. **会话搜索**：实现会话内容搜索功能
5. **导出功能**：支持导出对话记录为不同格式

## 总结

本项目的记忆系统通过`RunnableWithMessageHistory`实现了与LangChain框架的深度集成，提供了透明、高效、可扩展的记忆管理解决方案。Agent无需修改任何推理逻辑，即可获得完整的上下文记忆能力。