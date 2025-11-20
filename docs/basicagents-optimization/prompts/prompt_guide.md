# Prompt Guide: 非 Function Calling LLM + LangChain 工具调用

本文档说明我们在非 OpenAI、无原生 function calling 的 LLM 上，如何通过精简而稳定的 System Prompt、外置化的提示词管理、以及自定义 JSON ReAct 解析器，驱动 LangChain 工具调用与多轮执行。

## 目标与原则

- 明确目标：在不依赖 function calling 的前提下，让 LLM 稳定输出可解析 JSON，从而触发工具调用或直接产出最终答案。
- 单一职责：将 System Prompt 从 `zhipu_agent.py` 等代码中解耦，集中在 `config/prompts/` 下维护与版本化。
- 最小可用：System Prompt 保持精简，仅约束输出格式与使用工具的规则；复杂逻辑交给解析器与执行器。
- 可扩展性：支持不同厂商（GLM/Qwen/Yi/InternLM/DeepSeek）在提示侧的轻量差异化，不影响主体框架。
- 可观测：通过日志与测试衡量“可解析率、误用工具率、重试率”，持续迭代。

## 目录与文件组织

- `config/prompts/`
  - `prompt_guide.md`（本文件）
  - `react_json_zh_CN.md`（通用精简 System Prompt，中文）
  - `providers/`（厂商差异化的精简版覆盖，可选）
    - `zhipu_glm_react_json_zh_CN.md`
    - `qwen_react_json_zh_CN.md`

在代码侧建议新增：
- `src/prompts/registry.py`：统一加载/回退（provider/locale → prompt 文本）。
- `src/prompts/tooling.py`：将 LangChain `Tool` 列表序列化为 `tools_block` 注入到 prompt。

## 精简 System Prompt（建议模板）

> 说明：保持最小必需信息，保证解析器可稳定消费。不要在此处加入冗长规则与大量 Few-shot 示例，尽量依靠解析器与执行器兜底。

```
你是一个可使用工具的助手。仅输出一个 JSON 对象，不要包含任何额外文本、反引号或代码块标记。

允许字段：
- thought：简要中文思考（可省略）。
- action：要调用的工具名（从工具列表中选择，仅一个）。
- action_input：工具参数（JSON 对象，结构需符合工具定义）。
- final_answer：当无需再用工具时的最终答复（中文）。

规则：
- 若需要调用工具，只输出 {"thought":"…","action":"<tool>","action_input":{…}}。
- 若无需工具，输出 {"final_answer":"…"}，且不要包含其他字段。
- 每次最多调用一个工具，等待观察结果后再继续。
- 输出必须是有效 JSON，禁止额外文字/注释/反引号/代码块标记。

工具列表：
{{tools_block}}
```

备注：
- 如某些 LLM 偶尔输出中文引号或包裹 ```json 代码块，可在解析器中做轻度修复，但首要靠提示词强调“仅输出纯 JSON”。

## 工具注入与序列化

- 通过 `tooling.serialize_tools(tools)` 生成 `tools_block`：包含 name、description、args（JSON Schema 或简化结构）。
- 在构建 `PromptTemplate` 时，通过 `.partial(tools_block=...)` 注入。
- 避免在 prompt 内嵌示例参数过多，以减少模型复述/幻觉。

## 解析器与执行器协作

- 输出解析器（已实现）：
  - 继承 `ReActSingleInputOutputParser`，当检测 JSON 格式时转为 dict。
  - 允许轻量清洗：去除首尾空白、剥离 ```json/``` 包裹、尝试提取首个完整花括号 JSON 片段。
  - 字段校验：仅允许 thought/action/action_input/final_answer；若存在 action 则必须有 action_input；final_answer 不得与 action 同时出现。

- 执行器循环（建议）：
  - 每轮仅一次工具调用；Observation 追加到对话后再下一轮决策。
  - 解析失败时，追加一次“格式修复” System 提示重试；仍失败则安全终止并返回可读错误。
  - 对工具错误（参数/超时/空结果）支持一次纠错尝试，避免无休止循环。

## Provider 差异化要点

- GLM（智谱）：
  - 强调“禁止反引号/仅输出纯 JSON/使用英文双引号”。
  - 若仍出现花括号外文字，解析器先行剥离。

- Qwen/DeepSeek 等：
  - 通常遵守格式较好，但仍建议最小提示+解析兜底。

差异化做法：同一精简模板 + 极少量文字差异，放入 `config/prompts/providers/`，由 `PromptRegistry` 优先加载；找不到时回退到通用模板。

## 验收与测试

- 解析器单测：
  - 标准 JSON、被 ```json 包裹、前后污染文本、中文标点误用、首个 JSON 抽取。
