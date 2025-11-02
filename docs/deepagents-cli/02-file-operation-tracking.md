# 文件操作追踪和Diff预览实施文档

## deepagents-cli官方代码的优点

### 1. FileOpTracker设计

官方实现了完整的文件操作追踪机制：

- **全生命周期追踪**：从工具调用开始到执行完成，全程记录操作状态
- **变更捕获**：在执行前捕获 `before_content`，执行后计算 `after_content` 和 diff
- **指标收集**：自动统计行数变化、字节数、增删行数等详细指标
- **错误处理**：记录操作失败原因，便于调试和反馈

### 2. Diff预览机制

在HITL审批前显示变更预览：

- **unified diff格式**：使用标准diff格式，便于理解变更
- **智能截断**：大文件的diff自动截断，避免显示过长
- **行数统计**：显示新增、删除的行数，快速了解变更规模
- **路径解析**：正确处理虚拟路径和物理路径的映射

### 3. UI渲染层次化

文件操作结果按层次显示：

- **操作摘要**：工具名、文件路径、操作类型
- **详细指标**：行数、字节数、增删统计
- **Diff展示**：可选的diff预览（对编辑操作）
- **状态标识**：成功、失败、进行中三种状态

### 4. ApprovalPreview结构

设计良好的预览数据结构：

- **标题和详情**：操作类型、文件路径、影响范围
- **Diff内容**：完整的变更对比
- **错误信息**：操作失败时的错误详情

## 我们现有代码的优点和不足

### 优点

1. **HITL机制已实现**：`SessionHITLManager` 和 `handle_hitl_interrupt` 已具备基本功能
2. **工具调用拦截**：可以通过中间件拦截工具调用
3. **事件处理框架**：`DeepAgentEventHandler` 可以处理流式事件
4. **双文件系统架构**：虚拟文件系统和真实文件系统已实现，职责清晰

### 不足

1. **缺少文件操作追踪**：没有专门的类来追踪文件操作的全生命周期
2. **审批预览缺失**：HITL审批时只显示工具名和参数，缺少diff预览
3. **结果展示简单**：文件操作完成后没有详细的结果摘要
4. **Diff计算缺失**：没有实现文件变更的diff计算逻辑

### 文件系统操作范围说明

**需要追踪的操作（虚拟文件系统的写操作）**：
- `write_virtual_file`：创建新文件，需要HITL审批和diff预览
- `edit_virtual_file`：编辑已有文件，需要HITL审批和diff预览

**不需要追踪的操作**：
- `read_virtual_file`：只读操作，不改变文件，无需追踪
- `list_virtual_files`：只读操作，无需追踪
- 真实文件系统的所有操作（`read_real_file`, `list_real_files`, `glob_real_files`, `grep_real_files`）：只读操作，无需追踪

**设计原则**：仅追踪会改变文件内容的操作，只读操作不需要HITL审批和diff预览。

## 实施方案

### 实施步骤

#### 第一步：创建FileOpTracker类

**文件路径**：`src/application/services/agent/deep/hitl/file_ops.py`

**核心类设计**：
- `FileOperationRecord`：记录单次文件操作的完整信息
- `FileOpMetrics`：文件操作的指标数据（行数、字节数等）
- `FileOpTracker`：追踪器主类，管理多个操作记录

**关键方法**：
- `start_operation()`：工具调用开始时记录，尝试捕获 `before_content`
  - 仅处理 `write_virtual_file` 和 `edit_virtual_file`
  - 对于 `edit_virtual_file`，尝试从当前agent状态读取文件内容（如果可访问）
  - 对于 `write_virtual_file`，`before_content` 为空（新文件）
  - 注意：如果无法在审批前获取内容（如Store中的文件），`before_content` 可能为None
- `complete_with_message()`：工具执行完成后更新记录，计算diff和指标
  - 从工具执行结果或状态更新中获取 `after_content`
  - 如果 `before_content` 之前未获取，此时尝试获取
  - 计算diff和统计指标
- `build_approval_preview()`：为HITL生成预览信息
  - 仅针对虚拟文件系统的写操作
  - 如果无法获取 `before_content`，显示基本信息（文件路径、操作类型、内容大小）

**设计考虑**：
- 由于虚拟文件系统的Store访问可能受限，`before_content` 的获取可以延迟到 `complete_with_message` 阶段
- HITL预览主要显示操作类型和文件路径，完整的diff可以在操作完成后显示

#### 第二步：实现Diff计算

**文件路径**：`src/application/services/agent/deep/hitl/file_ops.py`

**功能实现**：
- 使用 `difflib.unified_diff` 计算标准diff
- 支持截断大文件diff（如超过800行）
- 统计增删行数
- 处理 `before_content` 为空的场景（新文件）

