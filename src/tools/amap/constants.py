"""
高德地图常量定义模块

定义高德地图API相关的常量
"""

# API基础URL
BASE_URL = "https://restapi.amap.com"

# API端点
API_ENDPOINTS = {
    # 搜索服务
    'PLACE_TEXT_SEARCH': '/v3/place/text',      # 文本搜索
    'PLACE_AROUND_SEARCH': '/v3/place/around',  # 周边搜索
    'PLACE_DETAIL': '/v3/place/detail',         # POI详情
    'INPUT_TIPS': '/v3/assistant/inputtips',    # 输入提示
    
    # 路径规划服务
    'ROUTE_DRIVING': '/v3/direction/driving',   # 驾车路径规划
    'ROUTE_WALKING': '/v3/direction/walking',   # 步行路径规划
    'ROUTE_TRANSIT': '/v3/direction/transit/integrated',  # 公共交通路径规划
    
    # 地理编码服务
    'GEOCODE_GEO': '/v3/geocode/geo',           # 地理编码（地址转坐标）
    'GEOCODE_REGEO': '/v3/geocode/regeo',       # 逆地理编码（坐标转地址）
    
    # 行政区域查询
    'CONFIG_DISTRICT': '/v3/config/district',   # 行政区域查询
}

# 驾车路径规划策略
DRIVING_STRATEGIES = {
    'DEFAULT': 0,           # 最快捷模式
    'SHORT_DISTANCE': 1,    # 最短距离模式
    'AVOID_CONGESTION': 2,  # 避开拥堵模式
    'AVOID_HIGHWAY': 3,     # 避开高速模式
    'AVOID_TOLL': 4,        # 避开收费模式
    'HIGHWAY_FIRST': 5,     # 高速优先模式
}

# 公共交通路径规划策略
TRANSIT_STRATEGIES = {
    'FASTEST': 0,           # 最快捷路线
    'CHEAPEST': 1,          # 最经济路线
    'LEAST_TRANSFER': 2,    # 最少换乘
    'LEAST_WALKING': 3,     # 最少步行
    'MOST_COMFORTABLE': 4,  # 最舒适
    'NO_SUBWAY': 5,         # 不坐地铁
}

# 默认参数
DEFAULT_PARAMS = {
    'PAGE_SIZE': 20,        # 每页记录数
    'PAGE_NUM': 1,          # 页码
    'RADIUS': 1000,         # 搜索半径（米）
    'EXTENSIONS': 'base',   # 返回结果控制
}