# 引擎模式 UI 差异说明

## 目录
- 1. 概述
- 2. LLM 引擎 UI
- 3. Agent Basic 模式 UI
- 4. Agent Deep 模式 UI
- 5. Dify 引擎 UI
- 6. 实施优先级
- 7. 修改检查清单

---

## 1. 概述

### 1.1 项目引擎架构

本项目支持多种执行引擎：

| 引擎 | 模式 | 说明 |
|-----|------|------|
| LLM | - | 直接 LLM 对话，无工具调用 |
| Agent | Basic | 基础 Agent，有工具但流式输出简单 |
| Agent | Deep | 深度 Agent，复杂工具编排和 HITL |
| AgentFlow | - | （未实现） |
| Dify | - | Dify 平台集成 |

### 1.2 UI 实现差异

每个引擎/模式的 UI 实现**完全独立**，使用不同的技术栈和样式：

| 引擎/模式 | UI 系统 | 文件位置 | 特点 |
|---------|--------|---------|------|
| LLM | StreamingDisplay | `src/llm/utils/streaming.py` | Rich Live + Panel 实时流式 |
| Agent Basic | 复用 LLM | `src/application/services/agent/basic/` | 与 LLM 相同 |
| Agent Deep | DeepAgentEventHandler | `src/application/services/agent/deep/streaming/` | 事件驱动，纯文本输出 |
| Dify | DifyStreaming | `src/application/services/dify/streaming.py` | 自定义流式处理 |

### 1.3 优化范围

本次 UI 优化需要**分别修改**每个引擎的实现：

1. 修改 LLM 引擎 → 自动影响 Agent Basic 模式
2. 单独修改 Agent Deep 模式
3. 单独修改 Dify 引擎
4. AgentFlow 待实现时再考虑

---

## 2. LLM 引擎 UI

### 2.1 文件位置

```
src/llm/utils/streaming.py
├── StreamingDisplay 类          # 流式显示管理器
├── StreamingCallbackHandler     # 回调处理
├── ZhipuStreamingLLM           # 智谱 AI
├── OpenAIStreamingLLM          # OpenAI
└── OllamaStreamingLLM          # Ollama
```

### 2.2 当前实现

**StreamingDisplay 类（101-161行）**：

```python
class StreamingDisplay:
    def _create_panel(self) -> Panel:
        display_content = self.content + "▊"  # 光标效果

        return Panel(
            Text(display_content, style="green"),  # 硬编码
            title=f"[bold cyan]{self.title}[/]",   # 硬编码
            border_style="cyan",                    # 硬编码
            padding=(1, 2)                          # 与官方不同
        )
```

**完成后显示（519-546行）**：

```python
console.print(Panel(
    full_response,
    title=f"[bold green]{display_title} (完成)[/]",  # 硬编码
    border_style="green"                            # 硬编码
))

console.print(
    f"[dim]⚡ 性能: {elapsed:.2f}s | ..."  # 硬编码
)
```

### 2.3 需要修改的内容

**修改 1：引入主题配置**

在文件开头添加：

```python
from src.application.cli.theme import COLORS, PANEL_DEFAULTS
```

**修改 2：更新 Panel 样式**

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
    **PANEL_DEFAULTS  # box=box.ROUNDED, padding=(0, 1)
)
```

**修改 3：更新完成显示**

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

**修改 4：更新性能指标样式**

```python
# 修改前
console.print(f"[dim]⚡ 性能: ...")

# 修改后
console.print(
    f"Performance: {elapsed:.2f}s | ...",
    style=COLORS["text_dim"]
)
```

### 2.4 实施清单

- [ ] 在 `streaming.py` 顶部导入 theme
- [ ] 修改 `_create_panel()` 方法
- [ ] 修改完成后的 Panel 显示
- [ ] 修改性能指标样式
- [ ] 移除硬编码颜色（green, cyan）
- [ ] 测试 LLM 引擎流式输出

---

## 3. Agent Basic 模式 UI

### 3.1 文件位置

```
src/application/services/agent/basic/streaming.py
```

### 3.2 当前实现

Basic 模式通过 `stream_response()` 函数复用 LLM 的流式输出：

```python
async def stream_response(...) -> str:
    return await stream_llm_response(
        provider=provider,
        prompt=prompt,
        llm=llm,
        ...
    )
