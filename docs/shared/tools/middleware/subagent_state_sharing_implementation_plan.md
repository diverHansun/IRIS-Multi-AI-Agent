# SubAgent 状态共享实施方案

## 执行摘要

基于对 LangChain/LangGraph 依赖的深入调查和官方 DeepAgents 实现的分析,本文档提供了完整的实施方案,用于在自定义 SubAgentMiddleware 中实现虚拟文件系统状态共享。

---

## 一、技术调研结果

### 1.1 ToolRuntime 源头追踪

**导入路径**:
```python
# 最终源头
from langgraph.prebuilt import ToolRuntime

# 向后兼容的导入路径
from langchain.tools import ToolRuntime
# → 实际指向 langgraph.prebuilt.ToolRuntime
```

**定义位置**: `.venv/Lib/site-packages/langgraph/prebuilt/tool_node.py:1471`

**类型定义**:
```python
@dataclass
class ToolRuntime(_DirectlyInjectedToolArg, Generic[ContextT, StateT]):
    """Runtime context automatically injected into tools.

    Attributes:
        state: StateT - 当前图状态
        context: ContextT - 运行时上下文
        config: RunnableConfig - 可运行配置
        stream_writer: StreamWriter - 流输出写入器
        tool_call_id: str | None - 工具调用 ID
        store: BaseStore | None - 持久化存储
    """
    state: StateT
    context: ContextT
    config: RunnableConfig
    stream_writer: StreamWriter
    tool_call_id: str | None
    store: BaseStore | None
```

### 1.2 @tool 装饰器的自动注入机制

**关键发现**:
- `ToolRuntime` 继承自 `_DirectlyInjectedToolArg`
- LangGraph 会自动检测工具函数签名中的 `runtime: ToolRuntime` 参数
- 在工具执行时,LangGraph 会自动注入 `ToolRuntime` 实例
- **不需要** `Annotated` 包装器
- **不会暴露**给 LLM(LLM 只看到其他参数)

**示例**:
```python
from langchain_core.tools import tool
from langchain.tools import ToolRuntime

@tool
def my_tool(
    x: int,  # ← LLM 可见
    runtime: ToolRuntime[None, FilesystemState],  # ← 自动注入,LLM 不可见
) -> str:
    # 访问状态
    files = runtime.state.get("files", {})
    # 访问 tool_call_id
    call_id = runtime.tool_call_id
    return f"Processed {x}"
```

### 1.3 Command 对象用于状态更新

**源头**:
```python
from langgraph.types import Command
```

**用法**:
```python
from langgraph.types import Command

@tool
def my_tool(runtime: ToolRuntime) -> Command | str:
    # 返回 Command 对象进行状态更新
    return Command(
        update={
            "files": {...},  # 使用 reducer 合并
            "messages": [ToolMessage(...)],
        }
    )
```

### 1.4 虚拟文件系统配置

**配置文件**: `config/agents/deep/middleware/filesystem/virtual_filesystem.json`

```json
{
  "enabled": true,
  "long_term_memory": false,
  "tool_token_limit_before_evict": 20000
}
```

**结论**:
- ✅ 虚拟文件系统已启用
- ✅ 不使用长期内存(简化实现)
- ✅ 20k token 限制(防止状态过大)

---

## 二、官方实现分析

### 2.1 官方 SubAgentMiddleware 的关键代码

**文件**: `deepagents/libs/deepagents/deepagents/middleware/subagents.py`

#### 2.1.1 排除键定义

```python
# Line 63
_EXCLUDED_STATE_KEYS = ("messages", "todos")
```

**含义**:
- `messages` 和 `todos` 不会传递给 subagent
- **`files` 不在排除列表中**,会被传递!

#### 2.1.2 状态准备函数

