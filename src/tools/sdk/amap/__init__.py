"""
高德地图工具包初始化文件

基于高德地图Web服务API提供地点搜索和路径规划功能。
专为中文环境优化，集成到LangChain工具系统中。
"""

# 导入主要的类和函数
from .provider import (
    AmapServiceProvider,
    get_amap_service_provider,
    get_available_amap_tools,
    init_amap_services
)

from .search import (
    AmapSearchService,
    amap_search_place,
    amap_search_nearby,
    amap_search_in_city,
    AMAP_SEARCH_TOOLS
)

from .route import (
    AmapRouteService,
    amap_route_driving,
    amap_route_walking,
    amap_route_transit,
    amap_route_subway,
    amap_route_bus,
    AMAP_ROUTE_TOOLS
)

from .geocode import AmapGeocodeService
from .client import AmapClient
from .formatter import (
    format_place_results,
    format_route_results,
    format_transit_results
)
from .validator import (
    validate_coordinates,
    is_chinese_coordinate,
    format_coordinates
)
from .exceptions import (
    AmapApiError,
    AmapApiRateLimitError,
    AmapApiParamError
)

# 导出工具列表
AMAP_TOOLS = []

def _init_tools():
    """初始化工具列表"""
    global AMAP_TOOLS
    AMAP_TOOLS.extend(AMAP_SEARCH_TOOLS)
    AMAP_TOOLS.extend(AMAP_ROUTE_TOOLS)

# 初始化工具列表
_init_tools()

__all__ = [
    # 主要类
    "AmapServiceProvider",
    "AmapSearchService",
    "AmapRouteService",
    "AmapGeocodeService",
    "AmapClient",
    
    # 工具函数
    "get_amap_service_provider",
    "get_available_amap_tools",
    "init_amap_services",
    
    # 搜索工具
    "amap_search_place",
    "amap_search_nearby",
    "amap_search_in_city",
    "AMAP_SEARCH_TOOLS",
    
    # 路线规划工具
    "amap_route_driving",
    "amap_route_walking",
    "amap_route_transit",
    "amap_route_subway",
    "amap_route_bus",
    "AMAP_ROUTE_TOOLS",
    
    # 格式化函数
    "format_place_results",
    "format_route_results",
    "format_transit_results",
    
    # 验证函数
    "validate_coordinates",
    "is_chinese_coordinate",
    "format_coordinates",
    
    # 异常类
    "AmapApiError",
    "AmapApiRateLimitError",
    "AmapApiParamError",
    
    # 工具列表
    "AMAP_TOOLS"
]