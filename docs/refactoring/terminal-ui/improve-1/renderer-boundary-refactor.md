# Terminal UI 渲染边界重构方案

> **文档定位**: 定义终端 UI 从 `service/conversation` 层迁移到 `src/application/cli/` 的最小可实施方案。
>
> **适用范围**:
> - 优先覆盖 Deep 模式流式终端输出
> - 为 Basic / LLM / Dify 后续统一渲染链路提供边界

---

## 1. 背景

当前项目里，终端会话输出并不主要由 `src/application/cli/` 渲染，而是由各类 `service/conversation` 直接调用 `ctx.console.print(...)` 输出。

这不是 Deep 模式单点问题，而是现有工程的整体模式：

- `src/application/cli/main.py`
  - 负责 CLI 循环、命令分发、prompt、欢迎页和静态结果展示
- `src/application/cli/gui/render.py`
  - 负责帮助信息、表格、信息面板等静态渲染
- `src/application/services/agent/basic/conversation.py`
  - 直接渲染 Basic agent 会话输出
- `src/application/services/llm/conversation.py`
  - 直接渲染 LLM 会话输出
- `src/application/services/agent/deep/streaming/conversation.py`
  - 直接编排并渲染 Deep 会话输出
- `src/application/services/agent/deep/streaming/event_handler.py`
  - 直接消费 LangGraph 事件并渲染 transcript

换句话说，当前分层不是：

`runtime/service -> structured events -> cli renderer`

而是：

`runtime/service -> console.print(...)`

---

## 2. 现状判断

### 2.1 现有做法为什么能工作

这种结构在 terminal-only 产品里是可运行的，原因很现实：

- 流式事件一到就能直接打印，落地很快
- `ctx.console` 已经挂在 `AppState` 上，接线成本低
- Deep/Basic/LLM 都能沿用同一个模式
- Rich spinner / Text / style 能直接在会话代码里使用

### 2.2 现有做法的问题

它的主要问题不在“能不能跑”，而在职责边界：

1. `service` 层知道太多 UI 细节
   - 颜色
   - 前缀文案
   - spinner 样式
   - summary 排版

2. streaming 编排与终端渲染强耦合
   - 事件消费逻辑一改，UI 一起改
   - UI 一改，又要深入运行态代码

3. 测试边界不干净
   - 很多测试不得不围绕打印结果断言
   - 不容易独立验证“产生了什么语义事件”

4. 后续前端复用困难
   - 如果以后有 GUI / Web / TUI，需要重做渲染层
   - 当前 service 层输出不能直接复用

5. CLI 模块职责反而偏轻
   - `src/application/cli/` 只负责外壳
   - 真正的会话视觉体验在 `services/` 里

---

## 3. 这次重构要解决什么

这次重构的目标不是“大规模重写所有 engine”，而是先建立正确边界。

核心目标：

1. Deep 模式先从“service 直接渲染”迁到“service 发事件，CLI 渲染”
2. 保持现有 compact transcript UI 设计不变
3. 不改动 agent runtime / LangGraph 事件协议
4. 为 Basic / LLM 后续复用同一套 terminal transcript renderer 留出接口

非目标：

- 不在这一轮统一改 Basic / LLM / Dify 的全部实现
- 不把 Rich 整体移出项目
- 不改 Deep agent runtime 的执行协议
- 不改 LangGraph streaming 模式

---

## 4. 目标架构

### 4.1 分层目标

目标架构应收敛为三层：

1. **Runtime / Streaming 层**
   - 负责消费 LangGraph / LangChain 事件
   - 负责会话控制、HITL、timeout、checkpoint、tool 状态统计
   - 不直接打印终端 UI

2. **Application Service 层**
   - 负责一次 query 的 orchestration
   - 负责生成“结构化会话事件”
   - 不包含 Rich 颜色和终端布局细节

3. **CLI Presenter / Renderer 层**
   - 负责将结构化事件渲染为 terminal transcript
   - 负责 spinner、颜色、前缀、summary、elapsed footer
   - 放在 `src/application/cli/` 下