```python
# Lines 324-330
def _validate_and_prepare_state(
    subagent_type: str,
    description: str,
    runtime: ToolRuntime
) -> tuple[Runnable, dict]:
    """准备 subagent 调用的状态 - 创建状态拷贝。"""
    subagent = subagent_graphs[subagent_type]

    # 🔑 核心:拷贝所有状态,除了 messages 和 todos
    subagent_state = {
        k: v for k, v in runtime.state.items()
        if k not in _EXCLUDED_STATE_KEYS
    }

    # 创建新的 messages 列表
    subagent_state["messages"] = [HumanMessage(content=description)]

    return subagent, subagent_state
```

#### 2.1.3 状态合并函数

```python
# Lines 315-322
def _return_command_with_state_update(result: dict, tool_call_id: str) -> Command:
    """返回包含状态更新的 Command 对象。"""

    # 🔑 核心:排除 messages 和 todos,其他全部返回
    state_update = {
        k: v for k, v in result.items()
        if k not in _EXCLUDED_STATE_KEYS
    }

    return Command(
        update={
            **state_update,  # files 等状态会被 reducer 合并
            "messages": [ToolMessage(result["messages"][-1].text, tool_call_id=tool_call_id)],
        }
    )
```

#### 2.1.4 Task 工具实现

```python
# Lines 339-352
def task(
    description: str,
    subagent_type: str,
    runtime: ToolRuntime,  # ← 自动注入
) -> str | Command:
    """同步 task 工具。"""
    if subagent_type not in subagent_graphs:
        allowed_types = ", ".join([f"`{k}`" for k in subagent_graphs])
        return f"We cannot invoke subagent {subagent_type}..."

    # 1. 准备:拷贝状态(除了 messages/todos)
    subagent, subagent_state = _validate_and_prepare_state(
        subagent_type, description, runtime
    )

    # 2. 执行:使用拷贝的状态运行 subagent
    result = subagent.invoke(subagent_state)

    if not runtime.tool_call_id:
        raise ValueError("Tool call ID is required for subagent invocation")

    # 3. 合并:返回状态更新
    return _return_command_with_state_update(result, runtime.tool_call_id)
```

### 2.2 官方实现的设计模式

| 模式 | 描述 |
|------|------|
| **状态拷贝模式** | 拷贝除排除键外的所有状态给 subagent |
| **Reducer 合并模式** | 使用 LangGraph 的 reducer 自动合并状态 |
| **Command 模式** | 通过 Command 对象传递状态更新 |
| **工具注入模式** | 使用 `runtime: ToolRuntime` 自动注入状态 |
| **排除键模式** | 明确定义不共享的状态键 |

---

## 三、完整实施方案

### 3.1 修改清单

需要修改的文件:
1. ✅ `src/components/deepagents/runtime_middlewares/subagents/middleware.py` - 主要修改
2. 🔍 测试验证(可选,推荐)

### 3.2 详细实施步骤

#### 步骤 1: 导入必要依赖

**在文件顶部添加/修改导入**:

```python
from __future__ import annotations

import logging
from typing import Any, Dict, List, Sequence, Optional

from langchain.agents.middleware.types import AgentMiddleware, ModelRequest, ModelResponse
from langchain.tools import ToolRuntime  # ✅ 添加这个
from langchain_core.tools import tool  # ✅ 添加这个
from langgraph.types import Command  # ✅ 添加这个

from .types import SubAgent, CompiledSubAgent
from ..virtual_filesystem.types import FilesystemState  # ✅ 添加这个

logger = logging.getLogger(__name__)

# ✅ 添加排除键定义
_EXCLUDED_STATE_KEYS = ("messages", "todos")
```

#### 步骤 2: 添加辅助函数

**在 `SubAgentMiddleware` 类定义之前添加**:

