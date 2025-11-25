# 图标符号规范

## 目录
- 1. 现状分析
- 2. 优化目标
- 3. 设计方案
- 4. 使用规范
- 5. 实施清单

---

## 1. 现状分析

### 1.1 官方 DeepAgents 的做法

参考文件：`deepagents/libs/deepagents-cli/deepagents_cli/execution.py:224-237`

**工具图标映射**：

```python
tool_icons = {
    "read_file": "📖",
    "write_file": "✏️",
    "edit_file": "✂️",
    "ls": "📁",
    "glob": "🔍",
    "grep": "🔎",
    "shell": "⚡",
    "execute": "🔧",
    "web_search": "🌐",
    "http_request": "🌍",
    "task": "🤖",
    "write_todos": "📋",
}
```

**状态符号**（`ui.py:248-257`）：

```python
icon = "☑"   # 已完成
icon = "⏳"   # 进行中
icon = "☐"   # 待处理
```

**其他符号**：

```python
"⏺ "  # 文件操作标记
"⎿  " # 详情缩进
"●"   # Agent 输出开始符
"✓"   # 成功标记
"⚡"   # 执行/能量
"⚠️"   # 警告
```

**特点**：
- 完整的工具图标体系
- 使用 emoji 提升识别度
- 状态符号清晰
- 一致的视觉语言

### 1.2 当前项目的现状

查看 `src/application/cli/` 目录：

**问题**：
1. 完全没有图标系统
2. 没有为工具定义 emoji
3. 缺少状态符号定义
4. 视觉识别度低

### 1.3 差距分析

| 对比项 | 官方 | 当前项目 | 差距 |
|-------|-----|---------|-----|
| 工具图标 | 12 个 emoji | 无 | 需要建立 |
| 状态符号 | 3 个符号 | 无 | 需要定义 |
| 使用位置 | execution.py | 无 | 需要集成 |
| 视觉效果 | 直观清晰 | 纯文本 | 需要增强 |

---

## 2. 优化目标

1. **建立完整的图标系统**
   - 为常用工具定义 emoji
   - 为状态定义符号

2. **提升视觉识别度**
   - 通过图标快速识别工具类型
   - 通过符号快速识别状态

3. **遵守使用约束**
   - emoji 仅在 `src/application/cli/` 目录下使用
   - 不在核心逻辑代码中使用 emoji

4. **保持终端兼容性**
   - 优先使用常见 emoji
   - 提供降级方案

---

## 3. 设计方案

### 3.1 图标分类

将图标分为三类：

1. **工具图标** - 用于标识不同的工具
2. **状态符号** - 用于标识任务状态
3. **装饰符号** - 用于视觉引导

### 3.2 图标定义

在 `src/application/cli/theme.py` 中定义：

```python
# 工具图标 - Emoji
TOOL_ICONS = {
    # 文件操作
    "read_file": "📖",
    "write_file": "✏️",
    "edit_file": "✂️",
    "list_files": "📁",

    # 搜索工具
    "glob": "🔍",
    "grep": "🔎",
    "search": "🔍",

    # 执行工具
    "shell": "⚡",
    "execute": "🔧",
    "run": "▶",

    # 网络工具
    "web_search": "🌐",
    "http_request": "🌍",
    "fetch_url": "🌐",

    # Agent 工具
    "task": "🤖",
    "subagent": "🤖",
    "write_todos": "📋",

    # 默认图标
    "default": "🔧",
}

# 状态符号 - Unicode
STATUS_SYMBOLS = {
    "completed": "☑",     # Ballot Box with Check
    "in_progress": "⏳",   # Hourglass
    "pending": "☐",       # Ballot Box
    "failed": "☒",        # Ballot Box with X
}

# 装饰符号 - Unicode
DECORATIVE_SYMBOLS = {
    "bullet": "●",        # Bullet
    "record": "⏺",        # Media Record
    "branch": "⎿",        # Box Drawings
    "checkmark": "✓",     # Check Mark
    "warning": "⚠",       # Warning Sign
    "info": "ℹ",          # Information
    "arrow_right": "→",   # Rightward Arrow
}
```

### 3.3 图标选择理由

| 图标 | 含义 | 选择理由 |
|-----|------|---------|
| 📖 | read_file | 书籍代表阅读 |
| ✏️ | write_file | 铅笔代表写入 |
| ✂️ | edit_file | 剪刀代表编辑 |
| 🔍 | 搜索类 | 放大镜代表搜索 |
| ⚡ | shell | 闪电代表执行 |
| 🤖 | Agent | 机器人代表 AI |
| 🌐 | 网络类 | 地球代表互联网 |

### 3.4 降级方案

对于不支持 emoji 的终端，提供纯 ASCII 降级：

```python
# 在 theme.py 中添加检测逻辑
import os
import sys

def is_emoji_supported() -> bool:
    """检测终端是否支持 emoji"""
    # Windows 较新版本支持
    if sys.platform == "win32":
        return sys.getwindowsversion().build >= 18362  # type: ignore
    # Unix 系统默认支持
    return True

# 根据支持情况选择图标
if is_emoji_supported():
    TOOL_ICONS = {...}  # emoji 版本
else:
    TOOL_ICONS = {      # ASCII 降级版本
        "read_file": "[R]",
        "write_file": "[W]",
        "shell": "[!]",
        # ...
    }
```

