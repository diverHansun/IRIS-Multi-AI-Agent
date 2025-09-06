# Patch 模块

这个模块包含对第三方库的扩展和修复，使其能够更好地适应项目需求。

## 模块列表

### json_react_parser.py
**功能**: 自定义的 ReAct 输出解析器，支持 JSON 格式的工具输入

**问题解决**: 
解决了 "String tool inputs are not allowed when using tools with JSON schema args_schema" 错误。

**使用场景**:
当 MCP 工具定义了 `args_schema`（JSON Schema）时，工具调用必须传入一个字典而不是字符串。默认的 ReAct 解析器会将 LLM 生成的 JSON 字符串作为字符串传递给工具，导致 StructuredTool 检查输入类型时抛出错误。

**解决方案**:
创建了 `JSONReActSingleInputOutputParser` 类，继承自 `ReActSingleInputOutputParser`，重写了 `parse` 方法，添加了 JSON 解析逻辑。当检测到 JSON 格式的输入时，自动将其解析为字典。

**导入方式**:
```python
# 直接从 patch 模块导入
from src.patch.json_react_parser import JSONReActSingleInputOutputParser

# 或者从项目根目录导入
from src import JSONReActSingleInputOutputParser
```

**使用示例**:
```python
parser = JSONReActSingleInputOutputParser()

# 解析 JSON 输入
result = parser.parse("""Action: mcp_list_directory
Action Input: {"path": "data"}""")
# result.tool_input 会是 {'path': 'data'}

# 解析字符串输入
result = parser.parse("""Action: tavily_search
Action Input: "Python tutorial" """)
# result.tool_input 会是 "Python tutorial"
```

## 使用建议

1. 在需要处理 JSON 格式工具输入的 Agent 中使用此解析器
2. 确保在虚拟环境中运行代码
3. 验证所有依赖包已正确安装