```python
def _prepare_subagent_state(
    runtime: ToolRuntime[None, FilesystemState],
    description: str
) -> dict:
    """准备 subagent 状态:拷贝除 messages 和 todos 外的所有状态。

    Args:
        runtime: 工具运行时上下文,包含当前状态
        description: 任务描述,将作为 subagent 的初始消息

    Returns:
        准备好的 subagent 状态字典
    """
    # 拷贝状态,排除 messages 和 todos
    subagent_state = {
        k: v for k, v in runtime.state.items()
        if k not in _EXCLUDED_STATE_KEYS
    }

    # 创建新的 messages 列表,只包含任务描述
    subagent_state["messages"] = [{"role": "user", "content": description}]

    logger.debug(
        f"[SubAgent] Prepared state with keys: {list(subagent_state.keys())}, "
        f"files count: {len(subagent_state.get('files', {}))}"
    )

    return subagent_state


def _return_state_update(
    result: dict,
    tool_call_id: str
) -> Command:
    """准备状态更新 Command,包含 subagent 的文件修改。

    Args:
        result: Subagent 执行结果,包含状态更新
        tool_call_id: 工具调用 ID

    Returns:
        包含状态更新的 Command 对象
    """
    # 提取状态更新,排除 messages 和 todos
    state_update = {
        k: v for k, v in result.items()
        if k not in _EXCLUDED_STATE_KEYS
    }

    # 提取响应消息
    messages = result.get("messages", [])
    response_text = ""
    if messages:
        last_msg = messages[-1]
        response_text = last_msg.content if hasattr(last_msg, 'content') else str(last_msg)

    logger.debug(
        f"[SubAgent] State update keys: {list(state_update.keys())}, "
        f"files count: {len(state_update.get('files', {}))}"
    )

    # 返回 Command 对象进行状态合并
    return Command(
        update={
            **state_update,  # 包含 files 的修改!
            "messages": [{"role": "tool", "content": response_text, "tool_call_id": tool_call_id}],
        }
    )
```

#### 步骤 3: 重写 `get_task_tool` 方法

**完全替换现有的 `get_task_tool` 方法**:

```python
def get_task_tool(self) -> Any | None:
    """创建并返回 task 工具,用于 subagent 委托。

    使用 @tool 装饰器创建工具,自动注入 ToolRuntime 进行状态共享。

    Returns:
        Task 工具实例,如果没有可用的 subagents 则返回 None
    """
    if not self._subagent_runnables:
        return None

    # 保存 self 引用,以便在闭包中访问
    middleware_self = self

    # 构建可用 subagent 类型列表
    available_types = ", ".join(self._subagent_runnables.keys())

    # 🔑 使用 @tool 装饰器创建工具
    @tool
    async def task(
        subagent_type: str,
        description: str,
        runtime: ToolRuntime[None, FilesystemState],  # ← 自动注入!
    ) -> str | Command:
        """Delegate complex tasks to specialized subagents.

        Args:
            subagent_type: Type of subagent to use. Available types: {available_types}
            description: Detailed task description for the subagent
            runtime: Runtime context (automatically injected, not visible to LLM)

        Returns:
            Result from subagent execution
        """
        # 验证 subagent 类型
        if subagent_type not in middleware_self._subagent_runnables:
            error_msg = (
                f"Error: Unknown subagent type '{subagent_type}'. "
                f"Available: {list(middleware_self._subagent_runnables.keys())}"
            )
            logger.warning(error_msg)
            return error_msg

        # 日志记录
        logger.info(f"[SubAgent] Main agent delegating task to '{subagent_type}' subagent")
        logger.debug(f"[SubAgent] Task description: {description[:100]}...")

        subagent = middleware_self._subagent_runnables[subagent_type]

        try:
            # ✅ 步骤 1: 准备状态 - 拷贝 files,排除 messages/todos
            subagent_state = _prepare_subagent_state(runtime, description)

            # ✅ 步骤 2: 执行 subagent
            result = await subagent.ainvoke(subagent_state)

            logger.info(f"[SubAgent] '{subagent_type}' completed successfully")

            # ✅ 步骤 3: 返回 Command 进行状态合并
            if not runtime.tool_call_id:
                # 降级:如果没有 tool_call_id,只返回文本
                logger.warning(
                    f"[SubAgent] No tool_call_id available, "
                    "state updates will not be merged"
                )
                messages = result.get("messages", [])
                if messages:
                    last_msg = messages[-1]
                    return last_msg.content if hasattr(last_msg, 'content') else str(last_msg)
                return "SubAgent completed but returned no response."

            return _return_state_update(result, runtime.tool_call_id)

        except Exception as exc:
            error_msg = f"SubAgent execution failed: {exc}"
            logger.error(f"[SubAgent] '{subagent_type}' failed: {exc}", exc_info=True)
            return error_msg

    # 更新 docstring 中的可用类型
    task.__doc__ = task.__doc__.format(available_types=available_types)

    return task
```

