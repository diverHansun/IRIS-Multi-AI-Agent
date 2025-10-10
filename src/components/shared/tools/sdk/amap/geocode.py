"""
高德地图地理编码服务模块

提供地理编码和逆地理编码相关的功能
"""

import logging
from typing import Dict, Any
from .client import AmapClient
from .constants import API_ENDPOINTS

logger = logging.getLogger(__name__)


class AmapGeocodeService:
    """高德地图地理编码服务"""
    
    def __init__(self, client: AmapClient):
        """
        初始化地理编码服务
        
        Args:
            client: 高德地图API客户端实例
        """
        self.client = client
    
    def geocode_address(self, address: str, city: str = "") -> Dict[str, Any]:
        """
        地址转坐标（地理编码）
        
        Args:
            address: 地址
            city: 城市
            
        Returns:
            地理编码结果
        """
        params = {
            'address': address,
            'batch': False,
            'output': 'json'
        }
        
        if city:
            params['city'] = city
        
        return self.client._make_request(API_ENDPOINTS['GEOCODE_GEO'], params)
    
    def regeocode_coordinates(self, location: str, radius: int = 1000, 
                            extensions: str = "base") -> Dict[str, Any]:
        """
        坐标转地址（逆地理编码）
        
        Args:
            location: 坐标（经度,纬度）
            radius: 搜索半径（米）
            extensions: 返回结果控制（base/all）
            
        Returns:
            逆地理编码结果
        """
        params = {
            'location': location,
            'radius': radius,
            'extensions': extensions,
            'batch': False,
            'output': 'json'
        }
        
        return self.client._make_request(API_ENDPOINTS['GEOCODE_REGEO'], params)