"""
OKX Market Configuration

OKX市场数据模块的配置管理
"""

import os
from typing import Dict, Any, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class OKXConfig:
    """OKX配置类"""
    
    # API配置
    base_url: str = "https://www.okx.com"
    timeout: int = 10
    max_retries: int = 3
    retry_delay: float = 1.0
    
    # 速率限制配置
    rate_limit_requests: int = 20  # 每个时间窗口的最大请求数
    rate_limit_window: int = 2     # 时间窗口（秒）
    
    # 缓存配置
    enable_cache: bool = True
    cache_expire_seconds: int = 60  # 缓存过期时间
    
    # 数据配置
    default_limit: int = 100       # 默认数据条数限制
    max_limit: int = 300           # 最大数据条数限制
    default_timeframe: str = "1D"  # 默认K线时间周期
    
    # 监控配置
    monitor_interval: int = 60     # 价格监控检查间隔（秒）
    max_alerts: int = 50          # 最大预警数量
    
    # 日志配置
    log_level: str = "INFO"
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    def __post_init__(self):
        """后初始化验证"""
        if self.timeout <= 0:
            self.timeout = 10
            
        if self.rate_limit_requests <= 0:
            self.rate_limit_requests = 20
            
        if self.rate_limit_window <= 0:
            self.rate_limit_window = 2
            
        if self.default_limit <= 0:
            self.default_limit = 100
            
        if self.max_limit <= 0 or self.max_limit > 500:
            self.max_limit = 300
            
        if self.monitor_interval < 10:  # 最小10秒间隔
            self.monitor_interval = 10


def load_config_from_env() -> OKXConfig:
    """从环境变量加载配置"""
    config = OKXConfig()
    
    # 从环境变量更新配置
    config.base_url = os.getenv("OKX_BASE_URL", config.base_url)
    
    # 超时设置
    timeout_str = os.getenv("OKX_TIMEOUT")
    if timeout_str and timeout_str.isdigit():
        config.timeout = int(timeout_str)
    
    # 重试设置
    retries_str = os.getenv("OKX_MAX_RETRIES")
    if retries_str and retries_str.isdigit():
        config.max_retries = int(retries_str)
    
    # 速率限制
    rate_limit_str = os.getenv("OKX_RATE_LIMIT_REQUESTS")
    if rate_limit_str and rate_limit_str.isdigit():
        config.rate_limit_requests = int(rate_limit_str)
    
    rate_window_str = os.getenv("OKX_RATE_LIMIT_WINDOW")
    if rate_window_str and rate_window_str.isdigit():
        config.rate_limit_window = int(rate_window_str)
    
    # 缓存设置
    enable_cache_str = os.getenv("OKX_ENABLE_CACHE", "").lower()
    if enable_cache_str in ("false", "0", "no"):
        config.enable_cache = False
    
    cache_expire_str = os.getenv("OKX_CACHE_EXPIRE_SECONDS")
    if cache_expire_str and cache_expire_str.isdigit():
        config.cache_expire_seconds = int(cache_expire_str)
    
    # 数据限制
    default_limit_str = os.getenv("OKX_DEFAULT_LIMIT")
    if default_limit_str and default_limit_str.isdigit():
        config.default_limit = int(default_limit_str)
    
    max_limit_str = os.getenv("OKX_MAX_LIMIT")
    if max_limit_str and max_limit_str.isdigit():
        config.max_limit = int(max_limit_str)
    
    # 默认时间周期
    default_timeframe = os.getenv("OKX_DEFAULT_TIMEFRAME")
    if default_timeframe:
        config.default_timeframe = default_timeframe
    
    # 监控设置
    monitor_interval_str = os.getenv("OKX_MONITOR_INTERVAL")
    if monitor_interval_str and monitor_interval_str.isdigit():
        config.monitor_interval = int(monitor_interval_str)
    
    max_alerts_str = os.getenv("OKX_MAX_ALERTS")
    if max_alerts_str and max_alerts_str.isdigit():
        config.max_alerts = int(max_alerts_str)
    
    # 日志设置
    log_level = os.getenv("OKX_LOG_LEVEL")
    if log_level:
        config.log_level = log_level.upper()
    
    return config


