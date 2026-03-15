# Provider Registry 动态化重构 -- 总体设计

## 1. 概述

本文档定义 `src/core/providers/` 和 `src/llm/managers/` 层面的重构方案，
目标是消除硬编码的 provider/model 白名单，实现配置驱动的动态注册。

重构完成后，用户可以通过编辑 JSON 配置文件自由增删 provider 和 model，
无需修改任何 Python 代码。

本文档与 `docs/setup/` 系列文档配合：setup 模块负责引导用户配置 API key 和
默认 provider；本文档负责确保 registry 层能正确识别和使用这些配置。

## 2. 当前问题

### 2.1 LLMProvider Enum 硬编码

`src/llm/managers/llm_manager.py` 中定义了 `LLMProvider` 枚举：

```python
class LLMProvider(Enum):
    ZHIPU = "zhipu"
    OPENAI = "openai"
    OLLAMA = "ollama"
```

所有 provider 识别、adapter 选择、API key 加载都依赖此枚举。
新增 provider（如 tongyi）必须修改源码，违反开闭原则。

### 2.2 硬编码 adapter/instance 映射

```python
_adapter_map = {
    "ZHIPU": ZhipuAdapter,
    "OPENAI": OpenAIAdapter,
    "OLLAMA": OllamaAdapter,
}
_instance_map = {
    "ZHIPU": ZhipuAILLM,
    "OPENAI": OpenAILLM,
    "OLLAMA": OllamaLLM,
}
```

BasicAgent 的 `AgentManager._create_adapter()` 同样硬编码：

```python
adapter_map = {
    "zhipu": ZhipuAgentAdapter,
    "openai": OpenAIAgentAdapter,
}
```

### 2.3 硬编码 API key 加载

```python
def _load_api_keys(self):
    if settings.zhipu_api_key:
        self._api_keys[LLMProvider.ZHIPU] = settings.zhipu_api_key
    if settings.openai_api_key:
        self._api_keys[LLMProvider.OPENAI] = settings.openai_api_key
```

通过 `Settings` 类的具体属性加载，新增 provider 需要同步扩展 Settings。

### 2.4 provider key 大小写不一致

| 模块 | Key 格式 | 示例 |
|------|---------|------|
| LLM registry | UPPERCASE | `"ZHIPU"`, `"OPENAI"` |
| BasicAgents registry | lowercase | `"zhipu"`, `"openai"` |
| DeepAgents registry | lowercase | `"zhipu"`, `"openai"` |
| SubAgents registry | lowercase | `"zhipu"`, `"tongyi"` |

LLM registry 使用大写 key 与其余三个 registry 不一致。

## 3. 设计目标

1. **消除 LLMProvider Enum** -- adapter 选择改为配置驱动
2. **统一 provider key 为小写** -- 所有 registry 使用 lowercase key
3. **动态 API key 加载** -- 从 JSON 配置的 `api_key_env` 字段读取环境变量名
4. **JSON 配置增加 `adapter` 字段** -- 声明每个 provider 使用哪种 adapter
5. **用户可动态增删 provider/model** -- 编辑 JSON 即可，无需改代码

## 4. 影响范围

### 4.1 受影响的引擎

| 引擎 | 是否受影响 | 说明 |
|------|----------|------|
| LLM 引擎 | 是 | 移除 Enum，改为 config-driven adapter |
| BasicAgent 引擎 | 是 | adapter 映射改为 config-driven |
| DeepAgent 引擎 | 否 | 已使用 `init_chat_model()` 动态创建，不依赖 adapter |
| SubAgent 引擎 | 否 | 同 DeepAgent，通过 `init_chat_model()` 创建 |

### 4.2 不受影响的模块

- `src/core/providers/deepagents_provider_registry.py` -- 不做修改
- `src/core/providers/subagents_provider_registry.py` -- 不做修改（配置结构变更见 `docs/setup/06-config-changes.md`）
- `src/agents/deepagents/` -- 不做修改

## 5. 设计约束

1. **混合适配器策略**：智谱保留专用 SDK（`ChatZhipuAI`），其他 provider（tongyi、自定义）
   均走 OpenAI-compatible 路径（`ChatOpenAI`），Ollama 保留专用路径
2. **三种 adapter 类型**：`"zhipu"` / `"openai"` / `"ollama"`，由配置声明
3. **API key 值只存 `.env`**：JSON 配置中只记录环境变量名（`api_key_env`），
   不包含实际 key 值
4. **最小变更原则**：不做大规模重构，确保现有功能正常运行

## 6. 与 Setup 模块的关系

| 职责 | 归属 |
|------|------|
| 引导用户输入 API key，写入 `.env` | Setup 模块（`docs/setup/`） |
| 从 `.env` 读取 API key，注入到 LLM 客户端 | Registry + Manager（本文档） |
| JSON 配置文件中的 provider/model 结构 | 两者共同约定 |
| `_validate_config()` 启动检查 | Registry 模块（本文档） |
| `/iris doctor` 配置健康检查 | Setup 模块的 `ConfigValidator` |

Setup 模块中 `docs/setup/06-config-changes.md` 定义了 JSON 配置文件的结构变更
（如 basic/providers.json 新增 tongyi、subagents 多 provider 结构等），
本文档定义 registry 代码如何消费这些变更后的配置。

## 7. 文档结构

| 文档 | 内容 |
|------|------|
| `01-overview.md`（本文档） | 问题分析、设计目标、影响范围 |
| `02-adapter-system.md` | adapter 类型系统、ADAPTER_REGISTRY、key 统一、动态 API key |
| `03-config-changes.md` | JSON 配置结构变更、`adapter` 字段、动态增删示例 |
| `04-code-change-manifest.md` | 逐文件代码修改清单 |
