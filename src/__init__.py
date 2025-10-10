"""
Muti-AI-Agent - 基于多LLM的智能代理

这是一个使用LangChain框架和多LLM的智能代理示例项目。
"""

__version__ = "3.0.0"
__author__ = "diverHansun"

import sys
import os
from pathlib import Path

# 直接从当前包导入config（这是安全的，不会造成循环导入）
from .config import settings

# 延迟导入，避免循环导入问题
def build_zhipu_agent(*args, **kwargs):
    """延迟导入的build_zhipu_agent函数"""
    try:
        from .agents.langchain.zhipu_agent import build_zhipu_agent as _build_zhipu_agent  # type: ignore
        return _build_zhipu_agent(*args, **kwargs)
    except ImportError as e:
        raise ImportError(f"无法导入build_zhipu_agent: {e}") from e

def build_simple_zhipu_chat(*args, **kwargs):
    """延迟导入的build_simple_zhipu_chat函数"""
    try:
        from .agents.langchain.zhipu_agent import build_simple_zhipu_chat as _build_simple_zhipu_chat  # type: ignore
        return _build_simple_zhipu_chat(*args, **kwargs)
    except ImportError as e:
        raise ImportError(f"无法导入build_simple_zhipu_chat: {e}") from e

def get_json_react_parser():
    """延迟导入的JSONReActSingleInputOutputParser"""
    from .components.langchain.parsers.json_react_output_parser import JSONReActSingleInputOutputParser
    return JSONReActSingleInputOutputParser

__all__ = [
    "settings",
    "build_zhipu_agent", 
    "build_simple_zhipu_chat",
    "get_json_react_parser"
] 
