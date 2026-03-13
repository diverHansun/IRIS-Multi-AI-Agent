# Deep 模式 Terminal UI 设计方案

> **文档定位**: 定义 Deep 模式终端主视图的最终交互形态。
>
> **设计结论**:
> 1. Deep 模式终端 UI 固定为单一 `compact transcript`
> 2. 终端主视图彻底移除 `Step N | time | ...` 行
> 3. middleware / raw updates / debug trace 不进入聊天 transcript
> 4. `--debug` 仅影响日志与运行时诊断，不产生独立 UI 模式
> 5. 保留一个极简总耗时模块，只显示从 Agent 启动到最终输出完成的总时长
>
> **相关文档**:
> - `renderer-boundary-refactor.md`: 说明该 UI 形态后续应如何从 `service/conversation` 层迁移到 `src/application/cli/` 渲染层

---

## 1. 设计范围

本文档只约束 **Agent Deep 模式的终端主视图**，不覆盖:

- LLM / Agent Basic / Dify 的 UI
- logger 输出格式
- middleware 内部实现
- LangGraph runtime 的事件协议

本文档覆盖:

- 终端里哪些内容应该显示
- 这些内容按什么顺序显示
- 哪些事件必须静默
- 现有配置字段在 compact 设计下如何兼容

---

## 2. 问题与判断

当前 Deep 模式的终端输出同时混合了三层信息:

1. 用户需要阅读的内容
   - 助手中间说明文本
   - 工具调用
   - HITL 请求
   - 错误 / 超时
   - 最终回答
2. 运行时控制信息
   - updates 流中的节点状态变化
   - per-step persist 相关完成标记
   - final state 捕获
3. 内部实现细节
   - middleware lifecycle hook
   - state patch
   - 私有运行时对象
   - 调试用 `repr(...)`

问题不在于“信息太少”，而在于 **主终端 transcript 没有做语义分层**。  
结果就是:

- Step 行持续打断阅读节奏
- middleware 噪声直接进入用户界面
- 文本内容与 Step 状态重复表达
- Step 编号会随着 middleware/subgraph 变化而漂移，稳定性很差

因此结论非常明确:

> Deep 模式终端 UI 不应该继续围绕 Step 设计，而应该回到“顺序化聊天 transcript”。

---

## 3. 核心决策

### 3.1 单一 compact transcript

Deep 模式终端 UI 只保留一种展示方式:

- 自上而下追加打印
- 不做覆盖式刷新
- 不显示 Step 编号
- 不显示 middleware hook
- 不显示 raw payload
- 不显示逐步计时
- 只显示用户可理解、可行动、可回顾的语义事件

这里的“compact”不是信息过少，而是:

- 去掉内部执行噪声
- 保留必要过程感
- 保持 transcript 可读、可滚动、可回看

### 3.2 不引入 UI debug 模式

本项目已有 `--debug`，但它应继续承担:

- logger 提升到 debug 级别
- 运行时诊断信息输出
- 排查 middleware / graph 行为

它不应承担:

- 在聊天主视图里重新打开 Step 行
- 直接把 middleware payload 打进终端 transcript
- 把 runtime trace 伪装成用户界面

边界定义如下:

- **终端主视图**: 面向用户的会话 transcript
- **debug 日志**: 面向开发排查的诊断信息

### 3.3 updates 继续消费，但默认静默

Deep 模式仍然要消费 `updates` 流，因为它承载:

- interrupt 检测
- step 完成标记
- final state 捕获
- timeout / execution control
- tool usage 统计

但设计上明确:

> `updates` 是运行时控制通道，不是默认的 UI 通道。

`messages` 负责内容显示，`updates` 只在极少数需要用户感知的场景下转化为可见文本。

---

## 4. 为什么要移除 Step

### 4.1 Step 对用户价值低

用户真正关心的是:

- 现在 agent 在做什么
- 是否调用了重要工具
- 是否需要我审批
- 是否出错
- 最终答案是什么

用户通常并不关心:

- 当前是第 7 步还是第 23 步
- 这一步来自 middleware 还是 model node
- 某个内部 hook 是否返回了 `None`

### 4.2 Step 粒度不稳定

Step 不是用户任务阶段，而是运行时事件计数。它会被以下因素放大或扭曲:

- middleware 数量变化
- LangGraph / LangChain 的事件粒度变化
- subgraph / subagent 嵌套
- runtime state patch 数量变化

这意味着:

- 同一类查询在不同版本上 Step 数可能完全不同
- Step 编号不能稳定代表“任务推进程度”
- Step 越多，越像 trace，越不像聊天 UI

### 4.3 Step 与 messages 天然重复

当前用户已经能从以下输出理解过程:

- `DeepAgent > ...` 中间文本
- `Tool: ...` 工具调用
- HITL / timeout / error 提示

再叠加 Step 行，通常只会形成重复表达，而不是新增信息。

---

