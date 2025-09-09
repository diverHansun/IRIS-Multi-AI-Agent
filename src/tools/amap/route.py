"""
高德地图路径规划服务模块

提供路径规划相关的功能
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
from .constants import API_ENDPOINTS, DRIVING_STRATEGIES, TRANSIT_STRATEGIES
from .formatter import format_route_results, format_transit_results
from .validator import validate_coordinates, is_chinese_coordinate
from .geocode import AmapGeocodeService

logger = logging.getLogger(__name__)


class AmapRouteService:
    """高德地图路径规划服务"""
    
    def __init__(self, client: AmapClient):
        """
        初始化路径规划服务
        
        Args:
            client: 高德地图API客户端实例
        """
        self.client = client
        self.geocode_service = AmapGeocodeService(client)
    
    def _convert_to_coordinates(self, location: str, city: str = "") -> str:
        """
        将地址转换为坐标，如果已经是坐标则直接返回
        
        Args:
            location: 地址或坐标
            city: 城市（用于地址解析）
            
        Returns:
            坐标字符串 "经度,纬度"
        """
        # 如果已经是坐标格式，验证并返回
        if validate_coordinates(location):
            # 确保坐标精度不超过6位小数
            parts = location.split(',')
            lon = round(float(parts[0]), 6)
            lat = round(float(parts[1]), 6)
            coord = f"{lon},{lat}"
            
            # 验证坐标是否在中国范围内
            if not is_chinese_coordinate(coord):
                raise ValueError(f"坐标不在中国范围内: {coord}")
                
            return coord
        
        # 地址转坐标
        try:
            data = self.geocode_service.geocode_address(location, city)
            geocodes = data.get('geocodes', [])
            if not geocodes:
                raise ValueError(f"无法找到地址 '{location}' 的坐标")
            
            location_coord = geocodes[0].get('location', '')
            if not location_coord:
                raise ValueError(f"地址 '{location}' 未返回有效坐标")
            
            # 验证坐标是否在中国范围内
            if not is_chinese_coordinate(location_coord):
                raise ValueError(f"地址解析的坐标不在中国范围内: {location_coord}")
                
            return location_coord
        except Exception as e:
            logger.error(f"地址转坐标失败: {location} -> {e}")
            raise ValueError(f"地址转坐标失败: {str(e)}")
    
    def plan_route(self, origin: str, destination: str, strategy: int = 10,
                   waypoints: str = "", extensions: str = "base") -> Dict[str, Any]:
        """
        规划驾车路线
        
        Args:
            origin: 起点（地址或坐标）
            destination: 终点（地址或坐标）
            strategy: 路线策略
            waypoints: 途经点
            extensions: 返回结果控制
            
        Returns:
            路线规划结果
        """
        params = {
            'origin': origin,
            'destination': destination,
            'strategy': strategy,
            'extensions': extensions
        }
        
        if waypoints:
            params['waypoints'] = waypoints
        
        return self.client._make_request(API_ENDPOINTS['ROUTE_DRIVING'], params)
    
    def plan_walking_route(self, origin: str, destination: str) -> Dict[str, Any]:
        """
        规划步行路线
        
        Args:
            origin: 起点（地址或坐标）
            destination: 终点（地址或坐标）
            
        Returns:
            步行路线规划结果
        """
        params = {
            'origin': origin,
            'destination': destination
        }
        
        return self.client._make_request(API_ENDPOINTS['ROUTE_WALKING'], params)
    
    def plan_transit_route(self, origin: str, destination: str, city: str = "",
                          strategy: int = 0, nightflag: int = 0) -> Dict[str, Any]:
        """
        规划公共交通路线
        
        Args:
            origin: 起点（地址或坐标）
            destination: 终点（地址或坐标）
            city: 城市
            strategy: 策略代码
            nightflag: 夜间出行标识
            
        Returns:
            公共交通路线规划结果
        """
        params = {
            'origin': origin,
            'destination': destination,
            'strategy': strategy,
            'nightflag': nightflag,
            'extensions': 'all'
        }
        
        if city:
            params['city'] = city
        
        # 确保策略参数在有效范围内 (0-5)
        if strategy not in [0, 1, 2, 3, 5]:
            params['strategy'] = 0
        
        return self.client._make_request(API_ENDPOINTS['ROUTE_TRANSIT'], params)


# 全局路径规划服务实例
_amap_route_service: Optional[AmapRouteService] = None


def _get_route_service() -> AmapRouteService:
    """获取全局路径规划服务实例"""
    global _amap_route_service
    if _amap_route_service is None:
        raise RuntimeError("高德地图路径规划服务未初始化")
    return _amap_route_service


@tool
def amap_route_driving(
    route_params: Annotated[str, "路线参数，格式为'起点,终点,策略'，如'南京,成都,10'或'116.397477,39.908692,116.434446,39.90816,10'"]
) -> str:
    """
    规划驾车路线
    
    Args:
        route_params: 路线参数字符串，格式为'起点,终点,策略'
                     起点和终点可以是地址或坐标(经度,纬度)
                     策略为可选数字：10-躲避拥堵最短路径，12-躲避收费，13-不走高速等
        
    Returns:
        详细的驾车路线规划结果
    """
    try:
        service = _get_route_service()
        
        # 解析参数 - 支持坐标和地址两种格式
        parts = route_params.strip().split(',')
        
        # 判断是坐标格式还是地址格式
        if len(parts) == 5:  # 坐标格式: 经度1,纬度1,经度2,纬度2,策略
            try:
                origin = f"{parts[0].strip()},{parts[1].strip()}"
                destination = f"{parts[2].strip()},{parts[3].strip()}"
                strategy = int(parts[4].strip()) if parts[4].strip().isdigit() else 10
            except (ValueError, IndexError):
                return "ERROR: 坐标格式错误，请使用格式：'经度1,纬度1,经度2,纬度2,策略'"
        elif len(parts) == 4:  # 坐标格式无策略: 经度1,纬度1,经度2,纬度2
            try:
                origin = f"{parts[0].strip()},{parts[1].strip()}"
                destination = f"{parts[2].strip()},{parts[3].strip()}"
                strategy = 10
            except (ValueError, IndexError):
                return "ERROR: 坐标格式错误，请使用格式：'经度1,纬度1,经度2,纬度2'"
        elif len(parts) == 3:  # 地址格式: 起点,终点,策略
            origin = parts[0].strip()
            destination = parts[1].strip()
            try:
                strategy = int(parts[2].strip()) if parts[2].strip().isdigit() else 10
            except ValueError:
                strategy = 10
        elif len(parts) == 2:  # 地址格式无策略: 起点,终点
            origin = parts[0].strip()
            destination = parts[1].strip()
            strategy = 10
        else:
            return "ERROR: 参数格式错误，支持格式：'起点,终点' 或 '经度1,纬度1,经度2,纬度2'"
        
        logger.info(f"执行高德地图驾车路线规划: {origin} -> {destination}, 策略: {strategy}")
        
        # 将地址转换为坐标
        try:
            origin_coord = service._convert_to_coordinates(origin)
            destination_coord = service._convert_to_coordinates(destination)
            logger.info(f"坐标转换: {origin} -> {origin_coord}, {destination} -> {destination_coord}")
        except Exception as e:
            return f"ERROR: 地址解析失败: {str(e)}"
        
        data = service.plan_route(
            origin=origin_coord,
            destination=destination_coord,
            strategy=strategy,
            extensions="all"
        )
        return format_route_results(data, f"{origin}({origin_coord})", f"{destination}({destination_coord})", "驾车")
        
    except Exception as e:
        logger.error(f"高德地图驾车路线规划失败: {e}")
        return f"ERROR: 高德地图驾车路线规划时发生错误: {str(e)}"


@tool
def amap_route_walking(
    route_params: Annotated[str, "路线参数，格式为'起点,终点'，如'南京,成都'或'116.397477,39.908692,116.434446,39.90816'"]
) -> str:
    """
    规划步行路线
    
    Args:
        route_params: 路线参数字符串，格式为'起点,终点'
                     起点和终点可以是地址或坐标(经度,纬度)
        
    Returns:
        详细的步行路线规划结果
    """
    try:
        service = _get_route_service()
        
        # 解析参数 - 支持坐标和地址两种格式
        parts = route_params.strip().split(',')
        
        # 判断是坐标格式还是地址格式
        if len(parts) == 4:  # 坐标格式: 经度1,纬度1,经度2,纬度2
            try:
                origin = f"{parts[0].strip()},{parts[1].strip()}"
                destination = f"{parts[2].strip()},{parts[3].strip()}"
            except (ValueError, IndexError):
                return "ERROR: 坐标格式错误，请使用格式：'经度1,纬度1,经度2,纬度2'"
        elif len(parts) == 2:  # 地址格式: 起点,终点
            origin = parts[0].strip()
            destination = parts[1].strip()
        else:
            return "ERROR: 参数格式错误，支持格式：'起点,终点' 或 '经度1,纬度1,经度2,纬度2'"
        
        logger.info(f"执行高德地图步行路线规划: {origin} -> {destination}")
        
        # 将地址转换为坐标
        try:
            origin_coord = service._convert_to_coordinates(origin)
            destination_coord = service._convert_to_coordinates(destination)
            logger.info(f"坐标转换: {origin} -> {origin_coord}, {destination} -> {destination_coord}")
        except Exception as e:
            return f"ERROR: 地址解析失败: {str(e)}"
        
        data = service.plan_walking_route(origin=origin_coord, destination=destination_coord)
        return format_route_results(data, f"{origin}({origin_coord})", f"{destination}({destination_coord})", "步行")
        
    except Exception as e:
        logger.error(f"高德地图步行路线规划失败: {e}")
        return f"ERROR: 高德地图步行路线规划时发生错误: {str(e)}"


@tool
def amap_route_transit(
    route_params: Annotated[str, "公共交通路线参数，格式为'起点,终点,策略,城市'，如'天安门,故宫,0,北京'。策略：0-最快路线，1-最经济，2-最少换乘，3-最少步行，5-不乘地铁"]
) -> str:
    """
    规划公共交通路线（公交、地铁、火车等）
    
    Args:
        route_params: 路线参数字符串，格式为'起点,终点,策略,城市'
                     策略代码：0-最快路线，1-最经济，2-最少换乘，3-最少步行，5-不乘地铁
                     
    Returns:
        详细的公共交通路线规划结果，包括公交、地铁、火车等多种交通方式
    """
    try:
        service = _get_route_service()
        
        # 解析参数
        parts = route_params.strip().split(',')
        if len(parts) < 2:
            return "ERROR: 参数格式错误，请使用格式：'起点,终点,策略,城市'，例如：'天安门,故宫,0,北京'"
        
        origin = parts[0].strip()
        destination = parts[1].strip()
        strategy = 0  # 默认最快路线
        city = ""
        
        if len(parts) >= 3:
            try:
                strategy = int(parts[2].strip()) if parts[2].strip().isdigit() else 0
            except ValueError:
                strategy = 0
        
        if len(parts) >= 4:
            city = parts[3].strip()
        
        logger.info(f"执行高德地图公共交通路线规划: {origin} -> {destination}, 策略: {strategy}, 城市: {city}")
        
        # 将地址转换为坐标
        try:
            origin_coord = service._convert_to_coordinates(origin, city)
            destination_coord = service._convert_to_coordinates(destination, city)
            logger.info(f"坐标转换: {origin} -> {origin_coord}, {destination} -> {destination_coord}")
        except Exception as e:
            return f"ERROR: 地址解析失败: {str(e)}"
        
        data = service.plan_transit_route(
            origin=origin_coord,
            destination=destination_coord,
            city=city,
            strategy=strategy
        )
        return format_transit_results(data, f"{origin}({origin_coord})", f"{destination}({destination_coord})")
        
    except Exception as e:
        logger.error(f"高德地图公共交通路线规划失败: {e}")
        return f"ERROR: 高德地图公共交通路线规划时发生错误: {str(e)}"


@tool
def amap_route_subway(
    route_params: Annotated[str, "地铁路线参数，格式为'起点,终点,城市'，如'天安门,故宫,北京'"]
) -> str:
    """
    规划地铁路线（优先使用地铁）
    
    Args:
        route_params: 路线参数字符串，格式为'起点,终点,城市'
        
    Returns:
        优先使用地铁的公共交通路线规划结果
    """
    try:
        service = _get_route_service()
        
        # 解析参数
        parts = route_params.strip().split(',')
        if len(parts) < 2:
            return "ERROR: 参数格式错误，请使用格式：'起点,终点,城市'，例如：'天安门,故宫,北京'"
        
        origin = parts[0].strip()
        destination = parts[1].strip()
        city = parts[2].strip() if len(parts) >= 3 else ""
        
        # 使用最少换乘策略，适合地铁出行
        return amap_route_transit.func(f"{origin},{destination},2,{city}")
        
    except Exception as e:
        logger.error(f"高德地图地铁路线规划失败: {e}")
        return f"ERROR: 高德地图地铁路线规划时发生错误: {str(e)}"


@tool
def amap_route_bus(
    route_params: Annotated[str, "公交路线参数，格式为'起点,终点,城市'，如'天安门,故宫,北京'"]
) -> str:
    """
    规划公交路线（不使用地铁，只使用公交）
    
    Args:
        route_params: 路线参数字符串，格式为'起点,终点,城市'
        
    Returns:
        只使用公交车的路线规划结果
    """
    try:
        service = _get_route_service()
        
        # 解析参数
        parts = route_params.strip().split(',')
        if len(parts) < 2:
            return "ERROR: 参数格式错误，请使用格式：'起点,终点,城市'，例如：'天安门,故宫,北京'"
        
        origin = parts[0].strip()
        destination = parts[1].strip()
        city = parts[2].strip() if len(parts) >= 3 else ""
        
        # 使用不乘地铁策略，只使用公交
        return amap_route_transit.func(f"{origin},{destination},5,{city}")
        
    except Exception as e:
        logger.error(f"高德地图公交路线规划失败: {e}")
        return f"ERROR: 高德地图公交路线规划时发生错误: {str(e)}"


# 导出工具列表
AMAP_ROUTE_TOOLS = [
    amap_route_driving,
    amap_route_walking,
    amap_route_transit,
    amap_route_subway,
    amap_route_bus
]


def init_route_service(api_key: str = None) -> AmapRouteService:
    """
    初始化路径规划服务
    
    Args:
        api_key: 高德地图API密钥
        
    Returns:
        AmapRouteService实例
    """
    # 如果没有提供api_key，则从项目配置中获取
    api_key = api_key or getattr(settings, 'amap_api_key', None)
    
    global _amap_route_service
    client = AmapClient(api_key)
    _amap_route_service = AmapRouteService(client)
    return _amap_route_service