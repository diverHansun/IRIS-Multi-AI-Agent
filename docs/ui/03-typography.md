# 字体排版规范

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

**样式修饰符使用**：

```python
# 标题
console.print("[bold]Token Usage:[/bold]", style=COLORS["primary"])

# 加粗 + 颜色组合
console.print(f"[bold]{agent_name}[/bold]", style=COLORS["primary"])

# 暗淡提示
console.print(f"  {desc}", style=COLORS["dim"])

# 组合样式
style=f"dim {COLORS['tool']}"
style=f"bold {COLORS['primary']}"
```

**特点**：
- 使用 Rich 标记语法 `[bold]`, `[dim]`
- 样式与颜色分离，通过 `style=` 应用颜色
- 一致的标题格式
- 统一的缩进规范

### 1.2 当前项目的现状

查看 `src/application/cli/gui/render.py`:

```python
# 混合使用
console.print(f"[red]{catalog['error']}[/]")
console.print(f"[yellow]{catalog['message']}[/]")
console.print(f"[bold red]{result.get('message')}[/]")
```

**问题**：
1. 颜色和样式混在一起 `[bold red]`
2. 缺少统一的标题样式
3. 没有明确的层级规范
4. 辅助文本没有统一标记

### 1.3 差距分析

| 对比项 | 官方 | 当前项目 | 差距 |
|-------|-----|---------|-----|
| 样式定义 | 使用 Rich 标记 | 使用 Rich 标记 | 基本一致 |
| 颜色应用 | 通过 style= 参数 | 内联或 style= | 不统一 |
| 标题格式 | `[bold]Title[/bold]` + style | 无统一格式 | 需要规范 |
| 层级区分 | bold/dim/normal 清晰 | 不明显 | 需要加强 |

---

## 2. 优化目标

1. **建立文本层级体系**
   - 明确标题/正文/辅助文本的样式
   - 统一样式修饰符的使用

2. **分离样式和颜色**
   - 样式通过 `[bold]` 等标记
   - 颜色通过 `style=COLORS[...]` 应用

3. **提升可读性**
   - 信息层级清晰
   - 视觉重点突出

4. **便于维护**
   - 统一的样式规范
   - 减少内联样式

---

## 3. 设计方案

### 3.1 文本层级定义

定义四级文本层次：

| 层级 | 样式 | 颜色 | 用途 | 示例 |
|-----|------|------|------|------|
| H1 | bold | primary | 主标题 | "System Information" |
| H2 | bold | primary | 副标题 | "Global Commands" |
| Body | normal | text_primary | 正文 | 命令说明文本 |
| Caption | dim | text_dim | 辅助文本 | 路径、提示 |

### 3.2 样式修饰符

Rich 支持的常用修饰符：

| 修饰符 | 说明 | 使用场景 |
|-------|------|---------|
| `[bold]...[/bold]` | 加粗 | 标题、重要信息 |
| `[dim]...[/dim]` | 暗淡 | 次要信息、提示 |
| `[italic]...[/italic]` | 斜体 | 引用、注释（少用） |
| `[underline]...[/underline]` | 下划线 | 链接、强调（少用） |

**推荐使用**：
- 主要使用 `bold` 和 `dim`
- 避免过度使用 `italic` 和 `underline`

### 3.3 样式组合规则

**规则 1：样式在内，颜色在外**

```python
# 推荐
console.print("[bold]Token Usage:[/bold]", style=COLORS["primary"])

# 不推荐
console.print("[bold primary]Token Usage[/]")  # 颜色内联
```

**规则 2：多样式组合**

```python
# 组合样式通过 style= 参数
style = f"bold {COLORS['primary']}"
style = f"dim {COLORS['text_dim']}"
```

**规则 3：避免过度装饰**

```python
# 不推荐 - 过度装饰
console.print("[bold italic underline]Text[/]")

# 推荐 - 简洁清晰
console.print("[bold]Text[/bold]", style=COLORS["primary"])
```

---

## 4. 使用规范

### 4.1 标题样式

**主标题（H1）**：