def setup_logging(config: OKXConfig) -> None:
    """设置日志配置"""
    logging.basicConfig(
        level=getattr(logging, config.log_level, logging.INFO),
        format=config.log_format,
        handlers=[
            logging.StreamHandler()
        ]
    )
    
    # 设置OKX相关模块的日志级别
    okx_logger = logging.getLogger("okx_market")
    okx_logger.setLevel(getattr(logging, config.log_level, logging.INFO))


# 全局配置实例
_global_config: Optional[OKXConfig] = None


def get_config() -> OKXConfig:
    """获取全局配置实例"""
    global _global_config
    if _global_config is None:
        _global_config = load_config_from_env()
        setup_logging(_global_config)
    return _global_config


def update_config(**kwargs) -> None:
    """更新配置"""
    global _global_config
    config = get_config()
    
    for key, value in kwargs.items():
        if hasattr(config, key):
            setattr(config, key, value)
            logger.info(f"配置已更新: {key} = {value}")
        else:
            logger.warning(f"未知的配置项: {key}")


def get_default_symbols() -> Dict[str, str]:
    """获取默认的热门交易对"""
    return {
        "BTC": "BTC-USDT",
        "ETH": "ETH-USDT", 
        "SOL": "SOL-USDT",
        "ADA": "ADA-USDT",
        "DOT": "DOT-USDT",
        "LINK": "LINK-USDT",
        "UNI": "UNI-USDT",
        "LTC": "LTC-USDT",
        "BCH": "BCH-USDT",
        "XRP": "XRP-USDT",
        "AVAX": "AVAX-USDT",
        "MATIC": "MATIC-USDT",
        "ATOM": "ATOM-USDT",
        "FTM": "FTM-USDT",
        "NEAR": "NEAR-USDT"
    }


def get_supported_timeframes() -> Dict[str, str]:
    """获取支持的时间周期"""
    return {
        "1m": "1分钟",
        "3m": "3分钟", 
        "5m": "5分钟",
        "15m": "15分钟",
        "30m": "30分钟",
        "1H": "1小时",
        "2H": "2小时",
        "4H": "4小时",
        "6H": "6小时",
        "12H": "12小时",
        "1D": "1天",
        "1W": "1周",
        "1M": "1月",
        "3M": "3月",
        "6M": "6月",
        "1Y": "1年"
    }


def validate_timeframe(timeframe: str) -> bool:
    """验证时间周期是否有效"""
    return timeframe in get_supported_timeframes()


def validate_symbol(symbol: str) -> bool:
    """验证交易对格式是否有效"""
    if not symbol:
        return False
    
    # 基本格式检查
    symbol = symbol.upper().strip()
    
    # 检查是否为热门币种简写
    if symbol in get_default_symbols():
        return True
    
    # 检查是否为完整交易对格式
    if "-" in symbol:
        parts = symbol.split("-")
        if len(parts) == 2 and all(part.isalpha() and len(part) >= 2 for part in parts):
            return True
    
    # 检查是否为有效的币种名称（可以添加USDT后缀）
    if symbol.isalpha() and len(symbol) >= 2:
        return True
    
    return False


def get_config_summary() -> Dict[str, Any]:
    """获取配置摘要"""
    config = get_config()
    
    return {
        "api_config": {
            "base_url": config.base_url,
            "timeout": config.timeout,
            "max_retries": config.max_retries
        },
        "rate_limit": {
            "requests_per_window": config.rate_limit_requests,
            "window_seconds": config.rate_limit_window
        },
        "data_limits": {
            "default_limit": config.default_limit,
            "max_limit": config.max_limit,
            "default_timeframe": config.default_timeframe
        },
        "monitoring": {
            "check_interval": config.monitor_interval,
            "max_alerts": config.max_alerts
        },
        "caching": {
            "enabled": config.enable_cache,
            "expire_seconds": config.cache_expire_seconds
        }
    }