---

## 4. 使用规范

### 4.1 使用约束

**约束 1：仅限 CLI 目录**

```
允许使用：
src/application/cli/
├── theme.py          # 定义图标
├── gui/
│   ├── render.py     # 使用图标
│   └── logo.py       # Logo 不使用 emoji
└── main.py           # 使用图标

禁止使用：
src/components/       # 核心逻辑
src/llm/              # LLM 相关
src/application/services/  # 服务层
```

**约束 2：集中管理**

所有图标定义必须在 `theme.py` 中，不得分散定义。

**约束 3：提供降级**

必须考虑终端兼容性，提供 ASCII 降级方案。

### 4.2 工具图标使用

**获取图标**：

```python
from src.application.cli.theme import TOOL_ICONS

# 获取特定工具图标
icon = TOOL_ICONS.get("read_file", TOOL_ICONS["default"])

# 使用
console.print(f"  {icon} {tool_name}({args})")
```

**显示工具调用**：

```python
# 参考官方 execution.py:515
icon = TOOL_ICONS.get(tool_name, "🔧")
console.print(f"  {icon} {display_str}", style=f"dim {COLORS['tool']}")
```

### 4.3 状态符号使用

**任务列表**：

```python
from src.application.cli.theme import STATUS_SYMBOLS

for task in tasks:
    icon = STATUS_SYMBOLS.get(task.status, "☐")
    console.print(f"{icon} {task.description}")
```

**输出示例**：

```
☑ Task 1 completed
⏳ Task 2 in progress
☐ Task 3 pending
```

### 4.4 装饰符号使用

**文件操作提示**：

```python
from src.application.cli.theme import DECORATIVE_SYMBOLS

# 操作标记
console.print(f"{DECORATIVE_SYMBOLS['record']} Update(file.py)")

# 详情缩进
console.print(f"  {DECORATIVE_SYMBOLS['branch']}  Details here")
```

**Agent 输出开始符**：

```python
console.print(f"{DECORATIVE_SYMBOLS['bullet']} ", style=COLORS["agent"], end="")
```

### 4.5 禁止的用法

1. **不要直接硬编码 emoji**

```python
# 错误
console.print("📖 Reading file...")

# 正确
icon = TOOL_ICONS["read_file"]
console.print(f"{icon} Reading file...")
```

2. **不要在核心逻辑中使用**

```python
# 错误 - 在 service 层使用
# src/application/services/agent/basic.py
def handle_query(...):
    logger.info("🤖 Processing query")  # 错误！

# 正确 - 仅在 CLI 层使用
# src/application/cli/main.py
console.print(f"{TOOL_ICONS['task']} Processing...")
```

3. **不要创建新的图标定义**

所有新图标必须添加到 `theme.py`，不得在使用位置定义。

---

## 5. 实施清单

### 5.1 创建图标定义

- [ ] 在 `theme.py` 中添加 `TOOL_ICONS` 字典
- [ ] 在 `theme.py` 中添加 `STATUS_SYMBOLS` 字典
- [ ] 在 `theme.py` 中添加 `DECORATIVE_SYMBOLS` 字典
- [ ] 实现 `is_emoji_supported()` 检测函数
- [ ] 实现 ASCII 降级方案

### 5.2 集成到渲染模块

- [ ] 修改 `render.py`，导入图标定义
- [ ] 在合适位置使用工具图标（如果有工具列表展示）
- [ ] 在合适位置使用状态符号（如果有任务列表）

### 5.3 集成到主循环

- [ ] 修改 `main.py`，导入图标定义
- [ ] 在错误/警告消息中使用装饰符号
- [ ] 确保不在核心逻辑中使用 emoji

### 5.4 验证

- [ ] 在支持 emoji 的终端测试显示效果
- [ ] 在不支持 emoji 的终端测试降级效果
- [ ] 检查 `src/components/` 等目录无 emoji
- [ ] 确认所有图标来自 `theme.py`

---

## 附录：Unicode 符号参考

### 常用状态符号

```
☐  U+2610  Ballot Box
☑  U+2611  Ballot Box with Check
☒  U+2612  Ballot Box with X
⏳  U+23F3  Hourglass
```

### 常用装饰符号

```
●  U+25CF  Black Circle
○  U+25CB  White Circle
⏺  U+23FA  Black Circle for Record
⎿  U+23BF  Dentistry Symbol Light Vertical with Bottom
✓  U+2713  Check Mark
✗  U+2717  Ballot X
→  U+2192  Rightward Arrow
⚠  U+26A0  Warning Sign
ℹ  U+2139  Information Source
```

### Emoji 编码

```
📖  U+1F4D6  Open Book
✏️  U+270F   Pencil
✂️  U+2702   Scissors
📁  U+1F4C1  File Folder
🔍  U+1F50D  Left-Pointing Magnifying Glass
⚡  U+26A1   High Voltage
🔧  U+1F527  Wrench
🌐  U+1F310  Globe with Meridians
🤖  U+1F916  Robot
📋  U+1F4CB  Clipboard
```

---

## 下一步

阅读 `05-components.md` 了解 Rich 组件规范。
