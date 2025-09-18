# Multi-AI-Agent 
基于LangChain和多LLM的中文优化智能代理演示项目，集成了上下文记忆系统、多搜索引擎、高德地图、OKX加密货币和Notion知识管理功能。

## 功能特性

- **多LLM支持**: 智谱AI GLM-4.5/GLM-4-Plus、OpenAI GPT-5/GPT-5-mini/GPT-4o系列、Ollama本地模型，支持动态切换
- **双模式智能对话**: 
  - ReAct推理框架（GLM-4-Plus等）：基于经典ReAct框架的自然语言交互
  - Function Calling模式（GLM-4.5）：基于智谱AI原生Function Calling API的高效工具调用
- **全局记忆系统**: 基于LangChain 2025最佳实践的统一记忆管理
- **工具调用**: 支持数学计算、网络搜索、地图导航、加密货币分析、Notion知识管理等多种工具
- **多搜索引擎**: 集成Tavily搜索API + DuckDuckGo备用搜索
- **高德地图集成**: 支持地点搜索、附近查询、驾车导航、步行导航、公共交通规划
- **OKX加密货币**: 实时行情、K线分析、价格预警、市场洞察
- **Notion集成**: 智能搜索、页面管理、数据库操作，支持Direct API访问
- **MCP工具支持**: 支持Model Context Protocol扩展工具，包括文件系统访问、网页内容获取等
- **JSON ReAct补丁**: 自定义解析器解决MCP工具JSON格式输入问题
- **中文优化**: 针对中文场景优化的提示词和交互体验
- **异步支持**: 支持同步和异步调用模式
- **多用户支持**: 支持会话隔离和持久化存储
- **智能降级**: 自动降级到备用方案保证服务可用性

## 快速开始

### 1. 环境准备

确保您的Python版本 >= 3.8

```bash
# 克隆项目
git clone <your-repo-url>
cd Multi-AI-Agent

# 创建虚拟环境
python -m venv .venv

# 激活虚拟环境 (Windows PowerShell)
.venv\Scripts\Activate.ps1

# 激活虚拟环境 (Linux/Mac)
source .venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 2. 配置API密钥

支持的API服务：

1. **智谱AI** - [智谱AI开放平台](https://open.bigmodel.cn/) (必需)
2. **OpenAI** - [OpenAI API](https://platform.openai.com/) (可选)
3. **Ollama本地模型** - [Ollama](https://ollama.com/) (可选，支持本地离线运行)
4. **Tavily搜索** - [Tavily](https://tavily.com/) (推荐)
5. **高德地图** - [高德地图开放平台](https://lbs.amap.com/dev/key/app) (推荐)
6. **Notion** - [Notion API](https://developers.notion.com/) (可选)

复制 `.env.example` 为 `.env`：

```bash
cp .env.example .env
```

编辑 `.env` 文件：
```env
# 必需 - 至少配置一个LLM
ZHIPU_API_KEY=your_zhipu_api_key_here
OPENAI_API_KEY=your_openai_api_key_here

# Ollama本地模型配置(可选)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=gpt-oss:20b
# 建议使用规则代理模式以获得最佳网络兼容性

# 推荐 - 搜索和地图功能
TAVILY_API_KEY=your_tavily_api_key_here
AMAP_API_KEY=your_amap_api_key_here

# 可选 - Notion知识管理
NOTION_TOKEN=your_notion_integration_token_here

# 可选 - 加密货币功能
# OKX_API_KEY=your_okx_api_key_here
# OKX_SECRET_KEY=your_okx_secret_key_here
# OKX_PASSPHRASE=your_okx_passphrase_here

# LLM配置
DEFAULT_LLM_PROVIDER=zhipu OR openai OR ollama
DEFAULT_LLM_MODEL=glm-4-plus OR gpt-4o
```

### 3. 运行程序

```bash
# 启动交互式CLI
python main.py

