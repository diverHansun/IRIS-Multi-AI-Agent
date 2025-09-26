"""
搜索和计算工具模块 - 修复版

提供网络搜索和计算器功能，移除MCP依赖问题。
"""

import json
import logging
import requests
from typing import Annotated, Dict, List, Any, Optional
from urllib.parse import quote_plus
from bs4 import BeautifulSoup

from langchain_core.tools import tool

logger = logging.getLogger(__name__)


class WebSearchProvider:
    """网络搜索服务提供者 - 无MCP依赖版本"""

    def __init__(self, timeout: int = 30, max_results: int = 10):
        self.timeout = timeout
        self.max_results = max_results
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })

    def search_duckduckgo(self, query: str, num_results: int = 5) -> List[Dict[str, Any]]:
        """
        使用DuckDuckGo进行搜索

        Args:
            query: 搜索查询
            num_results: 返回结果数量

        Returns:
            搜索结果列表
        """
        try:
            # DuckDuckGo搜索URL
            search_url = "https://duckduckgo.com/html/"
            params = {
                'q': query,
                'b': '',
                'kl': 'wt-wt',
                'df': '',
                'safe': 'moderate'
            }

            response = self.session.get(search_url, params=params, timeout=self.timeout)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser')
            results = []

            # 解析搜索结果
            result_containers = soup.find_all('div', {'class': 'result'})

            for i, container in enumerate(result_containers[:num_results]):
                try:
                    # 获取标题和链接
                    title_link = container.find('a', {'class': 'result__a'})
                    if not title_link:
                        continue

                    title = title_link.get_text(strip=True)
                    url = title_link.get('href', '')
                    
                    # 修复DuckDuckGo的相对URL
                    if url.startswith('//'):
                        url = 'https:' + url
                    elif url.startswith('/'):
                        url = 'https://duckduckgo.com' + url

                    # 获取描述
                    snippet = container.find('a', {'class': 'result__snippet'})
                    description = snippet.get_text(strip=True) if snippet else ""

                    # 获取域名
                    url_tag = container.find('span', {'class': 'result__url'})
                    domain = url_tag.get_text(strip=True) if url_tag else ""

                    results.append({
                        'title': title,
                        'url': url,
                        'description': description,
                        'domain': domain,
                        'rank': i + 1,
                        'source': 'DuckDuckGo'
                    })

                except Exception as e:
                    logger.warning(f"解析搜索结果时出错: {e}")
                    continue

            return results

        except Exception as e:
            logger.error(f"DuckDuckGo搜索失败: {e}")
            return []

    def search_bing(self, query: str, num_results: int = 5) -> List[Dict[str, Any]]:
        """
        使用Bing进行搜索（备用方案）

        Args:
            query: 搜索查询
            num_results: 返回结果数量

        Returns:
            搜索结果列表
        """
        try:
            # Bing搜索URL
            search_url = f"https://www.bing.com/search"
            params = {
                'q': query,
                'count': num_results,
                'offset': 0,
                'mkt': 'zh-CN'
            }

            response = self.session.get(search_url, params=params, timeout=self.timeout)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser')
            results = []

            # 解析Bing搜索结果
            result_containers = soup.find_all('li', {'class': 'b_algo'})

            for i, container in enumerate(result_containers[:num_results]):
                try:
                    # 获取标题和链接
                    title_link = container.find('h2').find('a') if container.find('h2') else None
                    if not title_link:
                        continue

                    title = title_link.get_text(strip=True)
                    url = title_link.get('href', '')

                    # 获取描述
                    description_tag = container.find('div', {'class': 'b_caption'})
                    description = description_tag.get_text(strip=True) if description_tag else ""

                    results.append({
                        'title': title,
                        'url': url,
                        'description': description,
                        'domain': url.split('/')[2] if '://' in url else '',
                        'rank': i + 1,
                        'source': 'Bing'
                    })

                except Exception as e:
                    logger.warning(f"解析Bing搜索结果时出错: {e}")
                    continue

            return results

        except Exception as e:
            logger.error(f"Bing搜索失败: {e}")
            return []

    def get_page_content(self, url: str, max_length: int = 3000) -> str:
        """
        获取网页内容

        Args:
            url: 网页URL
            max_length: 最大内容长度

        Returns:
            网页文本内容
        """
        try:
            # 增加更多请求头以避免403错误
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            }
            
            response = self.session.get(url, headers=headers, timeout=self.timeout)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser')

            # 移除不需要的标签
            for tag in soup(['script', 'style', 'nav', 'footer', 'header', 'aside']):
                tag.decompose()

            # 尝试找到主要内容区域
            main_content = (
                    soup.find('main') or
                    soup.find('article') or
                    soup.find('div', {'class': ['content', 'main', 'article']}) or
                    soup.find('body')
            )

            if main_content:
                text = main_content.get_text(separator=' ', strip=True)
            else:
                text = soup.get_text(separator=' ', strip=True)

            # 清理文本
            lines = text.split('\n')
            cleaned_lines = [line.strip() for line in lines if line.strip()]
            text = '\n'.join(cleaned_lines)

            # 截断内容
            if len(text) > max_length:
                text = text[:max_length] + "..."

            return text

        except Exception as e:
            logger.error(f"获取网页内容失败 {url}: {e}")
            return f"无法获取网页内容: {str(e)}"


