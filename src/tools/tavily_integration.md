# Tavily Search API 集成文档

## 项目背景

根据 CLAUDE.md 文档，本项目是一个基于 LangChain 和智谱 AI GLM-4 模型的中文优化 AI Agent 演示项目。目前使用 DuckDuckGo 搜索功能，但需要集成更强大的 Tavily Search API 来提供更准确的搜索结果。

## Tavily Search API 优势

1. **专业搜索引擎**: 专为 AI 应用设计的搜索 API
2. **高质量结果**: 提供结构化、清洁的搜索数据
3. **多语言支持**: 支持中文搜索查询
4. **实时搜索**: 提供最新的网络信息
5. **LangChain 集成**: 官方支持 LangChain 集成

## TODO 列表

### 高优先级任务
- [ ] 设置 Tavily API 配置
- [ ] 创建 tavily_search_tool.py 工具
- [ ] 集成到现有 Agent 系统

### 中等优先级任务
- [ ] 创建测试脚本
- [ ] 在虚拟环境中调试
- [ ] 性能优化和错误处理

## 技术实现规划

### 1. API 配置设置

**位置**: `src/config.py`
**内容**: 添加 Tavily API 密钥配置

```python
# Tavily Search API 配置
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
```

### 2. 工具文件创建

**位置**: `src/tools/tavily_search_tool.py`
**功能**: 
- 基于 LangChain TavilySearchResults 工具
- 中文优化的搜索功能
- 与现有工具架构兼容

### 3. Agent 集成

**位置**: `src/agents/zhipu_agent.py`
**修改**: 将 Tavily 搜索工具添加到工具列表中

### 4. 测试脚本

**位置**: `test_tavily_search.py`
**功能**: 测试 Tavily 搜索功能

## Tavily API 参数说明

### 搜索参数
- `query`: 搜索查询字符串
- `search_depth`: 搜索深度 ("basic" 或 "advanced")
- `max_results`: 最大结果数量 (默认 5)
- `include_answer`: 是否包含答案摘要
- `include_raw_content`: 是否包含原始内容
- `include_domains`: 包含的域名列表
- `exclude_domains`: 排除的域名列表

### 响应格式
```json
{
  "results": [
    {
      "title": "页面标题",
      "url": "页面URL",
      "content": "页面内容摘要",
      "score": 0.95
    }
  ],
  "answer": "搜索查询的答案摘要"
}
```

## 实现步骤

### 步骤 1: 环境准备
1. 获取 Tavily API 密钥
2. 在 `.env` 文件中配置 API 密钥
3. 安装必要依赖: `langchain-community`

### 步骤 2: 核心工具开发
1. 创建 `tavily_search_tool.py`
2. 实现基础搜索功能
3. 添加中文优化和错误处理

### 步骤 3: 系统集成
1. 修改 `zhipu_agent.py` 添加 Tavily 工具
2. 更新工具导入和初始化
3. 测试 Agent 功能

### 步骤 4: 测试和优化
1. 创建测试脚本
2. 在虚拟环境中测试
3. 性能优化和错误处理改进

## 代码示例

### 基础搜索工具
```python
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_core.tools import tool

@tool
def tavily_search(query: str, max_results: int = 5) -> str:
    """使用 Tavily 进行网络搜索"""
    search = TavilySearchResults(
        max_results=max_results,
        search_depth="basic",
        include_answer=True,
        include_raw_content=False
    )
    return search.run(query)
```

### 高级搜索工具
```python
@tool
def tavily_advanced_search(
    query: str,
    max_results: int = 10,
    include_answer: bool = True,
    search_depth: str = "advanced"
) -> str:
    """Tavily 高级搜索功能"""
    search = TavilySearchResults(
        max_results=max_results,
        search_depth=search_depth,
        include_answer=include_answer,
        include_raw_content=True
    )
    return search.run(query)
```

## 错误处理策略

1. **API 密钥验证**: 启动时检查 API 密钥
2. **网络错误处理**: 搜索失败时的优雅降级
3. **结果格式化**: 统一的中文结果格式
4. **日志记录**: 详细的操作日志

## 性能优化考虑

1. **缓存机制**: 避免重复搜索
2. **并发限制**: 控制 API 调用频率
3. **结果过滤**: 过滤低质量结果
4. **内容摘要**: 智能截断长内容

## 测试计划

### 功能测试
- 基础搜索功能测试
- 高级搜索参数测试
- 错误处理测试
- 中文搜索优化测试

### 集成测试
- Agent 工具调用测试
- 多工具协同测试
- 虚拟环境兼容性测试

### 性能测试
- 搜索速度测试
- 并发处理测试
- 内存使用测试

## 部署注意事项

1. **环境变量**: 确保 `TAVILY_API_KEY` 正确设置
2. **依赖管理**: 更新 `requirements.txt`
3. **虚拟环境**: 在 `.venv` 中测试
4. **配置文件**: 更新 `src/config.py`

## 文档更新

完成后需要更新以下文档：
- `CLAUDE.md`: 添加 Tavily 搜索功能说明
- `README.md`: 更新使用说明
- 代码注释: 添加详细的中文注释

## 参考资料

1. [LangChain Tavily Search Documentation](https://python.langchain.com/docs/integrations/tools/tavily_search/)
2. [Tavily API Reference](https://docs.tavily.com/documentation/api-reference/endpoint/search)
3. [LangChain Tools Documentation](https://python.langchain.com/docs/modules/tools/)
4. [智谱 AI GLM-4 Documentation](https://open.bigmodel.cn/dev/api)