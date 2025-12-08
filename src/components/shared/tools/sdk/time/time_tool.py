import datetime
import logging
from typing import Dict, Any

import pytz
from langchain_core.tools import tool

logger = logging.getLogger(__name__)


def get_current_time(timezone: str = "Asia/Shanghai") -> Dict[str, Any]:
    """
    获取当前日期和时间的工具函数
    
    Args:
        timezone (str): 时区，默认为"Asia/Shanghai"
        
    Returns:
        Dict[str, Any]: 包含当前日期和时间信息的字典
    """
    try:
        logger.debug("Fetching current time for timezone: %s", timezone)
        # 获取指定时区的当前时间
        tz = pytz.timezone(timezone)
        current_time = datetime.datetime.now(tz)
        
        # 格式化时间信息
        time_info = {
            "datetime": current_time.strftime("%Y-%m-%d %H:%M:%S"),
            "date": current_time.strftime("%Y-%m-%d"),
            "time": current_time.strftime("%H:%M:%S"),
            "weekday": current_time.strftime("%A"),
            "timezone": timezone,
            "timestamp": current_time.timestamp()
        }
        
        logger.debug("Current time fetched for timezone %s: %s", timezone, time_info["datetime"])
        return time_info
    except Exception as e:
        logger.error("Failed to fetch current time for timezone %s: %s", timezone, e, exc_info=True)
        return {"error": f"获取时间时发生错误: {str(e)}"}


@tool
def get_current_time_tool(timezone: str = "Asia/Shanghai") -> Dict[str, Any]:
    """
    获取当前日期和时间，支持指定时区
    
    Args:
        timezone (str): 时区，例如：Asia/Shanghai, America/New_York, Europe/London。默认为Asia/Shanghai
        
    Returns:
        Dict[str, Any]: 包含当前日期和时间信息的字典
    """
    return get_current_time(timezone)