# 查看帮助信息
python main.py --help
```

## 支持的LLM模型

### 智谱AI (推荐)

#### GLM-4.5 ⭐
新一代MoE架构模型，支持128K上下文，专精代码推理和工具调用
- ✅ 支持思考模式，复杂推理能力更强
- ✅ 96K输出token，128K上下文窗口
- ✅ 专精代码生成和工具调用
- 🚀 **Function Calling模式**: 使用智谱AI原生Function Calling API，工具调用更高效准确

#### GLM-4-Plus ⭐
最新旗舰模型，综合能力强
- ✅ 8K输出token，综合性能优秀
- ✅ 适合通用对话和任务处理
- 🧠 **ReAct模式**: 使用经典的ReAct推理框架，支持复杂的多步骤任务

### OpenAI

#### GPT-5 ⭐
新一代语言模型，推理和创造能力显著提升
- ✅ 8K输出token，先进推理能力
- ✅ 增强创造性和工具调用

#### GPT-5-mini ⭐
成本优化版本，速度快成本低
- ✅ 32K输出token，快速推理
- ✅ 成本效益优秀

#### GPT-4o ⭐
最新GPT-4优化版本，性能和成本平衡
- ✅ 4K输出token，平衡性能

#### GPT-4o-mini ⭐
轻量级版本，速度快成本低
- ✅ 16K输出token，快速响应

#### GPT-4-turbo
高性能版本
- ✅ 4K输出token，稳定可靠

### Ollama本地模型

支持所有Ollama兼容的本地模型，用户需要自行使用Ollama下载和管理模型。

#### 推荐模型（需自行下载）

| 模型 | 参数量 | 特点 | 适用场景 |
|------|--------|------|----------|
| **gpt-oss:20b** | 20B | 开源GPT，支持工具调用 | 复杂推理任务 |
| **qwen3:8b** | 8B | 通义千问3.0，中文优化 | 中文对话优先 |
| **gemma3:latest** | - | Google Gemma3最新版 | 性能稳定 |
| **deepseek-r1:1.5b** | 1.5B | DeepSeek推理模型 | 轻量快速 |

#### 使用方法

```bash
# 1. 安装Ollama
# 访问 https://ollama.com/ 下载安装

# 2. 下载模型（示例）
ollama pull qwen3:8b
ollama pull deepseek-r1:1.5b

# 3. 在项目中使用
switch ollama qwen3:8b
```

> **💡 网络配置建议**: 使用规则代理模式可以实现最佳网络兼容性，本地Ollama服务走直连，外部API服务（如搜索、地图等）通过代理访问，确保所有功能正常工作。

### 模型特性对比

| 特性 | GLM-4.5 | GLM-4-Plus | GPT-5 | GPT-5-mini | GPT-4o | GPT-4o-mini |
|------|---------|------------|-------|------------|--------|-------------|
| 输出Token | 96K | 8K | 8K | 32K | 4K | 16K |
| 上下文窗口 | 128K | 32K | 8K | 32K | 128K | 128K |
| 思考模式 | ✅ | ❌ | ✅ | ✅ | ❌ | ❌ |
| 逻辑推理 | 专精 | 优秀 | 优秀 | 优秀 | 良好 | 良好 |
| 工具调用 | 专精 | 优秀 | 优秀 | 优秀 | 良好 | 良好 |
| 代码生成 | 专精 | 优秀 | 优秀 | 优秀 | 良好 | 良好 |
| 成本效益 | 中等 | 优秀 | 中等 | 优秀 | 优秀 | 优秀 |

### 模型特性详细说明

#### GLM-4.5 (智谱AI最新旗舰)
- **上下文窗口**: 128K tokens - 支持超长文档处理
- **输出Token**: 96K tokens - 适合长文本生成
- **思考模式**: ✅ 自动启用，提供深度推理能力
- **架构**: 混合专家模型(MoE) - 更高效的参数利用
- **专精领域**: 代码生成、复杂推理、工具调用
- **适用场景**: 复杂编程任务、长文档分析、深度推理
- **Agent模式**: Function Calling模式，使用智谱AI原生API

#### GLM-4-Plus (智谱AI综合旗舰)
- **上下文窗口**: 32K tokens - 平衡性能和成本
- **输出Token**: 8K tokens - 适合一般对话和任务
- **架构**: Transformer - 经典架构，稳定可靠
- **适用场景**: 日常对话、创意写作、一般任务处理
- **Agent模式**: ReAct模式，使用经典的ReAct推理框架

### 智谱AI Provider架构说明

智谱AI Provider支持两种不同的Agent模式：

1. **Function Calling模式 (GLM-4.5)**
   - 使用智谱AI原生Function Calling API
   - 工具调用由API直接返回，无需解析LLM输出
   - 支持结构化的工具调用和参数传递
   - 集成完整的MCP工具支持
   - 更高效的工具调用性能

2. **ReAct模式 (GLM-4-Plus及其他模型)**
   - 使用经典的ReAct推理框架
   - 通过解析LLM输出提取工具调用指令
   - 支持复杂的多步骤任务处理
   - 通过JSON ReAct补丁支持MCP工具


## 使用示例

### CLI基本操作

```bash
# 基础命令
输入 'help' 查看帮助信息

