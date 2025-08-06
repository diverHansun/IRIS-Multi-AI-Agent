"""
OKX Price Monitor

提供价格监控、预警和趋势分析功能
"""

import logging
from typing import Dict, List, Optional, Callable, Any
from datetime import datetime, timedelta
import threading
import time
from dataclasses import dataclass
from enum import Enum

from .market_data import MarketDataTools

logger = logging.getLogger(__name__)


class AlertType(Enum):
    """预警类型枚举"""
    PRICE_ABOVE = "price_above"      # 价格高于指定值
    PRICE_BELOW = "price_below"      # 价格低于指定值
    CHANGE_ABOVE = "change_above"    # 涨幅超过指定比例
    CHANGE_BELOW = "change_below"    # 跌幅超过指定比例
    VOLUME_SPIKE = "volume_spike"    # 成交量暴涨


@dataclass
class PriceAlert:
    """价格预警配置"""
    id: str
    symbol: str
    alert_type: AlertType
    threshold: float
    message: str
    is_active: bool = True
    triggered_count: int = 0
    last_triggered: Optional[datetime] = None
    callback: Optional[Callable] = None


class TrendAnalyzer:
    """趋势分析器"""
    
    @staticmethod
    def analyze_price_trend(kline_data: List[Dict]) -> Dict[str, Any]:
        """
        分析价格趋势
        
        Args:
            kline_data: K线数据列表
            
        Returns:
            趋势分析结果
        """
        if not kline_data or len(kline_data) < 3:
            return {"trend": "insufficient_data", "confidence": 0}
        
        # 提取收盘价
        closes = [float(candle["close"]) for candle in kline_data]
        
        # 计算移动平均线
        short_ma = sum(closes[-5:]) / min(5, len(closes))  # 短期均线
        long_ma = sum(closes[-10:]) / min(10, len(closes))  # 长期均线
        
        # 计算价格变化
        recent_change = (closes[-1] - closes[0]) / closes[0] * 100
        
        # 判断趋势
        if short_ma > long_ma and recent_change > 2:
            trend = "bullish"
            confidence = min(abs(recent_change) / 10, 1.0)
        elif short_ma < long_ma and recent_change < -2:
            trend = "bearish" 
            confidence = min(abs(recent_change) / 10, 1.0)
        else:
            trend = "sideways"
            confidence = 0.5
        
        # 计算波动率
        volatility = TrendAnalyzer._calculate_volatility(closes)
        
        # 支撑位和阻力位
        support_level = min(closes[-10:]) if len(closes) >= 10 else min(closes)
        resistance_level = max(closes[-10:]) if len(closes) >= 10 else max(closes)
        
        return {
            "trend": trend,
            "confidence": round(confidence, 2),
            "short_ma": round(short_ma, 6),
            "long_ma": round(long_ma, 6),
            "change_pct": round(recent_change, 2),
            "volatility": round(volatility, 2),
            "support_level": round(support_level, 6),
            "resistance_level": round(resistance_level, 6),
            "current_price": closes[-1]
        }
    
    @staticmethod
    def _calculate_volatility(prices: List[float]) -> float:
        """计算价格波动率"""
        if len(prices) < 2:
            return 0
            
        # 计算价格变化率
        returns = []
        for i in range(1, len(prices)):
            returns.append((prices[i] - prices[i-1]) / prices[i-1])
        
        # 计算标准差
        if not returns:
            return 0
            
        mean_return = sum(returns) / len(returns)
        variance = sum((r - mean_return) ** 2 for r in returns) / len(returns)
        volatility = variance ** 0.5 * 100  # 转换为百分比
        
        return volatility


