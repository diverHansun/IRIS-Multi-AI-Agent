# 实施计划

## 目录
- 1. 实施概览
- 2. 文件清单
- 3. 实施步骤
- 4. 验证检查
- 5. 回滚方案

---

## 1. 实施概览

### 1.1 实施范围

本次优化**仅修改视觉呈现**，涉及以下文件：

```
src/application/cli/
├── theme.py               # 新建 - 主题配置
├── gui/
│   ├── logo.py            # 修改 - 更新颜色引用
│   ├── render.py          # 修改 - 更新组件样式
│   └── interact.py        # 检查 - 确认无需修改
└── main.py                # 修改 - 更新颜色引用
```

### 1.2 核心变更

1. **新建 theme.py** - 集中管理所有视觉定义
2. **更新颜色引用** - 从硬编码改为使用 COLORS 常量
3. **统一组件样式** - Panel 和 Table 使用标准配置
4. **引入图标系统** - 为工具和状态添加图标

### 1.3 不变更的内容

- 不修改业务逻辑
- 不修改命令实现
- 不修改 Agent 行为
- 不修改数据流程

---

## 2. 文件清单

### 2.1 新建文件

**`src/application/cli/theme.py`**

内容包括：
- `BRAND_COLORS` - 品牌色定义
- `COLORS` - 主题色定义
- `TOOL_ICONS` - 工具图标映射
- `STATUS_SYMBOLS` - 状态符号
- `DECORATIVE_SYMBOLS` - 装饰符号
- `PANEL_DEFAULTS` - Panel 标准配置
- `PANEL_STYLES` - Panel 边框颜色
- `TABLE_COLUMN_STYLES` - Table 列样式
- `INDENT` - 缩进定义
- `ALIGNMENT` - 对齐宽度

### 2.2 修改文件

**CLI 核心文件**：

| 文件 | 修改内容 | 优先级 |
|-----|---------|-------|
| `gui/logo.py` | 引入 BRAND_COLORS | 高 |
| `gui/render.py` | 更新所有样式引用 | 高 |
| `main.py` | 更新颜色引用 | 中 |
| `gui/interact.py` | 检查并更新（如需要） | 低 |

**引擎特定文件**（详见 `09-engine-modes.md`）：

| 文件 | 修改内容 | 优先级 |
|-----|---------|-------|
| `llm/utils/streaming.py` | LLM 流式输出样式更新 | 高 |
| `services/agent/deep/streaming/event_handler.py` | Deep Agent 事件处理样式更新 | 高 |
| `services/dify/service.py` | Dify 服务层样式更新 | 中 |
| `services/dify/streaming.py` | Dify 流式输出样式更新 | 中 |

### 2.3 不修改文件

以下文件**不应包含** emoji 或视觉定义：
- `src/components/` - 核心组件
- `src/application/commands/` - 命令处理
- `src/application/engine_adapters/` - 引擎适配器

**特别说明**：
- `src/llm/` 和 `src/application/services/` 中的流式输出文件需要修改样式，但不添加 emoji
- 详见 `09-engine-modes.md` 关于各引擎 UI 的说明

---

## 3. 实施步骤

### 步骤 1：创建主题文件

**任务**：创建 `src/application/cli/theme.py`

**内容结构**：

