"""
高德地图结果格式化模块

提供API结果格式化功能
"""

from typing import Dict, Any


def format_place_results(data: Dict[str, Any], query: str) -> str:
    """
    格式化地点搜索结果
    
    Args:
        data: API返回的数据
        query: 搜索关键词
        
    Returns:
        格式化后的结果字符串
    """
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


def format_route_results(data: Dict[str, Any], origin: str, destination: str, route_type: str = "驾车") -> str:
    """
    格式化路线规划结果
    
    Args:
        data: API返回的数据
        origin: 起点
        destination: 终点
        route_type: 路线类型
        
    Returns:
        格式化后的结果字符串
    """
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


def format_transit_results(data: Dict[str, Any], origin: str, destination: str) -> str:
    """
    格式化公共交通路线规划结果
    
    Args:
        data: API返回的数据
        origin: 起点
        destination: 终点
        
    Returns:
        格式化后的结果字符串
    """
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