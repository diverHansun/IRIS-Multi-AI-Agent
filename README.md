# Muti-AI Agent Demo

基于LangChain和多LLM的中文优化智能代理演示项目，集成了上下文记忆系统、多搜索引擎、高德地图和OKX加密货币分析功能。

## 功能特性

- **多LLM支持**: 智谱AI GLM-4系列、OpenAI GPT-4o系列，支持动态切换
- **智能对话**: 基于ReAct推理框架的自然语言交互
- **上下文记忆**: 基于LangChain 2025最佳实践的会话记忆系统
- **工具调用**: 支持数学计算、网络搜索、地图导航、加密货币分析等多种工具
- **多搜索引擎**: 集成Tavily搜索API + DuckDuckGo备用搜索
- **高德地图集成**: 支持地点搜索、附近查询、驾车导航、步行导航、公共交通规划
- **OKX加密货币**: 实时行情、K线分析、价格预警、市场洞察
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
cd ZHIPU_Agent_Demo

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
3. **Tavily搜索** - [Tavily](https://tavily.com/) (推荐)
4. **高德地图** - [高德地图开放平台](https://lbs.amap.com/dev/key/app) (推荐)

复制 `.env.example` 为 `.env`：

```bash
cp .env.example .env
```

编辑 `.env` 文件：
```env
# 必需 - 至少配置一个LLM
ZHIPU_API_KEY=your_zhipu_api_key_here
OPENAI_API_KEY=your_openai_api_key_here

# 推荐 - 搜索和地图功能
TAVILY_API_KEY=your_tavily_api_key_here
AMAP_API_KEY=your_amap_api_key_here

# 可选 - 加密货币功能
# OKX_API_KEY=your_okx_api_key_here
# OKX_SECRET_KEY=your_okx_secret_key_here
# OKX_PASSPHRASE=your_okx_passphrase_here

# LLM配置
DEFAULT_LLM_PROVIDER=zhipu
DEFAULT_LLM_MODEL=glm-4-plus
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
- **GLM-4-Plus**: 最新旗舰模型，综合能力强 (推荐)
- **GLM-4**: 基础模型

### OpenAI
- **GPT-4o**: 最新GPT-4优化版本，性能和成本平衡 (推荐)
- **GPT-4o-mini**: 轻量级版本，速度快成本低 (推荐)
- **GPT-4-turbo**: 高性能版本

## 项目结构

```
ZHIPU_Agent_Demo/
├── src/
│   ├── agents/              # Agent实现
│   │   ├── zhipu_agent.py          # 智谱AI Agent
│   │   ├── openai_agent.py         # OpenAI Agent  
│   │   └── agent_factory.py        # Agent工厂
│   ├── llm/                # 语言模型封装
│   │   ├── zhipu_llm.py            # 智谱AI LLM
│   │   ├── openai_llm.py           # OpenAI LLM
│   │   └── llm_manager.py          # LLM管理器
│   ├── memory/             # 记忆系统
│   │   ├── chat_memory.py           # 统一记忆管理器
│   │   ├── conversation_buffer.py   # 对话缓冲区
│   │   ├── memory_storage.py        # 持久化存储
│   │   └── memory_integration.md    # 记忆系统集成文档
│   ├── tools/              # 工具实现
│   │   ├── math_tools.py            # 数学计算工具
│   │   ├── search_tools.py          # DuckDuckGo搜索工具
│   │   ├── tavily_search_tool.py    # Tavily搜索工具
│   │   ├── amap_search.py           # 高德地图工具
│   │   ├── okx_market/              # OKX加密货币工具
│   │   │   ├── client.py            # OKX客户端
│   │   │   ├── langchain_tools.py   # LangChain工具集成
│   │   │   └── ...
│   │   ├── mcp_client.py            # MCP客户端(备用)
│   │   └── mcp_search_server.py     # MCP服务器(备用)
│   └── config.py           # 配置管理
├── main.py                 # 主程序入口
├── requirements.txt        # 依赖列表
├── .env.example           # 环境变量示例
├── .gitignore             # Git忽略文件
├── langchain_tutorial.md  # LangChain教程
└── README.md              # 项目说明
```

## 使用示例

### CLI基本操作

```bash
# 基础命令
输入 'help' 查看帮助信息
输入 'info' 查看当前Agent信息
输入 'llms' 查看可用的LLM列表
输入 'switch <provider> [model]' 切换LLM

# 记忆管理
输入 'clear' 清除当前会话记忆
输入 'sessions' 查看历史会话列表
输入 'restore <session_id>' 恢复指定会话
```

### 多LLM切换示例

```
你 > switch openai gpt-4o-mini
AI Agent > 已切换到 OpenAI GPT-4o-mini

你 > switch zhipu glm-4-plus  
AI Agent > 已切换到 智谱AI GLM-4-Plus
```

### 记忆功能示例

```python
from src.agents.agent_factory import agent_factory

# 创建带记忆的Agent
agent = await agent_factory.create_agent(
    provider="zhipu",
    model="glm-4-plus",
    enable_memory=True,
    verbose=True
)

# 第一轮对话
result1 = agent.invoke("我的名字是张三", session_id="user_001")
# 第二轮对话 - 会记住之前的信息
result2 = agent.invoke("你还记得我的名字吗？", session_id="user_001")

# 不同用户的会话完全隔离
result3 = agent.invoke("我是谁？", session_id="user_002")  # 不会知道张三
```

### 数学计算

```
你 > 帮我计算 125 + 375
AI Agent > 我来为您计算...
Action: add_numbers
Action Input: 125 + 375
Observation: 500
Final Answer: 125 + 375 = 500
```

### 搜索功能

```
你 > 搜索人工智能最新发展
AI Agent > 我来为您搜索相关信息...
Action: tavily_search
Action Input: 人工智能最新发展
Observation: [搜索结果]
Final Answer: 根据搜索结果，人工智能最新发展包括...
```

### 高德地图功能

#### 地点搜索
```
你 > 搜索北京的星巴克
AI Agent > Action: amap_search_place
Action Input: 星巴克
Final Answer: 在北京找到了多个星巴克门店...
```

#### 驾车路线规划
```
你 > 规划从南京到上海的驾车路线
AI Agent > Action: amap_route_driving
Action Input: 南京,上海
Final Answer: 为您规划了从南京到上海的驾车路线...
```

#### 公共交通规划
```
你 > 规划从西直门到国贸的公共交通路线
AI Agent > Action: amap_route_transit
Action Input: 西直门,国贸,0,北京
Final Answer: 为您推荐了3条公共交通路线...
```

### OKX加密货币分析

#### 价格查询
```
你 > 获取比特币的当前价格
AI Agent > Action: get_crypto_price
Action Input: BTC
Final Answer: 比特币(BTC)当前价格为...
```

#### 市场分析
```
你 > 分析比特币最近24小时的价格趋势
AI Agent > Action: analyze_price_trend
Action Input: BTC 1H 24
Final Answer: 根据24小时K线数据分析...
```

## 可用工具

### 数学计算工具
- **add_numbers**: 执行两个数字的加法运算
- **calculate_math**: 执行复杂数学表达式计算

### 搜索工具
- **tavily_search**: Tavily基础搜索(推荐)
- **tavily_search_advanced**: Tavily高级搜索
- **tavily_search_news**: Tavily新闻搜索
- **tavily_search_with_domains**: Tavily域名过滤搜索
- **web_search_tool**: DuckDuckGo基础搜索(备用)
- **web_search_detailed**: DuckDuckGo详细搜索(备用)
- **get_webpage_content**: 获取指定网页的文本内容

### 高德地图工具

#### 地点搜索工具
- **amap_search_place**: 地点搜索，搜索商店、景点、服务设施等
- **amap_search_nearby**: 附近搜索，查找指定位置周围的POI
- **amap_search_in_city**: 城市内搜索，在指定城市内搜索地点

#### 路线规划工具
- **amap_route_driving**: 驾车路线规划，规划最优驾车路线
- **amap_route_walking**: 步行路线规划，规划步行路线

#### 公共交通工具
- **amap_route_transit**: 综合公共交通路线规划(公交、地铁、火车等)
  - 支持多种策略：最快路线(0)、最经济(1)、最少换乘(2)、最少步行(3)、不乘地铁(5)
- **amap_route_subway**: 地铁优先路线规划，使用最少换乘策略
- **amap_route_bus**: 公交专线规划，只使用公交车不包含地铁

### OKX加密货币工具

#### 实时行情
- **get_crypto_price**: 单币种价格查询
- **get_market_data**: 批量行情数据获取

#### 技术分析
- **get_kline_data**: K线数据获取
- **analyze_price_trend**: 价格趋势分析

#### 风险管理
- **create_price_alert**: 创建价格预警
- **check_price_alerts**: 检查预警状态

#### 市场洞察
- **get_market_summary**: 市场概览
- **search_crypto_symbols**: 交易对搜索

## 技术栈

### 核心框架
- **LangChain**: Agent框架和工具链(2025最佳实践)
- **Pydantic**: 配置管理和数据验证
- **Rich**: 终端美化和交互

### LLM支持
- **智谱AI (GLM-4系列)**: 主要大语言模型
- **OpenAI (GPT-4o系列)**: 备选大语言模型

### 外部服务
- **Tavily**: 高质量AI搜索API
- **高德地图**: 地理位置服务和导航API
- **OKX**: 加密货币交易数据API
- **DuckDuckGo**: 备用搜索引擎

### 技术特性
- **RunnableWithMessageHistory**: 标准化记忆管理
- **BeautifulSoup**: 网页内容解析
- **Requests**: HTTP请求处理
- **Python-dotenv**: 环境变量管理

## 配置选项

在 `.env` 文件中可以配置：

### LLM配置
- `ZHIPU_API_KEY`: 智谱AI API密钥
- `OPENAI_API_KEY`: OpenAI API密钥
- `OPENAI_BASE_URL`: OpenAI API基础URL(可选)
- `DEFAULT_LLM_PROVIDER`: 默认LLM提供商(`zhipu`/`openai`)
- `DEFAULT_LLM_MODEL`: 默认模型名称

### 工具配置
- `TAVILY_API_KEY`: Tavily搜索API密钥(推荐)
- `AMAP_API_KEY`: 高德地图API密钥(推荐)
- `OKX_API_KEY`: OKX API密钥(可选)
- `OKX_SECRET_KEY`: OKX Secret密钥(可选)  
- `OKX_PASSPHRASE`: OKX Passphrase(可选)

### 模型参数
- `TEMPERATURE`: 温度参数，控制输出随机性，默认为 `0.1`
- `MAX_TOKENS`: 最大输出token数，默认为 `2048`

## 搜索功能说明

### Tavily搜索(推荐)
- **优势**: 专为AI应用设计，提供高质量搜索结果
- **功能**: 基础搜索、高级搜索、新闻搜索、域名过滤
- **配置**: 需要TAVILY_API_KEY

### DuckDuckGo搜索(备用)
- **优势**: 无需API密钥，免费使用
- **功能**: 基础搜索、详细搜索、网页内容获取
- **限制**: 搜索质量相对较低，可能受反爬虫限制

### 搜索策略
1. 优先使用Tavily搜索(如果配置了API密钥)
2. Tavily不可用时自动降级到DuckDuckGo搜索
3. 支持多轮搜索和结果筛选

## 开发说明

### 记忆系统架构

项目使用LangChain 2025最佳实践的记忆系统：

```
ChatMemoryManager (统一管理器)
├── ConversationBuffer (对话缓冲区)
│   ├── 继承 BaseChatMessageHistory
│   ├── 智能消息修剪 (trim_messages)
│   └── 会话级别的消息管理
└── MemoryStorage (持久化存储)
    ├── JSON文件存储
    ├── 会话元数据管理
    └── 自动清理机制
```

详细的记忆系统集成文档请参考：`src/memory/memory_integration.md`

### Agent架构

项目支持多LLM Agent架构：

```
AgentFactory (Agent工厂)
├── ZhipuAgent (智谱AI Agent)
├── OpenAIAgent (OpenAI Agent)
└── LLMManager (LLM管理器)
    ├── 动态LLM切换
    ├── 模型配置管理
    └── API密钥管理
```

### 工具系统架构

项目支持多层次的工具系统：

1. **数学工具**: 基础计算和复杂表达式
2. **Tavily搜索**: 高质量AI搜索引擎(推荐)
3. **DuckDuckGo搜索**: 免费备用搜索引擎
4. **高德地图**: 完整的地图和导航服务
5. **OKX加密货币**: 实时行情和技术分析
6. **MCP工具**: 基于MCP协议的扩展工具

### 添加新工具

1. 在 `src/tools/` 目录下创建新的工具文件
2. 使用 `@tool` 装饰器定义工具函数
3. 在相应的Agent中注册新工具

```python
from langchain_core.tools import tool

@tool
def your_new_tool(param: str) -> str:
    """工具描述"""
    # 实现逻辑
    return result
```

### 自定义Agent

可以通过AgentFactory来创建自定义Agent：

```python
from src.agents.agent_factory import agent_factory

# 创建自定义Agent
agent = await agent_factory.create_agent(
    provider="zhipu",  # 或 "openai"
    model="glm-4-plus",  # 或其他支持的模型
    verbose=True,
    temperature=0.1,
    enable_memory=True
)
```

### ReAct提示词

项目使用标准化的ReAct提示词模板，支持聊天历史和工具使用指南。确保：

- 严格的格式约束
- 明确的工具使用指南  
- 基于实际结果的回答
- 上下文记忆集成

## 已知问题与解决方案

### 1. 编码问题
- **问题**: Windows终端Unicode字符显示问题
- **解决**: 在代码中添加`sys.stdout.reconfigure(encoding='utf-8')`

### 2. URL解析问题
- **问题**: DuckDuckGo返回相对URL导致访问失败
- **解决**: 在`search_tools.py`中添加URL修复逻辑

### 3. 多参数工具问题
- **问题**: ReAct模式下工具只能接受单一字符串参数
- **解决**: 简化工具接口，内置默认参数

### 4. 网页内容获取限制
- **问题**: 403 Forbidden错误
- **解决**: 增强HTTP请求头，模拟真实浏览器

### 5. 代理设置问题
- **问题**: 网络代理导致连接失败
- **解决**: 在LLM初始化时清除代理设置

### 6. 高德地图API限制
- **问题**: 香港等地区地址查询可能失败
- **解决**: 添加错误处理和备用方案

## 注意事项

1. **API密钥**: 使用前请确保有足够的API额度
2. **网络环境**: 确保能够访问相关API服务
3. **虚拟环境**: 建议在虚拟环境中运行以避免依赖冲突
4. **编码设置**: 项目已设置UTF-8编码，支持中文显示
5. **备用方案**: 没有API密钥时会自动使用备用服务
6. **记忆存储**: 会话数据自动保存到`.memory`文件夹
7. **模型选择**: 根据需求选择合适的LLM模型和配置

## 故障排除

### 常见问题

1. **API密钥错误**: 检查 `.env` 文件中的密钥是否正确
2. **网络连接问题**: 确保能够访问API服务
3. **依赖安装失败**: 尝试使用 `pip install --upgrade pip` 更新pip
4. **编码问题**: 确保终端支持UTF-8编码
5. **搜索失败**: 检查网络连接和API密钥配置
6. **LLM切换失败**: 确保目标LLM的API密钥已正确配置

### 调试方法

1. 检查日志输出信息
2. 使用详细模式运行：`verbose=True`
3. 查看工具调用的中间步骤
4. 验证API密钥的有效性
5. 检查网络连接状态

## 贡献

欢迎提交Issue和Pull Request来改进项目！

### 贡献指南

1. Fork项目
2. 创建功能分支
3. 提交更改
4. 发起Pull Request

## 更新日志

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