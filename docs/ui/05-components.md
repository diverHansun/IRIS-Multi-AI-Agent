# Rich 组件规范

## 目录
- 1. 现状分析
- 2. 优化目标
- 3. 设计方案
- 4. 使用规范
- 5. 实施清单

---

## 1. 现状分析

### 1.1 官方 DeepAgents 的做法

参考文件：`deepagents/libs/deepagents-cli/deepagents_cli/ui.py`, `execution.py`

**Panel 使用**（`ui.py:259-266`）：

```python
Panel(
    "\n".join(lines),
    title="[bold]Task List[/bold]",
    border_style="cyan",
    box=box.ROUNDED,
    padding=(0, 1),
)
```

**Text 类使用**（`ui.py:289-298`）：

```python
from rich.text import Text

header = Text()
header.append("⏺ ", style=COLORS["tool"])
header.append(f"{label}({path})", style=f"bold {COLORS['tool']}")
console.print(header)
```

**Markdown 使用**（`execution.py:259`）：

```python
from rich.markdown import Markdown

markdown = Markdown(pending_text.rstrip())
console.print(markdown, style=COLORS["agent"])
```

**特点**：
- 统一使用 `box.ROUNDED`
- 固定 `padding=(0, 1)`
- 使用 Text 类精细控制样式
- Markdown 渲染 Agent 输出

### 1.2 当前项目的现状

查看 `src/application/cli/gui/render.py`：

```python
# Panel 使用
console.print(Panel(body, title="Welcome", border_style="cyan"))
# 问题：无 box 参数，无 padding

# Table 使用
table = Table(title="Sessions")
table.add_column("Active", style="cyan", justify="center", width=8)
# 问题：样式硬编码
```

**问题**：
1. Panel 没有设置 `box` 参数，使用默认样式
2. Panel 没有设置 `padding`，内容贴边
3. Table 列样式硬编码
4. 缺少 Text 类的使用
5. 没有使用 Markdown 渲染

### 1.3 差距分析

| 组件 | 官方 | 当前项目 | 差距 |
|-----|------|---------|------|
| Panel.box | box.ROUNDED | 默认（SQUARE） | 需要统一 |
| Panel.padding | (0, 1) | 无 | 需要添加 |
| Text 类 | 广泛使用 | 未使用 | 需要引入 |
| Markdown | Agent输出 | 未使用 | 需要引入 |

---

## 2. 优化目标

1. **统一 Panel 样式**
   - 所有 Panel 使用 `box.ROUNDED`
   - 所有 Panel 设置 `padding=(0, 1)`

2. **规范 Table 样式**
   - 列样式使用颜色常量
   - 统一标题样式

3. **引入 Text 类**
   - 在需要混合样式的场景使用
   - 提升样式控制精度

4. **使用 Markdown 渲染**
   - Agent 输出自动渲染为 Markdown
   - 支持代码块、列表等格式

---

## 3. 设计方案

### 3.1 Panel 标准样式

在 `theme.py` 中定义标准配置：

```python
from rich import box

# Panel 标准配置
PANEL_DEFAULTS = {
    "box": box.ROUNDED,
    "padding": (0, 1),
}

# 不同类型 Panel 的边框颜色
PANEL_STYLES = {
    "info": "blue",
    "success": "green",
    "warning": "yellow",
    "error": "red",
    "primary": "cyan",
}
```

**使用方式**：

```python
from src.application.cli.theme import PANEL_DEFAULTS, PANEL_STYLES

console.print(Panel(
    content,
    title="Information",
    border_style=PANEL_STYLES["info"],
    **PANEL_DEFAULTS
))
```

### 3.2 Table 标准样式

```python
# Table 列样式定义
TABLE_COLUMN_STYLES = {
    "id": "green",
    "status": "cyan",
    "count": "magenta",
    "time": "yellow",
}
```

**使用方式**：

```python
table = Table(title="Sessions")
table.add_column("Session ID", style=TABLE_COLUMN_STYLES["id"])
table.add_column("Status", style=TABLE_COLUMN_STYLES["status"])
```

### 3.3 Text 类使用场景

适用于需要在同一行混合多种样式的场景：

```python
from rich.text import Text

# 场景 1：带图标的标题
header = Text()
header.append("⏺ ", style=COLORS["tool"])
header.append("Update(file.py)", style=f"bold {COLORS['tool']}")
console.print(header)

# 场景 2：带缩进的详情
detail = Text()
detail.append("  ⎿  ", style=COLORS["text_dim"])
detail.append("Modified 5 lines", style=COLORS["text_dim"])
console.print(detail)
```

### 3.4 Markdown 渲染

用于 Agent 输出：