```python
"""
CLI 主题配置

包含颜色、图标、组件样式等视觉定义。
所有 CLI 相关的视觉元素统一在此管理。
"""

from rich import box

# ========== 颜色系统 ==========

# 品牌色 - 仅用于 Logo
BRAND_COLORS = {
    "jasmine": "#C2FF62",      # Jasmine Green
    "scifi_blue": "#50B4FF",   # Sci-Fi Blue
}

# 主题色 - 系统界面使用
COLORS = {
    # 主色调
    "primary": "#A8E650",      # 柔和的茉莉绿
    "secondary": "#50B4FF",    # 科幻蓝

    # 功能色
    "success": "#34d399",      # 成功
    "warning": "#fbbf24",      # 警告
    "error": "#ef4444",        # 错误
    "info": "#3b82f6",         # 信息

    # 文本色
    "text_primary": "#ffffff", # 主文本
    "text_dim": "#6b7280",     # 次要文本

    # 角色色
    "user": "#ffffff",         # 用户输入
    "agent": "#A8E650",        # Agent 输出
    "tool": "#fbbf24",         # 工具调用
}

# ========== 图标系统 ==========

TOOL_ICONS = {
    # 文件操作
    "read_file": "📖",
    "write_file": "✏️",
    "edit_file": "✂️",
    "list_files": "📁",

    # 搜索工具
    "glob": "🔍",
    "grep": "🔎",

    # 执行工具
    "shell": "⚡",
    "execute": "🔧",

    # 网络工具
    "web_search": "🌐",
    "http_request": "🌍",

    # Agent 工具
    "task": "🤖",
    "write_todos": "📋",

    # 默认
    "default": "🔧",
}

STATUS_SYMBOLS = {
    "completed": "☑",
    "in_progress": "⏳",
    "pending": "☐",
    "failed": "☒",
}

DECORATIVE_SYMBOLS = {
    "bullet": "●",
    "record": "⏺",
    "branch": "⎿",
    "checkmark": "✓",
    "warning": "⚠",
}

# ========== 组件样式 ==========

PANEL_DEFAULTS = {
    "box": box.ROUNDED,
    "padding": (0, 1),
}

PANEL_STYLES = {
    "info": "blue",
    "success": "green",
    "warning": "yellow",
    "error": "red",
    "primary": "cyan",
}

TABLE_COLUMN_STYLES = {
    "id": "green",
    "status": "cyan",
    "count": "magenta",
    "time": "yellow",
}

# ========== 布局间距 ==========

INDENT = {
    "none": "",
    "small": "  ",      # 2 空格
    "medium": "    ",   # 4 空格
    "large": "      ",  # 6 空格
}

ALIGNMENT = {
    "command": 28,      # 命令语法列
    "label": 12,        # 标签列
}

# ========== 辅助函数 ==========

def get_title_style() -> str:
    """获取标题样式"""
    return f"bold {COLORS['primary']}"

def get_caption_style() -> str:
    """获取辅助文本样式"""
    return f"dim {COLORS['text_dim']}"

def get_success_style() -> str:
    """获取成功消息样式"""
    return f"bold {COLORS['success']}"

def get_warning_style() -> str:
    """获取警告消息样式"""
    return f"bold {COLORS['warning']}"

def get_error_style() -> str:
    """获取错误消息样式"""
    return f"bold {COLORS['error']}"
```

**验证**：
- [ ] 文件可正常导入
- [ ] 所有字典定义无语法错误
- [ ] 辅助函数可正常调用

---

### 步骤 2：更新 Logo 模块

**文件**：`src/application/cli/gui/logo.py`

**修改**：

```python
# 修改前
PRIMARY_COLOUR = "#C2FF62"
SECONDARY_COLOUR = "#50B4FF"

# 修改后
from src.application.cli.theme import BRAND_COLORS

PRIMARY_COLOUR = BRAND_COLORS["jasmine"]
SECONDARY_COLOUR = BRAND_COLORS["scifi_blue"]
```

**验证**：
- [ ] Logo 显示正常
- [ ] 颜色与之前一致

---

### 步骤 3：更新渲染模块

**文件**：`src/application/cli/gui/render.py`

**修改清单**：

1. **添加导入**

```python
from src.application.cli.theme import (
    COLORS,
    PANEL_DEFAULTS,
    PANEL_STYLES,
    TABLE_COLUMN_STYLES,
    INDENT,
    ALIGNMENT,
)
```

2. **更新 Panel 使用**

```python
# 修改前
console.print(Panel(body, title="Welcome", border_style="cyan"))

# 修改后
console.print(Panel(
    body,
    title="[bold]Welcome[/bold]",
    border_style=PANEL_STYLES["primary"],
    **PANEL_DEFAULTS
))
```

3. **更新 Table 样式**

```python
# 修改前
table.add_column("Session ID", style="green", no_wrap=True)

# 修改后
table.add_column("Session ID", style=TABLE_COLUMN_STYLES["id"], no_wrap=True)
```

4. **更新内联颜色**

```python
# 修改前
console.print(f"[red]{catalog['error']}[/]")

# 修改后
console.print(catalog['error'], style=COLORS["error"])
```

