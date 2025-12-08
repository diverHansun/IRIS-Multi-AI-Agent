"""
高德地图工具测试模块
"""

import logging
from typing import List
from langchain_core.tools import BaseTool

from .adapter import get_amap_service_provider, get_available_amap_tools

logger = logging.getLogger(__name__)


def test_amap_tools(api_key: str = None) -> List[BaseTool]:
    """
    测试高德地图工具

    Args:
        api_key: 高德地图API密钥

    Returns:
        可用的工具列表
    """
    logger.info("Testing Amap tools...")

    # 初始化服务提供者
    provider = get_amap_service_provider(api_key)

    if not provider.is_available:
        logger.warning("Amap API key not configured, skipping test")
        return []

    # 获取可用工具
    tools = get_available_amap_tools()
    logger.info("Loaded %d Amap tools", len(tools))

    # 测试地点搜索
    logger.info("Test 1: Amap place search")
    try:
        search_tool = next((tool for tool in tools if tool.name == "amap_search_place"), None)
        if search_tool:
            result = search_tool.func("星巴克")
            logger.info("Place search success: %s...", result[:200])
        else:
            logger.warning("Place search tool not found")
    except Exception as e:
        logger.error("Place search failed: %s", e)

    # 测试附近搜索
    logger.info("Test 2: Amap nearby search")
    try:
        nearby_tool = next((tool for tool in tools if tool.name == "amap_search_nearby"), None)
        if nearby_tool:
            result = nearby_tool.func("餐厅,116.397477,39.908692,500")
            logger.info("Nearby search success: %s...", result[:200])
        else:
            logger.warning("Nearby search tool not found")
    except Exception as e:
        logger.error("Nearby search failed: %s", e)

    # 测试路线规划
    logger.info("Test 3: Amap driving route planning")
    try:
        driving_tool = next((tool for tool in tools if tool.name == "amap_route_driving"), None)
        if driving_tool:
            result = driving_tool.func("116.481028,39.989643,116.434446,39.90816,10")
            logger.info("Route planning success: %s...", result[:200])
        else:
            logger.warning("Driving route planning tool not found")
    except Exception as e:
        logger.error("Route planning failed: %s", e)

    logger.info("Amap tools test completed")
    return tools


if __name__ == "__main__":
    # 这里可以添加测试代码
    pass