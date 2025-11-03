# HITL交互体验增强实施文档

## deepagents-cli官方代码的优点

### 1. 工具特定格式化

官方为不同工具实现了专门的描述格式化函数：

- **write_file**：显示文件路径、操作类型（创建/覆盖）、行数、字节数
- **edit_file**：显示文件路径、替换模式（全部/单次）、匹配次数、行数变化
- **web_search**：显示查询内容、最大结果数、API使用警告
- **task（子代理）**：显示任务描述、子代理指令预览、权限警告

这种设计让用户能够快速理解操作的性质和影响范围。

### 2. 交互式菜单

官方实现了基于终端控制的交互式审批菜单：

- **箭头键导航**：上下键切换选项，Enter确认
- **视觉反馈**：选中项高亮显示，使用复选框图标
- **快捷键支持**：支持 'a'/'r' 快速选择，Ctrl+C 中断
- **跨平台兼容**：在非Unix系统上有降级方案

### 3. 自动审批模式

支持会话级别的自动审批：

- **工具级别记忆**：记住用户对特定工具的选择偏好
- **条件判断**：危险工具不允许自动审批
- **状态显示**：底部工具栏显示当前自动审批状态
- **快捷切换**：Ctrl+T 快速切换自动审批模式

### 4. 审批决策选项

提供多种审批选项：

- **批准**：允许本次操作
- **批准并记忆**：允许本次操作，并在会话中记住选择
- **拒绝**：拒绝本次操作，提供可选消息
- **拒绝并提供指导**：拒绝操作，但提供替代方案指导

## 我们现有代码的优点和不足

### 优点

1. **HITL基础设施完善**：`SessionHITLManager` 和 `handle_hitl_interrupt` 已实现
2. **审批决策支持**：支持批准、拒绝、带消息的拒绝等选项
3. **会话状态管理**：`SessionHITLManager` 支持工具级别的自动审批记忆

### 不足

1. **工具描述简单**：当前只显示工具名和原始参数JSON，不够友好
2. **缺少交互式菜单**：使用文本输入方式，用户体验不够直观
3. **预览信息不足**：虽然有文件操作预览，但其他工具缺少专门的格式化
4. **审批选项展示不够清晰**：选项的说明和功能不够明确

## 实施方案

### 实施步骤

#### 第一步：实现工具特定格式化函数

**文件路径**：[src/application/services/agent/deep/hitl/handler.py](../../src/application/services/agent/deep/hitl/handler.py)

**新增函数**：
- `format_write_file_description()`：格式化写文件操作
- `format_edit_file_description()`：格式化编辑文件操作
- `format_web_search_description()`：格式化网络搜索操作
- `format_task_description()`：格式化子代理调用操作

**格式化内容**：
- write_file：文件路径、创建/覆盖标识、行数、字节数
- edit_file：文件路径、替换模式、匹配次数、行数变化
- web_search：查询内容、结果数量限制、API使用警告
- task：任务描述、指令预览（截断）、权限说明

#### 第二步：增强审批提示生成

**文件路径**：[src/application/services/agent/deep/hitl/handler.py](../../src/application/services/agent/deep/hitl/handler.py)

**修改 `_resolve_decision` 函数**：
- 根据工具类型选择对应的格式化函数
- 将格式化后的描述添加到审批提示中
- 保持原有的错误和警告信息显示

**代码结构**：
```python
def _format_tool_description(tool_name: str, args: dict) -> str:
    """根据工具类型返回格式化描述"""
    formatters = {
        "write_file": format_write_file_description,
        "edit_file": format_edit_file_description,
        # ...
    }
    formatter = formatters.get(tool_name)
    return formatter(args) if formatter else _format_args_default(args)
```

#### 第三步：增强SessionHITLManager

**文件路径**：[src/application/services/agent/deep/hitl/session_manager.py](../../src/application/services/agent/deep/hitl/session_manager.py)

**新增功能**：
- 记录用户的审批偏好模式（批准、拒绝、提供指导）
- 支持工具级别的默认审批决策
- 在审批提示中显示"记住此选择"选项

**方法增强**：
- `register_preference()`：记录用户对特定工具的审批偏好
- `get_default_decision()`：获取工具的默认审批决策（如果已记录）

#### 第四步：可选实现交互式菜单

**文件路径**：`src/application/services/agent/deep/hitl/interactive_prompt.py`（新建，可选）

**功能说明**：
如果项目已有命令行交互库（如 `prompt_toolkit` 或 `rich.prompt`），可以实现交互式菜单。

**功能要点**：
- 使用箭头键导航选项
- Enter确认选择
- 支持快捷键（'a' 批准，'r' 拒绝）
- 显示当前选中的选项

**注意**：如果当前使用文本输入方式也能满足需求，此步骤可选。

#### 第五步：增强审批选项展示

**文件路径**：[src/application/services/agent/deep/hitl/handler.py](../../src/application/services/agent/deep/hitl/handler.py)

**修改 `_build_options` 函数**：
- 更清晰地说明每个选项的功能
- 对于危险工具，明确标识哪些选项不可用
- 显示工具的警告信息（如果有）

**选项说明增强**：
- 选项1：批准本次操作（默认）
- 选项2：批准并在本次会话中记住（仅非危险工具）
- 选项3：拒绝操作
- 选项4：拒绝并提供替代指导

### 文件创建清单

1. **可选新建**：`src/application/services/agent/deep/hitl/interactive_prompt.py`（如果实现交互式菜单）

### 文件修改清单

1. **修改文件**：[src/application/services/agent/deep/hitl/handler.py](../../src/application/services/agent/deep/hitl/handler.py)
2. **修改文件**：[src/application/services/agent/deep/hitl/session_manager.py](../../src/application/services/agent/deep/hitl/session_manager.py)

### 配置增强

在 `SessionHITLManager` 的初始化中支持：
- `tool_specific_formatters`：工具特定格式化函数字典
- `default_preferences`：从配置加载的默认审批偏好

### 注意事项

1. **向后兼容**：保持现有的文本输入方式作为降级方案
2. **错误处理**：格式化函数要能处理缺失或不规范的参数
3. **性能考虑**：格式化操作要快速，不能阻塞审批流程
4. **国际化准备**：格式化文本考虑未来国际化的可能性（使用配置或常量）

