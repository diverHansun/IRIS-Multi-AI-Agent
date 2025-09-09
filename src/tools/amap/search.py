"""
高德地图搜索服务模块

提供地点搜索相关的功能
"""

import logging
import sys
import os
from typing import Dict, Any, Optional
from langchain_core.tools import tool
from typing import Annotated

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 导入项目配置
try:
    from src.config import settings
except ImportError:
    try:
        from config import settings
    except ImportError:
        # 如果无法导入配置，创建一个简单的配置对象
        class Settings:
            amap_api_key = None
        settings = Settings()

from .client import AmapClient
from .constants import API_ENDPOINTS, DEFAULT_PARAMS
from .formatter import format_place_results
from .validator import validate_coordinates

logger = logging.getLogger(__name__)


class AmapSearchService:
    """高德地图搜索服务"""
    
    def __init__(self, client: AmapClient):
        """
        初始化搜索服务
        
        Args:
            client: 高德地图API客户端实例
        """
        self.client = client
    
    def search_places(self, keywords: str, city: str = "", types: str = "",
                     location: str = "", radius: int = DEFAULT_PARAMS['RADIUS'],
                     page: int = DEFAULT_PARAMS['PAGE_NUM']) -> Dict[str, Any]:
        """
        搜索地点POI
        
        Args:
            keywords: 搜索关键词
            city: 指定城市
            types: POI类型
            location: 中心点坐标（经纬度）
            radius: 搜索半径（米）
            page: 页码
            
        Returns:
            搜索结果
        """
        params = {
            'keywords': keywords,
            'extensions': 'all',
            'page': page,
            'offset': DEFAULT_PARAMS['PAGE_SIZE']
        }
        
        if city:
            params['city'] = city
        if types:
            params['types'] = types
        if location:
            # 验证坐标格式
            if not validate_coordinates(location):
                raise ValueError(f"坐标格式错误: {location}")
            params['location'] = location
            params['radius'] = radius
            endpoint = API_ENDPOINTS['PLACE_AROUND_SEARCH']
        else:
            endpoint = API_ENDPOINTS['PLACE_TEXT_SEARCH']
        
        return self.client._make_request(endpoint, params)
    
    def get_place_detail(self, poi_id: str) -> Dict[str, Any]:
        """
        获取POI详细信息
        
        Args:
            poi_id: POI ID
            
        Returns:
            POI详细信息
        """
        params = {
            'id': poi_id,
            'extensions': 'all'
        }
        
        return self.client._make_request(API_ENDPOINTS['PLACE_DETAIL'], params)


# 全局搜索服务实例
_amap_search_service: Optional[AmapSearchService] = None


def _get_search_service() -> AmapSearchService:
    """获取全局搜索服务实例"""
    global _amap_search_service
    if _amap_search_service is None:
        raise RuntimeError("高德地图搜索服务未初始化")
    return _amap_search_service


@tool
def amap_search_place(query: Annotated[str, "搜索关键词，如'星巴克'、'加油站'、'医院'"]) -> str:
    """
    使用高德地图搜索地点POI
    
    Args:
        query: 搜索关键词，可以是商店名称、地点类型等
        
    Returns:
        地点搜索结果，包含名称、地址、电话、坐标等信息
    """
    try:
        service = _get_search_service()
        logger.info(f"执行高德地图地点搜索: {query}")
        
        data = service.search_places(keywords=query)
        return format_place_results(data, query)
        
    except Exception as e:
        logger.error(f"高德地图地点搜索失败: {e}")
        return f"ERROR: 高德地图地点搜索时发生错误: {str(e)}"


@tool
def amap_search_nearby(
    search_params: Annotated[str, "搜索参数，格式为'关键词,坐标,半径'，如'餐厅,116.397477,39.908692,1000'"]
) -> str:
    """
    搜索指定位置附近的地点POI
    
    Args:
        search_params: 搜索参数字符串，格式为'关键词,坐标,半径'
                      坐标格式为'经度,纬度'，半径单位为米（可选，默认1000米）
        
    Returns:
        附近地点搜索结果
    """
    try:
        service = _get_search_service()
        
        # 解析参数
        parts = search_params.strip().split(',')
        if len(parts) < 3:
            return "ERROR: 参数格式错误，请使用格式：'关键词,经度,纬度,半径'，例如：'餐厅,116.397477,39.908692,1000'"
        
        query = parts[0].strip()
        try:
            longitude = parts[1].strip()
            latitude = parts[2].strip()
            location = f"{longitude},{latitude}"
        except (IndexError, ValueError):
            return "ERROR: 坐标格式错误，请使用'经度,纬度'格式"
        
        radius = DEFAULT_PARAMS['RADIUS']  # 默认半径
        if len(parts) >= 4:
            try:
                radius = int(parts[3].strip())
            except ValueError:
                radius = DEFAULT_PARAMS['RADIUS']
        
        logger.info(f"执行高德地图附近搜索: {query}, 位置: {location}, 半径: {radius}米")
        
        data = service.search_places(
            keywords=query,
            location=location,
            radius=radius
        )
        return format_place_results(data, f"{query}(附近{radius}米)")
        
    except Exception as e:
        logger.error(f"高德地图附近搜索失败: {e}")
        return f"ERROR: 高德地图附近搜索时发生错误: {str(e)}"


@tool
def amap_search_in_city(
    search_params: Annotated[str, "搜索参数，格式为'关键词,城市'，如'购物中心,北京'"]
) -> str:
    """
    在指定城市内搜索地点POI
    
    Args:
        search_params: 搜索参数字符串，格式为'关键词,城市'
        
    Returns:
        城市内地点搜索结果
    """
    try:
        service = _get_search_service()
        
        # 解析参数
        parts = search_params.strip().split(',')
        if len(parts) < 2:
            return "ERROR: 参数格式错误，请使用格式：'关键词,城市'，例如：'购物中心,北京'"
        
        query = parts[0].strip()
        city = parts[1].strip()
        
        logger.info(f"执行高德地图城市搜索: {query} in {city}")
        
        data = service.search_places(keywords=query, city=city)
        return format_place_results(data, f"{query}({city})")
        
    except Exception as e:
        logger.error(f"高德地图城市搜索失败: {e}")
        return f"ERROR: 高德地图城市搜索时发生错误: {str(e)}"


# 导出工具列表
AMAP_SEARCH_TOOLS = [
    amap_search_place,
    amap_search_nearby,
    amap_search_in_city
]


def init_search_service(api_key: str = None) -> AmapSearchService:
    """
    初始化搜索服务
    
    Args:
        api_key: 高德地图API密钥
        
    Returns:
        AmapSearchService实例
    """
    # 如果没有提供api_key，则从项目配置中获取
    api_key = api_key or getattr(settings, 'amap_api_key', None)
    
    global _amap_search_service
    client = AmapClient(api_key)
    _amap_search_service = AmapSearchService(client)
    return _amap_search_service