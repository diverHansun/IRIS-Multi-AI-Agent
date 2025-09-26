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
    print("测试高德地图工具...")
    
    # 初始化服务提供者
    provider = get_amap_service_provider(api_key)
    
    if not provider.is_available:
        print("高德地图 API key 未配置，无法进行测试")
        return []
    
    # 获取可用工具
    tools = get_available_amap_tools()
    print(f"已加载 {len(tools)} 个高德地图工具")
    
    # 测试地点搜索
    print("\n1. 测试地点搜索:")
    try:
        search_tool = next((tool for tool in tools if tool.name == "amap_search_place"), None)
        if search_tool:
            result = search_tool.func("星巴克")
            print(f"地点搜索成功: {result[:200]}...")
        else:
            print("未找到地点搜索工具")
    except Exception as e:
        print(f"地点搜索失败: {e}")
    
    # 测试附近搜索
    print("\n2. 测试附近搜索:")
    try:
        nearby_tool = next((tool for tool in tools if tool.name == "amap_search_nearby"), None)
        if nearby_tool:
            result = nearby_tool.func("餐厅,116.397477,39.908692,500")
            print(f"附近搜索成功: {result[:200]}...")
        else:
            print("未找到附近搜索工具")
    except Exception as e:
        print(f"附近搜索失败: {e}")
    
    # 测试路线规划
    print("\n3. 测试驾车路线规划:")
    try:
        driving_tool = next((tool for tool in tools if tool.name == "amap_route_driving"), None)
        if driving_tool:
            result = driving_tool.func("116.481028,39.989643,116.434446,39.90816,10")
            print(f"路线规划成功: {result[:200]}...")
        else:
            print("未找到驾车路线规划工具")
    except Exception as e:
        print(f"路线规划失败: {e}")
    
    print("\n高德地图工具测试完成!")
    return tools


if __name__ == "__main__":
    # 这里可以添加测试代码
    pass