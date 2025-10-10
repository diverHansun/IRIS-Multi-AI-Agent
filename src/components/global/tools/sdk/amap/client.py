"""
高德地图API客户端模块

负责与高德地图Web服务API进行交互，包括：
- API请求发送
- 连接池管理
- 重试机制
- 错误处理
- 超时设置
"""

import json
import logging
import time
from typing import Dict, Any, Optional
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .exceptions import AmapApiError, AmapApiRateLimitError

logger = logging.getLogger(__name__)


class AmapClient:
    """高德地图API客户端"""
    
    def __init__(self, api_key: str, base_url: str = "https://restapi.amap.com"):
        """
        初始化高德地图API客户端
        
        Args:
            api_key: 高德地图API密钥
            base_url: API基础URL
        """
        self.api_key = api_key
        self.base_url = base_url
        self.session = self._create_session()
        
    def _create_session(self) -> requests.Session:
        """
        创建带有连接池和重试机制的会话
        
        Returns:
            配置好的requests.Session对象
        """
        session = requests.Session()
        
        # 配置重试策略
        retry_strategy = Retry(
            total=3,  # 总重试次数
            backoff_factor=1,  # 退避因子
            status_forcelist=[429, 500, 502, 503, 504],  # 需要重试的状态码
        )
        
        # 配置适配器
        adapter = HTTPAdapter(
            pool_connections=10,  # 连接池大小
            pool_maxsize=20,  # 最大连接数
            max_retries=retry_strategy
        )
        
        # 为HTTP和HTTPS设置适配器
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        # 设置默认请求头
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
            "Content-Type": "application/json; charset=utf-8"
        })
        
        return session
    
    def _make_request(self, endpoint: str, params: Dict[str, Any], 
                     timeout: tuple = (5, 30)) -> Dict[str, Any]:
        """
        发起API请求
        
        Args:
            endpoint: API端点
            params: 请求参数
            timeout: 超时设置 (连接超时, 读取超时)
            
        Returns:
            API响应数据
            
        Raises:
            AmapApiError: API调用错误
            AmapApiRateLimitError: 频率限制错误
        """
        # 添加API密钥
        params['key'] = self.api_key
        
        url = f"{self.base_url}{endpoint}"
        
        try:
            logger.debug(f"请求URL: {url}")
            logger.debug(f"请求参数: {params}")
            
            response = self.session.get(
                url, 
                params=params, 
                timeout=timeout
            )
            
            # 检查HTTP状态码
            response.raise_for_status()
            
            # 解析JSON响应
            data = response.json()
            logger.debug(f"API响应: {data}")
            
            # 检查API状态码
            status = data.get('status', '0')
            if status != '1':
                infocode = data.get('infocode', 'N/A')
                info = data.get('info', '未知错误')
                
                # 特殊处理频率限制错误
                if infocode == '10003':
                    logger.warning(f"API频率限制: {info} (状态码: {infocode})")
                    raise AmapApiRateLimitError(f"API频率限制: {info}")
                
                logger.error(f"API返回错误状态: {data}")
                raise AmapApiError(f"高德地图API错误: {info} (状态码: {infocode})")
            
            return data
            
        except requests.exceptions.Timeout:
            logger.error(f"API请求超时: {url}")
            raise AmapApiError("API请求超时")
        except requests.exceptions.ConnectionError:
            logger.error(f"API连接错误: {url}")
            raise AmapApiError("API连接错误")
        except requests.exceptions.RequestException as e:
            logger.error(f"API请求失败: {e}")
            raise AmapApiError(f"网络请求失败: {str(e)}")
        except json.JSONDecodeError as e:
            logger.error(f"API响应JSON解析失败: {e}")
            raise AmapApiError("API响应格式错误")