```python
from rich.markdown import Markdown

# Agent 回复
response = "## Analysis\n\nHere is the **result**:\n```python\nprint('hello')\n```"
markdown = Markdown(response)
console.print(markdown, style=COLORS["agent"])
```

---

## 4. 使用规范

### 4.1 Panel 使用规范

**规则 1：必须使用标准配置**

```python
# 正确
console.print(Panel(content, title="Title", **PANEL_DEFAULTS))

# 错误
console.print(Panel(content, title="Title"))  # 缺少标准配置
```

**规则 2：根据场景选择边框颜色**

| 场景 | 边框颜色 | 示例 |
|-----|---------|------|
| 信息展示 | `PANEL_STYLES["info"]` | 系统信息 |
| 成功消息 | `PANEL_STYLES["success"]` | 操作成功 |
| 警告提示 | `PANEL_STYLES["warning"]` | HITL 审批 |
| 错误消息 | `PANEL_STYLES["error"]` | 错误详情 |
| 普通内容 | `PANEL_STYLES["primary"]` | 帮助文档 |

**规则 3：标题使用 bold**

```python
Panel(content, title="[bold]System Info[/bold]", ...)
```

### 4.2 Table 使用规范

**规则 1：使用标题**

```python
table = Table(title="Sessions")  # 始终提供标题
```

**规则 2：列样式从常量获取**

```python
# 正确
table.add_column("ID", style=TABLE_COLUMN_STYLES["id"])

# 错误
table.add_column("ID", style="green")  # 硬编码
```

**规则 3：设置列宽和对齐**

```python
table.add_column("Status", style=..., width=10, justify="center")
table.add_column("Count", style=..., justify="right")
```

### 4.3 Text 类使用时机

**何时使用 Text**：
- 同一行需要多种样式
- 需要精确控制样式边界
- 包含图标和文本的组合

**何时不使用 Text**：
- 单一样式的文本（直接用 console.print）
- 整段文本（使用 Markdown）

### 4.4 Markdown 使用时机

**适用场景**：
- Agent 生成的回复
- 包含代码块的文本
- 包含列表、标题的格式化文本

**不适用场景**：
- 简单的状态消息
- 固定格式的表格（使用 Table）
- 单行文本

---

## 5. 实施清单

### 5.1 创建组件配置

- [ ] 在 `theme.py` 中添加 `PANEL_DEFAULTS`
- [ ] 在 `theme.py` 中添加 `PANEL_STYLES`
- [ ] 在 `theme.py` 中添加 `TABLE_COLUMN_STYLES`

### 5.2 更新 Panel 使用

- [ ] 修改 `render.py` 所有 Panel 调用
- [ ] 添加 `**PANEL_DEFAULTS` 参数
- [ ] 更新 `border_style` 使用 `PANEL_STYLES`
- [ ] 确保标题使用 `[bold]...[/bold]`

### 5.3 更新 Table 使用

- [ ] 修改 `render.py` 的 Table 定义
- [ ] 列样式改用 `TABLE_COLUMN_STYLES`
- [ ] 确保所有 Table 有标题

### 5.4 引入 Text 类

- [ ] 在需要的地方导入 `from rich.text import Text`
- [ ] 替换需要混合样式的场景
- [ ] 例如：文件操作显示、带图标的提示

### 5.5 引入 Markdown

- [ ] 如果有 Agent 输出展示，导入 Markdown
- [ ] 将 Agent 回复渲染为 Markdown
- [ ] 测试代码块、列表显示

### 5.6 验证

- [ ] 所有 Panel 边框为圆角
- [ ] Panel 内容有左右边距
- [ ] Table 列颜色来自常量
- [ ] 无硬编码样式残留

---

## 附录：Rich 组件参考

### Panel 参数

```python
Panel(
    renderable,           # 内容
    title="Title",        # 标题
    border_style="cyan",  # 边框颜色
    box=box.ROUNDED,      # 边框样式
    padding=(0, 1),       # 内边距 (上下, 左右)
    expand=False,         # 是否填充宽度
)
```

### Box 样式选项

```python
from rich import box

box.ROUNDED      # 推荐 - 圆角
box.SQUARE       # 默认 - 方角
box.DOUBLE       # 双线
box.MINIMAL      # 最简
```

### Table 常用参数

```python
Table(
    title="Title",       # 标题
    show_header=True,    # 显示表头
    show_lines=False,    # 显示行分隔线
    padding=(0, 1),      # 单元格内边距
)

table.add_column(
    "Column Name",
    style="cyan",        # 列样式
    justify="left",      # 对齐方式: left/center/right
    width=10,            # 固定宽度
    no_wrap=True,        # 不换行
)
```

---

## 下一步

阅读 `06-layout-spacing.md` 了解布局间距规范。
