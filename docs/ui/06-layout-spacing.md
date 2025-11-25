# 布局间距规范

## 目录
- 1. 现状分析
- 2. 优化目标
- 3. 设计方案
- 4. 使用规范
- 5. 实施清单

---

## 1. 现状分析

### 1.1 官方 DeepAgents 的做法

参考文件：`deepagents/libs/deepagents-cli/deepagents_cli/ui.py`

**缩进规范**（`ui.py:498`）：

```python
# 命令列表 - 统一 2 空格缩进
for cmd, desc in COMMANDS.items():
    console.print(f"  /{cmd:<12} {desc}", style=COLORS["dim"])
    #               ^^          ^^
    #               缩进        对齐宽度 12
```

**对齐宽度**：
- 命令语法：12 字符宽度
- 文件路径：根据终端宽度自动换行

**垂直间距**：
- 标题后：空 1 行
- 章节间：空 1 行
- Panel 前后：空 1 行

**特点**：
- 固定的缩进规范
- 统一的对齐宽度
- 清晰的垂直节奏

### 1.2 当前项目的现状

查看 `src/application/cli/gui/render.py:76`：

```python
def _format_command_section(...):
    for syntax, description in commands:
        lines.append(f"{syntax:<28} {description}")
        #                      ^^
        #                      对齐宽度 28（比官方宽）
```

**问题**：
1. 对齐宽度 28，比官方的 12 更宽
2. 缩进不统一
3. 垂直间距随意

### 1.3 差距分析

| 对比项 | 官方 | 当前项目 | 差距 |
|-------|-----|---------|------|
| 缩进单位 | 2 空格 | 不固定 | 需要统一 |
| 对齐宽度 | 12 | 28 | 需要调整 |
| 垂直间距 | 规范 | 随意 | 需要规范 |

---

## 2. 优化目标

1. **建立统一的缩进体系**
   - 定义标准缩进单位
   - 明确各层级缩进

2. **规范对齐宽度**
   - 命令列表对齐
   - 避免过宽导致浪费空间

3. **规范垂直间距**
   - 标题、段落、章节的间距
   - 提升阅读节奏

---

## 3. 设计方案

### 3.1 缩进定义

在 `theme.py` 中定义：

```python
# 缩进单位
INDENT = {
    "none": "",
    "small": "  ",      # 2 空格 - 列表项
    "medium": "    ",   # 4 空格 - 嵌套内容
    "large": "      ",  # 6 空格 - 深度嵌套
}

# 对齐宽度
ALIGNMENT = {
    "command": 28,      # 命令语法列对齐（保留我们的 28）
    "label": 12,        # 标签对齐
}
```

**选择理由**：
- 保留 28 宽度：我们的命令更长（如 `/switch <engine>`）
- 2 空格缩进：与官方一致，节省空间

### 3.2 垂直间距规则

```python
# 垂直间距
SPACING = {
    "none": 0,          # 紧密相连
    "tight": 1,         # 标题后
    "normal": 1,        # 段落间
    "loose": 2,         # 章节间
}
```

**使用场景**：

| 场景 | 间距 | 实现 |
|-----|------|------|
| 标题后 | 1 行 | `console.print()` |
| 列表项间 | 0 行 | 连续 print |
| 段落间 | 1 行 | `console.print()` |
| 章节间 | 2 行 | `console.print("\n")` |
| Panel 前后 | 1 行 | `console.print()` |

---

## 4. 使用规范

### 4.1 缩进使用

**规则 1：列表项使用 small 缩进**

```python
# 命令列表
console.print("[bold]Commands:[/bold]")
console.print()
for cmd, desc in commands:
    console.print(f"{INDENT['small']}{cmd:<{ALIGNMENT['command']}} {desc}")
```

**规则 2：嵌套内容使用 medium 缩进**

```python
# 嵌套说明
console.print("[bold]Options:[/bold]")
console.print()
console.print(f"{INDENT['small']}--agent NAME")
console.print(f"{INDENT['medium']}Specify agent name")
```

**规则 3：不要手动拼接空格**

```python
# 错误
console.print("  Item")

# 正确
console.print(f"{INDENT['small']}Item")
```

### 4.2 对齐使用

**命令列表对齐**：

```python
# 使用 ALIGNMENT['command']
for syntax, desc in commands:
    console.print(f"{INDENT['small']}{syntax:<{ALIGNMENT['command']}} {desc}")
```

**输出示例**：

```
  /switch <engine>             Switch execution engine
  /help                        Show contextual help
  /info                        Display current engine status
```

**标签对齐**：

```python
# 信息列表
info = [
    ("Provider", "OpenAI"),
    ("Model", "gpt-4o"),
]
for label, value in info:
    console.print(f"{label:<{ALIGNMENT['label']}} {value}")
```

**输出示例**：

```
Provider     OpenAI
Model        gpt-4o
```

### 4.3 垂直间距使用

**标题后空 1 行**：

```python
console.print("[bold]Section Title[/bold]")
console.print()  # 空 1 行
console.print("Content...")
```

**段落间空 1 行**：

```python
console.print("First paragraph...")
console.print()  # 空 1 行
console.print("Second paragraph...")
```

**章节间空 2 行**：

```python
# 章节 1
console.print("[bold]Chapter 1[/bold]")
console.print("Content...")

console.print("\n")  # 空 2 行

# 章节 2
console.print("[bold]Chapter 2[/bold]")
console.print("Content...")
```

**Panel 前后空 1 行**：

```python
console.print("Text before panel...")
console.print()  # 空 1 行
console.print(Panel(...))
console.print()  # 空 1 行
console.print("Text after panel...")
```

---

## 5. 实施清单

### 5.1 创建间距配置

- [ ] 在 `theme.py` 中添加 `INDENT` 字典
- [ ] 在 `theme.py` 中添加 `ALIGNMENT` 字典
- [ ] 在 `theme.py` 中添加 `SPACING` 字典（可选）

### 5.2 更新缩进使用

- [ ] 修改 `render.py` 的命令列表格式化
- [ ] 将硬编码空格改为 `INDENT['small']`
- [ ] 将对齐宽度 28 改为 `ALIGNMENT['command']`

### 5.3 规范垂直间距

- [ ] 检查所有标题后是否空 1 行
- [ ] 检查段落间间距
- [ ] 检查 Panel 前后间距
- [ ] 统一章节间间距

### 5.4 验证

- [ ] 命令列表对齐整齐
- [ ] 无手动拼接的空格字符串
- [ ] 垂直间距一致
- [ ] 阅读节奏流畅

---

## 附录：排版示例

### 标准布局模板

```python
# 主标题
console.print("[bold]System Information[/bold]", style=COLORS["primary"])
console.print()  # 空 1 行

# 分组 1
console.print("[bold]Configuration[/bold]", style=COLORS["primary"])
console.print()
console.print(f"{INDENT['small']}Provider     OpenAI")
console.print(f"{INDENT['small']}Model        gpt-4o")

console.print()  # 段落间空 1 行

# 分组 2
console.print("[bold]Status[/bold]", style=COLORS["primary"])
console.print()
console.print(f"{INDENT['small']}Connected    Yes")
```

### 命令列表模板

```python
console.print("[bold]Available Commands[/bold]", style=COLORS["primary"])
console.print()

commands = [
    ("/switch <engine>", "Switch execution engine"),
    ("/help", "Show help"),
]

for syntax, desc in commands:
    console.print(f"{INDENT['small']}{syntax:<{ALIGNMENT['command']}} {desc}")
```

---

## 下一步

阅读 `07-implementation.md` 了解具体实施步骤。
