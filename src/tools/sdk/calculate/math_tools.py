"""
数学工具模块

提供基础的数学计算工具。
"""

from langchain_core.tools import tool
from typing import Annotated
import re
from typing import List
from langchain_core.tools import BaseTool

@tool
def add_numbers(expression: Annotated[str, "数学表达式，例如：'15 + 25' 或 '15和25相加'"]) -> str:
    """解析并计算两个数字的加法运算"""
    try:
        # 从输入中提取数字
        numbers = re.findall(r'-?\d+\.?\d*', expression)
        if len(numbers) < 2:
            return f"无法从 '{expression}' 中提取到两个数字"
        
        # 转换为数字并计算
        a = float(numbers[0])
        b = float(numbers[1])
        result = a + b
        
        # 如果结果是整数，则显示为整数
        if result.is_integer():
            a = int(a) if a.is_integer() else a
            b = int(b) if b.is_integer() else b
            result = int(result)
        
        return f"{a} + {b} = {result}"
    except Exception as e:
        return f"计算错误: {str(e)}"

@tool  
def calculate_math(expression: Annotated[str, "基础数学表达式，支持加减乘除"]) -> str:
    """计算基础数学表达式（加减乘除）"""
    try:
        # 简单的安全计算，只允许数字和基本运算符
        allowed_chars = set('0123456789+-*/.() ')
        if not all(c in allowed_chars for c in expression):
            return "表达式包含不允许的字符"
        
        # 计算结果
        result = eval(expression)
        return f"{expression} = {result}"
    except Exception as e:
        return f"计算错误: {str(e)}" 

def get_available_math_tools() -> List[BaseTool]:
    """获取可用的数学工具列表"""
    return [add_numbers, calculate_math]