#### 步骤 4: (可选但推荐) 添加同步版本

如果需要支持同步调用,添加同步版本的工具:

```python
def get_task_tool(self) -> Any | None:
    """创建并返回 task 工具。"""
    if not self._subagent_runnables:
        return None

    middleware_self = self
    available_types = ", ".join(self._subagent_runnables.keys())

    # 同步版本
    def task_sync(
        subagent_type: str,
        description: str,
        runtime: ToolRuntime[None, FilesystemState],
    ) -> str | Command:
        """同步版本的 task 工具。"""
        if subagent_type not in middleware_self._subagent_runnables:
            error_msg = f"Error: Unknown subagent type '{subagent_type}'..."
            logger.warning(error_msg)
            return error_msg

        logger.info(f"[SubAgent] Main agent delegating task to '{subagent_type}' (sync)")

        subagent = middleware_self._subagent_runnables[subagent_type]

        try:
            subagent_state = _prepare_subagent_state(runtime, description)
            result = subagent.invoke(subagent_state)  # ← 同步调用
            logger.info(f"[SubAgent] '{subagent_type}' completed successfully")

            if not runtime.tool_call_id:
                messages = result.get("messages", [])
                if messages:
                    last_msg = messages[-1]
                    return last_msg.content if hasattr(last_msg, 'content') else str(last_msg)
                return "SubAgent completed but returned no response."

            return _return_state_update(result, runtime.tool_call_id)

        except Exception as exc:
            error_msg = f"SubAgent execution failed: {exc}"
            logger.error(f"[SubAgent] '{subagent_type}' failed: {exc}", exc_info=True)
            return error_msg

    # 异步版本
    async def task_async(
        subagent_type: str,
        description: str,
        runtime: ToolRuntime[None, FilesystemState],
    ) -> str | Command:
        """异步版本的 task 工具。"""
        # ... (同上面的实现)
        pass

    # 使用 @tool 装饰器创建工具
    task_tool = tool(
        func=task_sync,
        coroutine=task_async,
        name="task",
        description=f"Delegate complex tasks to specialized subagents. Available types: {available_types}",
    )

    return task_tool
```

**但推荐只用异步版本**(因为你的代码已经是异步的):

```python
@tool
async def task(...) -> str | Command:
    # 只有异步实现
    pass
```

---

## 四、代码变更对比

### 4.1 关键变更总结

| 方面 | 修改前 | 修改后 |
|------|--------|--------|
| **工具创建方式** | `StructuredTool(...)` | `@tool` 装饰器 |
| **Runtime 参数** | ❌ 无 | ✅ `runtime: ToolRuntime` |
| **状态传递** | 只传递 `messages` | 传递除 `messages`/`todos` 外的所有状态 |
| **返回类型** | `str` | `str \| Command` |
| **状态合并** | ❌ 不合并 | ✅ 使用 `Command` 自动合并 |
| **虚拟文件系统** | ❌ 不共享 | ✅ 自动共享 |

### 4.2 导入语句对比

**修改前**:
```python
from typing import Any, Dict, List, Sequence, Optional
from langchain.agents.middleware.types import AgentMiddleware, ModelRequest, ModelResponse
from .types import SubAgent, CompiledSubAgent
```

