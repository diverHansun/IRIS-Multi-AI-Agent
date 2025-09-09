"""
工具适配器模块

将LangChain BaseTool转换为智谱AI Function Calling格式。
"""

import json
import logging
import asyncio
from typing import Dict, Any, List
from langchain_core.tools import BaseTool

# 导入工具模块
from ..tools.calculate.math_tools import add_numbers, calculate_math
from ..tools.search.search_tools import SEARCH_TOOLS
from ..tools.search.tavily_search_tool import get_available_tavily_tools
from ..tools.amap import get_available_amap_tools

logger = logging.getLogger(__name__)


def convert_tool_to_function(tool: BaseTool) -> Dict[str, Any]:
    """
    将LangChain BaseTool转换为智谱AI Function Calling格式。
    
    Args:
        tool: LangChain BaseTool实例
        
    Returns:
        符合智谱AI Function Calling格式的字典
    """
    schema = {}
    try:
        if hasattr(tool, "args_schema") and tool.args_schema is not None:
            # 检查args_schema是否为字典（MCP工具的情况）
            if isinstance(tool.args_schema, dict):
                schema = tool.args_schema
            # 检查args_schema是否有schema()方法（标准LangChain工具的情况）
            elif hasattr(tool.args_schema, "schema") and callable(getattr(tool.args_schema, "schema")):
                schema = tool.args_schema.schema()
            else:
                # 单参数回退：统一使用 input 字段
                schema = {
                    "type": "object",
                    "properties": {"input": {"type": "string", "description": tool.description or ""}},
                    "required": ["input"],
                }
        else:
            # 单参数回退：统一使用 input 字段
            schema = {
                "type": "object",
                "properties": {"input": {"type": "string", "description": tool.description or ""}},
                "required": ["input"],
            }
    except Exception as e:
        logger.warning(f"工具 {tool.name} 参数schema提取失败: {e}")
        schema = {"type": "object", "properties": {}, "additionalProperties": True}

    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description or tool.name,
            "parameters": schema or {"type": "object", "properties": {}},
        },
    }


def execute_tool_with_arguments(tool: BaseTool, arguments: Dict[str, Any]) -> Any:
    """
    使用参数执行工具。
    
    Args:
        tool: LangChain BaseTool实例
        arguments: 工具调用参数
        
    Returns:
        工具执行结果
    """
    try:
        # 添加详细的日志记录
        logger.debug(f"准备执行工具: {tool.name}")
        logger.debug(f"工具参数: {arguments}")
        logger.debug(f"工具是否有args_schema: {hasattr(tool, 'args_schema')}")
        if hasattr(tool, 'args_schema'):
            logger.debug(f"args_schema类型: {type(tool.args_schema)}")
        
        # 特别处理字符串参数
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
                logger.debug(f"解析JSON参数: {arguments}")
            except json.JSONDecodeError:
                # 如果不是有效的JSON，创建一个包含input字段的字典
                arguments = {"input": arguments}
                logger.debug(f"创建input参数: {arguments}")
        
        # 检查是否为BaseTool实例（具有args_schema）
        is_base_tool = hasattr(tool, 'args_schema') and tool.args_schema is not None
        logger.debug(f"是否为BaseTool实例: {is_base_tool}")
        
        if is_base_tool:
            # 对于BaseTool实例，使用tool_input参数
            # 检查args_schema是否为字典（MCP工具的情况）
            if isinstance(tool.args_schema, dict):
                schema = tool.args_schema
            # 检查args_schema是否有schema()方法（标准LangChain工具的情况）
            elif hasattr(tool.args_schema, "schema") and callable(getattr(tool.args_schema, "schema")):
                schema = tool.args_schema.schema()
            else:
                schema = {
                    "type": "object",
                    "properties": {},
                    "additionalProperties": True
                }
            
            logger.debug(f"Schema: {schema}")
            required_params = schema.get('required', [])
            logger.debug(f"必需参数: {required_params}")
            
            # 特别处理MCP工具 - 当使用JSON schema时，必须传递字典参数
            if isinstance(schema, dict) and schema.get('type') == 'object':
                # 确保传递给MCP工具的参数是字典格式
                if not isinstance(arguments, dict):
                    # 如果参数不是字典，尝试转换
                    if len(required_params) == 1:
                        # 如果只有一个必需参数，创建包含该参数的字典
                        arguments = {required_params[0]: arguments}
                        logger.debug(f"转换参数为字典: {arguments}")
                    else:
                        # 多个必需参数，无法自动转换
                        logger.warning(f"无法自动转换参数，必需参数: {required_params}")
                        arguments = {}
                else:
                    # 参数已经是字典，检查是否需要特殊处理
                    logger.debug(f"参数已经是字典: {arguments}")
            elif isinstance(arguments, dict) and len(arguments) == 1 and len(required_params) == 1:
                # 对于只有一个参数的工具，如果参数是字典且只有一个键，且该键匹配必需参数
                if list(arguments.keys())[0] == required_params[0]:
                    # 直接传递参数值
                    logger.debug(f"直接传递参数值: {list(arguments.values())[0]}")
                    return tool.run(list(arguments.values())[0])
            
            # 传递完整参数字典
            logger.debug(f"传递完整参数字典: {arguments}")
            return tool.run(arguments)
        else:
            # 对于使用@tool装饰器的函数，使用原始逻辑
            # 若 arguments 是 dict 且仅 1 个键，直接将其值传入 tool.run/async_run
            if isinstance(arguments, dict) and len(arguments) == 1:
                single_value = next(iter(arguments.values()))
                # 如果是字符串且看起来像JSON，尝试解析
                if isinstance(single_value, str):
                    try:
                        parsed = json.loads(single_value)
                        if isinstance(parsed, (dict, list)):
                            arguments = parsed
                            logger.debug(f"解析嵌套JSON参数: {arguments}")
                    except json.JSONDecodeError:
                        pass
                else:
                    arguments = single_value
                    logger.debug(f"使用单值参数: {arguments}")
            
            # 优先调用 tool.func（如果存在）
            if hasattr(tool, 'func') and callable(tool.func):
                logger.debug("调用 tool.func")
                if asyncio.iscoroutinefunction(tool.func):
                    return asyncio.run(tool.func(**arguments)) if isinstance(arguments, dict) else asyncio.run(tool.func(arguments))
                else:
                    return tool.func(**arguments) if isinstance(arguments, dict) else tool.func(arguments)
            
            # 否则调用 tool.run/tool.arun
            if asyncio.iscoroutinefunction(getattr(tool, '_run', None)):
                return asyncio.run(tool._run(**arguments)) if isinstance(arguments, dict) else asyncio.run(tool._run(arguments))
            else:
                return tool.run(**arguments) if isinstance(arguments, dict) else tool.run(arguments)
        
    except Exception as e:
        logger.error(f"执行工具 {tool.name} 时出错: {e}", exc_info=True)
        # 根据错误类型判断是否可重试
        error_str = str(e).lower()
        retryable = any(keyword in error_str for keyword in [
            "timeout", "network", "connection", "临时", "暂时", "retry"
        ])
        
        return {
            "error": str(e), 
            "type": "tool_runtime", 
            "retryable": retryable,
            "tool_name": tool.name
        }


