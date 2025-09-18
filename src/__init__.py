"""
Muti-AI-Agent - 基于多LLM的智能代理

这是一个使用LangChain框架和多LLM的智能代理示例项目。
"""

__version__ = "1.0.0"
__author__ = "diverHansun"

import sys
import os
from pathlib import Path

# 直接从当前包导入config
from .config import settings
from .agents.zhipu_agent import build_zhipu_agent, build_simple_zhipu_chat

# 导出 patch 模块中的解析器
from .parsers.json_react_output_parser import JSONReActSingleInputOutputParser

__all__ = [
    "settings",
    "build_zhipu_agent", 
    "build_simple_zhipu_chat",
    "JSONReActSingleInputOutputParser"
] 