**修改后**:
```python
from typing import Any, Dict, List, Sequence, Optional

from langchain.agents.middleware.types import AgentMiddleware, ModelRequest, ModelResponse
from langchain.tools import ToolRuntime  # ✅ 新增
from langchain_core.tools import tool  # ✅ 新增
from langgraph.types import Command  # ✅ 新增

from .types import SubAgent, CompiledSubAgent
from ..virtual_filesystem.types import FilesystemState  # ✅ 新增

# ✅ 新增排除键定义
_EXCLUDED_STATE_KEYS = ("messages", "todos")
```

### 4.3 invoke_task 函数对比

**修改前** (Lines 234-267):
```python
async def invoke_task(subagent_type: str, description: str) -> str:
    """Invoke a subagent to handle a specific task."""
    if subagent_type not in self._subagent_runnables:
        error_msg = f"Error: Unknown subagent type '{subagent_type}'..."
        return error_msg

    subagent = self._subagent_runnables[subagent_type]
    try:
        # ❌ 只传递 messages,不传递 files!
        result = await subagent.ainvoke({
            "messages": [{"role": "user", "content": description}]
        })

        messages = result.get("messages", [])
        if messages:
            response = messages[-1].content if hasattr(messages[-1], 'content') else str(messages[-1])
            return response  # ❌ 只返回文本,不返回状态
        return "SubAgent completed but returned no response."
    except Exception as exc:
        return f"SubAgent execution failed: {exc}"
```

**修改后**:
```python
@tool
async def task(
    subagent_type: str,
    description: str,
    runtime: ToolRuntime[None, FilesystemState],  # ✅ 添加 runtime
) -> str | Command:  # ✅ 返回 Command
    """Delegate complex tasks to specialized subagents."""
    if subagent_type not in middleware_self._subagent_runnables:
        error_msg = f"Error: Unknown subagent type '{subagent_type}'..."
        return error_msg

    subagent = middleware_self._subagent_runnables[subagent_type]
    try:
        # ✅ 拷贝状态,包括 files!
        subagent_state = _prepare_subagent_state(runtime, description)

        # 执行 subagent
        result = await subagent.ainvoke(subagent_state)

        # ✅ 返回 Command 进行状态合并
        if not runtime.tool_call_id:
            # 降级处理
            messages = result.get("messages", [])
            if messages:
                last_msg = messages[-1]
                return last_msg.content if hasattr(last_msg, 'content') else str(last_msg)
            return "SubAgent completed but returned no response."

        return _return_state_update(result, runtime.tool_call_id)

    except Exception as exc:
        return f"SubAgent execution failed: {exc}"
```

---

## 五、测试验证方案

### 5.1 单元测试

创建测试文件: `tests/unit/test_subagent_state_sharing.py`

```python
import pytest
from unittest.mock import Mock, AsyncMock
from src.components.deepagents.runtime_middlewares.subagents.middleware import (
    _prepare_subagent_state,
    _return_state_update,
    _EXCLUDED_STATE_KEYS,
)
from src.components.deepagents.runtime_middlewares.virtual_filesystem.types import FileData


def test_excluded_state_keys():
    """验证排除键定义。"""
    assert "messages" in _EXCLUDED_STATE_KEYS
    assert "todos" in _EXCLUDED_STATE_KEYS
    assert "files" not in _EXCLUDED_STATE_KEYS  # files 应该被共享!


def test_prepare_subagent_state():
    """测试状态准备函数。"""
    # 模拟 runtime
    runtime = Mock()
    runtime.state = {
        "messages": ["msg1", "msg2"],
        "todos": ["todo1"],
        "files": {
            "/workspace/shared/test.txt": FileData(
                content=["test content"],
                created_at="2024-01-01T00:00:00",
                modified_at="2024-01-01T00:00:00"
            )
        },
        "custom_state": "value"
    }

    description = "Test task"

    # 执行
    result = _prepare_subagent_state(runtime, description)

    # 验证
    assert "messages" in result
    assert result["messages"] == [{"role": "user", "content": description}]
    assert "todos" not in result  # 排除
    assert "files" in result  # 包含!
    assert result["files"] == runtime.state["files"]
    assert "custom_state" in result


def test_return_state_update():
    """测试状态更新返回函数。"""
    # 模拟 subagent 结果
    result = {
        "messages": [
            Mock(content="Task completed", role="ai")
        ],
        "todos": ["new_todo"],
        "files": {
            "/workspace/shared/result.txt": FileData(
                content=["result"],
                created_at="2024-01-01T00:00:00",
                modified_at="2024-01-01T00:00:00"
            )
        },
    }

    tool_call_id = "test-call-id"

    # 执行
    command = _return_state_update(result, tool_call_id)

    # 验证
    assert hasattr(command, "update")
    update = command.update

    assert "messages" in update
    assert update["messages"][0]["tool_call_id"] == tool_call_id
    assert update["messages"][0]["content"] == "Task completed"

    assert "todos" not in update  # 排除
    assert "files" in update  # 包含!
    assert "/workspace/shared/result.txt" in update["files"]
```

