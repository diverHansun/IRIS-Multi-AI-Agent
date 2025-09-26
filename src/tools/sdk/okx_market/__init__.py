"""
OKX Market API Integration Module

该模块提供OKX交易所的市场数据获取功能，包括：
- 实时价格数据获取
- K线数据获取  
- 交易对信息查询
- 价格监控和分析
- 与LangChain Agent的集成

主要组件:
- OKXMarketClient: OKX API客户端封装
- MarketDataTools: 市场数据获取工具
- PriceMonitor: 价格监控功能
- langchain_tools: LangChain工具集成
"""

from .client import OKXMarketClient
from .market_data import MarketDataTools
from .price_monitor import PriceMonitor
from .adapter import (
    get_crypto_price,
    get_market_data,
    get_kline_data,
    analyze_price_trend,
    create_price_alert,
    check_price_alerts,
    get_market_summary,
    search_crypto_symbols,
    get_available_okx_tools
)

__version__ = "1.0.0"
__author__ = "Agent Demo"

__all__ = [
    "OKXMarketClient",
    "MarketDataTools", 
    "PriceMonitor",
    "get_crypto_price",
    "get_market_data", 
    "get_kline_data",
    "analyze_price_trend",
    "create_price_alert",
    "check_price_alerts",
    "get_market_summary",
    "search_crypto_symbols",
    "get_available_okx_tools"
]