**代码参考**：
```python
def compute_unified_diff(before: str, after: str, display_path: str, max_lines: int = 800) -> str | None:
    """计算unified diff，支持截断
    
    Args:
        before: 修改前的内容（可能为空，表示新文件）
        after: 修改后的内容
        display_path: 用于显示的路径
        max_lines: 最大显示行数
    """
    # 实现diff计算和截断逻辑
    # 对于新文件（before为空），diff显示全部为新增
```

**虚拟文件系统内容获取**：

由于虚拟文件系统不映射到物理文件系统，内容获取方式与deepagents-cli不同。需要区分两种场景：

**场景1：在Event Handler中获取（工具执行后）**

Event Handler可以通过 `_last_agent_state` 访问当前状态：

```python
from src.components.deepagents.runtime_middlewares.virtual_filesystem.utils import (
    normalize_virtual_path,
    file_data_to_string,
)
from src.components.deepagents.runtime_middlewares.virtual_filesystem.types import MEMORIES_PREFIX

# 从Event Handler的状态中获取
virtual_path = normalize_virtual_path(file_path)
is_long_term = virtual_path.startswith(MEMORIES_PREFIX)

if is_long_term:
    # 长期记忆需要从Store读取，在Event Handler中可能无法直接访问
    # 需要从工具执行结果中获取，或通过其他机制
    before_content = None  # 暂时标记，需要后续实现
else:
    # 从AgentState读取（临时文件）
    files = self._last_agent_state.get("files", {})
    file_data = files.get(virtual_path)
    if file_data:
        before_content = file_data_to_string(file_data)
```

**场景2：在HITL Handler中获取（审批前）**

HITL Handler需要从运行时状态或Store中读取，但可能无法直接访问runtime。建议方案：
- 方案A：通过HITL请求中的state信息获取（如果可用）
- 方案B：延迟读取，在工具执行时通过Event Handler获取
- 方案C：在conversation层面传递runtime引用给FileOpTracker

**实施建议**：
- 优先在Event Handler中实现内容获取（状态可访问）
- HITL预览可以简化为基本信息（文件路径、操作类型），完整diff在操作完成后显示
- Store访问可以通过agent.runtime获取（在conversation层面传递）

2. **获取 `after_content`（操作完成后）**：
   - 优先从状态更新中提取：从 `Command.update.get("files", {}).get(virtual_path)` 获取
   - 如果状态更新中没有，从Event Handler的 `_last_agent_state` 中读取
   - 长期记忆文件需要从Store重新读取最新内容

**Runtime访问方式**：
- 在 `conversation.py` 中可以访问 `agent.runtime`
- 可以将runtime传递给FileOpTracker，或通过Event Handler间接访问
- Store访问：`runtime.store.get(namespace, path)`

3. **路径处理关键点**：
   - 使用 `normalize_virtual_path()` 规范化所有路径输入
   - 长期记忆路径（`/memories/`）需要去除前缀后再访问Store
   - Store的namespace可能包含assistant_id，需要从运行时配置获取

#### 第三步：增强HITL Handler

**文件路径**：`src/application/services/agent/deep/hitl/handler.py`

**修改内容**：
- 在 `_resolve_decision` 中检测虚拟文件系统的写操作工具（`write_virtual_file`、`edit_virtual_file`）
- 如果是虚拟文件系统的写操作，调用 `build_approval_preview` 生成预览
- 在审批提示中显示预览信息，包括diff（如果存在）
- 真实文件系统的操作不需要特殊处理（只读，不会触发HITL审批）

**关键修改点**：
```python
# 需要追踪的工具名称
VIRTUAL_WRITE_TOOLS = {"write_virtual_file", "edit_virtual_file"}

# 在审批提示生成时
if tool_name in VIRTUAL_WRITE_TOOLS:
    preview = build_approval_preview(tool_name, args, assistant_id)
    if preview:
        # 显示预览信息和diff
```

**注意**：真实文件系统的工具（`read_real_file`等）不需要进入此逻辑，因为它们只读，不会触发HITL审批。

#### 第四步：增强Event Handler

**文件路径**：`src/application/services/agent/deep/streaming/event_handler.py`

**修改内容**：
- 在工具调用开始时，检测是否为虚拟文件系统的写操作工具
- 如果是，调用 `FileOpTracker.start_operation()`
  - 对于 `edit_virtual_file`，需要从虚拟文件系统状态中读取当前文件内容
  - 对于 `write_virtual_file`，`before_content` 为空