```

### 3.3 需要修改的内容

**无需单独修改**！

修改 LLM 引擎的 `streaming.py` 会自动影响 Basic 模式。

### 3.4 注意事项

- Basic 模式与 LLM 引擎共享 UI
- 测试时需要同时验证 LLM 和 Basic 模式
- 确保两者显示一致

---

## 4. Agent Deep 模式 UI

### 4.1 文件位置

```
src/application/services/agent/deep/streaming/
├── conversation.py            # 对话处理
└── event_handler.py          # 事件处理和 UI 渲染
```

### 4.2 当前实现

**DeepAgentEventHandler 类（30-62行）**：

使用纯文本输出，没有 Panel 包装，直接 `console.print` 硬编码样式。

**工具调用显示（351行）**：

```python
self.console.print(
    f"  Tool: {escape(display_str)}",
    style="dim cyan",  # 硬编码
    markup=False
)
```

**错误显示（155, 189行）**：

```python
self.console.print(tool_content, style="red", markup=False)  # 硬编码
```

**Agent 输出（392, 395行）**：

```python
self.console.print("Agent:", style="bold blue", markup=False)  # 硬编码
self.console.print(escape(self._pending_text), style="white")  # 硬编码
```

### 4.3 需要修改的内容

**修改 1：引入主题配置**

在 `event_handler.py` 顶部添加：

```python
from src.application.cli.theme import COLORS
```

**修改 2：更新工具调用样式**

```python
# 修改前（351行）
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

**修改 3：更新错误样式**

```python
# 修改前（155, 189行）
self.console.print(tool_content, style="red", markup=False)

# 修改后
self.console.print(tool_content, style=COLORS["error"], markup=False)
```

**修改 4：更新 Agent 输出样式**

```python
# 修改前（392, 395行）
self.console.print("Agent:", style="bold blue", markup=False)
self.console.print(escape(self._pending_text), style="white")

# 修改后
self.console.print("Agent:", style=f"bold {COLORS['agent']}", markup=False)
self.console.print(escape(self._pending_text), style=COLORS["text_primary"])
```

### 4.4 设计决策

**为什么不添加 Panel 包装？**

1. Deep Agent 输出复杂，包含多个工具调用、子 Agent 等
2. Panel 会增加视觉噪音，干扰信息阅读
3. 纯文本输出更适合复杂场景
4. 保持与官方 DeepAgents 的一致性（官方也不用 Panel 包装 Agent 输出）

**优化策略**：
- 统一颜色系统
- 保持纯文本简洁风格
- 通过颜色区分信息类型

### 4.5 实施清单

- [ ] 在 `event_handler.py` 导入 theme
- [ ] 更新工具调用样式（351行）
- [ ] 更新错误样式（155, 189行）
- [ ] 更新 Agent 输出样式（392, 395行）
- [ ] 检查所有硬编码颜色
- [ ] 测试 Deep Agent 各种场景

---

## 5. Dify 引擎 UI

### 5.1 文件位置

```
src/application/services/dify/
├── service.py        # 服务主逻辑
├── streaming.py      # 流式输出处理
└── upload.py         # 文件上传
```

### 5.2 当前实现

**service.py 中的硬编码样式**：

```python
# 129, 136行 - 信息提示
self.console.print(f"[dim]...[/]")

# 185, 207行 - 重试提示
self.console.print(f"[yellow]Warning: ...[/]")
self.console.print(f"[yellow]Retrying in {retry_delay}s...[/]")

# 223行 - 错误提示
self.console.print(f"[red]{error_msg}[/]")

# 298, 308, 317行 - 文件列表
self.console.print(f"[blue]Pending files: {len(self.uploaded_files)}[/]")
self.console.print(f"[dim]No files are queued...[/]")

# 340, 341行 - 操作反馈
self.console.print(f"[green]Removed file: {filename}[/]")
self.console.print(f"[dim]{len(self.uploaded_files)} file(s) remain...[/]")
```

