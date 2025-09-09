"""
搜索工具模块

统一管理各种搜索工具，包括 Tavily 高级搜索和通用搜索工具。
"""

# 安全导入搜索工具，处理可能的导入错误
try:
    from .search_tools import SEARCH_TOOLS, web_search_tool, web_search_detailed, get_webpage_content
except ImportError as e:
    print(f"警告: 无法导入通用搜索工具: {e}")
    SEARCH_TOOLS = []
    web_search_tool = None
    web_search_detailed = None
    get_webpage_content = None

# 安全导入Tavily搜索工具，处理可能的导入错误
try:
    from .tavily_search_tool import TAVILY_TOOLS, get_available_tavily_tools
except ImportError as e:
    print(f"警告: 无法导入Tavily搜索工具: {e}")
    TAVILY_TOOLS = []
    get_available_tavily_tools = lambda: []

# 导出所有搜索工具
__all__ = [
    # 通用搜索工具
    'SEARCH_TOOLS',
    'web_search_tool',
    'web_search_detailed', 
    'get_webpage_content',
    
    # Tavily 搜索工具
    'TAVILY_TOOLS',
    'get_available_tavily_tools',
]

def get_all_search_tools():
    """获取所有可用的搜索工具"""
    tools = []
    
    # 添加通用搜索工具
    if SEARCH_TOOLS:
        tools.extend(SEARCH_TOOLS)
    
    # 添加 Tavily 工具（如果可用）
    try:
        tavily_tools = get_available_tavily_tools()
        if tavily_tools:
            tools.extend(tavily_tools)
    except Exception as e:
        print(f"警告: 获取Tavily工具时出错: {e}")
    
    return tools