# 快速参考

## 目录
- 1. 颜色速查表
- 2. 图标速查表
- 3. 组件速查表
- 4. 常用代码片段

---

## 1. 颜色速查表

### 1.1 主题色

| 颜色名 | 色值 | 用途 | 使用方式 |
|-------|------|------|---------|
| primary | #A8E650 | 主色调、标题 | `COLORS["primary"]` |
| secondary | #50B4FF | 次要色 | `COLORS["secondary"]` |
| success | #34d399 | 成功消息 | `COLORS["success"]` |
| warning | #fbbf24 | 警告消息 | `COLORS["warning"]` |
| error | #ef4444 | 错误消息 | `COLORS["error"]` |
| info | #3b82f6 | 信息提示 | `COLORS["info"]` |

### 1.2 文本色

| 颜色名 | 色值 | 用途 | 使用方式 |
|-------|------|------|---------|
| text_primary | #ffffff | 主文本 | `COLORS["text_primary"]` |
| text_dim | #6b7280 | 次要文本、提示 | `COLORS["text_dim"]` |

### 1.3 角色色

| 颜色名 | 色值 | 用途 | 使用方式 |
|-------|------|------|---------|
| user | #ffffff | 用户输入 | `COLORS["user"]` |
| agent | #A8E650 | Agent 输出 | `COLORS["agent"]` |
| tool | #fbbf24 | 工具调用 | `COLORS["tool"]` |

### 1.4 品牌色

| 颜色名 | 色值 | 用途 | 使用方式 |
|-------|------|------|---------|
| jasmine | #C2FF62 | Logo 主色 | `BRAND_COLORS["jasmine"]` |
| scifi_blue | #50B4FF | Logo 次色 | `BRAND_COLORS["scifi_blue"]` |

---

## 2. 图标速查表

### 2.1 工具图标

| 工具 | Emoji | Unicode | 用途 |
|-----|-------|---------|------|
| read_file | 📖 | U+1F4D6 | 文件读取 |
| write_file | ✏️ | U+270F | 文件写入 |
| edit_file | ✂️ | U+2702 | 文件编辑 |
| list_files | 📁 | U+1F4C1 | 文件列表 |
| glob | 🔍 | U+1F50D | 文件搜索 |
| grep | 🔎 | U+1F50E | 内容搜索 |
| shell | ⚡ | U+26A1 | Shell 命令 |
| execute | 🔧 | U+1F527 | 执行操作 |
| web_search | 🌐 | U+1F310 | 网络搜索 |
| http_request | 🌍 | U+1F30D | HTTP 请求 |
| task | 🤖 | U+1F916 | 任务/子 Agent |
| write_todos | 📋 | U+1F4CB | 任务列表 |

### 2.2 状态符号

| 状态 | 符号 | Unicode | 用途 |
|-----|------|---------|------|
| completed | ☑ | U+2611 | 已完成 |
| in_progress | ⏳ | U+23F3 | 进行中 |
| pending | ☐ | U+2610 | 待处理 |
| failed | ☒ | U+2612 | 失败 |

### 2.3 装饰符号

| 名称 | 符号 | Unicode | 用途 |
|-----|------|---------|------|
| bullet | ● | U+25CF | 项目符号 |
| record | ⏺ | U+23FA | 记录标记 |
| branch | ⎿ | U+23BF | 树形缩进 |
| checkmark | ✓ | U+2713 | 成功标记 |
| warning | ⚠ | U+26A0 | 警告标记 |

---

## 3. 组件速查表

### 3.1 Panel 组件

**标准用法**：

```python
from src.application.cli.theme import PANEL_DEFAULTS, PANEL_STYLES

console.print(Panel(
    content,
    title="[bold]Title[/bold]",
    border_style=PANEL_STYLES["info"],
    **PANEL_DEFAULTS
))
```

**边框样式选择**：

| 场景 | 样式 |
|-----|------|
| 信息展示 | `PANEL_STYLES["info"]` |
| 成功消息 | `PANEL_STYLES["success"]` |
| 警告提示 | `PANEL_STYLES["warning"]` |
| 错误消息 | `PANEL_STYLES["error"]` |
| 普通内容 | `PANEL_STYLES["primary"]` |

### 3.2 Table 组件

**标准用法**：

```python
from src.application.cli.theme import TABLE_COLUMN_STYLES

table = Table(title="Title")
table.add_column("ID", style=TABLE_COLUMN_STYLES["id"])
table.add_column("Status", style=TABLE_COLUMN_STYLES["status"])
table.add_column("Count", style=TABLE_COLUMN_STYLES["count"], justify="right")
```

### 3.3 Text 类

**混合样式**：

```python
from rich.text import Text
from src.application.cli.theme import TOOL_ICONS, COLORS

text = Text()
text.append(TOOL_ICONS["read_file"] + " ", style=COLORS["tool"])
text.append("Reading file...", style=f"bold {COLORS['tool']}")
console.print(text)
```

---

## 4. 常用代码片段

### 4.1 标题显示

```python
from src.application.cli.theme import COLORS, INDENT

# 主标题
console.print("[bold]Main Title[/bold]", style=COLORS["primary"])
console.print()

# 副标题
console.print("[bold]Subtitle[/bold]", style=COLORS["primary"])
console.print()
```

### 4.2 命令列表

```python
from src.application.cli.theme import INDENT, ALIGNMENT, COLORS

console.print("[bold]Commands:[/bold]", style=COLORS["primary"])
console.print()

commands = [
    ("/switch <engine>", "Switch execution engine"),
    ("/help", "Show help"),
]

for syntax, desc in commands:
    console.print(f"{INDENT['small']}{syntax:<{ALIGNMENT['command']}} {desc}")
```