**streaming.py 中的硬编码样式**：

```python
# 240, 272, 284行 - Agent 思考
self.console.print(f"\n[cyan]Agent Thought: {thought}[/cyan]")

# 310行 - 最终答案标题
self.console.print(f"\n[bold green]Answer:[/bold green]")

# 323行 - 内容输出
self.console.print(final_content, style="bright_white")

# 358, 368行 - 错误和文件
self.console.print(f"\n[red]Error: {error_msg}[/red]")
self.console.print(f"\n[blue]File: {filename}[/blue]")

# 377, 387, 396行 - 缓冲输出和元数据
self.console.print(buffered_content, end="", style="bright_white")
self.console.print(f"\n[dim]Tokens: {usage}[/dim]")
```

### 5.3 需要修改的内容

**修改 1：引入主题配置**

在 `service.py` 和 `streaming.py` 顶部添加：

```python
from src.application.cli.theme import COLORS
```

**修改 2：更新 service.py 样式**

```python
# 暗提示
# 修改前：self.console.print(f"[dim]...[/]")
# 修改后：self.console.print("...", style=COLORS["text_dim"])

# 警告
# 修改前：self.console.print(f"[yellow]Warning: ...[/]")
# 修改后：self.console.print("Warning: ...", style=COLORS["warning"])

# 错误
# 修改前：self.console.print(f"[red]{error_msg}[/]")
# 修改后：self.console.print(error_msg, style=COLORS["error"])

# 成功
# 修改前：self.console.print(f"[green]Removed file: ...[/]")
# 修改后：self.console.print("Removed file: ...", style=COLORS["success"])

# 信息
# 修改前：self.console.print(f"[blue]Pending files: ...[/]")
# 修改后：self.console.print("Pending files: ...", style=COLORS["info"])
```

**修改 3：更新 streaming.py 样式**

```python
# Agent 思考
# 修改前：self.console.print(f"\n[cyan]Agent Thought: {thought}[/cyan]")
# 修改后：self.console.print(f"\nAgent Thought: {thought}", style=COLORS["info"])

# 答案标题
# 修改前：self.console.print(f"\n[bold green]Answer:[/bold green]")
# 修改后：self.console.print("\n[bold]Answer:[/bold]", style=COLORS["success"])

# 内容输出
# 修改前：self.console.print(final_content, style="bright_white")
# 修改后：self.console.print(final_content, style=COLORS["text_primary"])

# 错误
# 修改前：self.console.print(f"\n[red]Error: {error_msg}[/red]")
# 修改后：self.console.print(f"\nError: {error_msg}", style=COLORS["error"])

# 元数据
# 修改前：self.console.print(f"\n[dim]Tokens: {usage}[/dim]")
# 修改后：self.console.print(f"\nTokens: {usage}", style=COLORS["text_dim"])
```

### 5.4 实施清单

- [ ] 在 `service.py` 导入 theme
- [ ] 在 `streaming.py` 导入 theme
- [ ] 更新 `service.py` 所有颜色引用
- [ ] 更新 `streaming.py` 所有颜色引用
- [ ] 检查 `upload.py` 是否有硬编码
- [ ] 测试 Dify 引擎各种场景

---

## 6. 实施优先级

### 6.1 推荐顺序

按影响范围和重要性排序：

| 优先级 | 引擎/模式 | 原因 | 预计耗时 |
|-------|---------|------|---------|
| 1 | LLM 引擎 | 影响 LLM + Basic 两种模式 | 15 分钟 |
| 2 | Agent Deep | 独立系统，高频使用 | 10 分钟 |
| 3 | Dify | 独立系统，使用相对少 | 20 分钟 |

### 6.2 实施步骤

**步骤 1：修改 LLM 引擎**
1. 修改 `src/llm/utils/streaming.py`
2. 测试 LLM 引擎流式输出
3. 测试 Agent Basic 模式（自动继承）

**步骤 2：修改 Deep Agent**
1. 修改 `src/application/services/agent/deep/streaming/event_handler.py`
2. 测试工具调用显示
3. 测试错误处理
4. 测试 Agent 输出

