"""
高德地图异常处理模块

定义高德地图API相关的自定义异常类
"""

class AmapApiError(Exception):
    """高德地图API基础异常类"""
    pass


class AmapApiRateLimitError(AmapApiError):
    """高德地图API频率限制异常"""
    pass


class AmapApiParamError(AmapApiError):
    """高德地图API参数错误异常"""
    pass