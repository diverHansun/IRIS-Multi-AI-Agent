"""
高德地图服务提供者模块

整合各个服务模块，提供统一的接口
"""

import logging
import sys
import os
from typing import List, Dict, Any
from langchain_core.tools import BaseTool

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
from .search import AmapSearchService, init_search_service, AMAP_SEARCH_TOOLS
from .route import AmapRouteService, init_route_service, AMAP_ROUTE_TOOLS
from .geocode import AmapGeocodeService
from .formatter import format_place_results, format_route_results, format_transit_results
from .validator import validate_coordinates, is_chinese_coordinate, format_coordinates
from .constants import BASE_URL
from .exceptions import AmapApiError, AmapApiRateLimitError

logger = logging.getLogger(__name__)


class AmapServiceProvider:
    """高德地图服务提供者"""
    
    def __init__(self, api_key: str = None):
        """
        初始化高德地图服务提供者
        
        Args:
            api_key: 高德地图API密钥
        """
        # 如果没有提供api_key，则从项目配置中获取
        self.api_key = api_key or getattr(settings, 'amap_api_key', None)
        self.is_available = bool(self.api_key)
        self.client = None
        self.search_service = None
        self.route_service = None
        self.geocode_service = None
        
        if self.is_available:
            self._init_services()
        else:
            logger.warning("Amap API key not found. Amap search functionality will be disabled.")
    
    def _init_services(self):
        """初始化各个服务"""
        try:
            # 初始化搜索服务（这会同时初始化全局变量）
            from .search import init_search_service
            from .route import init_route_service
            
            # 初始化搜索服务，这会初始化全局的_amap_search_service变量
            init_search_service(self.api_key)
            
            # 初始化路径规划服务，这会初始化全局的_amap_route_service变量
            init_route_service(self.api_key)
            
            # 获取已初始化的服务实例
            from .search import _amap_search_service
            from .route import _amap_route_service
            
            self.search_service = _amap_search_service
            self.route_service = _amap_route_service
            
            # 初始化客户端
            self.client = self.search_service.client if self.search_service else None
            
            # 初始化地理编码服务
            if self.client:
                from .geocode import AmapGeocodeService
                self.geocode_service = AmapGeocodeService(self.client)
            
            logger.info("高德地图服务初始化成功")
        except Exception as e:
            logger.error(f"高德地图服务初始化失败: {e}")
            self.is_available = False
    
    def get_available_tools(self) -> List[BaseTool]:
        """
        获取可用的高德地图工具列表
        
        Returns:
            BaseTool列表
        """
        if not self.is_available:
            logger.warning("Amap API key not configured, returning empty tool list")
            return []
        
        # 合并所有工具
        all_tools = []
        all_tools.extend(AMAP_SEARCH_TOOLS)
        all_tools.extend(AMAP_ROUTE_TOOLS)
        
        return all_tools
    
    # 代理搜索服务方法
    def search_places(self, keywords: str, city: str = "", types: str = "",
                     location: str = "", radius: int = 1000, page: int = 1) -> Dict[str, Any]:
        """代理搜索地点方法"""
        if not self.search_service:
            raise AmapApiError("搜索服务未初始化")
        return self.search_service.search_places(keywords, city, types, location, radius, page)
    
    def get_place_detail(self, poi_id: str) -> Dict[str, Any]:
        """代理获取POI详情方法"""
        if not self.search_service:
            raise AmapApiError("搜索服务未初始化")
        return self.search_service.get_place_detail(poi_id)
    
    # 代理路径规划服务方法
    def plan_route(self, origin: str, destination: str, strategy: int = 10,
                   waypoints: str = "", extensions: str = "base") -> Dict[str, Any]:
        """代理驾车路线规划方法"""
        if not self.route_service:
            raise AmapApiError("路径规划服务未初始化")
        return self.route_service.plan_route(origin, destination, strategy, waypoints, extensions)
    
    def plan_walking_route(self, origin: str, destination: str) -> Dict[str, Any]:
        """代理步行路线规划方法"""
        if not self.route_service:
            raise AmapApiError("路径规划服务未初始化")
        return self.route_service.plan_walking_route(origin, destination)
    
    def plan_transit_route(self, origin: str, destination: str, city: str = "",
                          strategy: int = 0, nightflag: int = 0) -> Dict[str, Any]:
        """代理公共交通路线规划方法"""
        if not self.route_service:
            raise AmapApiError("路径规划服务未初始化")
        return self.route_service.plan_transit_route(origin, destination, city, strategy, nightflag)
    
    # 代理地理编码服务方法
    def geocode_address(self, address: str, city: str = "") -> Dict[str, Any]:
        """代理地址转坐标方法"""
        if not self.geocode_service:
            raise AmapApiError("地理编码服务未初始化")
        return self.geocode_service.geocode_address(address, city)
    
    def regeocode_coordinates(self, location: str, radius: int = 1000,
                            extensions: str = "base") -> Dict[str, Any]:
        """代理坐标转地址方法"""
        if not self.geocode_service:
            raise AmapApiError("地理编码服务未初始化")
        return self.geocode_service.regeocode_coordinates(location, radius, extensions)
    
    # 代理格式化方法
    def format_place_results(self, data: Dict[str, Any], query: str) -> str:
        """代理地点搜索结果格式化方法"""
        return format_place_results(data, query)
    
    def format_route_results(self, data: Dict[str, Any], origin: str, destination: str,
                           route_type: str = "驾车") -> str:
        """代理路线规划结果格式化方法"""
        return format_route_results(data, origin, destination, route_type)
    
    def format_transit_results(self, data: Dict[str, Any], origin: str, destination: str) -> str:
        """代理公共交通路线规划结果格式化方法"""
        return format_transit_results(data, origin, destination)
    
    # 代理验证方法
    def validate_coordinates(self, location_str: str) -> bool:
        """代理坐标验证方法"""
        return validate_coordinates(location_str)
    
    def is_chinese_coordinate(self, location_str: str) -> bool:
        """代理中国坐标范围检查方法"""
        return is_chinese_coordinate(location_str)
    
    def format_coordinates(self, location: str) -> str:
        """代理坐标格式化方法"""
        return format_coordinates(location)


# 全局服务提供者实例
_amap_service_provider: AmapServiceProvider = None


def get_amap_service_provider(api_key: str = None) -> AmapServiceProvider:
    """
    获取全局高德地图服务提供者实例
    
    Args:
        api_key: 高德地图API密钥
        
    Returns:
        AmapServiceProvider实例
    """
    global _amap_service_provider
    if _amap_service_provider is None:
        _amap_service_provider = AmapServiceProvider(api_key)
    return _amap_service_provider


def get_available_amap_tools() -> List[BaseTool]:
    """
    获取可用的高德地图工具列表
    
    Returns:
        BaseTool列表
    """
    provider = get_amap_service_provider()
    return provider.get_available_tools()


def init_amap_services(api_key: str = None) -> AmapServiceProvider:
    """
    初始化高德地图服务
    
    Args:
        api_key: 高德地图API密钥
        
    Returns:
        AmapServiceProvider实例
    """
    # 如果没有提供api_key，则从项目配置中获取
    api_key = api_key or getattr(settings, 'amap_api_key', None)
    
    global _amap_service_provider
    _amap_service_provider = AmapServiceProvider(api_key)
    return _amap_service_provider