- 在工具执行完成后，调用 `FileOpTracker.complete_with_message()`
  - 从工具执行结果中提取 `after_content`（虚拟文件系统的状态更新）
  - 计算diff和指标
- 在适当时机渲染文件操作结果

**集成点**：
- `handle_event()` 方法中检测 `ToolMessage`
- 仅对虚拟文件系统的写操作工具进行追踪：
  ```python
  VIRTUAL_WRITE_TOOLS = {"write_virtual_file", "edit_virtual_file"}
  if tool_name in VIRTUAL_WRITE_TOOLS:
      # 追踪操作
  ```
- 调用UI渲染函数显示结果

#### 第五步：创建UI渲染函数

**文件路径**：`src/application/services/agent/deep/hitl/file_ops.py`（与FileOpTracker在同一文件）

**说明**：UI渲染函数与文件操作追踪紧密相关，建议放在同一文件中。这些渲染函数是deep agent HITL流程特有的，不需要放到通用的CLI GUI模块（`src/application/cli/gui/`）。

**核心函数**：
- `render_file_operation()`：渲染文件操作摘要
- `render_diff()`：使用Rich库渲染diff
- `format_file_metrics()`：格式化文件操作指标

**渲染内容**：
- 操作类型图标和名称
- 文件路径（简化显示）
- 指标信息（行数、字节数、增删统计）
- Diff内容（编辑操作时）

### 文件创建清单

1. **新建文件**：`src/application/services/agent/deep/hitl/file_ops.py`
   - 包含 `FileOpTracker` 类和相关数据结构
   - 包含UI渲染函数：`render_file_operation()`, `render_diff()`, `format_file_metrics()`

**注意**：UI渲染函数放在 `hitl/file_ops.py` 中，而不是 `src/application/cli/gui/`，因为：
- 这些渲染函数是deep agent HITL流程特有的功能
- 与 `FileOpTracker` 紧密耦合，放在同一文件便于维护
- CLI GUI模块（`gui/`）用于跨engine的通用UI组件

### 文件修改清单

1. **修改文件**：`src/application/services/agent/deep/hitl/handler.py`
2. **修改文件**：`src/application/services/agent/deep/streaming/event_handler.py`
3. **修改文件**：`src/application/services/agent/deep/streaming/conversation.py`（创建FileOpTracker实例）

### 数据结构设计

**FileOperationRecord**：
```python
@dataclass
class FileOperationRecord:
    tool_name: str  # 仅限 write_virtual_file 或 edit_virtual_file
    display_path: str  # 虚拟路径（如 /workspace/file.py 或 /memories/notes.md）
    virtual_path: str  # 规范化后的虚拟路径
    is_long_term: bool  # 是否为长期记忆路径（/memories/ 前缀）
    tool_call_id: str | None
    status: FileOpStatus  # pending, success, error
    metrics: FileOpMetrics
    diff: str | None
    before_content: str | None  # 来自虚拟文件系统状态或Store
    after_content: str | None  # 来自工具执行后的状态更新
```

**说明**：
- `virtual_path` 和 `is_long_term` 用于区分文件存储位置（State vs Store）
- 不需要 `physical_path`，因为虚拟文件系统不映射到物理文件系统

**FileOpMetrics**：
```python
@dataclass
class FileOpMetrics:
    lines_read: int = 0
    lines_written: int = 0
    lines_added: int = 0
    lines_removed: int = 0
    bytes_written: int = 0
```

### 注意事项

1. **工具名称识别**：
   - 仅追踪 `write_virtual_file` 和 `edit_virtual_file`
   - 不追踪虚拟文件系统的读操作（`read_virtual_file`, `list_virtual_files`）
   - 不追踪真实文件系统的任何操作（所有操作都是只读）

2. **虚拟文件系统路径处理**：
   - 虚拟路径使用 `/` 开头的绝对路径
   - `/memories/` 前缀表示长期记忆，存储在LangGraph Store
   - 普通路径存储在AgentState中
   - 需要正确区分路径类型以读取 `before_content`

3. **内容获取方式**：
   - `edit_virtual_file` 的 `before_content`：从虚拟文件系统状态或Store中读取
   - `write_virtual_file` 的 `before_content`：为空（新文件）
   - `after_content`：从工具执行后的状态更新中提取

4. **内容大小限制**：大文件的 `before_content` 和 `after_content` 可能需要限制大小，避免内存占用过大

5. **错误处理**：
   - 文件不存在时的处理（`edit_virtual_file` 时文件不存在）
   - 文件读取失败时的错误提示
   - 虚拟文件系统状态访问失败的处理

6. **性能考虑**：diff计算可能耗时，对大文件考虑异步或延迟计算

7. **UI一致性**：渲染风格要与现有的console输出保持一致

