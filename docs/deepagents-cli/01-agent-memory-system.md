# Agent记忆系统实施文档

## deepagents-cli官方代码的优点

### 1. AgentMemoryMiddleware设计

官方实现了一个专门的中间件 `AgentMemoryMiddleware`，具备以下特点：

- **职责分离**：将记忆加载逻辑从业务代码中分离，通过中间件机制自动注入
- **状态管理**：使用 `AgentMemoryState` 管理记忆内容，仅在首次加载时读取文件
- **提示词注入**：通过 `wrap_model_call` 将记忆内容注入系统提示词，使用 `<agent_memory>` 标签明确标识来源
- **路径抽象**：支持自定义 `memory_path`，默认为 `/memories/`，与实际存储路径解耦

### 2. 记忆管理协议

官方在系统提示词中明确定义了记忆使用协议：

- **何时检查记忆**：会话开始时、回答问题前、执行任务前
- **何时更新记忆**：收到用户反馈时、学习新模式时、明确要求时
- **记忆优先原则**：优先使用保存的知识，而非通用知识

### 3. 持久化存储机制

使用 `CompositeBackend` 和 `FilesystemBackend` 实现：

- **分离存储**：工作目录和记忆目录分离，记忆存储在 `~/.deepagents/AGENT_NAME/`
- **虚拟路径映射**：`/memories/` 路径映射到实际文件系统目录
- **agent.md核心文件**：作为agent的核心记忆，可被agent自己修改

## 我们现有代码的优点和不足

### 优点

1. **虚拟文件系统已支持**：`VirtualFilesystemMiddleware` 已实现，支持 `/memories/` 路径前缀
2. **长期记忆机制存在**：通过 `long_term_memory` 配置项支持跨会话持久化
3. **状态管理完善**：使用 LangGraph 的状态管理机制，支持文件数据持久化

### 不足

1. **缺少记忆加载中间件**：没有专门的中间件在agent启动时加载 `/memories/agent.md`
2. **系统提示词未集成**：记忆相关的使用协议未明确写入系统提示词
3. **记忆更新引导不足**：agent不知道何时以及如何更新自己的记忆
4. **记忆目录管理缺失**：没有为每个agent实例创建独立的记忆目录

## 实施方案

### 实施步骤

#### 第一步：创建AgentMemoryMiddleware

**文件路径**：`src/components/deepagents/runtime_middlewares/agent_memory/middleware.py`

**注意**：此文件位于 `runtime_middlewares` 目录，与 `src/application/services/agent/deep` 不同。runtime_middlewares 是参与运行时执行的中间件，而 services 是服务层逻辑。

**核心功能**：
- 定义 `AgentMemoryState`，包含 `agent_memory` 字段
- 实现 `before_agent` 方法，从虚拟文件系统读取 `/memories/agent.md`
- 实现 `wrap_model_call` 方法，将记忆内容注入系统提示词
- 定义记忆使用协议的系统提示词模板

**关键实现点**：
- 使用虚拟文件系统的工具读取文件（通过运行时状态访问）
- 仅在状态中 `agent_memory` 为空时读取，避免重复加载
- 记忆内容使用 `<agent_memory>` 标签包装

#### 第二步：集成到Runtime Builder

**文件路径**：`src/components/deepagents/runtime.py`

**修改内容**：
- 在 `create_deep_agent_runtime` 函数中检查 `middleware_config` 的 `agent_memory` 配置
- 如果启用，创建 `AgentMemoryMiddleware` 实例
- 将中间件添加到 `deepagent_middleware` 列表的开头（优先执行）

**配置示例**：
```python
agent_memory_config = middleware_config.get("agent_memory", {})
if agent_memory_config.get("enabled", False):
    from .runtime_middlewares.agent_memory import AgentMemoryMiddleware
    memory_path = agent_memory_config.get("memory_path", "/memories/")
    agent_memory_middleware = AgentMemoryMiddleware(memory_path=memory_path)
    deepagent_middleware.insert(0, agent_memory_middleware)
```

#### 第三步：修改Factory支持配置

**文件路径**：`src/agents/deepagents/factories/base.py`

**修改内容**：
- 在 `_inject_filesystem_tools` 或独立的配置解析方法中处理 `agent_memory` 配置
- 确保 `agent_memory` 配置能够传递到 runtime builder

#### 第四步：增强系统提示词

**文件路径**：各agent实例的提示词文件（如 `src/agents/deepagents/instances/research_agent.py`）

**修改内容**：
- 在系统提示词中添加记忆使用协议说明
- 明确告诉agent如何使用 `/memories/` 路径
- 说明何时检查和更新记忆

**协议内容要点**：
- 会话开始时检查 `ls /memories/`
- 回答问题前优先查阅记忆文件
- 收到反馈时立即更新记忆
- agent.md 是核心记忆文件

### 文件创建清单

1. **新建目录**：`src/components/deepagents/runtime_middlewares/agent_memory/`
2. **新建文件**：`src/components/deepagents/runtime_middlewares/agent_memory/__init__.py`
3. **新建文件**：`src/components/deepagents/runtime_middlewares/agent_memory/middleware.py`
4. **新建文件**：`src/components/deepagents/runtime_middlewares/agent_memory/types.py`（如果需要）

### 配置项说明

在 `config/agents/deep/middleware/agent_memory.json` 中添加配置：

```json
{
  "enabled": true,
  "memory_path": "/memories/",
  "agent_file_path": "/memories/agent.md",
  "default_instructions_path": "config/agents/deep/prompts/default_agent_instructions.md"
}
```

### 注意事项

1. **文件读取时机**：需要在虚拟文件系统中间件初始化之后读取，确保文件系统可用
2. **错误处理**：如果 `/memories/agent.md` 不存在，应创建默认文件或跳过记忆加载
3. **性能考虑**：记忆内容可能较大，需要限制加载的文件大小
4. **兼容性**：确保与现有的虚拟文件系统和长期记忆机制兼容