```python
# 用于大块内容的标题（如 Panel 标题、章节标题）
console.print("[bold]System Information[/bold]", style=COLORS["primary"])
```

**副标题（H2）**：

```python
# 用于分组标题
console.print("[bold]Global Commands[/bold]", style=COLORS["primary"])
console.print()  # 标题后空一行
```

### 4.2 正文样式

**普通文本**：

```python
# 正文无需修饰符，使用默认颜色
console.print("Provider: OpenAI")
```

**列表项**：

```python
# 列表项前加缩进
console.print(f"  /switch <engine>    Switch execution engine")
```

**重要文本**：

```python
# 在正文中强调特定部分
console.print(f"Provider: [bold]{provider}[/bold]")
```

### 4.3 辅助文本样式

**提示文本**：

```python
# 使用 dim 修饰符 + text_dim 颜色
console.print(f"  {path}", style=COLORS["text_dim"])
```

**路径和元信息**：

```python
console.print(f"[dim]Location: {agent_dir}[/dim]", style=COLORS["text_dim"])
```

### 4.4 状态消息样式

**成功消息**：

```python
console.print("[bold]Operation completed successfully[/bold]", style=COLORS["success"])
```

**警告消息**：

```python
console.print("[bold]Warning: Configuration not found[/bold]", style=COLORS["warning"])
```

**错误消息**：

```python
console.print("[bold]Error: Connection failed[/bold]", style=COLORS["error"])
```

### 4.5 特殊场景

**Agent 输出（Markdown）**：

```python
from rich.markdown import Markdown

# Agent 输出渲染为 Markdown
markdown = Markdown(agent_response)
console.print(markdown, style=COLORS["agent"])
```

**代码块**：

```python
# 使用 dim 样式，避免过于突出
console.print(f"[dim]$ {command}[/dim]")
```

---

## 5. 实施清单

### 5.1 更新渲染函数

- [ ] 修改 `src/application/cli/gui/render.py`
- [ ] 统一标题样式（使用 `[bold]...[/bold]` + primary 颜色）
- [ ] 统一辅助文本样式（使用 `[dim]...[/dim]` + text_dim 颜色）
- [ ] 分离内联颜色，改用 `style=` 参数

### 5.2 更新主循环

- [ ] 修改 `src/application/cli/main.py`
- [ ] 更新错误消息样式
- [ ] 更新警告消息样式
- [ ] 统一提示信息样式

### 5.3 添加辅助函数

在 `theme.py` 中添加样式辅助函数：

```python
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

使用示例：

```python
from src.application.cli.theme import get_title_style

console.print("[bold]System Info[/bold]", style=get_title_style())
```

### 5.4 验证

- [ ] 检查所有标题是否统一格式
- [ ] 检查辅助文本是否使用 dim
- [ ] 确认无内联颜色残留（如 `[bold red]`）
- [ ] 确保信息层级清晰

---

## 附录：Rich 标记语法参考

### 基本标记

```
[bold]粗体文本[/bold]
[dim]暗淡文本[/dim]
[italic]斜体文本[/italic]
[underline]下划线文本[/underline]
[strike]删除线文本[/strike]
```

### 嵌套标记

```
[bold]这是[dim]嵌套[/dim]的示例[/bold]
```

### 闭合标记

```
[bold]粗体[/]           # 使用 [/] 关闭
[bold]粗体[/bold]        # 或显式关闭
```

### 不推荐的用法

```
# 不推荐：颜色内联
[bold red]文本[/]

# 推荐：分离样式和颜色
console.print("[bold]文本[/bold]", style=COLORS["error"])
```

---

## 对比示例

### 修改前

```python
console.print(f"[bold red]{result.get('message')}[/]")
console.print("[yellow]No MCP status available.[/]")
console.print(f"[cyan]{result.message}[/]")
```

### 修改后

```python
console.print(f"[bold]{result.get('message')}[/bold]", style=COLORS["error"])
console.print("No MCP status available.", style=COLORS["warning"])
console.print(result.message, style=COLORS["info"])
```

---

## 下一步

阅读 `04-icons-symbols.md` 了解图标符号规范。