### 4.3 成功消息

```python
from src.application.cli.theme import COLORS, DECORATIVE_SYMBOLS

console.print(
    f"{DECORATIVE_SYMBOLS['checkmark']} Operation completed",
    style=COLORS["success"]
)
```

### 4.4 警告消息

```python
from src.application.cli.theme import COLORS, DECORATIVE_SYMBOLS

console.print(
    f"{DECORATIVE_SYMBOLS['warning']} Warning: Configuration not found",
    style=COLORS["warning"]
)
```

### 4.5 错误消息

```python
from src.application.cli.theme import COLORS

console.print("[bold]Error:[/bold] Connection failed", style=COLORS["error"])
```

### 4.6 信息面板

```python
from src.application.cli.theme import PANEL_DEFAULTS, PANEL_STYLES

info_text = """Provider: OpenAI
Model: gpt-4o
Status: Connected"""

console.print(Panel(
    info_text,
    title="[bold]System Information[/bold]",
    border_style=PANEL_STYLES["info"],
    **PANEL_DEFAULTS
))
```

### 4.7 任务列表

```python
from src.application.cli.theme import STATUS_SYMBOLS, COLORS

tasks = [
    ("completed", "Task 1"),
    ("in_progress", "Task 2"),
    ("pending", "Task 3"),
]

for status, task in tasks:
    icon = STATUS_SYMBOLS[status]
    console.print(f"{icon} {task}")
```

### 4.8 工具调用显示

```python
from src.application.cli.theme import TOOL_ICONS, COLORS, INDENT

tool_name = "read_file"
tool_args = "config.py"

icon = TOOL_ICONS.get(tool_name, TOOL_ICONS["default"])
console.print(
    f"{INDENT['small']}{icon} {tool_name}({tool_args})",
    style=f"dim {COLORS['tool']}"
)
```

---

## 5. 样式组合速查

### 5.1 文本样式

| 效果 | 代码 |
|-----|------|
| 粗体 | `[bold]Text[/bold]` |
| 暗淡 | `[dim]Text[/dim]` |
| 粗体+颜色 | `style=f"bold {COLORS['primary']}"` |
| 暗淡+颜色 | `style=f"dim {COLORS['text_dim']}"` |

### 5.2 缩进

| 级别 | 代码 | 空格数 |
|-----|------|--------|
| 无缩进 | `INDENT['none']` | 0 |
| 小缩进 | `INDENT['small']` | 2 |
| 中缩进 | `INDENT['medium']` | 4 |
| 大缩进 | `INDENT['large']` | 6 |

### 5.3 对齐

| 用途 | 代码 | 宽度 |
|-----|------|------|
| 命令语法 | `ALIGNMENT['command']` | 28 |
| 标签 | `ALIGNMENT['label']` | 12 |

### 5.4 垂直间距

| 场景 | 代码 | 效果 |
|-----|------|------|
| 标题后 | `console.print()` | 空 1 行 |
| 段落间 | `console.print()` | 空 1 行 |
| 章节间 | `console.print("\n")` | 空 2 行 |

---

## 6. 检查清单

### 6.1 代码检查

- [ ] 所有颜色来自 `COLORS` 或 `BRAND_COLORS`
- [ ] 所有图标来自 `TOOL_ICONS`, `STATUS_SYMBOLS`, `DECORATIVE_SYMBOLS`
- [ ] Panel 使用 `**PANEL_DEFAULTS`
- [ ] Table 列样式来自 `TABLE_COLUMN_STYLES`
- [ ] 缩进使用 `INDENT`
- [ ] 对齐宽度使用 `ALIGNMENT`

### 6.2 视觉检查

- [ ] Panel 边框为圆角
- [ ] Panel 有左右内边距
- [ ] 命令列表对齐整齐
- [ ] 标题后有空行
- [ ] 颜色在深色终端可读

### 6.3 约束检查

- [ ] emoji 仅在 `src/application/cli/` 目录
- [ ] 无硬编码颜色字符串
- [ ] 无硬编码缩进空格
- [ ] `src/components/` 等核心目录无 emoji

---

## 7. 导入语句参考

```python
# 颜色
from src.application.cli.theme import COLORS, BRAND_COLORS

# 图标
from src.application.cli.theme import (
    TOOL_ICONS,
    STATUS_SYMBOLS,
    DECORATIVE_SYMBOLS,
)

# 组件样式
from src.application.cli.theme import (
    PANEL_DEFAULTS,
    PANEL_STYLES,
    TABLE_COLUMN_STYLES,
)

# 布局
from src.application.cli.theme import INDENT, ALIGNMENT

# 辅助函数
from src.application.cli.theme import (
    get_title_style,
    get_caption_style,
    get_success_style,
    get_warning_style,
    get_error_style,
)

# Rich 组件
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.markdown import Markdown
from rich import box
```

---

## 8. 文档链接

- [01-overview.md](01-overview.md) - 概览和原则
- [02-color-system.md](02-color-system.md) - 颜色系统详解
- [03-typography.md](03-typography.md) - 字体排版详解
- [04-icons-symbols.md](04-icons-symbols.md) - 图标符号详解
- [05-components.md](05-components.md) - Rich 组件详解
- [06-layout-spacing.md](06-layout-spacing.md) - 布局间距详解
- [07-implementation.md](07-implementation.md) - 实施计划
- [08-reference.md](08-reference.md) - 本文档

---

## 9. 相关资源

- Rich 官方文档: https://rich.readthedocs.io/
- 官方 DeepAgents: `deepagents/libs/deepagents-cli/`
- 项目 CLI: `src/application/cli/`
- 主题配置: `src/application/cli/theme.py`