**步骤 3：修改 Dify**
1. 修改 `src/application/services/dify/service.py`
2. 修改 `src/application/services/dify/streaming.py`
3. 测试完整对话流程
4. 测试文件上传功能

---

## 7. 修改检查清单

### 7.1 代码检查

**LLM 引擎**：
- [ ] `streaming.py` 导入 theme
- [ ] `StreamingDisplay._create_panel()` 更新
- [ ] 完成后 Panel 样式更新
- [ ] 性能指标样式更新
- [ ] 无硬编码颜色（green, cyan）

**Agent Deep**：
- [ ] `event_handler.py` 导入 theme
- [ ] 工具调用样式更新（351行）
- [ ] 错误样式更新（155, 189行）
- [ ] Agent 输出样式更新（392, 395行）
- [ ] 无硬编码颜色（red, cyan, blue, white）

**Dify**：
- [ ] `service.py` 导入 theme
- [ ] `streaming.py` 导入 theme
- [ ] 所有 console.print 更新颜色
- [ ] 无硬编码颜色（yellow, red, green, blue, cyan）

### 7.2 功能验证

**LLM 引擎**：
- [ ] 启动 CLI，切换到 LLM 引擎
- [ ] 发送查询，查看流式输出
- [ ] 检查 Panel 边框为圆角
- [ ] 检查 Panel padding 正确
- [ ] 检查颜色符合主题

**Agent Basic**：
- [ ] 切换到 Agent 引擎，Basic 模式
- [ ] 发送查询，查看流式输出
- [ ] 与 LLM 引擎显示一致

**Agent Deep**：
- [ ] 切换到 Agent 引擎，Deep 模式
- [ ] 发送复杂查询（触发工具调用）
- [ ] 检查工具调用显示
- [ ] 检查错误处理显示
- [ ] 检查 Agent 输出显示

**Dify**：
- [ ] 切换到 Dify 引擎
- [ ] 测试对话流程
- [ ] 测试文件上传
- [ ] 测试错误提示
- [ ] 检查所有输出颜色

### 7.3 视觉一致性

- [ ] 所有引擎的成功消息颜色一致
- [ ] 所有引擎的错误消息颜色一致
- [ ] 所有引擎的警告消息颜色一致
- [ ] 所有引擎的暗提示颜色一致
- [ ] LLM/Basic 的 Panel 样式统一

---

## 8. 特殊注意事项

### 8.1 LLM 引擎的 padding 变更

**变更内容**：
- 从 `padding=(1, 2)` 改为 `padding=(0, 1)`
- 与官方 DeepAgents 保持一致

**影响**：
- Panel 内容上下间距变小
- 视觉上更紧凑

**验证**：
- 确保文本不会贴边
- 长文本输出仍然清晰

### 8.2 Deep Agent 保持纯文本

**设计决策**：
- 不添加 Panel 包装
- 保持纯文本简洁输出
- 通过颜色区分信息类型

**原因**：
- Deep Agent 输出复杂
- Panel 会增加视觉噪音
- 与官方实践一致

### 8.3 Dify 引擎的特殊样式

**Dify 特有的显示**：
- Agent Thought（思考过程）
- 文件列表展示
- 元数据（Tokens 等）

**处理方式**：
- 使用 `COLORS["info"]` 表示思考
- 使用 `COLORS["text_dim"]` 表示元数据
- 保持 Dify 特有的输出结构

---

## 9. 后续扩展

### 9.1 AgentFlow 引擎

AgentFlow 引擎目前未实现，实现时需要：

1. 参考本文档的结构
2. 决定使用何种 UI 系统
3. 统一使用 theme.py 配色
4. 更新本文档添加 AgentFlow 章节

### 9.2 其他可能的引擎

如果将来添加新引擎，流程为：

1. 设计 UI 系统（Panel/纯文本/自定义）
2. 从一开始就使用 theme.py
3. 在本文档中添加对应章节
4. 更新修改检查清单

---

## 下一步

阅读 `07-implementation.md` 了解具体实施步骤和代码示例。