# 全局搜索提供者实例
search_provider = WebSearchProvider()


@tool
def web_search_tool(query: Annotated[str, "搜索查询关键词"]) -> str:
    """
    网络搜索工具，用于搜索实时信息

    Args:
        query: 搜索关键词

    Returns:
        搜索结果摘要
    """
    try:
        logger.info(f"执行搜索: {query}")

        # 首先尝试DuckDuckGo搜索
        results = search_provider.search_duckduckgo(query, num_results=5)

        # 如果DuckDuckGo失败，尝试Bing
        if not results:
            logger.info("DuckDuckGo搜索无结果，尝试Bing搜索")
            results = search_provider.search_bing(query, num_results=5)

        if not results:
            return f"抱歉，没有找到关于 '{query}' 的搜索结果。"

        # 格式化搜索结果
        formatted_results = [f"🔍 搜索查询: {query}\n📊 找到 {len(results)} 个结果\n"]

        for result in results:
            formatted_result = f"""
📌 排名 {result['rank']}: {result['title']}
🔗 链接: {result['url']}
🏷️ 来源: {result['domain']} ({result['source']})
📝 描述: {result['description'][:200]}{'...' if len(result['description']) > 200 else ''}
"""
            formatted_results.append(formatted_result.strip())

        return "\n\n".join(formatted_results)

    except Exception as e:
        logger.error(f"搜索工具执行失败: {e}")
        return f"搜索时发生错误: {str(e)}"


@tool
def web_search_detailed(query: Annotated[str, "搜索查询关键词"]) -> str:
    """
    详细网络搜索工具，返回更多搜索结果

    Args:
        query: 搜索关键词

    Returns:
        详细搜索结果
    """
    try:
        logger.info(f"执行详细搜索: {query}")

        # 设置详细搜索参数
        num_results = 8  # 详细搜索返回更多结果
        include_content = True  # 详细搜索包含网页内容

        # 执行搜索
        results = search_provider.search_duckduckgo(query, num_results=num_results)

        if not results:
            results = search_provider.search_bing(query, num_results=num_results)

        if not results:
            return f"抱歉，没有找到关于 '{query}' 的搜索结果。"

        # 格式化结果
        formatted_results = [f"详细搜索: {query}\n共找到 {len(results)} 个结果\n"]

        for result in results:
            formatted_result = f"""
{'=' * 50}
第 {result['rank']} 个结果
标题: {result['title']}
链接: {result['url']}
域名: {result['domain']}
描述: {result['description']}
"""

            # 获取网页内容
            if include_content and result['url']:
                content = search_provider.get_page_content(result['url'], max_length=1000)
                formatted_result += f"\n网页内容预览:\n{content[:500]}{'...' if len(content) > 500 else ''}\n"

            formatted_results.append(formatted_result.strip())

        return "\n".join(formatted_results)

    except Exception as e:
        logger.error(f"详细搜索工具执行失败: {e}")
        return f"详细搜索时发生错误: {str(e)}"


@tool
def get_webpage_content(url: Annotated[str, "网页URL地址"]) -> str:
    """
    获取指定网页的文本内容

    Args:
        url: 网页URL地址

    Returns:
        网页文本内容
    """
    try:
        logger.info(f"获取网页内容: {url}")

        content = search_provider.get_page_content(url, max_length=4000)

        return f"📄 网页内容 ({url}):\n\n{content}"

    except Exception as e:
        logger.error(f"获取网页内容失败: {e}")
        return f"获取网页内容时发生错误: {str(e)}"


# 计算器工具已移动到 math_tools.py，避免重复


def get_available_search_tools():
    """
    获取可用的搜索工具列表
    
    Returns:
        搜索工具列表
    """
    return [web_search_tool, web_search_detailed, get_webpage_content]


def test_search_tools():
    """测试搜索工具"""
    print("测试搜索工具...")

    # 测试基础搜索
    print("\n1. 测试基础搜索:")
    try:
        result = web_search_tool.func("Python教程")
        print(f"基础搜索成功: {result[:200]}...")
    except Exception as e:
        print(f"基础搜索失败: {e}")

    # 计算器工具已移动到 math_tools.py

    print("\n搜索工具测试完成!")


if __name__ == "__main__":
    test_search_tools()