# Multi-Engine Terminal Renderer 统一方案

> **文档定位**: 在 Deep 模式 renderer 边界重构基础上，评估并规划 Basic / LLM / Dify 一起收敛到统一终端渲染层的方案。
>
> **结论摘要**:
> 1. 这个模块可以一起优化，但不建议“一步到位同时重写四个引擎”
> 2. Deep 与 Dify 的终端 transcript 形态最接近，适合先统一到同一类 renderer 边界
> 3. Basic 适合作为第二批迁移对象
> 4. LLM 也应纳入统一方案，但它目前依赖 `src/llm/utils/streaming.py` 的旧式 live/panel 机制，迁移成本最高

---

## 1. 目标问题

前一份文档 `renderer-boundary-refactor.md` 聚焦于 Deep 模式，回答的是：

- Deep 的终端 UI 为什么不应继续留在 `service/conversation`
- Deep 应该怎样迁到 `src/application/cli/`

但项目实际情况是，终端会话输出的分层问题并不只存在于 Deep：

- Basic：`conversation.py` 直接渲染状态和结果
- LLM：`conversation.py` + `src/llm/utils/streaming.py` 共同渲染
- Dify：`service.py` + `_DifyRuntime` + `DifyStreaming` 直接渲染

因此，这个问题本质上是：

> 当前整个 CLI 会话渲染都分散在 engine/service/runtime 内部，缺少统一的 terminal renderer 边界。

---

## 2. 现状对比

### 2.1 Basic

入口：

- `src/application/services/agent/basic/service.py`
- `src/application/services/agent/basic/conversation.py`

特点：

- 非流式 agent 调用为主
- 直接使用 `ctx.console.status(...)`
- 直接打印：
  - `BasicAgent > ...`
  - `Used X tools`
  - 错误 / 中断 / 取消提示

判断：

- 实现简单
- 渲染逻辑集中
- 最容易迁移到统一 renderer

### 2.2 Deep

入口：

- `src/application/services/agent/deep/streaming/conversation.py`
- `src/application/services/agent/deep/streaming/event_handler.py`

特点：

- LangGraph 双流：`messages` + `updates`
- 终端 transcript 已经被收敛成 compact 设计
- 仍然直接依赖 `ctx.console.print(...)`
- spinner、tool call、summary、elapsed footer 都在 service 层或 event handler 里

判断：

- 逻辑最复杂
- 但 UI 目标最清楚
- 是最值得先抽象 renderer 的一条线

### 2.3 LLM

入口：

- `src/application/services/llm/conversation.py`
- `src/application/services/llm/streaming.py`
- `src/llm/utils/streaming.py`

特点：

- 非 streaming 模式下较简单
- streaming 模式并不走 `application/cli`
- 使用 `src/llm/utils/streaming.py` 里的：
  - `StreamingDisplay`
  - `Live`
  - `Panel`
  - 全局 `console = Console()`

判断：

- LLM 的 UI 不仅耦合在 service 层，还耦合在更底层共享工具层
- 当前形态与 compact transcript 设计不一致
- 想统一 renderer，必须先把 `src/llm/utils/streaming.py` 从“自带 UI”降级为“流 token source / event source”

### 2.4 Dify

入口：

- `src/application/services/dify/service.py`
- `src/application/services/dify/streaming.py`

特点：

- `_DifyRuntime` 自己拿着 `Console`
- `DifyStreaming` 是专用 UI 打印器
- `display_stream()` 内部直接处理：
  - waiting status
  - message streaming
  - agent thought
  - metadata
  - token usage
  - error / file

判断：

- 它和 Deep 一样，已经是“流式事件 -> UI”的形态
- 只是事件源来自 Dify SSE，而不是 LangGraph
- 很适合迁到统一 transcript renderer 边界

---

## 3. 哪些能统一，哪些不能硬统一

### 3.1 可以统一的部分

这几类 UI 语义，四个引擎都能共享：

- 会话开始 / waiting
- assistant text
- warning / error
- elapsed footer
- summary / metadata footer

也就是说，可以定义一个共享的终端 transcript 事件模型，例如：

- `thinking_started`
- `thinking_stopped`
- `assistant_text`
- `warning`
- `error`
- `elapsed`
- `summary`

### 3.2 需要引擎特化的部分

以下内容不应该强行完全统一：

- Deep 的 tool call / subagent / HITL
- Basic 的 tool usage summary
- Dify 的 file upload / retriever resources / usage metadata
- LLM 的纯 token streaming

因此合理做法不是“一个 renderer 覆盖一切”，而是：

- 一套共享的 transcript event 基础协议
- 每个引擎一个轻量 renderer/presenter
- 共享基础行为，不共享全部细节

---

## 4. 推荐目标架构

推荐结构：

- `src/application/cli/renderers/events.py`
  - 定义共享 transcript event
- `src/application/cli/renderers/base.py`
  - 定义基础 renderer 接口和通用工具
- `src/application/cli/renderers/deep.py`
  - Deep transcript renderer
