# UI 控件与渲染设计

## 1. 概述

本文档定义 Setup Wizard 的交互控件和 Rich 渲染规范。
交互控件基于 prompt_toolkit 处理键盘事件，基于 Rich 进行视觉渲染。
两个库均为现有项目依赖，不引入新依赖。

## 2. 控件清单

| 控件 | 用途 | 键盘交互 |
|------|------|---------|
| `SelectOne` | 单选列表（选 provider 等） | PgUp/PgDn 导航，Enter 确认 |
| `SelectMany` | 多选列表（选工具等） | PgUp/PgDn 导航，Space 选中/取消，Enter 确认 |
| Rich `Prompt.ask()` | 文本输入（API key、URL） | 直接输入 |
| Rich `Prompt.ask(choices=...)` | 确认输入（y/N/skip） | 直接输入 |

## 3. SelectOne 控件

### 3.1 接口

```python
@dataclass
class Option:
    """A single selectable option."""
    key: str            # unique identifier, e.g., "zhipu"
    label: str          # display text, e.g., "zhipu"
    description: str    # detail text, e.g., "Zhipu GLM (recommended)"
    status: str = ""    # right-side status, e.g., "configured"
    disabled: bool = False

class SelectOne:
    """Single-select list with keyboard navigation."""

    def __init__(
        self,
        title: str,
        options: List[Option],
        console: Console,
        default: str = None,       # default option key
    ):
        ...

    def run(self) -> Optional[Option]:
        """Block until user selects an option. Returns selected Option or None."""
        ...
```

### 3.2 渲染效果

```
Select default LLM provider:

    zhipu     Zhipu GLM (recommended, free tier)       not configured
  > openai    OpenAI GPT (supports custom base_url)    not configured
    tongyi    Tongyi Qwen                              not configured
    ollama    Local models (no API key needed)          available

  [PgUp/PgDn] Navigate  [Enter] Select
```

视觉规范：
- 当前高亮行使用 `>` 前缀标记，文字使用 bold + 主题高亮色
- 非高亮行使用默认色
- Status 列右对齐，`configured` 使用绿色，`not configured` 使用暗灰色
- 底部提示行使用 dim 样式
- disabled 选项使用删除线或暗灰色，不可选中

### 3.3 键盘绑定

| 按键 | 行为 |
|------|------|
| PgUp / Up | 上移高亮 |
| PgDn / Down | 下移高亮 |
| Enter | 确认选中当前高亮项 |
| q / Escape | 取消（返回 None） |

### 3.4 实现要点

**渲染与输入的职责分离：**

- **prompt_toolkit** 负责：键盘事件监听、交互状态管理、选项列表的动态渲染。
  使用 `prompt_toolkit.application.Application` 创建独立的事件循环，
  选项列表使用 `prompt_toolkit.formatted_text.FormattedText` 渲染。
- **Rich** 负责：静态输出（标题、表格、Banner），在 `SelectOne.run()` 调用前后使用。
  交互期间不调用 Rich 渲染，避免两个库同时管理终端状态。

**渲染刷新机制：**

- 每次按键触发重新构建 `FormattedText`（更新高亮位置）
- `prompt_toolkit.layout` 自动处理终端刷新和光标定位
- 渲染和输入在同一事件循环中，无并发问题

**颜色映射：**

将项目 Rich 主题色映射到 prompt_toolkit 的 ANSI 样式，保持视觉一致：

```python
PT_STYLES = {
    "highlight": "bold ansibrightcyan",
    "configured": "ansibrightgreen",
    "not_configured": "ansigray",
    "hint": "italic ansigray",
}
```

## 4. SelectMany 控件

### 4.1 接口

```python
class SelectMany:
    """Multi-select list with keyboard navigation and toggle."""

    def __init__(
        self,
        title: str,
        options: List[Option],
        console: Console,
        pre_selected: List[str] = None,  # pre-selected option keys
    ):
        ...

    def run(self) -> List[Option]:
        """Block until user confirms. Returns list of selected Options."""
        ...
```

### 4.2 渲染效果

