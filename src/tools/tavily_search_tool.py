"""
Tavily Search API 工具模块

基于 LangChain 的 Tavily 搜索工具集成，提供高质量的网络搜索功能。
专为中文环境优化，替代 DuckDuckGo 搜索功能。
"""

import json
import logging
from typing import Annotated, Dict, List, Any, Optional
from langchain_core.tools import tool
from langchain_community.tools.tavily_search import TavilySearchResults

from ..config import settings

logger = logging.getLogger(__name__)


class TavilySearchProvider:
    """Tavily 搜索服务提供者"""
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or settings.tavily_api_key
        self.is_available = bool(self.api_key)
        
        if not self.is_available:
            logger.warning("Tavily API key not found. Tavily search functionality will be disabled.")
    
    def create_search_tool(self, **kwargs) -> TavilySearchResults:
        """创建 Tavily 搜索工具实例"""
        if not self.is_available:
            raise ValueError("Tavily API key not configured")
        
        return TavilySearchResults(
            tavily_api_key=self.api_key,
            **kwargs
        )
    
    def format_search_results(self, results: List[Dict], query: str) -> str:
        """格式化搜索结果为中文显示"""
        if not results:
            return f"抱歉，没有找到关于 '{query}' 的搜索结果。"
        
        formatted_results = [f"🔍 Tavily搜索结果: {query}\n📊 共找到 {len(results)} 个结果\n"]
        
        for i, result in enumerate(results, 1):
            formatted_result = f"""
📌 第 {i} 个结果:
📰 标题: {result.get('title', '无标题')}
🔗 链接: {result.get('url', '无链接')}
📝 内容: {result.get('content', '无内容')[:300]}{'...' if len(result.get('content', '')) > 300 else ''}
⭐ 相关度: {result.get('score', 0):.2f}
"""
            formatted_results.append(formatted_result.strip())
        
        return "\n\n".join(formatted_results)


# 全局搜索提供者实例
tavily_provider = TavilySearchProvider()


@tool
def tavily_search(query: Annotated[str, "搜索查询关键词"]) -> str:
    """
    使用 Tavily 进行网络搜索
    
    Args:
        query: 搜索关键词
        
    Returns:
        搜索结果摘要
    """
    try:
        if not tavily_provider.is_available:
            return "❌ Tavily 搜索功能未配置。请在 .env 文件中设置 TAVILY_API_KEY"
        
        logger.info(f"执行 Tavily 搜索: {query}")
        
        search_tool = tavily_provider.create_search_tool(
            max_results=5,
            search_depth="basic",
            include_answer=True,
            include_raw_content=False
        )
        
        results = search_tool.run(query)
        
        # 如果结果是字符串，直接返回
        if isinstance(results, str):
            return f"🔍 Tavily搜索结果: {query}\n\n{results}"
        
        # 如果结果是列表，格式化显示
        if isinstance(results, list):
            return tavily_provider.format_search_results(results, query)
        
        return f"🔍 Tavily搜索结果: {query}\n\n{str(results)}"
        
    except Exception as e:
        logger.error(f"Tavily 搜索失败: {e}")
        return f"❌ Tavily 搜索时发生错误: {str(e)}"


@tool
def tavily_search_advanced(
    query: Annotated[str, "搜索查询关键词"],
    max_results: Annotated[int, "最大结果数量"] = 10,
    search_depth: Annotated[str, "搜索深度 (basic/advanced)"] = "advanced",
    include_answer: Annotated[bool, "是否包含答案摘要"] = True,
    include_raw_content: Annotated[bool, "是否包含原始内容"] = False
) -> str:
    """
    Tavily 高级搜索工具
    
    Args:
        query: 搜索关键词
        max_results: 最大结果数量 (1-20)
        search_depth: 搜索深度 ("basic" 或 "advanced")
        include_answer: 是否包含答案摘要
        include_raw_content: 是否包含原始内容
        
    Returns:
        详细搜索结果
    """
    try:
        if not tavily_provider.is_available:
            return "❌ Tavily 搜索功能未配置。请在 .env 文件中设置 TAVILY_API_KEY"
        
        logger.info(f"执行 Tavily 高级搜索: {query}, 深度: {search_depth}, 结果数量: {max_results}")
        
        # 限制参数范围
        max_results = max(1, min(20, max_results))
        search_depth = search_depth if search_depth in ["basic", "advanced"] else "basic"
        
        search_tool = tavily_provider.create_search_tool(
            max_results=max_results,
            search_depth=search_depth,
            include_answer=include_answer,
            include_raw_content=include_raw_content
        )
        
        results = search_tool.run(query)
        
        # 如果结果是字符串，直接返回
        if isinstance(results, str):
            return f"🔍 Tavily高级搜索结果: {query}\n搜索深度: {search_depth}\n\n{results}"
        
        # 如果结果是列表，格式化显示
        if isinstance(results, list):
            formatted_results = tavily_provider.format_search_results(results, query)
            return f"搜索深度: {search_depth}\n最大结果数: {max_results}\n\n{formatted_results}"
        
        return f"🔍 Tavily高级搜索结果: {query}\n搜索深度: {search_depth}\n\n{str(results)}"
        
    except Exception as e:
        logger.error(f"Tavily 高级搜索失败: {e}")
        return f"❌ Tavily 高级搜索时发生错误: {str(e)}"