- Prompt 回路单测（mock LLM）：
  - 直接回答（final_answer）
  - 单步工具调用（action+action_input）
  - 多步串联（两轮工具 + 最终回答）
- 指标关注：
  - 可解析率（> 99%）
  - 非法附加文本率
  - 重试率/修复成功率

## 迁移与上线计划

1) 外置化：从 `zhipu_agent.py` 中移除内嵌系统提示，改为通过 `PromptRegistry` 加载。
2) 注入：在构建链路时注入 `tools_block`，并将自定义 JSON ReAct 解析器设为默认 `output_parser`。
3) 日志：为 LLM 原始输出增加 debug 日志，记录解析失败与重试情况。
4) 测试：补充解析器与回路单测，覆盖常见坏样例。
5) 渐进上线：先在开发/灰度环境观测指标，必要时微调模板措辞（始终保持“精简”）。

## 风险与缓解

- 偶发非 JSON 输出：精简模板 + 解析器剥离 + 一次格式修复重试。
- 工具参数不匹配：清晰的 `args` schema + 解析器字段校验 + 观察后纠错一次。
- 厂商特殊习惯（如输出代码块）：provider 覆盖提示 + 解析器兜底。

---

如需扩展英文或更强约束版本，可在 `react_json_en_US.md` 或 `providers/` 目录下添加对应精简模板。

## 实现确认与约束（已对齐）

- Provider 选择与来源：
  - 当前提供商参数存在于 `agent_factory.py`，后续 `PromptRegistry` 将基于该参数选择模板：
    - GLM → `config/prompts/providers/glm_template.md`
    - 其他 → 回退 `config/prompts/react_json_zh_CN.md`
    - Qwen 专属模板 `providers/qwen_template.md` 预留（后续添加）。

- 模板格式与注入：
  - 模板使用 `.md`，通过占位符 `{{tools_block}}` 注入工具声明。
  - 可用 `PromptTemplate.partial` 或简单字符串替换进行注入，避免在模板中加入复杂逻辑。

- 字段名严格锁定（不增不减）：
  - `thought`、`action`、`action_input`、`final_answer`
  - 工具交互字段名保持英文，与 MCP 工具命名对齐；Agent 面向用户的回答内容以中文为主。

- 工具清单注入策略：
  - Agent 内部调用时注入完整 JSON Schema：包含 `type`、`required`、`properties` 等。
  - 参数命名保持英文，与 MCP 工具一致；如无示例可省略 `examples`。

- 解析器“轻度修复”边界（实现于 `src\\parsers` 解析器中）：
  1) 自动剥离 ```json/``` 包裹与多余反引号
  2) 自动替换全角引号为半角引号（例如 “ ” → " ）
  3) 容忍并修复末尾多余逗号以生成合法 JSON
  4) 不对缺字段/错类型做过度猜测，不擅自更换工具名
  5) 如输出含杂质文本，仅提取首个完整的花括号 JSON 对象进行解析

- 执行器循环与重试：
  - 最大步数：8
  - 解析失败时进行一次“格式修复”重试；若仍失败，直接抛错以便 debug（记录原始输出）。

- 语言与一致性：
  - Agent 对用户的自然语言输出使用中文；工具参数/字段名保持英文，以利于与 MCP 工具生态一致。

- 当前阶段：
  - 仅更新文档与约束，不提交代码改动。后续将按本文档新增模板文件与加载骨架，再接入 `agent_factory.py`。