## 5. 终端 UI 契约

### 5.1 总体形态

Deep 模式终端 transcript 采用 append-only 结构:

1. 一个可选的启动提示
2. 若干条助手文本
3. 若干条工具调用或结果摘要
4. 必要时的 HITL / timeout / error 行
5. 一个可选的结束摘要

不使用:

- Step 前缀
- 时间前缀
- 中间态 Panel
- 覆盖式 spinner / live 区块

### 5.2 可见事件

| 事件类型 | 是否可见 | 终端表现 |
|----------|----------|----------|
| 会话开始 | 是 | `Deep agent reasoning...` |
| AI 中间文本 | 是 | `DeepAgent > ...` |
| AI 最终文本 | 是 | `DeepAgent > ...` |
| 可感知的工具调用 | 是 | `  Tool: ...` |
| 文件写入/编辑结果 | 是 | 文件操作结果渲染 |
| 工具失败 | 是 | 错误摘要 |
| HITL interrupt | 是 | 审批/确认提示 |
| 最大执行时间超时 | 是 | 超时提示 |
| 总耗时 footer | 是 | `Elapsed: 12.4s` |
| 最终统计摘要 | 可选 | `Summary:` 区块 |

### 5.3 不可见事件

以下内容不应进入主终端 transcript:

- `before_agent`
- `before_model`
- `after_model`
- `after_agent`
- `None` payload
- `repr(payload)`
- 私有对象句柄
- `shell_session=<...>`
- `execution_start_time=...`
- 纯内部读文件 / 列目录 / grep / glob 工具噪声
- 大段 read tool 原始结果
- 单步耗时
- `Step N | 0.0s | ...`

---

## 6. 事件映射规则

### 6.1 messages 流

messages 是终端内容展示主通道。

#### AI 文本

- 文本按出现顺序直接进入 `DeepAgent > ...`
- 中间文本与最终文本共用同一主通道
- 可以保留轻微样式差异，但不能分裂成不同 UI 模块
- 若最终答案已在流中完整展示，结束时不再重复打印

#### 工具调用

- 工具调用前先 flush pending 文本
- 工具调用显示为独立一行
- 默认只显示用户有感知价值的工具

建议保留可见的工具类型:

- `web_search`
- `shell`
- 写文件 / 改文件工具
- 触发外部副作用的工具
- 需要用户理解 agent 行为的高价值工具

建议默认隐藏的工具类型:

- `read_real_file`
- `read_virtual_file`
- `list_real_files`
- `list_virtual_files`
- `grep_real_files`
- `glob_real_files`
- 仅用于内部推理的读取类工具

#### ToolMessage

- 成功的读取类结果默认静默
- 成功的写入/编辑类结果显示为文件操作摘要
- 失败结果显示为错误摘要
- 不直接展开大段工具原始文本

### 6.2 updates 流

updates 默认不直接打印。

只在以下场景转成可见 UI:

| updates 信号 | UI 行为 |
|--------------|---------|
| `__interrupt__` | 显示 HITL 请求 |
| 运行时超时/执行错误 | 显示警告或错误 |
| 最终 summary 所需统计 | 更新内部状态，不即时打印 |

其他 updates:

- 继续参与内部控制
- 继续驱动 checkpoint/persist
- 不生成终端文本

---

## 7. middleware 展示策略

### 7.1 设计原则

middleware 是执行层机制，不是终端交互层。

因此:

- middleware hook 不应有独立 UI 行
- middleware patch 不应直接 repr 输出
- middleware 私有状态不应泄露给用户

### 7.2 明确禁止的终端效果

以下输出属于设计违例:

```text
Step 5 | 0.0s | ShellToolMiddleware.before_agent: shell_session=<PersistentShellSession ...>
Step 6 | 0.0s | ExecutionTimeoutMiddleware.before_agent: execution_start_time=...
Step 7 | 0.0s | HumanInTheLoopMiddleware.after_model: None
Step 8 | 0.0s | SummarizationMiddleware.before_model: None
```

这些内容应进入:

- debug 日志
- runtime trace
- 单元测试或排查工具

而不是主会话 transcript。

---

## 8. 顺序与展示约束

### 8.1 顺序约束

终端输出必须满足以下顺序:

1. AI 文本先于紧随其后的工具调用 flush
2. 工具调用按实际触发顺序显示
3. 工具结果在对应调用之后出现
4. interrupt/approval 在执行暂停点出现
5. 最终答案只显示一次

### 8.2 展示约束

终端输出必须满足以下风格约束:

1. 只做向下追加打印
2. 不做“回到上一行修改”的 UI
3. 不引入第二条并行调试视图
4. 不用 Step 编号表达过程
5. 不用 middleware 名称表达过程
6. 不显示逐步耗时，只显示总耗时

---

## 9. 计时模块策略

### 9.1 设计目标

终端 UI 需要保留“执行花了多久”的信息，但不能重新回到 Step 计时模型。

