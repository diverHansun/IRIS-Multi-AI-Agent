"""
OKX Market Data Tools

提供市场数据获取和处理功能
"""

import logging
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
import json

from .client import OKXMarketClient, OKXAPIError

logger = logging.getLogger(__name__)


class MarketDataTools:
    """市场数据工具类"""
    
    def __init__(self, client: Optional[OKXMarketClient] = None):
        """
        初始化市场数据工具
        
        Args:
            client: OKX客户端实例，如果为None则自动创建
        """
        self.client = client or OKXMarketClient()
        
        # 常用交易对映射
        self.popular_pairs = {
            "BTC": "BTC-USDT",
            "ETH": "ETH-USDT", 
            "SOL": "SOL-USDT",
            "ADA": "ADA-USDT",
            "DOT": "DOT-USDT",
            "LINK": "LINK-USDT",
            "UNI": "UNI-USDT",
            "LTC": "LTC-USDT",
            "BCH": "BCH-USDT",
            "XRP": "XRP-USDT"
        }
    
    def normalize_symbol(self, symbol: str) -> str:
        """
        标准化交易对符号
        
        Args:
            symbol: 输入的交易对符号
            
        Returns:
            标准化后的交易对符号
        """
        symbol = symbol.upper().strip()
        
        # 如果是常用币种简写，转换为完整交易对
        if symbol in self.popular_pairs:
            return self.popular_pairs[symbol]
            
        # 如果没有交易对格式，默认添加USDT
        if '-' not in symbol and 'USDT' not in symbol:
            symbol = f"{symbol}-USDT"
            
        return symbol
    
    def get_price(self, symbol: str) -> Dict[str, Any]:
        """
        获取指定交易对的实时价格
        
        Args:
            symbol: 交易对符号
            
        Returns:
            价格信息字典
        """
        try:
            inst_id = self.normalize_symbol(symbol)
            ticker = self.client.get_ticker(inst_id)
            
            if not ticker:
                return {"error": f"未找到交易对 {inst_id} 的数据"}
            
            # 解析ticker数据
            price_info = {
                "symbol": inst_id,
                "price": float(ticker.get('last', 0)),
                "bid": float(ticker.get('bidPx', 0)),
                "ask": float(ticker.get('askPx', 0)),
                "volume_24h": float(ticker.get('vol24h', 0)),
                "change_24h": float(ticker.get('change24h', 0)),
                "change_pct_24h": float(ticker.get('changePct24h', 0)) * 100,
                "high_24h": float(ticker.get('high24h', 0)),
                "low_24h": float(ticker.get('low24h', 0)),
                "timestamp": int(ticker.get('ts', 0)),
                "update_time": datetime.fromtimestamp(int(ticker.get('ts', 0)) / 1000).strftime('%Y-%m-%d %H:%M:%S')
            }
            
            return price_info
            
        except OKXAPIError as e:
            logger.error(f"获取价格数据失败: {str(e)}")
            return {"error": str(e)}
        except Exception as e:
            logger.error(f"处理价格数据时发生错误: {str(e)}")
            return {"error": f"数据处理错误: {str(e)}"}
    
    def get_multiple_prices(self, symbols: List[str]) -> Dict[str, Dict[str, Any]]:
        """
        批量获取多个交易对的价格
        
        Args:
            symbols: 交易对符号列表
            
        Returns:
            价格信息字典，键为交易对符号
        """
        results = {}
        
        try:
            # 获取所有现货ticker
            all_tickers = self.client.get_ticker(inst_type="SPOT")
            
            # 创建ticker字典方便查找
            ticker_dict = {ticker.get('instId'): ticker for ticker in all_tickers}
            
            for symbol in symbols:
                inst_id = self.normalize_symbol(symbol)
                ticker = ticker_dict.get(inst_id)
                
                if ticker:
                    results[symbol] = {
                        "symbol": inst_id,
                        "price": float(ticker.get('last', 0)),
                        "change_24h": float(ticker.get('change24h', 0)),
                        "change_pct_24h": float(ticker.get('changePct24h', 0)) * 100,
                        "volume_24h": float(ticker.get('vol24h', 0)),
                        "update_time": datetime.fromtimestamp(int(ticker.get('ts', 0)) / 1000).strftime('%Y-%m-%d %H:%M:%S')
                    }
                else:
                    results[symbol] = {"error": f"未找到交易对 {inst_id} 的数据"}
                    
        except Exception as e:
            logger.error(f"批量获取价格数据失败: {str(e)}")
            for symbol in symbols:
                results[symbol] = {"error": str(e)}
                
        return results
    
    def get_kline_data(self, symbol: str, timeframe: str = "1D", limit: int = 100) -> Dict[str, Any]:
        """
        获取K线数据
        
        Args:
            symbol: 交易对符号
            timeframe: 时间周期 (1m, 5m, 15m, 30m, 1H, 4H, 1D, 1W)
            limit: 数据条数
            
        Returns:
            K线数据
        """
        try:
            inst_id = self.normalize_symbol(symbol)
            candles = self.client.get_candles(inst_id, bar=timeframe, limit=limit)
            
            if not candles:
                return {"error": f"未找到交易对 {inst_id} 的K线数据"}
            
            # 处理K线数据
            processed_candles = []
            for candle in candles:
                processed_candles.append({
                    "timestamp": int(candle[0]),
                    "datetime": datetime.fromtimestamp(int(candle[0]) / 1000).strftime('%Y-%m-%d %H:%M:%S'),
                    "open": float(candle[1]),
                    "high": float(candle[2]),
                    "low": float(candle[3]),
                    "close": float(candle[4]),
                    "volume": float(candle[5]),
                    "volume_ccy": float(candle[6]),
                    "confirmed": candle[8] == "1"
                })
            
            # 按时间正序排列
            processed_candles.reverse()
            
            return {
                "symbol": inst_id,
                "timeframe": timeframe,
                "count": len(processed_candles),
                "data": processed_candles
            }
            
        except OKXAPIError as e:
            logger.error(f"获取K线数据失败: {str(e)}")
            return {"error": str(e)}
        except Exception as e:
            logger.error(f"处理K线数据时发生错误: {str(e)}")
            return {"error": f"数据处理错误: {str(e)}"}
    
    def get_orderbook(self, symbol: str, depth: int = 20) -> Dict[str, Any]:
        """
        获取订单簿数据
        
        Args:
            symbol: 交易对符号
            depth: 订单簿深度
            
        Returns:
            订单簿数据
        """
        try:
            inst_id = self.normalize_symbol(symbol)
            orderbook = self.client.get_orderbook(inst_id, sz=depth)
            
            if not orderbook:
                return {"error": f"未找到交易对 {inst_id} 的订单簿数据"}
            
            # 处理订单簿数据
            bids = [[float(bid[0]), float(bid[1])] for bid in orderbook.get('bids', [])]
            asks = [[float(ask[0]), float(ask[1])] for ask in orderbook.get('asks', [])]
            
            return {
                "symbol": inst_id,
                "timestamp": int(orderbook.get('ts', 0)),
                "update_time": datetime.fromtimestamp(int(orderbook.get('ts', 0)) / 1000).strftime('%Y-%m-%d %H:%M:%S'),
                "bids": bids,  # [价格, 数量]
                "asks": asks,  # [价格, 数量]
                "bid_price": bids[0][0] if bids else 0,
                "ask_price": asks[0][0] if asks else 0,
                "spread": asks[0][0] - bids[0][0] if bids and asks else 0
            }
            
        except OKXAPIError as e:
            logger.error(f"获取订单簿数据失败: {str(e)}")
            return {"error": str(e)}
        except Exception as e:
            logger.error(f"处理订单簿数据时发生错误: {str(e)}")
            return {"error": f"数据处理错误: {str(e)}"}
    
    def get_market_summary(self, symbols: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        获取市场概览
        
        Args:
            symbols: 交易对列表，如果为None则使用热门交易对
            
        Returns:
            市场概览数据
        """
        if symbols is None:
            symbols = list(self.popular_pairs.keys())
            
        try:
            price_data = self.get_multiple_prices(symbols)
            
            # 统计市场数据
            total_pairs = len(symbols)
            gainers = []
            losers = []
            
            for symbol, data in price_data.items():
                if "error" not in data:
                    change_pct = data.get("change_pct_24h", 0)
                    if change_pct > 0:
                        gainers.append((symbol, change_pct))
                    elif change_pct < 0:
                        losers.append((symbol, abs(change_pct)))
            
            # 排序
            gainers.sort(key=lambda x: x[1], reverse=True)
            losers.sort(key=lambda x: x[1], reverse=True)
            
            return {
                "total_pairs": total_pairs,
                "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "top_gainers": gainers[:5],
                "top_losers": losers[:5],
                "market_data": price_data
            }
            
        except Exception as e:
            logger.error(f"获取市场概览失败: {str(e)}")
            return {"error": f"获取市场概览失败: {str(e)}"}
    
    def search_instruments(self, keyword: str, inst_type: str = "SPOT") -> List[Dict[str, Any]]:
        """
        搜索交易对
        
        Args:
            keyword: 搜索关键词
            inst_type: 产品类型
            
        Returns:
            匹配的交易对列表
        """
        try:
            instruments = self.client.get_instruments(inst_type)
            keyword = keyword.upper()
            
            matches = []
            for inst in instruments:
                inst_id = inst.get('instId', '')
                if keyword in inst_id:
                    matches.append({
                        "symbol": inst_id,
                        "base_currency": inst.get('baseCcy', ''),
                        "quote_currency": inst.get('quoteCcy', ''),
                        "state": inst.get('state', ''),
                        "min_size": inst.get('minSz', ''),
                        "tick_size": inst.get('tickSz', '')
                    })
                    
            return matches[:20]  # 限制返回结果数量
            
        except Exception as e:
            logger.error(f"搜索交易对失败: {str(e)}")
            return []