```
Select tools to configure:

    [x] Tavily Search     TAVILY_API_KEY     not configured
  > [ ] AMap Services     AMAP_API_KEY       not configured
    [x] Notion MCP        NOTION_TOKEN       not configured
    [ ] Context7 MCP      CONTEXT7_API_KEY   not configured
    [ ] AMap Maps MCP     AMAP_MAPS_API_KEY  not configured
    [ ] Firecrawl MCP     FIRECRAWL_API_KEY  not configured

  [PgUp/PgDn] Navigate  [Space] Toggle  [Enter] Confirm
```

视觉规范：
- `[x]` 表示已选中，使用主题色
- `[ ]` 表示未选中
- 当前高亮行使用 `>` 前缀
- 底部提示行包含三个操作说明

### 4.3 键盘绑定

| 按键 | 行为 |
|------|------|
| PgUp / Up | 上移高亮 |
| PgDn / Down | 下移高亮 |
| Space | 切换当前行选中状态 |
| Enter | 确认所有选中项 |
| a | 全选 |
| n | 全不选 |
| q / Escape | 取消（返回空列表） |

## 5. Rich 渲染规范

### 5.1 颜色主题

复用项目现有主题定义 (`src/application/cli/theme.py` 的 `COLORS`)：

| 语义 | 用途 | 引用 |
|------|------|------|
| `COLORS["info"]` | 标题、高亮、选中项 | 青色系 |
| `COLORS["success"]` | pass 状态、已配置项 | 绿色系 |
| `COLORS["warning"]` | warn 状态、提示 | 黄色系 |
| `COLORS["error"]` | fail 状态、错误 | 红色系 |
| `COLORS["text_dim"]` | 辅助文字、未配置项 | 暗灰色 |

### 5.2 Setup Wizard 渲染元素

**Welcome Banner:**
```python
Panel(
    Text("IRIS Setup Wizard", style="bold"),
    subtitle=f"v{version}",
    border_style=COLORS["info"],
    padding=(1, 2),
)
```

**Step Header:**
```python
Rule(f"Step {i}/{total}: {step.title}", style=COLORS["info"])
```

**Status Table:**
```python
table = Table(show_header=True, header_style="bold")
table.add_column("Provider", style="bold")
table.add_column("Description")
table.add_column("Status", justify="right")
# For each row:
#   configured -> style=COLORS["success"]
#   not configured -> style=COLORS["text_dim"]
```

**Result Indicators:**
```python
# pass
console.print(f"  [*] {message}", style=COLORS["success"])
# fail
console.print(f"  [x] {message}", style=COLORS["error"])
# warn
console.print(f"  [!] {message}", style=COLORS["warning"])
# skip
console.print(f"  [-] {message}", style=COLORS["text_dim"])
```

**Summary Panel:**
```python
Panel(
    summary_text,
    title="Setup Complete",
    border_style=COLORS["success"],
    padding=(1, 2),
)
```

### 5.3 Doctor 报告渲染

```python
# Category header
console.print(f"\n{category}:", style="bold")

# Check results
for result in results:
    icon_map = {"pass": "[*]", "fail": "[x]", "warn": "[!]"}
    style_map = {
        "pass": COLORS["success"],
        "fail": COLORS["error"],
        "warn": COLORS["warning"],
    }
    console.print(
        f"  {icon_map[result.status]} {result.message}",
        style=style_map[result.status],
    )

# Summary line
Rule(style=COLORS["text_dim"])
console.print(
    f"Summary: {pass_count} passed, {fail_count} failed, {warn_count} warnings",
    style="bold",
)
```

### 5.4 API Key 输入

```python
# Masked input for sensitive values
key = Prompt.ask(
    f"  {key_name}",
    password=True,       # mask with ****
    console=console,
)
```

### 5.5 Confirmation Input

```python
# y/N style
answer = Prompt.ask(
    "  Configure another provider?",
    choices=["y", "N"],
    default="N",
    console=console,
)

# y/skip style
answer = Prompt.ask(
    f"  Configure {key_name}?",
    choices=["y", "skip"],
    default="skip",
    console=console,
)
```

## 6. 控件文件位置

```
src/core/config/setup/widgets.py
```

包含：
- `Option` dataclass
- `SelectOne` class
- `SelectMany` class

控件仅依赖 `prompt_toolkit` 和 `rich`，不依赖项目其他模块。
