from typing import List
from langchain_core.tools import BaseTool
from .time_tool import get_current_time_tool


def get_available_time_tools() -> List[BaseTool]:
    """
    获取所有可用的时间工具
    
    Returns:
        List[BaseTool]: 时间工具列表
    """
    tools = []
    
    # 添加获取当前时间的工具
    tools.append(get_current_time_tool)
    
    return tools