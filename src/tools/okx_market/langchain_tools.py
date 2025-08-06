"""
OKX Market LangChain Tools Integration

将OKX市场数据功能集成到LangChain工具系统中，供AI Agent使用
"""

import json
import logging
from typing import Dict, List, Optional, Any, Union
from langchain_core.tools import tool

from .market_data import MarketDataTools
from .price_monitor import PriceMonitor, PriceAlert, AlertType
from .client import OKXMarketClient

logger = logging.getLogger(__name__)

# 全局实例
_market_data_tools = None
_price_monitor = None


def get_market_data_tools() -> MarketDataTools:
    """获取市场数据工具实例（单例模式）"""
    global _market_data_tools
    if _market_data_tools is None:
        _market_data_tools = MarketDataTools()
    return _market_data_tools


def get_price_monitor() -> PriceMonitor:
    """获取价格监控器实例（单例模式）"""
    global _price_monitor
    if _price_monitor is None:
        _price_monitor = PriceMonitor(get_market_data_tools())
    return _price_monitor


@tool
def get_crypto_price(symbol: str) -> str:
    """
    获取指定加密货币的实时价格信息
    
    Args:
        symbol: 加密货币符号，支持简写（如BTC、ETH）或完整交易对（如BTC-USDT）
        
    Returns:
        包含价格、涨跌幅、成交量等信息的JSON字符串
        
    Examples:
        get_crypto_price("BTC") -> 获取比特币价格
        get_crypto_price("ETH-USDT") -> 获取以太坊对USDT的价格
    """
    try:
        tools = get_market_data_tools()
        price_data = tools.get_price(symbol)
        
        if "error" in price_data:
            return f"Failed to get price: {price_data['error']}"
        
        # 格式化输出
        result = f"""
{price_data['symbol']} 实时行情

当前价格: ${price_data['price']:,.6f}
24小时涨跌: {price_data['change_pct_24h']:+.2f}% (${price_data['change_24h']:+,.6f})
24小时最高: ${price_data['high_24h']:,.6f}
24小时最低: ${price_data['low_24h']:,.6f}
24小时成交量: {price_data['volume_24h']:,.2f}
买一价: ${price_data['bid']:,.6f}
卖一价: ${price_data['ask']:,.6f}
更新时间: {price_data['update_time']}
        """.strip()
        
        return result
        
    except Exception as e:
        logger.error(f"获取加密货币价格失败: {str(e)}")
        return f"获取价格信息时发生错误: {str(e)}"


@tool
def get_market_data(input_string: str) -> str:
    """
    批量获取多个加密货币的市场数据
    
    Args:
        input_string: 输入参数，格式："符号1,符号2,符号3"或"符号1,符号2,符号3 格式类型"，如"BTC,ETH,SOL"或"BTC,ETH,SOL json"
        
    Returns:
        市场数据的格式化字符串
        
    Examples:
        get_market_data("BTC,ETH,SOL") -> 获取比特币、以太坊、Solana的价格数据
    """
    try:
        # 解析输入参数
        parts = input_string.strip().split(' ', 1)
        symbols = parts[0]
        format_type = parts[1] if len(parts) > 1 else "table"
        
        # 解析符号列表
        symbol_list = [s.strip() for s in symbols.split(",")]
        
        tools = get_market_data_tools()
        market_data = tools.get_multiple_prices(symbol_list)
        
        if format_type.lower() == "json":
            return json.dumps(market_data, indent=2, ensure_ascii=False)
        
        # 表格格式输出
        result = "加密货币市场数据\n\n"
        result += f"{'符号':<12} {'价格':<15} {'24H涨跌':<12} {'成交量':<15}\n"
        result += "─" * 60 + "\n"
        
        for symbol, data in market_data.items():
            if "error" not in data:
                price = f"${data['price']:,.6f}"
                change = f"{data['change_pct_24h']:+.2f}%"
                volume = f"{data['volume_24h']:,.0f}"
                result += f"{symbol:<12} {price:<15} {change:<12} {volume:<15}\n"
            else:
                result += f"{symbol:<12} {'错误':<15} {'':<12} {'':<15}\n"
        
        return result
        
    except Exception as e:
        logger.error(f"获取市场数据失败: {str(e)}")
        return f"获取市场数据时发生错误: {str(e)}"