async def execute_tool_with_arguments_async(tool: BaseTool, arguments: Dict[str, Any]) -> Any:
    """
    使用参数异步执行工具。
    
    Args:
        tool: LangChain BaseTool实例
        arguments: 工具调用参数
        
    Returns:
        工具执行结果
    """
    try:
        # 添加详细的日志记录
        logger.debug(f"准备异步执行工具: {tool.name}")
        logger.debug(f"工具参数: {arguments}")
        logger.debug(f"工具是否有args_schema: {hasattr(tool, 'args_schema')}")
        if hasattr(tool, 'args_schema'):
            logger.debug(f"args_schema类型: {type(tool.args_schema)}")
        
        # 特别处理字符串参数
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
                logger.debug(f"解析JSON参数: {arguments}")
            except json.JSONDecodeError:
                # 如果不是有效的JSON，创建一个包含input字段的字典
                arguments = {"input": arguments}
                logger.debug(f"创建input参数: {arguments}")
        
        # 检查是否为BaseTool实例（具有args_schema）
        is_base_tool = hasattr(tool, 'args_schema') and tool.args_schema is not None
        logger.debug(f"是否为BaseTool实例: {is_base_tool}")
        
        if is_base_tool:
            # 对于BaseTool实例，使用tool_input参数
            # 检查args_schema是否为字典（MCP工具的情况）
            if isinstance(tool.args_schema, dict):
                schema = tool.args_schema
            # 检查args_schema是否有schema()方法（标准LangChain工具的情况）
            elif hasattr(tool.args_schema, "schema") and callable(getattr(tool.args_schema, "schema")):
                schema = tool.args_schema.schema()
            else:
                schema = {
                    "type": "object",
                    "properties": {},
                    "additionalProperties": True
                }
            
            logger.debug(f"Schema: {schema}")
            required_params = schema.get('required', [])
            logger.debug(f"必需参数: {required_params}")
            
            # 特别处理MCP工具 - 当使用JSON schema时，必须传递字典参数
            if isinstance(schema, dict) and schema.get('type') == 'object':
                # 确保传递给MCP工具的参数是字典格式
                if not isinstance(arguments, dict):
                    # 如果参数不是字典，尝试转换
                    if len(required_params) == 1:
                        # 如果只有一个必需参数，创建包含该参数的字典
                        arguments = {required_params[0]: arguments}
                        logger.debug(f"转换参数为字典: {arguments}")
                    else:
                        # 多个必需参数，无法自动转换
                        logger.warning(f"无法自动转换参数，必需参数: {required_params}")
                        arguments = {}
                else:
                    # 参数已经是字典，检查是否需要特殊处理
                    logger.debug(f"参数已经是字典: {arguments}")
            elif isinstance(arguments, dict) and len(arguments) == 1 and len(required_params) == 1:
                # 对于只有一个参数的工具，如果参数是字典且只有一个键，且该键匹配必需参数
                if list(arguments.keys())[0] == required_params[0]:
                    # 直接传递参数值
                    logger.debug(f"直接传递参数值: {list(arguments.values())[0]}")
                    if asyncio.iscoroutinefunction(getattr(tool, '_arun', None)):
                        result = await tool.arun(list(arguments.values())[0])
                    else:
                        result = tool.run(list(arguments.values())[0])
                    return result
            
            # 传递完整参数字典
            # 对于MCP工具，使用异步调用
            logger.debug(f"传递完整参数字典: {arguments}")
            if asyncio.iscoroutinefunction(getattr(tool, '_arun', None)):
                result = await tool.arun(arguments)
            else:
                result = tool.run(arguments)
        else:
            # 对于使用@tool装饰器的函数，使用原始逻辑
            # 若 arguments 是 dict 且仅 1 个键，直接将其值传入 tool.run/async_run
            if isinstance(arguments, dict) and len(arguments) == 1:
                single_value = next(iter(arguments.values()))
                # 如果是字符串且看起来像JSON，尝试解析
                if isinstance(single_value, str):
                    try:
                        parsed = json.loads(single_value)
                        if isinstance(parsed, (dict, list)):
                            arguments = parsed
                            logger.debug(f"解析嵌套JSON参数: {arguments}")
                    except json.JSONDecodeError:
                        pass
                else:
                    arguments = single_value
                    logger.debug(f"使用单值参数: {arguments}")
            
            # 优先调用 tool.func（如果存在）
            if hasattr(tool, 'func') and callable(tool.func):
                logger.debug("调用 tool.func")
                if asyncio.iscoroutinefunction(tool.func):
                    result = await tool.func(**arguments) if isinstance(arguments, dict) else await tool.func(arguments)
                else:
                    result = tool.func(**arguments) if isinstance(arguments, dict) else tool.func(arguments)
            else:
                # 否则调用 tool.arun/tool._arun
                logger.debug("调用 tool.arun/tool._run")
                if asyncio.iscoroutinefunction(getattr(tool, '_arun', None)):
                    result = await tool.arun(**arguments) if isinstance(arguments, dict) else await tool.arun(arguments)
                elif asyncio.iscoroutinefunction(getattr(tool, '_run', None)):
                    result = await tool._run(**arguments) if isinstance(arguments, dict) else await tool._run(arguments)
                else:
                    result = tool.run(**arguments) if isinstance(arguments, dict) else tool.run(arguments)
        
        # 验证结果
        if result is None:
            logger.warning(f"工具 {tool.name} 返回空结果")
        else:
            logger.debug(f"工具执行成功，结果: {result}")
        
        return result
        
    except Exception as e:
        logger.error(f"执行工具 {tool.name} 时出错: {e}", exc_info=True)
        # 根据错误类型判断是否可重试
        error_str = str(e).lower()
        retryable = any(keyword in error_str for keyword in [
            "timeout", "network", "connection", "临时", "暂时", "retry"
        ])
        
        return {
            "error": str(e), 
            "type": "tool_runtime", 
            "retryable": retryable,
            "tool_name": tool.name
        }


def get_all_available_tools() -> List[BaseTool]:
    """
    获取所有可用的工具
    
    Returns:
        BaseTool列表
    """
    tools = []
    
    # 添加数学工具
    tools.extend([add_numbers, calculate_math])
    
    # 添加Tavily搜索工具（优先）
    tavily_tools = get_available_tavily_tools()
    if tavily_tools:
        tools.extend(tavily_tools)
    else:
        # 添加备用搜索工具
        tools.extend(SEARCH_TOOLS)
    
    # 添加高德地图工具
    amap_tools = get_available_amap_tools()
    if amap_tools:
        tools.extend(amap_tools)
    
    # 添加OKX加密货币工具（如果可用）
    try:
        from ..tools.okx_market import get_available_okx_tools
        okx_tools = get_available_okx_tools()
        if okx_tools:
            tools.extend(okx_tools)
    except ImportError:
        logger.warning("OKX工具未安装")
    
    # 添加Notion工具（如果可用）
    try:
        from ..tools.notion import get_notion_tools
        notion_tools = get_notion_tools()
        if notion_tools:
            tools.extend(notion_tools)
    except ImportError:
        logger.warning("Notion工具未安装")
    
    logger.info(f" 已加载 {len(tools)} 个工具")
    return tools