5. **更新命令列表格式**

```python
# 修改前
lines.append(f"{syntax:<28} {description}")

# 修改后
lines.append(f"{INDENT['small']}{syntax:<{ALIGNMENT['command']}} {description}")
```

**验证**：
- [ ] 所有 Panel 边框为圆角
- [ ] Panel 有左右内边距
- [ ] Table 列颜色正确
- [ ] 无硬编码颜色残留

---

### 步骤 4：更新主循环

**文件**：`src/application/cli/main.py`

**修改**：

```python
# 添加导入
from src.application.cli.theme import COLORS

# 修改错误消息
# 修改前
ctx.console.print(f"[bold red]Error:[/] {escape(str(exc))}")

# 修改后
ctx.console.print(f"[bold]Error:[/bold] {escape(str(exc))}", style=COLORS["error"])

# 修改警告消息
# 修改前
ctx.console.print("\n[yellow]Interrupted. Cleaning up...[/]")

# 修改后
ctx.console.print("\nInterrupted. Cleaning up...", style=COLORS["warning"])
```

**验证**：
- [ ] 错误消息显示正确
- [ ] 警告消息显示正确
- [ ] 功能正常

---

### 步骤 5：检查其他文件

**文件**：`src/application/cli/gui/interact.py`

**任务**：检查是否有需要更新的颜色引用

**验证**：
- [ ] 无硬编码颜色
- [ ] 如有 console.print，使用 COLORS 常量

---

### 步骤 6：更新 LLM 引擎流式输出

**文件**：`src/llm/utils/streaming.py`

**修改内容**（详见 `09-engine-modes.md` 第 2 章）：

1. **添加导入**

```python
from src.application.cli.theme import COLORS, PANEL_DEFAULTS
```

2. **修改 StreamingDisplay._create_panel() 方法（147-158行）**

```python
# 修改前
return Panel(
    Text(display_content, style="green"),
    title=f"[bold cyan]{self.title}[/]",
    border_style="cyan",
    padding=(1, 2)
)

# 修改后
return Panel(
    Text(display_content, style=COLORS["agent"]),
    title=f"[bold]{self.title}[/bold]",
    border_style=COLORS["info"],
    **PANEL_DEFAULTS
)
```

3. **修改完成后的 Panel 显示（519-524行）**

```python
# 修改前
console.print(Panel(
    full_response,
    title=f"[bold green]{display_title} (完成)[/]",
    border_style="green"
))

# 修改后
console.print(Panel(
    full_response,
    title=f"[bold]{display_title} (完成)[/bold]",
    border_style=COLORS["success"],
    **PANEL_DEFAULTS
))
```

4. **修改性能指标显示（537-543行）**

```python
# 修改前
console.print(
    f"[dim]⚡ 性能: {elapsed:.2f}s | ..."
)

# 修改后
console.print(
    f"Performance: {elapsed:.2f}s | ...",
    style=COLORS["text_dim"]
)
```

**验证**：
- [ ] LLM 引擎流式输出显示正确
- [ ] Panel 边框为圆角
- [ ] Panel padding 为 (0, 1)
- [ ] Agent Basic 模式自动继承

---

### 步骤 7：更新 Deep Agent 流式输出

**文件**：`src/application/services/agent/deep/streaming/event_handler.py`

**修改内容**（详见 `09-engine-modes.md` 第 4 章）：

1. **添加导入**

```python
from src.application.cli.theme import COLORS
```

2. **更新工具调用样式（351行）**

```python
# 修改前
self.console.print(
    f"  Tool: {escape(display_str)}",
    style="dim cyan",
    markup=False
)

# 修改后
self.console.print(
    f"  Tool: {escape(display_str)}",
    style=f"dim {COLORS['tool']}",
    markup=False
)
```

3. **更新错误样式（155, 189行）**

```python
# 修改前
self.console.print(tool_content, style="red", markup=False)

# 修改后
self.console.print(tool_content, style=COLORS["error"], markup=False)
```

4. **更新 Agent 输出样式（392, 395行）**