### 5.2 集成测试

创建测试文件: `tests/integration/test_virtual_filesystem_sharing.py`

```python
import pytest
from src.components.deepagents.runtime import create_deep_agent_runtime


@pytest.mark.asyncio
async def test_virtual_filesystem_sharing_between_main_and_subagent():
    """端到端测试:虚拟文件系统在 main agent 和 subagent 之间共享。"""

    # 创建 runtime
    runtime = create_deep_agent_runtime(
        model="gpt-4",
        system_prompt="Test assistant",
        tools=[],
        middleware_config={
            "filesystem": {
                "virtual": {"enabled": True}
            }
        },
        subagents=[
            {
                "name": "worker",
                "description": "Worker subagent",
                "system_prompt": "You are a worker agent",
                "tools": [],
            }
        ],
    )

    # 步骤 1: Main agent 写入文件
    result1 = await runtime.ainvoke({
        "messages": [{
            "role": "user",
            "content": "Write 'Hello from main agent' to /workspace/shared/test.txt"
        }]
    })

    # 验证文件已创建
    state1 = result1
    assert "files" in state1
    assert "/workspace/shared/test.txt" in state1["files"]

    # 步骤 2: Main agent 调用 subagent,让它读取并修改文件
    result2 = await runtime.ainvoke({
        "messages": result1["messages"] + [{
            "role": "user",
            "content": """
            Use the task tool to delegate to the 'worker' subagent:
            - Read /workspace/shared/test.txt
            - Append ' + Hello from subagent'
            - Write to /workspace/shared/result.txt
            """
        }]
    })

    # 验证 subagent 创建了新文件
    state2 = result2
    assert "files" in state2
    assert "/workspace/shared/result.txt" in state2["files"]

    # 步骤 3: Main agent 读取结果
    result3 = await runtime.ainvoke({
        "messages": result2["messages"] + [{
            "role": "user",
            "content": "Read /workspace/shared/result.txt and tell me what it says"
        }]
    })

    # 验证 main agent 能读取 subagent 创建的文件
    final_message = result3["messages"][-1].content
    assert "Hello from main agent" in final_message
    assert "Hello from subagent" in final_message


@pytest.mark.asyncio
async def test_file_data_reducer_merging():
    """测试文件数据 reducer 正确合并状态。"""
    from src.components.deepagents.runtime_middlewares.virtual_filesystem.types import (
        _file_data_reducer,
        FileData,
    )

    # 初始状态(main agent)
    current = {
        "/file1.txt": FileData(
            content=["line1"],
            created_at="2024-01-01T00:00:00",
            modified_at="2024-01-01T00:00:00"
        ),
    }

    # Subagent 的更新
    updates = {
        "/file1.txt": FileData(  # 修改现有文件
            content=["line1", "line2"],
            created_at="2024-01-01T00:00:00",
            modified_at="2024-01-02T00:00:00"
        ),
        "/file2.txt": FileData(  # 新增文件
            content=["new file"],
            created_at="2024-01-02T00:00:00",
            modified_at="2024-01-02T00:00:00"
        ),
    }

    # 合并
    merged = _file_data_reducer(current, updates)

    # 验证
    assert "/file1.txt" in merged
    assert len(merged["/file1.txt"]["content"]) == 2  # 已更新
    assert "/file2.txt" in merged  # 新增的文件
```