# 切换LLM模型
你 > switch zhipu glm-4-plus  
AI Agent > 已切换到 智谱AI GLM-4-Plus

你 > switch zhipu glm-4.5
AI Agent > 已切换到 智谱AI GLM-4.5 (思考模式已启用)
```

### 模型选择建议

#### 智谱AI模型选择建议
- **GLM-4.5**: 适合复杂推理、代码生成、长文档处理
  - 支持128K上下文，可处理超长文档
  - 思考模式提供更好的推理能力
  - 专精代码生成和工具调用
  - **Function Calling模式**: 工具调用更高效准确，适合需要频繁工具调用的场景
- **GLM-4-Plus**: 适合日常对话、创意写作、一般任务
  - 综合性能优秀，响应速度快
  - 成本效益好，适合频繁使用
  - **ReAct模式**: 支持复杂的多步骤任务，适合需要深度推理的场景

#### OpenAI模型选择建议
- **GPT-5**: 适合复杂推理、创意写作、高级任务
  - 最新一代模型，推理能力最强
  - 适合需要深度思考的场景
- **GPT-5-mini**: 适合快速响应、日常对话、成本敏感场景
  - 32K输出token，适合长文本生成
  - 成本效益优秀
- **GPT-4o**: 适合平衡性能和成本的场景
- **GPT-4o-mini**: 适合快速响应和成本敏感场景

#### 模型切换最佳实践
```bash
# 查看所有可用模型
llms

# 根据任务类型切换模型
switch zhipu glm-4.5    # 复杂推理任务
switch zhipu glm-4-plus # 日常对话任务
switch openai gpt-5     # 创意写作任务
switch openai gpt-5-mini # 快速响应任务
```

## 配置选项

创建 `.env` 文件进行配置参见.env.example：

### LLM配置
- `ZHIPU_API_KEY`: 智谱AI API密钥 (必需，用于GLM-4.5和GLM-4-Plus)
- `OPENAI_API_KEY`: OpenAI API密钥 (必需，用于GPT-5、GPT-5-mini、GPT-4o等)
- `OPENAI_BASE_URL`: OpenAI API基础URL(可选，用于自定义API端点)
- `DEFAULT_LLM_PROVIDER`: 默认LLM提供商(`zhipu`/`openai`)，默认为`zhipu`
- `DEFAULT_LLM_MODEL`: 默认模型名称，如`glm-4-plus`、`gpt-4o-mini`等

#### LLM配置示例
```bash
# 智谱AI配置
ZHIPU_API_KEY=your_zhipu_api_key_here
DEFAULT_LLM_PROVIDER=zhipu
DEFAULT_LLM_MODEL=glm-4-plus

# OpenAI配置
OPENAI_API_KEY=your_openai_api_key_here
DEFAULT_LLM_PROVIDER=openai
DEFAULT_LLM_MODEL=gpt-4o-mini