### 4.2 目标数据流

从：

`conversation.py / event_handler.py -> ctx.console.print(...)`

变成：

`conversation.py / event_handler.py -> TranscriptEvent -> cli renderer -> console.print(...)`

---

## 5. 建议的数据模型

建议在 `src/application/cli/` 或 `src/application/services/shared/` 引入统一的终端 transcript 事件模型。

### 5.1 核心事件类型

建议最小集合如下：

- `run_started`
- `thinking_started`
- `thinking_stopped`
- `assistant_text`
- `tool_call`
- `tool_result`
- `tool_error`
- `interrupt_requested`
- `warning`
- `error`
- `elapsed`
- `summary`
- `run_completed`

### 5.2 事件结构建议

建议采用 dataclass，而不是裸 dict：

```python
@dataclass
class TranscriptEvent:
    type: str
    text: str | None = None
    payload: dict[str, Any] | None = None
```

如果需要更严格，可以按类型拆成多个 dataclass；但第一阶段不必过度设计。

### 5.3 为什么先用结构化事件

因为一旦有了稳定的 transcript 事件，后面所有 UI 都只是在消费同一个语义层：

- terminal CLI
- 测试假 renderer
- 将来的 Web/TUI

---

## 6. Deep 模式的最小重构方案

### 6.1 保留现有文件，但改变职责

第一阶段不建议大搬家，优先做“职责收口”。

保留：

- `src/application/services/agent/deep/streaming/conversation.py`
- `src/application/services/agent/deep/streaming/event_handler.py`

但职责调整为：

- `conversation.py`
  - 继续 orchestrate Deep query
  - 不再直接拼 Rich 文本
  - 改为向 renderer 发结构化事件

- `event_handler.py`
  - 继续消费 LangGraph 双流事件
  - 不再直接 `console.print`
  - 改为生成 `TranscriptEvent`

### 6.2 引入 CLI renderer

建议新增模块：

- `src/application/cli/renderers/deep_transcript.py`

职责：

- 接收 `TranscriptEvent`
- 管理 spinner 生命周期
- 渲染 `DeepAgent >`
- 渲染工具调用
- 渲染错误 / 文件结果
- 渲染 elapsed footer
- 渲染 compact summary

### 6.3 建议的调用方式

`handle_deep_agent_query()` 中构建一个 renderer 实例，然后把它传给 event handler：

```python
renderer = DeepTranscriptRenderer(ctx.console, streaming_opts)
event_handler = DeepAgentEventHandler(renderer=renderer, file_tracker=file_tracker, ...)
```

之后：

- event handler 不再知道 `Console`
- 只调用 `renderer.emit(...)`
- conversation 结束时调用 `renderer.finish(...)`

---

## 7. 迁移步骤

### Phase 1: 提取 Deep transcript 渲染接口

目标：

- 先把 Deep 模式的 `console.print(...)` 从 service 里拔出来
- 不改变用户看到的终端效果

步骤：

1. 定义 `TranscriptEvent` / `DeepTranscriptRenderer`
2. 让 `event_handler.py` 改为 `emit(event)` 而不是直接 print
3. 让 `conversation.py` 的最终 fallback / elapsed / summary 改走 renderer
4. 保持所有现有 compact transcript 行为一致

收益：

- UI 与 streaming 编排首次解耦
- 变更风险可控
- 不需要同时改 Basic / LLM

### Phase 2: 提取通用 terminal transcript 接口

目标：

- 把 Deep renderer 的共性抽出

可新增：

- `src/application/cli/renderers/base.py`
- `src/application/cli/renderers/events.py`

然后让：

- Basic mode
- LLM mode

逐步改成同样的 presenter 模式。

### Phase 3: CLI 统一管理会话显示

目标：

- 让 `src/application/cli/` 真正成为会话展示层

到这一阶段，可以考虑：

- `main.py` 负责创建 renderer
- adapter/service 只处理结构化结果
- `services/` 完全脱离 Rich theme

---

## 8. 模块调整建议

### 8.1 新增模块

