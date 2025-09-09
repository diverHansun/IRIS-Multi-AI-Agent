"""
高德地图坐标验证模块

提供坐标格式验证和处理功能
"""

import re


def validate_coordinates(location_str: str) -> bool:
    """
    判断字符串是否为坐标格式
    
    Args:
        location_str: 待验证的字符串
        
    Returns:
        是否为有效的坐标格式
    """
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


def is_chinese_coordinate(location_str: str) -> bool:
    """
    判断坐标是否在中国范围内
    
    Args:
        location_str: 坐标字符串（经度,纬度）
        
    Returns:
        是否在中国范围内
    """
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


def format_coordinates(location: str) -> str:
    """
    格式化坐标字符串，确保精度不超过6位小数
    
    Args:
        location: 坐标字符串
        
    Returns:
        格式化后的坐标字符串
    """
    if not validate_coordinates(location):
        raise ValueError(f"坐标格式错误: {location}")
    
    parts = location.split(',')
    lon = round(float(parts[0]), 6)
    lat = round(float(parts[1]), 6)
    return f"{lon},{lat}"