### 5.3 手动测试场景

**场景 1: 简单的文件共享**

```
User: Write "test data" to /workspace/shared/input.txt
Main Agent: [writes file]

User: Use task tool with worker subagent to read /workspace/shared/input.txt and write the uppercase version to /workspace/shared/output.txt
Main Agent: [calls task tool]
  → SubAgent: [reads input.txt, writes output.txt]
  → Returns to Main Agent

User: Read /workspace/shared/output.txt
Main Agent: [reads file]
Expected: "TEST DATA"
```

**场景 2: 多个 subagent 协作**

```
User: Write this JSON data to /workspace/shared/data.json: {"numbers": [1,2,3,4,5]}
Main Agent: [writes file]

User: Use analyzer subagent to calculate the sum and write to /workspace/shared/sum.txt
Main Agent: [calls analyzer subagent]
  → SubAgent: [reads data.json, calculates sum=15, writes sum.txt]

User: Use reporter subagent to read /workspace/shared/sum.txt and create a report in /workspace/shared/report.txt
Main Agent: [calls reporter subagent]
  → SubAgent: [reads sum.txt, creates report.txt]

User: Read /workspace/shared/report.txt
Main Agent: [reads file]
Expected: Report containing "Sum: 15"
```

---

## 六、潜在问题和解决方案

### 6.1 问题: 状态过大导致性能问题

**症状**:
- 拷贝大量文件时内存占用高
- Subagent 调用变慢

**解决方案**:
1. **启用 token 限制**:
   - 配置已设置 `tool_token_limit_before_evict: 20000`
   - 自动清理大文件

2. **只传递必要的文件**:
   ```python
   # 可以扩展为只拷贝特定目录的文件
   def _prepare_subagent_state_selective(runtime, description, include_paths=None):
       subagent_state = {...}
       if include_paths:
           subagent_state["files"] = {
               path: data for path, data in runtime.state.get("files", {}).items()
               if any(path.startswith(p) for p in include_paths)
           }
       return subagent_state
   ```

3. **监控和日志**:
   ```python
   logger.debug(
       f"State size: {len(str(subagent_state))} chars, "
       f"files count: {len(subagent_state.get('files', {}))}"
   )
   ```

### 6.2 问题: 文件冲突

**症状**:
- Main agent 和 subagent 同时修改同一个文件
- 最后一次修改覆盖之前的修改

**解决方案**:
1. **使用唯一文件名**:
   ```python
   # 使用时间戳或任务 ID
   file_path = f"/workspace/shared/task_{task_id}_result.txt"
   ```

2. **使用不同的目录**:
   ```python
   # Main agent 使用 /workspace/main/
   # Subagent 使用 /workspace/subagent_{name}/
   ```

3. **文档约定**:
   - 更新系统提示,明确文件命名约定
   - 教育 agent 避免覆盖文件

### 6.3 问题: runtime.tool_call_id 为 None

**症状**:
- 某些情况下 `runtime.tool_call_id` 可能为 `None`
- 无法返回 `Command` 对象

**解决方案**:
```python
if not runtime.tool_call_id:
    logger.warning(
        "[SubAgent] No tool_call_id available, "
        "returning text response instead of Command"
    )
    # 降级:只返回文本
    return response_text
```

已在实现中包含此降级逻辑。

### 6.4 问题: 导入错误

**症状**:
- `from ..virtual_filesystem.types import FilesystemState` 导入失败

**解决方案**:
1. **检查相对导入路径**:
   ```python
   # 当前文件: src/components/deepagents/runtime_middlewares/subagents/middleware.py
   # 目标文件: src/components/deepagents/runtime_middlewares/virtual_filesystem/types.py
   # 正确导入: from ..virtual_filesystem.types import FilesystemState
   ```

