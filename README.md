# 智谱AI Agent Demo

基于LangChain和智谱AI构建的中文优化智能代理演示项目，集成了上下文记忆系统和多搜索引擎。

## 功能特性

- 🤖 **智能对话**: 基于智谱AI GLM-4-PLUS模型的自然语言交互
- 🧠 **上下文记忆**: 基于LangChain 2025最佳实践的会话记忆系统
- 🔧 **工具调用**: 支持数学计算、网络搜索等多种工具
- 🔍 **多搜索引擎**: 集成Tavily搜索API + DuckDuckGo备用搜索
- 🎯 **ReAct架构**: 使用推理-行动循环进行复杂问题解决
- 💬 **中文优化**: 针对中文场景优化的提示词和交互体验
- ⚡ **异步支持**: 支持同步和异步调用模式
- 👥 **多用户支持**: 支持会话隔离和持久化存储
- 🔄 **备用机制**: 自动降级到DuckDuckGo搜索作为备用方案

## 快速开始

### 1. 环境准备

确保您的Python版本 >= 3.8

```bash
# 克隆项目
git clone <your-repo-url>
cd Agent_Demo

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

1. 访问 [智谱AI开放平台](https://open.bigmodel.cn/) 申请API密钥
2. 访问 [Tavily](https://tavily.com/) 申请搜索API密钥
3. 复制 `.env.example` 为 `.env`
4. 在 `.env` 文件中填入您的API密钥

```bash
cp .env.example .env
```

编辑 `.env` 文件：
```
ZHIPU_API_KEY=your_zhipu_api_key_here
TAVILY_API_KEY=your_tavily_api_key_here
```

### 3. 运行程序

```bash
# 启动交互式CLI
python main.py

# 或者运行异步示例
python main.py async
```

## 项目结构

```
Agent_Demo/
├── src/
│   ├── agents/              # Agent实现
│   │   └── zhipu_agent.py
│   ├── llm/                # 语言模型封装
│   │   └── zhipu_llm.py
│   ├── memory/             # 记忆系统
│   │   ├── chat_memory.py           # 统一记忆管理器
│   │   ├── conversation_buffer.py   # 对话缓冲区
│   │   ├── memory_storage.py        # 持久化存储
│   │   └── memory_integration.md    # 记忆系统集成文档
│   ├── tools/              # 工具实现
│   │   ├── math_tools.py           # 数学计算工具
│   │   ├── search_tools.py         # DuckDuckGo搜索工具
│   │   ├── tavily_search_tool.py   # Tavily搜索工具
│   │   ├── mcp_client.py           # MCP客户端（备用）
│   │   └── mcp_search_server.py    # MCP服务器（备用）
│   ├── config.py           # 配置管理
│   └── __init__.py
├── main.py                 # 主程序入口
├── requirements.txt        # 依赖列表
├── .env.example           # 环境变量示例
├── .gitignore             # Git忽略文件
├── CLAUDE.md              # 开发文档
└── README.md              # 项目说明
```

## 使用示例

### 基础对话
```
你 > 你好，请介绍一下自己
智谱AI > 您好！我是基于智谱AI GLM-4模型的智能助手...
```

### 记忆功能示例
```
python
from src.agents.zhipu_agent import build_zhipu_agent

