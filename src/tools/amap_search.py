"""
高德地图(AutoNavi)搜索工具模块

基于高德地图Web服务API提供地点搜索和路径规划功能。
专为中文环境优化，集成到LangChain工具系统中。
"""

import json
import logging
import requests
from typing import Annotated, Dict, List, Any, Optional
from langchain_core.tools import tool

from ..config import settings

logger = logging.getLogger(__name__)


class AmapSearchProvider:
    """高德地图搜索服务提供者"""
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or getattr(settings, 'amap_api_key', None)
        self.is_available = bool(self.api_key)
        self.base_url = "https://restapi.amap.com"
        
        if not self.is_available:
            logger.warning("Amap API key not found. Amap search functionality will be disabled.")
    
    def _make_request(self, endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """发起API请求"""
        if not self.is_available:
            raise ValueError("Amap API key not configured")
        
        params['key'] = self.api_key
        url = f"{self.base_url}{endpoint}"
        
        try:
            logger.info(f"请求URL: {url}")
            logger.info(f"请求参数: {params}")
            
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            logger.info(f"API响应: {data}")
            
            if data.get('status') != '1':
                logger.error(f"API返回错误状态: {data}")
                raise ValueError(f"Amap API错误: {data.get('info', '未知错误')} (状态码: {data.get('infocode', 'N/A')})")
            
            return data
        except requests.RequestException as e:
            logger.error(f"高德地图API请求失败: {e}")
            raise ValueError(f"网络请求失败: {str(e)}")
    
    def search_places(self, keywords: str, city: str = "", types: str = "", 
                     location: str = "", radius: int = 1000, page: int = 1) -> Dict[str, Any]:
        """搜索地点POI"""
        params = {
            'keywords': keywords,
            'extensions': 'all'
        }
        
        if city:
            params['city'] = city
        if types:
            params['types'] = types
        if location:
            params['location'] = location
            params['radius'] = radius
            endpoint = '/v3/place/around'
        else:
            endpoint = '/v3/place/text'
        
        params['page'] = page
        params['offset'] = 20  # 每页最大20条
        
        return self._make_request(endpoint, params)
    
    def get_place_detail(self, poi_id: str) -> Dict[str, Any]:
        """获取POI详细信息"""
        params = {
            'id': poi_id,
            'extensions': 'all'
        }
        
        return self._make_request('/v3/place/detail', params)
    
    def plan_route(self, origin: str, destination: str, strategy: int = 10, 
                   waypoints: str = "", extensions: str = "base") -> Dict[str, Any]:
        """规划驾车路线"""
        params = {
            'origin': origin,
            'destination': destination,
            'strategy': strategy,
            'extensions': extensions
        }
        
        if waypoints:
            params['waypoints'] = waypoints
        
        return self._make_request('/v3/direction/driving', params)
    
    def plan_walking_route(self, origin: str, destination: str) -> Dict[str, Any]:
        """规划步行路线"""
        params = {
            'origin': origin,
            'destination': destination
        }
        
        return self._make_request('/v3/direction/walking', params)
    
    def geocode_address(self, address: str, city: str = "") -> Dict[str, Any]:
        """地址转坐标（地理编码）"""
        params = {
            'address': address,
            'batch': False,
            'output': 'json'
        }
        
        if city:
            params['city'] = city
        
        return self._make_request('/v3/geocode/geo', params)
    
    def is_coordinate(self, location_str: str) -> bool:
        """判断字符串是否为坐标格式"""
        try:
            parts = location_str.split(',')
            if len(parts) != 2:
                return False
            
            lon = float(parts[0])
            lat = float(parts[1])
            
            # 检查是否在中国范围内的合理坐标
            if 73 <= lon <= 135 and 18 <= lat <= 54:
                return True
            return False
        except:
            return False
    
    def convert_to_coordinates(self, location: str, city: str = "") -> str:
        """将地址转换为坐标，如果已经是坐标则直接返回"""
        if self.is_coordinate(location):
            # 确保坐标精度不超过6位小数
            parts = location.split(',')
            lon = round(float(parts[0]), 6)
            lat = round(float(parts[1]), 6)
            return f"{lon},{lat}"
        
        # 地址转坐标
        try:
            data = self.geocode_address(location, city)
            geocodes = data.get('geocodes', [])
            if not geocodes:
                raise ValueError(f"无法找到地址 '{location}' 的坐标")
            
            location_coord = geocodes[0].get('location', '')
            if not location_coord:
                raise ValueError(f"地址 '{location}' 未返回有效坐标")
            
            return location_coord
        except Exception as e:
            logger.error(f"地址转坐标失败: {location} -> {e}")
            raise ValueError(f"地址转坐标失败: {str(e)}")
    
    def plan_transit_route(self, origin: str, destination: str, city: str = "", 
                          strategy: int = 0, nightflag: int = 0) -> Dict[str, Any]:
        """规划公共交通路线"""
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
        
        return self._make_request('/v3/direction/transit/integrated', params)
    
    def format_place_results(self, data: Dict[str, Any], query: str) -> str:
        """格式化地点搜索结果"""
        pois = data.get('pois', [])
        
        if not pois:
            return f"抱歉，没有找到关于 '{query}' 的地点信息。"
        
        count = data.get('count', len(pois))
        formatted_results = [f"MAP 高德地图搜索结果: {query}\nCOUNT 共找到 {count} 个地点\n"]
        
        for i, poi in enumerate(pois[:10], 1):  # 最多显示10个结果
            address = poi.get('address', '').strip()
            district = poi.get('adname', '').strip()
            if address and district and address != district:
                full_address = f"{district}{address}"
            else:
                full_address = address or district or "地址未知"
            
            distance = poi.get('distance', '')
            distance_info = f" (距离: {distance}米)" if distance and distance != '[]' else ""
            
            formatted_result = f"""
PLACE 第 {i} 个地点:
NAME 名称: {poi.get('name', '未知')}
TYPE 类型: {poi.get('type', '未知类型')}
ADDR 地址: {full_address}{distance_info}
TEL 电话: {poi.get('tel', '暂无电话')}
LOC 坐标: {poi.get('location', '未知')}
RATING 评分: {poi.get('rating', '暂无评分')}
"""
            formatted_results.append(formatted_result.strip())
        
        return "\n\n".join(formatted_results)
    
    def format_route_results(self, data: Dict[str, Any], origin: str, destination: str, route_type: str = "驾车") -> str:
        """格式化路线规划结果"""
        route = data.get('route', {})
        
        if not route:
            return f"抱歉，无法规划从 '{origin}' 到 '{destination}' 的{route_type}路线。"
        
        paths = route.get('paths', [])
        if not paths:
            return f"抱歉，没有找到从 '{origin}' 到 '{destination}' 的可行{route_type}路线。"
        
        # 使用第一条路线（通常是推荐路线）
        path = paths[0]
        distance = path.get('distance', '0')
        duration = path.get('duration', '0')
        
        # 转换单位
        distance_km = f"{float(distance) / 1000:.1f}" if distance.isdigit() else "未知"
        duration_min = f"{int(float(duration)) // 60}" if duration.replace('.', '').isdigit() else "未知"
        
        formatted_result = f"""
ROUTE {route_type}路线规划结果:
PLACE 起点: {origin}
END 终点: {destination}
DIST 总距离: {distance_km} 公里
TIME 预计时间: {duration_min} 分钟

ROADS 主要路段:
"""
        
        # 添加路段信息
        steps = path.get('steps', [])
        for i, step in enumerate(steps[:8], 1):  # 最多显示8个主要路段
            instruction = step.get('instruction', '')
            road_name = step.get('road', '')
            step_distance = step.get('distance', '0')
            step_duration = step.get('duration', '0')
            
            step_distance_km = f"{float(step_distance) / 1000:.1f}" if step_distance.isdigit() else "0.0"
            step_duration_min = f"{int(float(step_duration)) // 60}" if step_duration.replace('.', '').isdigit() else "0"
            
            formatted_result += f"  {i}. {instruction}"
            if road_name:
                formatted_result += f" (经{road_name})"
            formatted_result += f" - {step_distance_km}km, {step_duration_min}分钟\n"
        
        if len(steps) > 8:
            formatted_result += f"  ... 还有 {len(steps) - 8} 个路段\n"
        
        # 添加策略信息
        strategy_names = {
            10: "躲避拥堵的最短路径",
            12: "躲避收费",
            13: "不走高速", 
            14: "躲避拥堵",
            19: "走高速优先"
        }
        strategy = data.get('route', {}).get('origin', '').split(',')  # 这里需要从请求参数获取
        
        return formatted_result
    
    def format_transit_results(self, data: Dict[str, Any], origin: str, destination: str) -> str:
        """格式化公共交通路线规划结果"""
        route = data.get('route', {})
        
        if not route:
            return f"抱歉，无法规划从 '{origin}' 到 '{destination}' 的公共交通路线。"
        
        # 基本信息
        origin_coord = route.get('origin', '')
        destination_coord = route.get('destination', '')
        distance = route.get('distance', '0')
        taxi_cost = route.get('taxi_cost', '0')
        
        # 转换单位
        distance_km = f"{float(distance) / 1000:.1f}" if distance.isdigit() else "未知"
        
        formatted_result = f"""
TRANSIT 公共交通路线规划结果:
PLACE 起点: {origin}
END 终点: {destination}
DIST 总距离: {distance_km} 公里
TAXI 出租车费用: {taxi_cost} 元

ROUTES 可选路线:
"""
        
        # 路线选择
        transits = route.get('transits', [])
        for i, transit in enumerate(transits[:3], 1):  # 最多显示3条路线
            duration = transit.get('duration', '0')
            walking_distance = transit.get('walking_distance', '0')
            cost = transit.get('cost', '0')
            
            duration_min = f"{int(float(duration)) // 60}" if duration.replace('.', '').isdigit() else "未知"
            walking_km = f"{float(walking_distance) / 1000:.1f}" if walking_distance.isdigit() else "0.0"
            
            formatted_result += f"""
  路线 {i}:
  TIME 总时间: {duration_min} 分钟
  WALK 步行距离: {walking_km} 公里
  COST 费用: {cost} 元
  
  详细路段:"""
            
            # 路段信息
            segments = transit.get('segments', [])
            for j, segment in enumerate(segments[:8], 1):  # 最多显示8个路段
                # 处理步行路段
                if segment.get('walking'):
                    walk_info = segment.get('walking', {})
                    walk_distance = walk_info.get('distance', '0')
                    walk_km = f"{float(walk_distance) / 1000:.2f}" if walk_distance.isdigit() else "0.00"
                    
                    # 获取步行详细指导
                    walk_steps = walk_info.get('steps', [])
                    if walk_steps and len(walk_steps) > 0:
                        # 获取主要步行指导
                        main_instruction = walk_steps[0].get('instruction', '步行')
                        formatted_result += f"\n    {j}. 步行 {walk_km}公里 - {main_instruction}"
                    else:
                        formatted_result += f"\n    {j}. 步行 {walk_km}公里"
                
                # 处理公交/地铁路段
                elif segment.get('bus'):
                    bus_data = segment.get('bus', {})
                    buslines = bus_data.get('buslines', [])
                    
                    if buslines and len(buslines) > 0:
                        bus_info = buslines[0]  # 取第一条线路
                        bus_name = bus_info.get('name', '未知线路')
                        departure_stop = bus_info.get('departure_stop', {}).get('name', '') if bus_info.get('departure_stop') else ''
                        arrival_stop = bus_info.get('arrival_stop', {}).get('name', '') if bus_info.get('arrival_stop') else ''
                        bus_type = bus_info.get('type', '')
                        bus_distance = bus_info.get('distance', '0')
                        bus_duration = bus_info.get('duration', '0')
                        
                        # 判断交通类型
                        if '地铁' in bus_name or bus_name.startswith('地铁') or 'subway' in bus_type.lower():
                            transport_type = "[地铁]"
                        elif '高铁' in bus_name or '动车' in bus_name:
                            transport_type = "[高铁]"
                        elif '火车' in bus_name or '列车' in bus_name:
                            transport_type = "[火车]"
                        elif '公交' in bus_type or 'bus' in bus_type.lower():
                            transport_type = "[公交]"
                        else:
                            transport_type = "[公交]"
                        
                        formatted_result += f"\n    {j}. {transport_type}: {bus_name}"
                        
                        # 添加起终点站信息
                        if departure_stop and arrival_stop:
                            formatted_result += f"\n        {departure_stop} → {arrival_stop}"
                        
                        # 添加距离和时间信息
                        if bus_distance and bus_distance.isdigit():
                            distance_km = f"{float(bus_distance) / 1000:.1f}" if float(bus_distance) > 0 else ""
                            if distance_km:
                                formatted_result += f" - {distance_km}公里"
                        if bus_duration and bus_duration.replace('.', '').isdigit():
                            duration_min = f"{int(float(bus_duration)) // 60}" if float(bus_duration) > 0 else ""
                            if duration_min and duration_min != "0":
                                formatted_result += f", {duration_min}分钟"
        
        return formatted_result


# 全局搜索提供者实例
amap_provider = AmapSearchProvider()


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
        if not amap_provider.is_available:
            return "ERROR: 高德地图搜索功能未配置。请设置 AMAP_API_KEY 环境变量"
        
        logger.info(f"执行高德地图地点搜索: {query}")
        
        data = amap_provider.search_places(keywords=query)
        return amap_provider.format_place_results(data, query)
        
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
        if not amap_provider.is_available:
            return "ERROR: 高德地图搜索功能未配置。请设置 AMAP_API_KEY 环境变量"
        
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
        
        radius = 1000  # 默认半径
        if len(parts) >= 4:
            try:
                radius = int(parts[3].strip())
            except ValueError:
                radius = 1000
        
        logger.info(f"执行高德地图附近搜索: {query}, 位置: {location}, 半径: {radius}米")
        
        data = amap_provider.search_places(
            keywords=query, 
            location=location, 
            radius=radius
        )
        return amap_provider.format_place_results(data, f"{query}(附近{radius}米)")
        
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
        if not amap_provider.is_available:
            return "ERROR: 高德地图搜索功能未配置。请设置 AMAP_API_KEY 环境变量"
        
        # 解析参数
        parts = search_params.strip().split(',')
        if len(parts) < 2:
            return "ERROR: 参数格式错误，请使用格式：'关键词,城市'，例如：'购物中心,北京'"
        
        query = parts[0].strip()
        city = parts[1].strip()
        
        logger.info(f"执行高德地图城市搜索: {query} in {city}")
        
        data = amap_provider.search_places(keywords=query, city=city)
        return amap_provider.format_place_results(data, f"{query}({city})")
        
    except Exception as e:
        logger.error(f"高德地图城市搜索失败: {e}")
        return f"ERROR: 高德地图城市搜索时发生错误: {str(e)}"


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
        if not amap_provider.is_available:
            return "❌ 高德地图路线规划功能未配置。请设置 AMAP_API_KEY 环境变量"
        
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
            origin_coord = amap_provider.convert_to_coordinates(origin)
            destination_coord = amap_provider.convert_to_coordinates(destination)
            logger.info(f"坐标转换: {origin} -> {origin_coord}, {destination} -> {destination_coord}")
        except Exception as e:
            return f"ERROR: 地址解析失败: {str(e)}"
        
        data = amap_provider.plan_route(
            origin=origin_coord,
            destination=destination_coord, 
            strategy=strategy,
            extensions="all"
        )
        return amap_provider.format_route_results(data, f"{origin}({origin_coord})", f"{destination}({destination_coord})", "驾车")
        
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
        if not amap_provider.is_available:
            return "❌ 高德地图路线规划功能未配置。请设置 AMAP_API_KEY 环境变量"
        
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
            origin_coord = amap_provider.convert_to_coordinates(origin)
            destination_coord = amap_provider.convert_to_coordinates(destination)
            logger.info(f"坐标转换: {origin} -> {origin_coord}, {destination} -> {destination_coord}")
        except Exception as e:
            return f"ERROR: 地址解析失败: {str(e)}"
        
        data = amap_provider.plan_walking_route(origin=origin_coord, destination=destination_coord)
        return amap_provider.format_route_results(data, f"{origin}({origin_coord})", f"{destination}({destination_coord})", "步行")
        
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
        if not amap_provider.is_available:
            return "ERROR: 高德地图公共交通规划功能未配置。请设置 AMAP_API_KEY 环境变量"
        
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
            origin_coord = amap_provider.convert_to_coordinates(origin, city)
            destination_coord = amap_provider.convert_to_coordinates(destination, city)
            logger.info(f"坐标转换: {origin} -> {origin_coord}, {destination} -> {destination_coord}")
        except Exception as e:
            return f"ERROR: 地址解析失败: {str(e)}"
        
        data = amap_provider.plan_transit_route(
            origin=origin_coord,
            destination=destination_coord,
            city=city,
            strategy=strategy
        )
        return amap_provider.format_transit_results(data, f"{origin}({origin_coord})", f"{destination}({destination_coord})")
        
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
        if not amap_provider.is_available:
            return "ERROR: 高德地图地铁规划功能未配置。请设置 AMAP_API_KEY 环境变量"
        
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
        if not amap_provider.is_available:
            return "ERROR: 高德地图公交规划功能未配置。请设置 AMAP_API_KEY 环境变量"
        
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
AMAP_TOOLS = [
    amap_search_place,
    amap_search_nearby, 
    amap_search_in_city,
    amap_route_driving,
    amap_route_walking,
    amap_route_transit,
    amap_route_subway,
    amap_route_bus
]


def get_available_amap_tools() -> List:
    """获取可用的高德地图工具列表"""
    if amap_provider.is_available:
        return AMAP_TOOLS
    else:
        logger.warning("Amap API key not configured, returning empty tool list")
        return []


def test_amap_tools():
    """测试高德地图搜索工具"""
    print("测试高德地图搜索工具...")
    
    if not amap_provider.is_available:
        print("高德地图 API key 未配置，无法进行测试")
        return
    
    # 测试地点搜索
    print("\n1. 测试地点搜索:")
    try:
        result = amap_search_place.func("星巴克")
        print(f"地点搜索成功: {result[:200]}...")
    except Exception as e:
        print(f"地点搜索失败: {e}")
    
    # 测试附近搜索
    print("\n2. 测试附近搜索:")
    try:
        result = amap_search_nearby.func("餐厅", "116.397477,39.908692", 500)
        print(f"附近搜索成功: {result[:200]}...")
    except Exception as e:
        print(f"附近搜索失败: {e}")
    
    # 测试路线规划
    print("\n3. 测试驾车路线规划:")
    try:
        result = amap_route_driving.func("116.481028,39.989643", "116.434446,39.90816", 10)
        print(f"路线规划成功: {result[:200]}...")
    except Exception as e:
        print(f"路线规划失败: {e}")
    
    print("\n高德地图搜索工具测试完成!")


if __name__ == "__main__":
    test_amap_tools()