class PriceMonitor:
    """价格监控器"""
    
    def __init__(self, market_data_tools: Optional[MarketDataTools] = None):
        """
        初始化价格监控器
        
        Args:
            market_data_tools: 市场数据工具实例
        """
        self.market_data = market_data_tools or MarketDataTools()
        self.alerts: Dict[str, PriceAlert] = {}
        self.is_monitoring = False
        self._monitor_thread = None
        self._stop_event = threading.Event()
        
    def add_alert(self, alert: PriceAlert) -> bool:
        """
        添加价格预警
        
        Args:
            alert: 预警配置
            
        Returns:
            是否添加成功
        """
        try:
            self.alerts[alert.id] = alert
            logger.info(f"添加价格预警: {alert.symbol} - {alert.alert_type.value}")
            return True
        except Exception as e:
            logger.error(f"添加价格预警失败: {str(e)}")
            return False
    
    def remove_alert(self, alert_id: str) -> bool:
        """
        移除价格预警
        
        Args:
            alert_id: 预警ID
            
        Returns:
            是否移除成功
        """
        if alert_id in self.alerts:
            del self.alerts[alert_id]
            logger.info(f"移除价格预警: {alert_id}")
            return True
        return False
    
    def get_alerts(self) -> List[Dict[str, Any]]:
        """获取所有预警配置"""
        return [
            {
                "id": alert.id,
                "symbol": alert.symbol,
                "alert_type": alert.alert_type.value,
                "threshold": alert.threshold,
                "message": alert.message,
                "is_active": alert.is_active,
                "triggered_count": alert.triggered_count,
                "last_triggered": alert.last_triggered.strftime('%Y-%m-%d %H:%M:%S') if alert.last_triggered else None
            }
            for alert in self.alerts.values()
        ]
    
    def check_alerts(self) -> List[Dict[str, Any]]:
        """
        检查所有预警条件
        
        Returns:
            触发的预警列表
        """
        triggered_alerts = []
        
        for alert in self.alerts.values():
            if not alert.is_active:
                continue
                
            try:
                # 获取当前价格数据
                price_data = self.market_data.get_price(alert.symbol)
                if "error" in price_data:
                    continue
                
                current_price = price_data["price"]
                change_pct_24h = price_data["change_pct_24h"]
                volume_24h = price_data["volume_24h"]
                
                is_triggered = False
                
                # 检查不同类型的预警条件
                if alert.alert_type == AlertType.PRICE_ABOVE and current_price > alert.threshold:
                    is_triggered = True
                elif alert.alert_type == AlertType.PRICE_BELOW and current_price < alert.threshold:
                    is_triggered = True
                elif alert.alert_type == AlertType.CHANGE_ABOVE and change_pct_24h > alert.threshold:
                    is_triggered = True
                elif alert.alert_type == AlertType.CHANGE_BELOW and change_pct_24h < -alert.threshold:
                    is_triggered = True
                elif alert.alert_type == AlertType.VOLUME_SPIKE and volume_24h > alert.threshold:
                    is_triggered = True
                
                if is_triggered:
                    alert.triggered_count += 1
                    alert.last_triggered = datetime.now()
                    
                    triggered_alert_info = {
                        "alert_id": alert.id,
                        "symbol": alert.symbol,
                        "alert_type": alert.alert_type.value,
                        "threshold": alert.threshold,
                        "current_value": current_price if alert.alert_type in [AlertType.PRICE_ABOVE, AlertType.PRICE_BELOW] else change_pct_24h,
                        "message": alert.message,
                        "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        "price_data": price_data
                    }
                    
                    triggered_alerts.append(triggered_alert_info)
                    
                    # 执行回调函数
                    if alert.callback:
                        try:
                            alert.callback(triggered_alert_info)
                        except Exception as e:
                            logger.error(f"执行预警回调失败: {str(e)}")
                            
            except Exception as e:
                logger.error(f"检查预警 {alert.id} 时发生错误: {str(e)}")
        
        return triggered_alerts
    
    def analyze_trend(self, symbol: str, timeframe: str = "1H", periods: int = 24) -> Dict[str, Any]:
        """
        分析价格趋势
        
        Args:
            symbol: 交易对符号
            timeframe: 时间周期
            periods: 分析周期数
            
        Returns:
            趋势分析结果
        """
        try:
            kline_data = self.market_data.get_kline_data(symbol, timeframe, periods)
            
            if "error" in kline_data:
                return {"error": kline_data["error"]}
            
            # 进行趋势分析
            trend_analysis = TrendAnalyzer.analyze_price_trend(kline_data["data"])
            trend_analysis["symbol"] = symbol
            trend_analysis["timeframe"] = timeframe
            trend_analysis["analysis_time"] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            return trend_analysis
            
        except Exception as e:
            logger.error(f"分析价格趋势失败: {str(e)}")
            return {"error": f"趋势分析失败: {str(e)}"}
    
    def get_market_alerts_summary(self, symbols: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        获取市场预警摘要
        
        Args:
            symbols: 要监控的交易对列表
            
        Returns:
            市场预警摘要
        """
        if symbols is None:
            symbols = list(set(alert.symbol for alert in self.alerts.values()))
        
        summary = {
            "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "total_alerts": len(self.alerts),
            "active_alerts": sum(1 for alert in self.alerts.values() if alert.is_active),
            "monitored_symbols": symbols,
            "recent_triggers": []
        }
        
        # 获取最近24小时的触发记录
        now = datetime.now()
        for alert in self.alerts.values():
            if alert.last_triggered and (now - alert.last_triggered) < timedelta(hours=24):
                summary["recent_triggers"].append({
                    "alert_id": alert.id,
                    "symbol": alert.symbol,
                    "alert_type": alert.alert_type.value,
                    "last_triggered": alert.last_triggered.strftime('%Y-%m-%d %H:%M:%S'),
                    "triggered_count": alert.triggered_count
                })
        
        return summary
    
    def start_monitoring(self, interval: int = 60) -> bool:
        """
        启动价格监控
        
        Args:
            interval: 检查间隔（秒）
            
        Returns:
            是否启动成功
        """
        if self.is_monitoring:
            return False
        
        self.is_monitoring = True
        self._stop_event.clear()
        
        def monitor_loop():
            while not self._stop_event.is_set():
                try:
                    triggered_alerts = self.check_alerts()
                    if triggered_alerts:
                        logger.info(f"触发了 {len(triggered_alerts)} 个价格预警")
                        
                except Exception as e:
                    logger.error(f"监控循环中发生错误: {str(e)}")
                
                # 等待指定间隔
                self._stop_event.wait(interval)
        
        self._monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
        self._monitor_thread.start()
        
        logger.info(f"价格监控已启动，检查间隔: {interval}秒")
        return True
    
    def stop_monitoring(self) -> bool:
        """
        停止价格监控
        
        Returns:
            是否停止成功
        """
        if not self.is_monitoring:
            return False
        
        self.is_monitoring = False
        self._stop_event.set()
        
        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=5)
        
        logger.info("价格监控已停止")
        return True