```python
# 修改前
self.console.print("Agent:", style="bold blue", markup=False)
self.console.print(escape(self._pending_text), style="white")

# 修改后
self.console.print("Agent:", style=f"bold {COLORS['agent']}", markup=False)
self.console.print(escape(self._pending_text), style=COLORS["text_primary"])
```

**验证**：
- [ ] Deep Agent 工具调用显示正确
- [ ] 错误消息颜色正确
- [ ] Agent 输出颜色正确
- [ ] 保持纯文本风格（无 Panel）

---

### 步骤 8：更新 Dify 引擎样式

**文件 1**：`src/application/services/dify/service.py`
**文件 2**：`src/application/services/dify/streaming.py`

**修改内容**（详见 `09-engine-modes.md` 第 5 章）：

1. **在两个文件中添加导入**

```python
from src.application.cli.theme import COLORS
```

2. **更新 service.py 中的硬编码颜色**

- `[dim]` → `style=COLORS["text_dim"]`
- `[yellow]` → `style=COLORS["warning"]`
- `[red]` → `style=COLORS["error"]`
- `[green]` → `style=COLORS["success"]`
- `[blue]` → `style=COLORS["info"]`

3. **更新 streaming.py 中的硬编码颜色**

- `[cyan]` → `style=COLORS["info"]`
- `[bold green]` → `[bold]` + `style=COLORS["success"]`
- `bright_white` → `COLORS["text_primary"]`
- `[red]` → `style=COLORS["error"]`
- `[dim]` → `style=COLORS["text_dim"]`

**验证**：
- [ ] Dify 对话流程显示正确
- [ ] 文件上传提示正确
- [ ] 错误和警告显示正确
- [ ] Agent 思考过程显示正确

---

## 4. 验证检查

### 4.1 视觉验证

启动 CLI，逐一检查：

- [ ] Logo 颜色正确
- [ ] 欢迎信息显示正常
- [ ] Panel 边框为圆角
- [ ] Panel 有内边距
- [ ] 命令列表对齐整齐
- [ ] 错误消息颜色正确
- [ ] 警告消息颜色正确
- [ ] Table 显示正常

### 4.2 代码检查

- [ ] `theme.py` 创建成功
- [ ] 所有文件导入无错误
- [ ] 无硬编码颜色（grep 检查：`[red]`, `[yellow]` 等）
- [ ] 无硬编码缩进（grep 检查：`"  "` 在 print 中）
- [ ] `src/components/` 等目录无 emoji

### 4.3 功能验证

- [ ] 所有命令正常执行
- [ ] Agent 响应正常
- [ ] Session 管理正常
- [ ] 工具调用正常

### 4.4 终端兼容性

- [ ] Windows Terminal 显示正常
- [ ] 深色主题可读
- [ ] 浅色主题可读（如果支持）

---

## 5. 回滚方案

如果出现问题，按以下步骤回滚：

### 5.1 Git 回滚

```bash
# 查看修改
git status
git diff

# 回滚单个文件
git checkout -- src/application/cli/gui/render.py

# 回滚所有修改
git reset --hard HEAD
```

### 5.2 删除新文件

```bash
# 删除 theme.py
rm src/application/cli/theme.py
```

### 5.3 恢复原始代码

保留一份修改前的备份：

```bash
# 修改前备份
cp -r src/application/cli src/application/cli.backup

# 回滚
rm -rf src/application/cli
mv src/application/cli.backup src/application/cli
```

---

## 6. 后续优化

完成基础优化后，可考虑：

1. **添加更多图标** - 根据实际使用的工具扩展 TOOL_ICONS
2. **引入 Text 类** - 在需要混合样式的场景使用
3. **Markdown 渲染** - 如果 Agent 输出需要格式化
4. **主题切换** - 支持浅色/深色主题
5. **自定义配置** - 允许用户自定义颜色

---

## 7. 注意事项

1. **emoji 仅限 CLI 目录** - 不要在其他地方使用
2. **测试深色终端** - 确保颜色在深色背景下可读
3. **保留品牌识别** - Logo 保持原有颜色
4. **向后兼容** - 不破坏现有功能
5. **文档同步** - 修改后更新相关文档

---

## 下一步

阅读 `08-reference.md` 查看快速参考表。