2. **如果仍然失败,使用绝对导入**:
   ```python
   from src.components.deepagents.runtime_middlewares.virtual_filesystem.types import FilesystemState
   ```

---

## 七、部署检查清单

部署前请确认:

- [ ] **代码修改完成**
  - [ ] 添加了必要的导入
  - [ ] 定义了 `_EXCLUDED_STATE_KEYS`
  - [ ] 实现了 `_prepare_subagent_state` 函数
  - [ ] 实现了 `_return_state_update` 函数
  - [ ] 重写了 `get_task_tool` 方法

- [ ] **日志和调试**
  - [ ] 添加了适当的日志记录
  - [ ] 日志级别设置正确(DEBUG 用于开发,INFO 用于生产)

- [ ] **错误处理**
  - [ ] 处理了 `tool_call_id` 为 `None` 的情况
  - [ ] 添加了异常捕获和错误消息
  - [ ] 降级策略已实现

- [ ] **测试**
  - [ ] 运行了单元测试
  - [ ] 运行了集成测试
  - [ ] 手动测试了至少一个完整场景

- [ ] **文档**
  - [ ] 更新了代码注释
  - [ ] 记录了变更
  - [ ] 更新了用户文档(如果需要)

- [ ] **兼容性**
  - [ ] 确认虚拟文件系统已启用
  - [ ] 检查了与现有代码的兼容性
  - [ ] 验证了不会破坏现有功能

---

## 八、回滚计划

如果实施后出现问题,回滚步骤:

1. **保存当前版本**:
   ```bash
   git add src/components/deepagents/runtime_middlewares/subagents/middleware.py
   git commit -m "feat: implement state sharing in SubAgentMiddleware"
   ```

2. **如果需要回滚**:
   ```bash
   git revert HEAD
   ```

3. **或者恢复到特定版本**:
   ```bash
   git checkout <previous-commit-hash> -- src/components/deepagents/runtime_middlewares/subagents/middleware.py
   ```

---

## 九、后续优化建议

实施完成后,可以考虑的优化:

1. **性能优化**
   - 实现增量状态拷贝(只拷贝变更)
   - 添加状态压缩
   - 实现文件延迟加载

2. **功能增强**
   - 可配置的排除键
   - 选择性文件共享(指定目录)
   - 文件版本控制
   - 冲突检测和解决

3. **监控和分析**
   - 状态大小监控
   - 性能指标收集
   - 文件访问模式分析

4. **测试覆盖**
   - 压力测试(大量文件)
   - 并发测试(多个 subagent)
   - 边界测试(空状态、无 files 等)

---

## 十、实施时间表

建议的实施步骤和时间:

| 步骤 | 任务 | 预计时间 |
|------|------|----------|
| 1 | 代码修改 | 30 分钟 |
| 2 | 单元测试编写 | 20 分钟 |
| 3 | 集成测试编写 | 30 分钟 |
| 4 | 手动测试 | 20 分钟 |
| 5 | 代码审查 | 15 分钟 |
| 6 | 文档更新 | 15 分钟 |
| 7 | 部署和验证 | 10 分钟 |
| **总计** | | **~2.5 小时** |

---

## 总结

本实施方案提供了完整的技术细节和步骤,用于在自定义 `SubAgentMiddleware` 中实现虚拟文件系统的状态共享。

**核心变更**:
1. ✅ 使用 `@tool` 装饰器
2. ✅ 添加 `runtime: ToolRuntime` 参数
3. ✅ 拷贝状态(排除 messages/todos)
4. ✅ 返回 `Command` 对象
5. ✅ 利用 reducer 自动合并

**预期结果**:
- Main agent 和 subagents 可以通过虚拟文件系统共享数据
- 遵循官方 DeepAgents 的设计模式
- 保持代码简洁和可维护性

准备好开始实施了!