@tool
def get_kline_data(input_string: str) -> str:
    """
    获取K线数据用于技术分析
    
    Args:
        input_string: 输入参数，格式："符号 时间周期 数量"，如"BTC 1H 10"
        
    Returns:
        K线数据的格式化字符串
        
    Examples:
        get_kline_data("BTC 1H 10") -> 获取比特币最近10个小时的K线数据
    """
    try:
        # 解析输入参数
        parts = input_string.strip().split()
        if len(parts) < 1:
            return "输入格式错误，请使用格式：符号 时间周期 数量，如：BTC 1H 10"
        
        symbol = parts[0]
        timeframe = parts[1] if len(parts) > 1 else "1D"
        limit = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 20
        
        tools = get_market_data_tools()
        kline_data = tools.get_kline_data(symbol, timeframe, min(limit, 100))
        
        if "error" in kline_data:
            return f"获取K线数据失败: {kline_data['error']}"
        
        result = f"{kline_data['symbol']} K线数据 ({timeframe})\n\n"
        result += f"{'时间':<20} {'开盘':<12} {'最高':<12} {'最低':<12} {'收盘':<12} {'成交量':<15}\n"
        result += "─" * 90 + "\n"
        
        # 只显示最近的几条数据
        display_data = kline_data['data'][-min(limit, 10):]
        
        for candle in display_data:
            time_str = candle['datetime']
            result += f"{time_str:<20} {candle['open']:<12.6f} {candle['high']:<12.6f} {candle['low']:<12.6f} {candle['close']:<12.6f} {candle['volume']:<15.2f}\n"
        
        if len(kline_data['data']) > 10:
            result += f"\n... 还有 {len(kline_data['data']) - 10} 条数据\n"
        
        return result
        
    except Exception as e:
        logger.error(f"获取K线数据失败: {str(e)}")
        return f"获取K线数据时发生错误: {str(e)}"


@tool
def analyze_price_trend(input_string: str) -> str:
    """
    分析价格趋势和技术指标
    
    Args:
        input_string: 输入参数，格式："符号 时间周期 周期数"，如"BTC 1H 24"
        
    Returns:
        趋势分析结果
        
    Examples:
        analyze_price_trend("BTC 1H 24") -> 分析比特币最近24小时的趋势
    """
    try:
        # 解析输入参数
        parts = input_string.strip().split()
        if len(parts) < 1:
            return "输入格式错误，请使用格式：符号 时间周期 周期数，如：BTC 1H 24"
        
        symbol = parts[0]
        timeframe = parts[1] if len(parts) > 1 else "1H"
        periods = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 24
        
        monitor = get_price_monitor()
        analysis = monitor.analyze_trend(symbol, timeframe, periods)
        
        if "error" in analysis:
            return f"趋势分析失败: {analysis['error']}"
        
        # 中文趋势描述
        trend_desc = {
            "bullish": "看涨",
            "bearish": "看跌", 
            "sideways": "横盘"
        }
        
        result = f"""
{analysis['symbol']} 趋势分析报告

趋势方向: {trend_desc.get(analysis['trend'], analysis['trend'])}
置信度: {analysis['confidence'] * 100:.0f}%
短期均线: ${analysis['short_ma']:,.6f}
长期均线: ${analysis['long_ma']:,.6f}
价格变化: {analysis['change_pct']:+.2f}%
波动率: {analysis['volatility']:.2f}%

关键价位:
   支撑位: ${analysis['support_level']:,.6f}
   阻力位: ${analysis['resistance_level']:,.6f}
   当前价: ${analysis['current_price']:,.6f}

分析时间: {analysis['analysis_time']}
时间周期: {timeframe} × {periods}
        """.strip()
        
        return result
        
    except Exception as e:
        logger.error(f"趋势分析失败: {str(e)}")
        return f"进行趋势分析时发生错误: {str(e)}"


@tool
def create_price_alert(input_string: str) -> str:
    """
    创建价格预警
    
    Args:
        input_string: 输入参数，格式："符号 预警类型 阈值 消息"，如"BTC price_above 50000 比特币突破5万美元"
        
    Returns:
        创建结果
        
    Examples:
        create_price_alert("BTC price_above 50000 比特币突破5万美元") -> 创建价格上涨预警
        create_price_alert("ETH change_below 5 以太坊跌幅超过5%") -> 创建跌幅预警
    """
    try:
        # 解析输入参数
        parts = input_string.strip().split(' ', 3)  # 最多分割成4部分
        if len(parts) < 3:
            return "输入格式错误，请使用格式：符号 预警类型 阈值 [消息]，如：BTC price_above 50000 比特币突破5万美元"
        
        symbol = parts[0]
        alert_type = parts[1]
        try:
            threshold = float(parts[2])
        except ValueError:
            return "阈值必须是数字"
        
        message = parts[3] if len(parts) > 3 else ""
        
        # 验证预警类型
        alert_type_map = {
            "price_above": AlertType.PRICE_ABOVE,
            "price_below": AlertType.PRICE_BELOW,
            "change_above": AlertType.CHANGE_ABOVE,
            "change_below": AlertType.CHANGE_BELOW,
            "volume_spike": AlertType.VOLUME_SPIKE
        }
        
        if alert_type not in alert_type_map:
            return f"不支持的预警类型: {alert_type}。支持的类型: {', '.join(alert_type_map.keys())}"
        
        # 生成预警ID
        alert_id = f"{symbol}_{alert_type}_{int(threshold)}_{len(get_price_monitor().alerts)}"
        
        # 默认消息
        if not message:
            if alert_type == "price_above":
                message = f"{symbol} 价格突破 ${threshold:,.2f}"
            elif alert_type == "price_below":
                message = f"{symbol} 价格跌破 ${threshold:,.2f}"
            elif alert_type == "change_above":
                message = f"{symbol} 24小时涨幅超过 {threshold:.1f}%"
            elif alert_type == "change_below":
                message = f"{symbol} 24小时跌幅超过 {threshold:.1f}%"
            else:
                message = f"{symbol} 触发预警条件"
        
        # 创建预警
        alert = PriceAlert(
            id=alert_id,
            symbol=symbol,
            alert_type=alert_type_map[alert_type],
            threshold=threshold,
            message=message
        )
        
        monitor = get_price_monitor()
        success = monitor.add_alert(alert)
        
        if success:
            return f"预警创建成功！\n\n预警ID: {alert_id}\n符号: {symbol}\n类型: {alert_type}\n阈值: {threshold}\n消息: {message}"
        else:
            return "预警创建失败"
            
    except Exception as e:
        logger.error(f"创建价格预警失败: {str(e)}")
        return f"创建预警时发生错误: {str(e)}"