建议新增：

- `src/application/cli/renderers/events.py`
  - 定义 transcript 事件模型
- `src/application/cli/renderers/deep_transcript.py`
  - Deep 模式 terminal renderer

### 8.2 重构模块

建议修改：

- `src/application/services/agent/deep/streaming/event_handler.py`
  - 从“渲染器”降级为“事件解释器”
- `src/application/services/agent/deep/streaming/conversation.py`
  - 从“会话控制 + UI 拼接”降级为“会话控制 + renderer 驱动”

### 8.3 暂不改的模块

这一轮建议不动：

- `src/application/cli/gui/render.py`
  - 它目前主要承担静态帮助/表格/信息展示
- `src/application/services/agent/basic/conversation.py`
- `src/application/services/llm/conversation.py`
- `src/application/services/dify/*`

原因：

- 先把最复杂的 Deep 流式链路跑通
- 避免一次性扩大战线

---

## 9. Deep renderer 的职责边界

### 9.1 应该由 renderer 负责的事情

- `DeepAgent >` 前缀样式
- dim / primary / error / warning 等颜色
- spinner 文案与动态计时
- tool call 行文案
- elapsed footer
- compact summary 布局

### 9.2 不应该由 renderer 负责的事情

- 解析 LangGraph 原始 payload
- 判断 tool step completion
- 更新 checkpoint marker
- HITL 状态机控制
- runtime timeout 决策

### 9.3 不应该再由 service 负责的事情

- Rich `Text.assemble(...)`
- `console.print(...)`
- spinner start/stop 的具体样式
- transcript 的逐行排版

---

## 10. 对测试的影响

重构后，测试可以更清楚地分层：

### 10.1 event handler 测试

验证：

- 给定 LangGraph 事件，产生哪些 `TranscriptEvent`
- 是否正确过滤 middleware 噪声
- 是否正确过滤 subagent 正文
- 是否保留文件结果 / 错误 / summary 统计

### 10.2 renderer 测试

验证：

- 给定 `TranscriptEvent`，终端应输出什么
- spinner 文案是否正确
- elapsed footer 是否正确
- summary 是否符合 compact 设计

### 10.3 conversation 测试

验证：

- 是否在正确时机启动/完成 renderer
- 最终 fallback 去重是否正确
- interrupt / timeout / error 是否走对事件

---

## 11. 风险与取舍

### 11.1 风险

1. 初期会增加一些样板代码
2. Deep event handler 的测试需要调整
3. 如果一次性抽象过度，容易把设计做复杂

### 11.2 取舍

因此建议：

- 第一阶段只做 Deep
- 第一阶段只抽“够用”的事件模型
- 不急着做全引擎统一

这比“一步到位重写全部 conversation/rendering”更稳。

---

## 12. 推荐实施顺序

建议按以下顺序推进：

1. 新增 transcript 事件模型
2. 新增 Deep terminal renderer
3. 改 `event_handler.py` 为事件发射器
4. 改 `conversation.py` 为 renderer 驱动器
5. 跑现有 deep streaming 测试并补 renderer 测试
6. 确认 Deep UI 无回归后，再评估是否迁移 Basic / LLM

---

## 13. 推荐结论

我的建议不是立刻做“大一统 CLI 重构”，而是做一个非常清楚的收敛：

> 先把 Deep 模式从“service 直接渲染”迁到“service 发结构化事件，CLI renderer 渲染”。

这是最小但正确的一步。

它能同时满足三件事：

1. 解决当前 UI 逻辑侵入运行态代码的问题
2. 保持已经确定的 compact transcript 设计
3. 为后续统一 Basic / LLM / Dify 的终端展示留出稳定边界

---

## 14. 与现有文档关系

本文档补充并细化了以下文档：

- `docs/refactoring/terminal-ui/design-proposal.md`

关系如下：

- `design-proposal.md`
  - 说明 Deep 终端 UI 最终应该长什么样
- `renderer-boundary-refactor.md`
  - 说明这个 UI 应该由哪一层负责渲染，以及如何迁移过去

