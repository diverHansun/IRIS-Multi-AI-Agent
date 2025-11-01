# 虚拟文件系统工具未注册问题分析

## 问题现象

Agent创建后,虚拟文件系统的4个工具(list_virtual_files, read_virtual_file, write_virtual_file, edit_virtual_file)**未被注册**到agent。

实际测试显示:
- Agent总共有126个工具
- 但是没有虚拟文件系统的4个工具
- 有MCP的文件系统工具(mcp_read_file, mcp_write_file等)

## 根本原因

**工具注入的时序问题**

### 当前流程:

1. **Factory** (base.py:57-62)
   ```python
   tools = user_params.get("tools")
   if not tools:
       tool_manager = UnifiedToolManager(auto_register_defaults=True)
       await tool_manager.initialize_all()
       tools = tool_manager.get_all_tools()  # ← 126个工具
   ```

2. **Factory调用Runtime** (base.py:86-89)
   ```python
   runtime = create_deep_agent_runtime(
       model=adapter.get_model_identifier(),
       system_prompt=system_prompt,
       tools=tools,  # ← 传递了已经确定的126个工具
       ...
   )
   ```

3. **Runtime尝试注入** (runtime.py:65-68)
   ```python
   filesystem_tools = filesystem_middleware.get_tools()  # ← 4个工具
   if filesystem_tools:
       tools = list(tools) if tools else []
       tools.extend(filesystem_tools)  # ← 将4个工具添加到tools
   ```

4. **问题**: Runtime修改的`tools`变量是**局部的**,factory传递进来的原始`tools`列表不会被修改!

### 为什么工具没有注入?

Python的参数传递机制:
```python
# Factory中
tools = [1, 2, 3]  # 126个工具
runtime = create_deep_agent_runtime(tools=tools)

# Runtime中
def create_deep_agent_runtime(tools=None):
    tools = list(tools) if tools else []  # ← 创建新列表!
    tools.extend([4, 5])  # ← 修改的是新列表,不是factory的原始列表
    # factory的tools仍然是[1, 2, 3]
```

**关键**: 第67行的`tools = list(tools) if tools else []`创建了一个**新列表**,后续的修改不会影响factory传递进来的原始tools列表。

## 解决方案

有3个可能的解决方案:

### 方案1: 在Factory中注入虚拟文件系统工具 (推荐)

在factory获取tools之后,创建runtime之前注入:

```python
# base.py:86之前
tools = user_params.get("tools")
if not tools:
    tool_manager = UnifiedToolManager(auto_register_defaults=True)
    await tool_manager.initialize_all()
    tools = tool_manager.get_all_tools()

# 注入虚拟文件系统工具
from src.components.deepagents.runtime_middlewares.virtual_filesystem import VirtualFilesystemMiddleware
filesystem_middleware = VirtualFilesystemMiddleware(
    long_term_memory=resolved_middleware.get("filesystem", {}).get("long_term_memory", False),
    tool_token_limit_before_evict=resolved_middleware.get("filesystem", {}).get("tool_token_limit_before_evict"),
)
filesystem_tools = filesystem_middleware.get_tools()
if filesystem_tools:
    tools.extend(filesystem_tools)

# 然后调用runtime
runtime = create_deep_agent_runtime(tools=tools, ...)
```

### 方案2: Runtime返回修改后的tools

让runtime返回修改后的tools列表:

```python
# runtime.py
def create_deep_agent_runtime(...):
    # ... existing code ...
    
    filesystem_tools = filesystem_middleware.get_tools()
    if filesystem_tools:
        tools = list(tools) if tools else []
        tools.extend(filesystem_tools)
    
    # ... create agent ...
    
    return agent_graph, tools  # ← 返回修改后的tools

# factory中
runtime, updated_tools = create_deep_agent_runtime(...)
tools = updated_tools
```

### 方案3: Runtime直接修改传入的列表

不创建新列表,直接修改:

```python
# runtime.py:65-68
filesystem_tools = filesystem_middleware.get_tools()
if filesystem_tools:
    if not tools:
        tools = []
    tools.extend(filesystem_tools)  # ← 直接修改,不创建新列表
```

但这要求factory传递一个可变列表,并且不要在runtime调用后继续使用原始列表。

## 推荐方案

**方案1**最清晰且最安全:
- 在factory层面完全控制工具列表
- 不依赖runtime的副作用
- 易于理解和维护

## 验证方法

修改后,运行测试:
```python
agent = await deep_agent_manager.create_deep_agent(
    provider='zhipu',
    model='glm-4.6',
    function_type='research'
)

info = agent.get_info()
tools = info['tools']

# 检查虚拟文件系统工具
assert 'list_virtual_files' in tools
assert 'read_virtual_file' in tools
assert 'write_virtual_file' in tools
assert 'edit_virtual_file' in tools
```

## 影响范围

当前所有使用factory创建的agent都**没有**虚拟文件系统工具,需要修复才能让agent使用虚拟文件系统。