@tool
def check_price_alerts() -> str:
    """
    检查所有价格预警状态
    
    Returns:
        预警检查结果
    """
    try:
        monitor = get_price_monitor()
        triggered_alerts = monitor.check_alerts()
        
        if not triggered_alerts:
            alerts_list = monitor.get_alerts()
            if not alerts_list:
                return "暂无设置的价格预警"
            else:
                return f"已检查 {len(alerts_list)} 个预警，暂无触发"
        
        result = f"发现 {len(triggered_alerts)} 个预警触发！\n\n"
        
        for alert in triggered_alerts:
            result += f"预警触发: {alert['message']}\n"
            result += f"   符号: {alert['symbol']}\n"
            result += f"   当前值: {alert['current_value']}\n"
            result += f"   触发时间: {alert['timestamp']}\n\n"
        
        return result
        
    except Exception as e:
        logger.error(f"检查价格预警失败: {str(e)}")
        return f"检查预警时发生错误: {str(e)}"


@tool
def get_market_summary() -> str:
    """
    获取加密货币市场概览
    
    Returns:
        市场概览信息
    """
    try:
        tools = get_market_data_tools()
        summary = tools.get_market_summary()
        
        if "error" in summary:
            return f"获取市场概览失败: {summary['error']}"
        
        result = f"加密货币市场概览\n\n"
        result += f"更新时间: {summary['timestamp']}\n"
        result += f"监控币种: {summary['total_pairs']} 个\n\n"
        
        if summary['top_gainers']:
            result += "今日涨幅榜:\n"
            for symbol, change in summary['top_gainers']:
                result += f"   {symbol}: +{change:.2f}%\n"
            result += "\n"
        
        if summary['top_losers']:
            result += "今日跌幅榜:\n"
            for symbol, change in summary['top_losers']:
                result += f"   {symbol}: -{change:.2f}%\n"
            result += "\n"
        
        return result
        
    except Exception as e:
        logger.error(f"获取市场概览失败: {str(e)}")
        return f"获取市场概览时发生错误: {str(e)}"


@tool
def search_crypto_symbols(keyword: str) -> str:
    """
    搜索加密货币交易对
    
    Args:
        keyword: 搜索关键词
        
    Returns:
        匹配的交易对列表
    """
    try:
        tools = get_market_data_tools()
        matches = tools.search_instruments(keyword)
        
        if not matches:
            return f"未找到包含 '{keyword}' 的交易对"
        
        result = f"搜索结果 (关键词: {keyword})\n\n"
        result += f"{'交易对':<15} {'基础货币':<10} {'计价货币':<10} {'状态':<8}\n"
        result += "─" * 50 + "\n"
        
        for match in matches[:10]:  # 限制显示数量
            result += f"{match['symbol']:<15} {match['base_currency']:<10} {match['quote_currency']:<10} {match['state']:<8}\n"
        
        if len(matches) > 10:
            result += f"\n... 还有 {len(matches) - 10} 个结果\n"
        
        return result
        
    except Exception as e:
        logger.error(f"搜索交易对失败: {str(e)}")
        return f"搜索时发生错误: {str(e)}"


# 导出所有工具函数
__all__ = [
    "get_crypto_price",
    "get_market_data", 
    "get_kline_data",
    "analyze_price_trend",
    "create_price_alert",
    "check_price_alerts",
    "get_market_summary",
    "search_crypto_symbols"
]