- `src/application/cli/renderers/basic.py`
  - Basic transcript renderer
- `src/application/cli/renderers/dify.py`
  - Dify transcript renderer
- `src/application/cli/renderers/llm.py`
  - LLM transcript renderer

共享层负责：

- 颜色主题访问
- Rich console
- waiting spinner 生命周期
- elapsed footer
- 常见 error/warning 样式

引擎层负责：

- Deep：tool calls / file ops / summary / HITL
- Basic：simple answer + tool usage
- Dify：SSE message / files / metadata
- LLM：token streaming / final response

---

## 5. 为什么不建议一步到位

### 5.1 四条链路的成熟度不同

- Basic：很薄
- Deep：复杂但边界清楚
- Dify：中等复杂，独立 streaming helper
- LLM：最老、最散，还下沉到了 `src/llm/utils`

### 5.2 一次性改会把风险叠加

如果四条线同时动，会同时引入：

- 深度 streaming 回归风险
- Dify SSE 渲染回归风险
- LLM token streaming / panel 行为回归风险
- Basic 结果呈现回归风险

这会让测试面和排查面急剧扩大。

### 5.3 共享抽象容易被过度设计

如果一开始就试图抽一个“超级统一 renderer”，大概率会把 Deep / Dify / LLM 的差异也一起揉进去，最终得到一个过于抽象又不好维护的中间层。

---

## 6. 推荐实施顺序

### Phase 1: Deep + Renderer 基础设施

先做：

- 共享 transcript event 模型
- shared renderer base
- Deep renderer 落地

原因：

- Deep 的 UI 目标已经最清楚
- 现有 compact transcript 设计已经稳定
- 事件语义也最丰富，适合做抽象基线

### Phase 2: Dify 接入共享 renderer

然后做：

- `DifyStreaming` 从“直接 print”改成“解析 Dify SSE -> 发 transcript events”
- Dify runtime/service 不再自己拼 UI

原因：

- 它和 Deep 一样，都是事件驱动流式输出
- 更接近“renderer 接收事件”的目标模型

### Phase 3: Basic 接入共享 renderer

再做：

- Basic conversation 改成通过 renderer 输出
- 把 waiting、answer、tool summary 统一到 renderer 行为

原因：

- 基础模式简单，改造成本低
- 可以顺手统一前缀与 footer 风格

### Phase 4: LLM streaming 旧链路迁移

最后做：

- 把 `src/llm/utils/streaming.py` 从 UI 模块降级为流 token source
- 去掉内置的 `Live + Panel + global console`
- 改由 application CLI renderer 接管 LLM streaming 终端展示

原因：

- 这是跨层最多的一条线
- 需要最谨慎处理兼容性

---

## 7. 为什么 Deep 和 Dify 应该优先一起收敛

Deep 和 Dify 虽然后端来源不同，但从终端 UI 视角，它们有高度相似性：

- 都是长时运行
- 都有等待态
- 都有流式文本
- 都可能有附加元信息
- 都需要 error / warning / footer

这意味着：

- 它们最容易共享一套 transcript renderer 设计语言
- 可以先把 CLI 层真正建立起来
- 不必先去动历史包袱更重的 LLM streaming utility

---

## 8. 为什么 LLM 不建议第一批就一起改

LLM 这条线的问题不是不能改，而是它的旧实现离 `application/cli` 最远：

- `src/application/services/llm/conversation.py`
  - 只是薄薄一层入口
- 真正的 streaming UI 在 `src/llm/utils/streaming.py`
  - 里面直接 new 了 `Console()`
  - 直接管理 `Live`
  - 直接渲染 `Panel`
  - 直接打印性能统计

这代表：

- LLM renderer 改造不是单纯“service 挪到 cli”
- 而是“共享 utils 去 UI 化”

这一步应该做，但不该和 Deep / Dify 一起首发。

---

## 9. 推荐方案

推荐的整体策略是：

1. 不做“四引擎同时重写”
2. 先建立共享 renderer 基础设施
3. 第一批迁移 Deep
4. 第二批迁移 Dify
5. 第三批迁移 Basic
6. 最后迁移 LLM 的旧 streaming 工具链

也就是说：

> 可以一起优化，但要统一方向、分批落地，而不是一起硬改。

---

## 10. 第一阶段后的收益

只要 Deep + Dify 被收进统一 renderer 基础设施，项目就已经会明显变干净：

- CLI 不再只是外壳
- streaming UI 开始真正归位到 `src/application/cli/`
- service/runtime 层不再持续膨胀 UI 细节
- 后续改 Basic/LLM 的成本会显著下降

---

## 11. 与现有文档关系

本文档与以下文档配合使用：

- `design-proposal.md`
  - 定义 Deep 终端 UI 最终形态
- `renderer-boundary-refactor.md`
  - 定义 Deep 从 service 渲染迁到 CLI 渲染的边界
- `multi-engine-renderer-unification.md`
  - 评估 Basic / LLM / Dify 是否一起纳入、以及推荐迁移顺序