# 自定义OpenAI端点(可选)
OPENAI_BASE_URL=https://api.openai.com/v1
```

### 工具配置
- `TAVILY_API_KEY`: Tavily搜索API密钥(推荐)
- `AMAP_API_KEY`: 高德地图API密钥(推荐)
- `NOTION_TOKEN`: Notion集成Token(可选)
- `OKX_API_KEY`: OKX API密钥(可选)
- `OKX_SECRET_KEY`: OKX Secret密钥(可选)  
- `OKX_PASSPHRASE`: OKX Passphrase(可选)

### 模型参数
- `TEMPERATURE`: 温度参数，控制输出随机性，默认为 `0.1`
- `MAX_TOKENS`: 最大输出token数，默认为 `2048`

## 更新日志

### v2.8.0 (2025-09-18)
- **JSON配置系统**: 全面从硬编码配置迁移到灵活的JSON配置
  - 新增 `config/llms/providers.json` 主配置文件
  - 实现 `LLMConfigLoader` 配置加载器，支持缓存和热重载
  - 添加完整的配置验证系统：JSON Schema验证 + 业务逻辑检查
  - 支持自动配置修复和错误处理
  - 新增 `reload` CLI命令，支持配置热重载
- **配置架构优化**:
  - 重构 `src/components/validation.py` 配置验证组件
  - 创建 `config/llms/schema.json` JSON Schema定义
  - 添加 `config/llms/example_provider.json` 示例配置
  - 完善的文档和使用指南
- **MCP配置整理**:
  - 重组MCP配置文件到 `config/mcp/` 目录
  - 更新所有相关路径引用和文档
  - 优化配置文件组织结构
- **向后兼容性**:
  - 保持硬编码备用配置，确保系统稳定性
  - 优雅的降级机制，配置加载失败时自动回退
  - 无破坏性变更，现有用户无需修改使用方式

### v2.7.0 (2025-09-08)
- **Function Calling支持**: 完整集成智谱AI原生Function Calling API
  - 支持GLM-4.5模型的原生工具调用
  - 实现`ZhipuFunctionCallingAgent`和工具适配器
  - 集成完整的MCP工具支持
  - 支持结构化的错误处理和重试机制
- **双模式Agent架构**:
  - Function Calling模式（GLM-4.5）：基于原生API的高效工具调用
  - ReAct模式（其他模型）：基于经典ReAct框架的复杂任务处理
  - 统一的Agent工厂和接口
- **工具适配器优化**:
  - 重命名`tool_adapter.py`为`functioncalling_adapter.py`
  - 增强MCP工具参数处理
  - 完善错误处理和重试机制

### v2.6.0 (2025-09-06)
- **MCP工具支持**: 完整集成Model Context Protocol扩展工具
  - 支持Filesystem MCP：本地文件系统访问
  - 支持Fetch MCP：网页内容获取
  - 支持Notion MCP：Notion页面和数据库交互
  - 完善的MCP配置管理和服务自动启动
- **JSON ReAct补丁**: 解决MCP工具JSON格式输入问题
  - 实现自定义的`JSONReActSingleInputOutputParser`解析器
  - 自动解析JSON格式的工具输入参数
  - 支持字典和数组格式的工具调用
  - 模块化设计，便于在其他项目中复用

### v2.5.0 (2025-08-28)
- **Ollama本地LLM支持**: 新增完整的Ollama本地模型集成
  - 支持gpt-oss:20b、qwen3:8b、gemma3:latest、deepseek-r1:1.5b等主流开源模型
  - 智能模型自动切换：系统启动时自动检测可用模型并切换
  - 工具调用支持：所有支持的模型都具备工具调用能力
  - 健康检查机制：自动检测Ollama服务状态和模型可用性
- **网络代理处理优化**: 彻底重构代理处理机制
  - 移除粗暴的全局代理删除逻辑，避免影响其他服务
  - 支持规则代理配置（如Clash规则模式），智能路由本地和外部服务
  - 保持外部API服务的代理访问能力（OKX、Tavily、Notion等）
  - 提升网络兼容性，适配多种网络环境
- **Agent工厂增强**: 
  - 新增create_ollama_agent函数，支持本地模型Agent创建
  - 统一的Agent创建接口，支持zhipu、openai、ollama三种提供商
  - 自动配置推荐参数，提升本地模型性能
- **配置管理优化**:
  - 新增OLLAMA_BASE_URL、OLLAMA_MODEL等配置选项
  - 支持本地模型的自定义超时、保活等参数配置
  - 向后兼容现有配置，无需修改已有部署

### v2.4.0 (2025-08-15)
- **Notion集成**: 完整的Notion知识管理功能
  - 智能搜索算法：解决相关性排序问题，精确匹配目标内容
  - 页面管理：支持页面信息获取、内容提取、搜索功能
  - 数据库操作：支持数据库查询、记录获取、架构分析
  - Direct API集成：使用原生Notion API，性能稳定可靠
- **智能搜索增强**：
  - 多维度评分算法：精确匹配、子串匹配、字符串相似度、日期格式匹配
  - 备选查询生成：自动生成多种格式的搜索查询提升覆盖率
  - 结果去重排序：基于相关性重新排列搜索结果
- **OpenAI Agent优化**：
  - 解决页面内容获取问题：修复无法获取完整页面内容的bug
  - 工具调用改进：使用隐式工具调用，提升用户体验
  - 多步骤任务支持：自动完成复杂的工具调用序列
- **代码清理和优化**：
  - 移除临时测试文件，保持项目结构清洁
  - 完善错误处理和异常管理
  - 统一同步异步接口，提升代码一致性

### v2.3.0 (2025-08-08)
- **全局记忆系统**: 重构为统一的全局记忆管理架构
  - 跨模式记忆共享(LLM ↔ Agent)
  - 自动消息过滤和上下文管理
  - 智能会话恢复和持久化存储
  - 统一存储到 `data/sessions` 目录
- **架构清理**: 消除代码冗余，优化模块结构
  - 移除重复的记忆管理实现
  - 统一记忆接口和API
  - 完善错误处理和日志记录
- **会话管理增强**: 
  - 自动会话索引和元数据管理
  - 支持会话统计和清理功能
  - 改进的消息修剪和Token管理

### v2.2.0 (2025-08-06)
- **多LLM支持**: 新增OpenAI GPT-4o系列支持
- **Agent工厂**: 统一Agent创建和管理
- **LLM管理器**: 支持动态LLM切换
- **OKX集成**: 新增加密货币分析工具
- **代码优化**: 重构架构，提升可扩展性

### v2.1.0 (2025-07-30)
- **高德地图集成**: 完整的地图服务集成
  - 地点搜索：支持关键词、附近、城市内搜索
  - 驾车导航：智能路线规划和导航指导
  - 步行导航：精确的步行路线规划
  - 公共交通：完整的公交、地铁、综合交通规划
- **公共交通增强**:
  - 详细线路信息显示(线路名称、起终点站、距离时间)
  - 多种路线策略(最快、最经济、最少换乘等)
  - 智能地址解析和坐标转换
  - 城市上下文支持，避免同名地点混淆
- **工具系统优化**:
  - ReAct模式兼容的单参数工具设计
  - 完善的错误处理和参数验证
  - 详细的步行指导和路线展示
- **代码清理**: 移除冗余测试文件，完善文档

### v2.0.0 (2025-07-17)
- **重大更新**: 集成LangChain 2025最佳实践的记忆系统
- **RunnableWithMessageHistory**: 使用标准化的记忆管理模式
- **多用户支持**: 实现会话隔离和持久化存储
- **智能消息修剪**: 基于token和消息数量的自动修剪
- **文档完善**: 新增记忆系统集成文档
- **代码清理**: 移除冗余的memory_manager模块
- **代理修复**: 解决网络代理导致的连接问题

### v1.0.0 (2025-07-16)
- 集成Tavily搜索API
- 优化ReAct提示词模板
- 增强网页内容获取功能
- 修复DuckDuckGo搜索URL解析问题
- 完善错误处理和日志记录