# 创建带记忆的Agent
agent = await build_zhipu_agent(
    enable_memory=True,
    memory_config={
        "max_messages": 20,
        "max_tokens": 4000,
        "auto_save": True
    }
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
智谱AI > 我来为您计算...
Action: add_numbers
Action Input: 125,375
Observation: 125 + 375 = 500
Final Answer: 125 + 375 = 500
```

### 搜索功能
```
你 > 搜索人工智能最新发展
智谱AI > 我来为您搜索相关信息...
Action: tavily_search
Action Input: 人工智能最新发展
Observation: [Tavily搜索结果]
Final Answer: 根据搜索结果，人工智能最新发展包括...
```

### 上下文记忆搜索
```
你 > 搜索Python教程
智谱AI > 我来为您搜索Python教程...
[返回搜索结果]

你 > 刚才搜索的内容中，哪个最适合初学者？
智谱AI > 根据刚才搜索的Python教程结果，最适合初学者的是...
```

## 可用工具

### 数学计算工具
- **add_numbers**: 执行两个数字的加法运算
- **calculate_math**: 执行复杂数学表达式计算

### 搜索工具
- **tavily_search**: Tavily基础搜索（推荐）
- **tavily_search_advanced**: Tavily高级搜索
- **tavily_search_news**: Tavily新闻搜索
- **tavily_search_with_domains**: Tavily域名过滤搜索
- **web_search_tool**: DuckDuckGo基础搜索（备用）
- **web_search_detailed**: DuckDuckGo详细搜索（备用）

### 内容获取工具
- **get_webpage_content**: 获取指定网页的文本内容

## 技术栈

- **LangChain**: Agent框架和工具链 (2025最佳实践)
- **智谱AI (GLM-4-PLUS)**: 大语言模型
- **Tavily**: 高质量AI搜索API
- **RunnableWithMessageHistory**: 标准化记忆管理
- **Rich**: 终端美化和交互
- **Pydantic**: 配置管理和数据验证
- **Python-dotenv**: 环境变量管理
- **BeautifulSoup**: 网页内容解析
- **Requests**: HTTP请求处理

## 配置选项

在 `.env` 文件中可以配置：

- `ZHIPU_API_KEY`: 智谱AI API密钥（必需）
- `TAVILY_API_KEY`: Tavily搜索API密钥（推荐）
- `MODEL_NAME`: 模型名称，默认为 `glm-4-plus`
- `TEMPERATURE`: 温度参数，控制输出随机性，默认为 `0.1`
- `MAX_TOKENS`: 最大输出token数，默认为 `2048`

## 搜索功能说明

### Tavily搜索 (推荐)
- **优势**：专为AI应用设计，提供高质量搜索结果
- **功能**：基础搜索、高级搜索、新闻搜索、域名过滤
- **配置**：需要TAVILY_API_KEY

### DuckDuckGo搜索 (备用)
- **优势**：无需API密钥，免费使用
- **功能**：基础搜索、详细搜索、网页内容获取
- **限制**：搜索质量相对较低，可能受反爬虫限制

### 搜索策略
1. 优先使用Tavily搜索（如果配置了API密钥）
2. Tavily不可用时自动降级到DuckDuckGo搜索
3. 支持多轮搜索和结果筛选

## 开发说明

### 记忆系统架构

项目使用LangChain 2025最佳实践的记忆系统：

```
python
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

### 工具系统架构

项目支持多层次的工具系统：

1. **数学工具**：基础计算和复杂表达式
2. **Tavily搜索**：高质量AI搜索引擎（推荐）
3. **DuckDuckGo搜索**：免费备用搜索引擎
4. **MCP工具**：基于MCP协议的扩展工具

### 添加新工具

1. 在 `src/tools/` 目录下创建新的工具文件
2. 使用 `@tool` 装饰器定义工具函数
3. 在 `src/agents/zhipu_agent.py` 中注册新工具

```
python
from langchain_core.tools import tool

@tool
def your_new_tool(param: str) -> str:
    """工具描述"""
    # 实现逻辑
    return result
```

### 自定义Agent

可以通过修改 `build_zhipu_agent` 函数来自定义agent行为：

- 调整模型参数
- 添加/移除工具
- 修改提示词模板
- 配置记忆参数
- 设置执行参数

### ReAct提示词

项目使用标准化的ReAct提示词模板，支持聊天历史：

```
python
REACT_PROMPT_ZH = """你是一个功能强大的AI助手...

## 聊天历史
{chat_history}

## 可用工具列表
{tools}
```

确保：
- 严格的格式约束
- 明确的工具使用指南
- 基于实际结果的回答
- 上下文记忆集成

## 已知问题与解决方案

### 1. ✅ 编码问题
- **问题**：Windows终端Unicode字符显示问题
- **解决**：在代码中添加`sys.stdout.reconfigure(encoding='utf-8')`

### 2. ✅ URL解析问题
- **问题**：DuckDuckGo返回相对URL导致访问失败
- **解决**：在`search_tools.py`中添加URL修复逻辑

### 3. ✅ 多参数工具问题
- **问题**：ReAct模式下工具只能接受单一字符串参数
- **解决**：简化工具接口，内置默认参数

### 4. ✅ 网页内容获取限制
- **问题**：403 Forbidden错误
- **解决**：增强HTTP请求头，模拟真实浏览器

### 5. ✅ 代理设置问题
- **问题**：网络代理导致连接失败
- **解决**：在LLM初始化时清除代理设置

## 注意事项

1. **API密钥**：使用前请确保有足够的API额度
2. **网络环境**：确保能够访问智谱AI和Tavily API服务
3. **虚拟环境**：建议在虚拟环境中运行以避免依赖冲突
4. **编码设置**：项目已设置UTF-8编码，支持中文显示
5. **备用方案**：没有Tavily API密钥时会自动使用DuckDuckGo搜索
6. **记忆存储**：会话数据自动保存到`.memory`文件夹

## 故障排除

### 常见问题

1. **API密钥错误**：检查 `.env` 文件中的密钥是否正确
2. **网络连接问题**：确保能够访问API服务
3. **依赖安装失败**：尝试使用 `pip install --upgrade pip` 更新pip
4. **编码问题**：确保终端支持UTF-8编码
5. **搜索失败**：检查网络连接和API密钥配置

### 调试方法

1. 检查日志文件 `*.log`
2. 使用详细模式运行：`verbose=True`
3. 查看工具调用的中间步骤
4. 验证API密钥的有效性

## 许可证

MIT License

## 贡献

欢迎提交Issue和Pull Request来改进项目！

### 贡献指南

1. Fork项目
2. 创建功能分支
3. 提交更改
4. 发起Pull Request

## 更新日志

### v2.0.0 (2025-07-17)
- 🧠 **重大更新**：集成LangChain 2025最佳实践的记忆系统
- 🔄 **RunnableWithMessageHistory**：使用标准化的记忆管理模式
- 👥 **多用户支持**：实现会话隔离和持久化存储
- 📝 **智能消息修剪**：基于token和消息数量的自动修剪
- 🗂️ **文档完善**：新增记忆系统集成文档
- 🧹 **代码清理**：移除冗余的memory_manager模块
- 🔧 **代理修复**：解决网络代理导致的连接问题

### v1.0.0 (2025-07-16)
- 集成Tavily搜索API
- 优化ReAct提示词模板
- 增强网页内容获取功能
- 修复DuckDuckGo搜索URL解析问题
- 完善错误处理和日志记录