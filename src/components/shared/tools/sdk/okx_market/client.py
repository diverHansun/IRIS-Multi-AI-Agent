"""
OKX Market API Client

提供OKX交易所API的Python客户端封装，支持：
- 公共市场数据获取
- 错误处理和重试机制
- 速率限制管理
"""

import asyncio
import time
from typing import Dict, List, Optional, Union, Any
import requests
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class OKXAPIError(Exception):
    """OKX API异常类"""
    pass


class OKXRateLimitError(OKXAPIError):
    """OKX API速率限制异常"""
    pass


class OKXMarketClient:
    """
    OKX市场数据API客户端
    
    提供获取OKX交易所公共市场数据的功能，包括：
    - 实时ticker数据
    - K线历史数据
    - 交易对信息
    - 订单簿数据
    """
    
    def __init__(self, base_url: str = "https://www.okx.com", timeout: int = 10):
        """
        初始化OKX客户端
        
        Args:
            base_url: API基础URL，默认为OKX官方地址
            timeout: 请求超时时间（秒）
        """
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'Agent Demo OKX Client/1.0.0'
        })
        
        # 速率限制管理
        self._last_request_time = 0
        self._request_count = 0
        self._rate_limit_window = 2  # 2秒窗口
        self._max_requests_per_window = 20  # 每2秒最多20次请求
        
    def _check_rate_limit(self) -> None:
        """检查并处理速率限制"""
        current_time = time.time()
        
        # 如果超过时间窗口，重置计数器
        if current_time - self._last_request_time >= self._rate_limit_window:
            self._request_count = 0
            self._last_request_time = current_time
            
        # 如果达到速率限制，等待
        if self._request_count >= self._max_requests_per_window:
            sleep_time = self._rate_limit_window - (current_time - self._last_request_time)
            if sleep_time > 0:
                logger.warning(f"达到速率限制，等待 {sleep_time:.2f} 秒")
                time.sleep(sleep_time)
                self._request_count = 0
                self._last_request_time = time.time()
        
        self._request_count += 1
    
    def _make_request(self, endpoint: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """
        发起API请求
        
        Args:
            endpoint: API端点
            params: 查询参数
            
        Returns:
            API响应数据
            
        Raises:
            OKXAPIError: API请求失败
            OKXRateLimitError: 速率限制错误
        """
        self._check_rate_limit()
        
        url = f"{self.base_url}{endpoint}"
        
        try:
            response = self.session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            
            data = response.json()
            
            # 检查OKX API响应状态
            if data.get('code') != '0':
                error_msg = data.get('msg', '未知错误')
                if 'rate limit' in error_msg.lower():
                    raise OKXRateLimitError(f"速率限制: {error_msg}")
                raise OKXAPIError(f"API错误: {error_msg}")
                
            return data
            
        except requests.exceptions.Timeout:
            raise OKXAPIError(f"请求超时: {url}")
        except requests.exceptions.RequestException as e:
            raise OKXAPIError(f"请求失败: {str(e)}")
        except ValueError as e:
            raise OKXAPIError(f"响应解析失败: {str(e)}")
    
    def get_instruments(self, inst_type: str = "SPOT") -> List[Dict[str, Any]]:
        """
        获取交易产品信息
        
        Args:
            inst_type: 产品类型 (SPOT, SWAP, FUTURES, OPTION)
            
        Returns:
            交易对信息列表
        """
        endpoint = "/api/v5/public/instruments"
        params = {"instType": inst_type}
        
        try:
            response = self._make_request(endpoint, params)
            return response.get('data', [])
        except Exception as e:
            logger.error(f"获取交易对信息失败: {str(e)}")
            raise
    
    def get_ticker(self, inst_id: Optional[str] = None, inst_type: str = "SPOT") -> Union[Dict, List[Dict]]:
        """
        获取ticker数据
        
        Args:
            inst_id: 交易对ID，如果为None则获取所有
            inst_type: 产品类型
            
        Returns:
            单个或多个ticker数据
        """
        endpoint = "/api/v5/market/tickers" if inst_id is None else "/api/v5/market/ticker"
        params = {"instType": inst_type}
        
        if inst_id:
            params["instId"] = inst_id
            
        try:
            response = self._make_request(endpoint, params)
            data = response.get('data', [])
            return data[0] if inst_id and data else data
        except Exception as e:
            logger.error(f"获取ticker数据失败: {str(e)}")
            raise
    
    def get_candles(self, inst_id: str, bar: str = "1D", limit: int = 100, 
                   after: Optional[str] = None, before: Optional[str] = None) -> List[List[str]]:
        """
        获取K线数据
        
        Args:
            inst_id: 交易对ID
            bar: K线周期 (1m, 3m, 5m, 15m, 30m, 1H, 2H, 4H, 6H, 12H, 1D, 1W, 1M, 3M, 6M, 1Y)
            limit: 数据条数限制 (1-300)
            after: 时间戳，查询该时间戳之后的数据
            before: 时间戳，查询该时间戳之前的数据
            
        Returns:
            K线数据列表，每个元素为 [时间戳, 开盘价, 最高价, 最低价, 收盘价, 成交量, 成交额, 确认状态]
        """
        endpoint = "/api/v5/market/candles"
        params = {
            "instId": inst_id,
            "bar": bar,
            "limit": str(limit)
        }
        
        if after:
            params["after"] = after
        if before:
            params["before"] = before
            
        try:
            response = self._make_request(endpoint, params)
            return response.get('data', [])
        except Exception as e:
            logger.error(f"获取K线数据失败: {str(e)}")
            raise
    
    def get_orderbook(self, inst_id: str, sz: int = 20) -> Dict[str, Any]:
        """
        获取订单簿数据
        
        Args:
            inst_id: 交易对ID
            sz: 订单簿深度 (1-400)
            
        Returns:
            订单簿数据
        """
        endpoint = "/api/v5/market/books"
        params = {
            "instId": inst_id,
            "sz": str(sz)
        }
        
        try:
            response = self._make_request(endpoint, params)
            data = response.get('data', [])
            return data[0] if data else {}
        except Exception as e:
            logger.error(f"获取订单簿数据失败: {str(e)}")
            raise
    
    def get_trades(self, inst_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """
        获取最近成交数据
        
        Args:
            inst_id: 交易对ID
            limit: 数据条数限制 (1-500)
            
        Returns:
            最近成交数据列表
        """
        endpoint = "/api/v5/market/trades"
        params = {
            "instId": inst_id,
            "limit": str(limit)
        }
        
        try:
            response = self._make_request(endpoint, params)
            return response.get('data', [])
        except Exception as e:
            logger.error(f"获取成交数据失败: {str(e)}")
            raise
    
    def close(self) -> None:
        """关闭HTTP会话"""
        if self.session:
            self.session.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()