@tool
def tavily_search_with_domains(
    query: Annotated[str, "搜索查询关键词"],
    include_domains: Annotated[Optional[List[str]], "包含的域名列表"] = None,
    exclude_domains: Annotated[Optional[List[str]], "排除的域名列表"] = None,
    max_results: Annotated[int, "最大结果数量"] = 5
) -> str:
    """
    Tavily 域名过滤搜索工具
    
    Args:
        query: 搜索关键词
        include_domains: 只搜索这些域名 (例如: ["wikipedia.org", "baidu.com"])
        exclude_domains: 排除这些域名 (例如: ["ads.com", "spam.com"])
        max_results: 最大结果数量
        
    Returns:
        过滤后的搜索结果
    """
    try:
        if not tavily_provider.is_available:
            return "❌ Tavily 搜索功能未配置。请在 .env 文件中设置 TAVILY_API_KEY"
        
        logger.info(f"执行 Tavily 域名过滤搜索: {query}")
        
        search_kwargs = {
            "max_results": max(1, min(20, max_results)),
            "search_depth": "basic"
        }
        
        if include_domains:
            search_kwargs["include_domains"] = include_domains
        
        if exclude_domains:
            search_kwargs["exclude_domains"] = exclude_domains
        
        search_tool = tavily_provider.create_search_tool(**search_kwargs)
        results = search_tool.run(query)
        
        # 添加域名过滤信息
        filter_info = []
        if include_domains:
            filter_info.append(f"包含域名: {', '.join(include_domains)}")
        if exclude_domains:
            filter_info.append(f"排除域名: {', '.join(exclude_domains)}")
        
        filter_text = "\n".join(filter_info) if filter_info else "无域名过滤"
        
        if isinstance(results, str):
            return f"🔍 Tavily域名过滤搜索: {query}\n{filter_text}\n\n{results}"
        
        if isinstance(results, list):
            formatted_results = tavily_provider.format_search_results(results, query)
            return f"{filter_text}\n\n{formatted_results}"
        
        return f"🔍 Tavily域名过滤搜索: {query}\n{filter_text}\n\n{str(results)}"
        
    except Exception as e:
        logger.error(f"Tavily 域名过滤搜索失败: {e}")
        return f"❌ Tavily 域名过滤搜索时发生错误: {str(e)}"


@tool
def tavily_search_news(query: Annotated[str, "新闻搜索查询关键词"]) -> str:
    """
    Tavily 新闻搜索工具
    
    Args:
        query: 新闻搜索关键词
        
    Returns:
        新闻搜索结果
    """
    try:
        if not tavily_provider.is_available:
            return "❌ Tavily 搜索功能未配置。请在 .env 文件中设置 TAVILY_API_KEY"
        
        logger.info(f"执行 Tavily 新闻搜索: {query}")
        
        # 使用高级搜索模式获取更准确的新闻结果
        search_tool = tavily_provider.create_search_tool(
            max_results=8,
            search_depth="advanced",
            include_answer=True,
            include_raw_content=False,
            include_domains=["news.baidu.com", "news.sina.com.cn", "news.163.com", 
                           "news.qq.com", "news.sohu.com", "xinhuanet.com", 
                           "people.com.cn", "chinanews.com", "cctv.com"]
        )
        
        results = search_tool.run(query)
        
        if isinstance(results, str):
            return f"📰 Tavily新闻搜索: {query}\n\n{results}"
        
        if isinstance(results, list):
            formatted_results = tavily_provider.format_search_results(results, query)
            return f"📰 {formatted_results}"
        
        return f"📰 Tavily新闻搜索: {query}\n\n{str(results)}"
        
    except Exception as e:
        logger.error(f"Tavily 新闻搜索失败: {e}")
        return f"❌ Tavily 新闻搜索时发生错误: {str(e)}"


# 导出工具列表
TAVILY_TOOLS = [
    tavily_search,
    tavily_search_advanced,
    tavily_search_with_domains,
    tavily_search_news
]


def get_available_tavily_tools() -> List:
    """获取可用的 Tavily 工具列表"""
    if tavily_provider.is_available:
        return TAVILY_TOOLS
    else:
        logger.warning("Tavily API key not configured, returning empty tool list")
        return []


def test_tavily_tools():
    """测试 Tavily 搜索工具"""
    print("测试 Tavily 搜索工具...")
    
    if not tavily_provider.is_available:
        print("Tavily API key 未配置，无法进行测试")
        return
    
    # 测试基础搜索
    print("\n1. 测试基础搜索:")
    try:
        result = tavily_search.func("Python编程教程")
        print(f"基础搜索成功: {result[:200]}...")
    except Exception as e:
        print(f"基础搜索失败: {e}")
    
    # 测试高级搜索
    print("\n2. 测试高级搜索:")
    try:
        result = tavily_search_advanced.func("人工智能最新发展", max_results=3, search_depth="advanced")
        print(f"高级搜索成功: {result[:200]}...")
    except Exception as e:
        print(f"高级搜索失败: {e}")
    
    # 测试新闻搜索
    print("\n3. 测试新闻搜索:")
    try:
        result = tavily_search_news.func("今日科技新闻")
        print(f"新闻搜索成功: {result[:200]}...")
    except Exception as e:
        print(f"新闻搜索失败: {e}")
    
    print("\nTavily 搜索工具测试完成!")


if __name__ == "__main__":
    test_tavily_tools()