因此计时模块的目标是:

- 让用户知道整次 deep reasoning 总共耗时多久
- 不打断主 transcript 阅读
- 不产生每步刷新的噪声
- 不依赖 Step 行存在

### 9.2 显示规则

计时模块只显示一次，展示:

- 起点: Agent 开始执行时
- 终点: 最终可见结果输出完成时

推荐表现:

```text
Elapsed: 12.4s
```

样式建议:

- dim / 次要信息样式
- 独立一行
- 放在最终回答之后
- 若有 `Summary:`，放在 summary 之前

### 9.3 明确不做的事

计时模块不承担以下职责:

- 不显示单步耗时
- 不显示 `Step 7 | 3.2s`
- 不做 live ticking UI
- 不做终端原地刷新
- 不显示 middleware/节点级耗时

### 9.4 配置语义

`show_elapsed_time` 在 compact 模式下应重新解释为:

> 是否显示整次 Deep Agent 会话的总耗时 footer。

它不再表示:

- 是否显示 Step 旁边的耗时
- 是否显示 node/middleware 粒度耗时
- 是否启用逐步计时 transcript

---

## 10. 结束摘要策略

compact transcript 允许保留一个很短的结束摘要，但摘要不能重新引入 Step 视角，也不应与总耗时 footer 重复表达。

建议摘要字段:

- Tool calls
- Tool names
- Subagent delegations
- Brief subagent list

不建议摘要字段:

- Reasoning steps
- middleware count
- raw node update count
- Total time（已由独立 elapsed footer 表达）

推荐效果:

```text
Elapsed: 12.4s

Summary:
  - Tool calls: 3
  - Subagent delegations: 1
    [1] coding (completed) - Create a plugin example
```

---

## 11. 配置兼容策略

当前已有字段:

- `streaming_enabled`
- `show_reasoning_steps`
- `show_tool_calls`
- `show_tool_results`
- `show_subagent_delegations`
- `show_elapsed_time`

compact 方案下的处理建议如下:

| 字段 | 处理建议 |
|------|----------|
| `streaming_enabled` | 保留 |
| `show_tool_calls` | 保留，控制 inline 工具调用是否显示 |
| `show_tool_results` | 保留，控制文件结果/错误摘要是否显示 |
| `show_subagent_delegations` | 保留，控制结束摘要中的 subagent 信息 |
| `show_elapsed_time` | 保留，控制总耗时 footer 是否显示 |
| `show_reasoning_steps` | 兼容读取，但不再驱动 Step UI |

对 `show_reasoning_steps` 的建议:

- 短期: 保留字段，避免配置破坏
- 中期: 在文档中标记 deprecated
- 长期: 从 Deep terminal UI 配置里移除

---

## 12. 代码职责边界

### 11.1 `event_handler.py`

负责:

- 渲染顺序化助手文本
- 渲染可见工具调用
- 渲染必要的工具错误/文件结果
- 静默消费大部分 updates
- 统计工具与 subagent 信息

不负责:

- 暴露 middleware trace
- 生成 Step transcript
- 承担 debug 日志职责
- 生成单步计时 UI

### 11.2 `conversation.py`

负责:

- 启动提示
- HITL 交互编排
- timeout / interrupt 处理
- 最终答案 fallback
- 总耗时 footer 渲染
- 结束摘要渲染

### 11.3 middleware 与 runtime

保持不变:

- middleware 返回 state patch 的语义
- shell/timeout/session 等运行时状态管理
- LangGraph streaming 与 checkpoint 机制

根因在显示层，因此优先修正 event rendering，而不是重写 middleware 返回值协议。

---

## 13. 推荐的终端效果

```text
Deep agent reasoning...

DeepAgent > 我先检查一下当前项目结构，再定位问题来源。
  Tool: shell("rg -n \"ShellToolMiddleware|_describe_update\" src")

DeepAgent > 我已经定位到问题了。当前不是 shell middleware 自己输出太多，而是 updates payload 被当作 UI 直接打印。

DeepAgent > 接下来我会把 middleware 相关更新改成默认静默，并保留工具调用、错误和最终回答。

Elapsed: 3.2s

Summary:
  - Tool calls: 1
```

不应再出现:

```text
Step 1 | 0.0s | model: Thinking
Step 2 | 0.0s | ShellToolMiddleware.before_agent: shell_session=<...>
Step 3 | 0.0s | ExecutionTimeoutMiddleware.before_model: None
```

---

## 14. 与既有文档的关系

本文档是 Deep 模式 terminal UI 的上层约束。

它对既有 `docs/refactoring/message-display/` 方案的要求是:

- 终端主视图以 compact transcript 为目标
- Step 行不再作为默认展示对象
- middleware 噪声治理以“静默 updates + 语义化 messages”为主
- 最终输出去重仍然保留

后续所有 Deep terminal UI 相关实现，应以本文档为准。
