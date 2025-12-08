# Tools模块日志改进计划

## 概览

- **项目总logging覆盖率**: 26.2% (73/279文件)
- **Tools模块logging覆盖率**: 46.6% (34/73文件)
- **缺少logging的关键文件**: 8+个
- **需要改进的异常处理**: 12+处

---

## 扫描结果总结

### Tools模块文件分布

```
tools/
├── __init__.py                          # 无日志
├── unified_manager.py                   # 良好（有详细日志）
├── adapter/
│   ├── functioncalling_adapter.py       # 良好
│   └── __init__.py
├── connector/
│   ├── manager.py                       # 关键，缺日志
│   ├── crawl4ai/
│   │   ├── client.py                    # 网络日志良好
│   │   ├── adapter.py
│   │   ├── config.py
│   │   ├── errors.py
│   │   └── __init__.py
│   └── __init__.py
├── mcp/
│   ├── manager.py                       # 良好
│   ├── tool_adapter.py                  # 关键，缺日志
│   ├── types.py
│   ├── errors.py
│   ├── config_loader.py                 # 已改进
│   └── __init__.py
├── sdk/
│   ├── manager.py                       # 关键，缺日志
│   ├── __init__.py
│   ├── amap/
│   │   ├── adapter.py                   # 有日志
│   │   ├── client.py                    # 有日志
│   │   ├── formatter.py                 # 缺日志
│   │   ├── validator.py                 # 缺日志
│   │   ├── constants.py
│   │   ├── exceptions.py
│   │   └── ...
│   ├── calculate/
│   │   └── math_tools.py                # 关键，缺日志
│   ├── notion/
│   │   ├── client.py                    # 有日志
│   │   ├── adapter.py
│   │   ├── sync_utils.py                # 缺日志
│   │   ├── config.py                    # 缺日志
│   │   └── ...
│   ├── time/
│   │   ├── time_tool.py                 # 缺日志
│   │   └── adapter.py
│   ├── okx_market/
│   │   └── client.py                    # 缺日志
│   ├── search/
│   │   └── duckduckgo_search_tools.py   # 有日志
│   └── ...
└── strategy/
    └── ...
```

---

## 优先级 1 - 关键管理器（立即改进）

### 1.1 sdk/manager.py - SDKToolManager

**问题**: 工具加载时无日志，无法追踪工具初始化情况

**文件位置**: `src/components/shared/tools/sdk/manager.py`

**需要改进的地方**:
- [ ] 添加 logging 导入和初始化
- [ ] 在工具加载时添加 info 日志（如 Amap、Notion、OKX 工具加载）
- [ ] 异常捕获改为 logger.error（特别是 Notion 工具可选但应记录跳过原因）
- [ ] 工具聚合完成时添加 info 日志统计工具数量

**日志改进示例**:
```python
logger = logging.getLogger(__name__)

def load_tools(self):
    all_tools = []

    # Amap 工具
    logger.info("Loading Amap tools...")
    try:
        amap_tools = get_available_amap_tools()
        logger.info(f"Loaded {len(amap_tools)} Amap tools")
        all_tools.extend(amap_tools)
    except Exception as e:
        logger.warning(f"Failed to load Amap tools: {e}")

    # 其他工具类似处理...

    logger.info(f"Total tools loaded: {len(all_tools)}")
```

---

### 1.2 connector/manager.py - ConnectorToolManager

**问题**: 工具初始化和重新加载时无日志，无法追踪连接器状态

**文件位置**: `src/components/shared/tools/connector/manager.py`

**需要改进的地方**:
- [ ] 添加 logging 导入和初始化
- [ ] `_initialize_tools()` 添加 info/debug 日志
- [ ] `reload_tools()` 添加 info 日志（显示重新加载的工具数）
- [ ] 异常捕获改为 logger.error，不仅返回字典

**日志改进示例**:
```python
logger = logging.getLogger(__name__)

def _initialize_tools(self):
    logger.debug(f"Initializing {len(self._tool_configs)} connector tools")
    for config in self._tool_configs:
        try:
            logger.debug(f"Loading tool: {config.get('name')}")
            # 初始化逻辑
        except Exception as e:
            logger.error(f"Failed to initialize tool {config.get('name')}: {e}")

def reload_tools(self):
    logger.info("Reloading all connector tools...")
    try:
        old_count = len(self._tools)
        self._tools.clear()
        self._initialize_tools()
        new_count = len(self._tools)
        logger.info(f"Tools reloaded: {old_count} -> {new_count}")
    except Exception as e:
        logger.error(f"Failed to reload tools: {e}")
```

---

### 1.3 mcp/tool_adapter.py - MCPToolAdapter

**问题**: 工具适配、命名过滤等操作无日志，无法追踪工具修改

**文件位置**: `src/components/shared/tools/mcp/tool_adapter.py`

**需要改进的地方**:
- [ ] 添加 logging 导入和初始化
- [ ] `apply_naming_and_filter()` 添加 debug 日志
- [ ] `_safe_set_tool_name()` 异常改为 logger.warning
- [ ] `schema_summary()` 异常改为 logger.warning

**日志改进示例**:
```python
logger = logging.getLogger(__name__)

def apply_naming_and_filter(self, tools):
    logger.debug(f"Applying naming and filter to {len(tools)} tools")
    filtered_tools = []
    for tool in tools:
        try:
            logger.debug(f"Processing tool: {tool.name}")
            self._safe_set_tool_name(tool)
            if self._should_include_tool(tool):
                filtered_tools.append(tool)
        except Exception as e:
            logger.warning(f"Failed to process tool {tool.name}: {e}")
    logger.debug(f"Filtering complete: {len(filtered_tools)} tools remaining")
    return filtered_tools

def _safe_set_tool_name(self, tool):
    try:
        # 设置工具名称
        pass
    except Exception as e:
        logger.warning(f"Failed to set tool name: {e}")
```

---

## 优先级 2 - 工具执行层（高优先级）

### 2.1 calculate/math_tools.py

**问题**: 异常仅返回错误字符串，无日志记录

**文件位置**: `src/components/shared/tools/sdk/calculate/math_tools.py`

**需要改进的地方**:
- [ ] 添加 logging 导入和初始化
- [ ] `add_numbers()` 异常改为 logger.error
- [ ] `calculate_math()` 异常改为 logger.error

---

### 2.2 time/time_tool.py

**问题**: 时间获取操作无日志

**文件位置**: `src/components/shared/tools/sdk/time/time_tool.py`

**需要改进的地方**:
- [ ] 添加 logging 导入和初始化
- [ ] 时间操作添加 debug 日志
- [ ] 异常捕获添加 error 日志

---

### 2.3 notion/sync_utils.py

**问题**: 同步操作无日志，无法追踪同步进度

**文件位置**: `src/components/shared/tools/sdk/notion/sync_utils.py`

**需要改进的地方**:
- [ ] 添加 logging 导入和初始化
- [ ] 同步开始/完成时添加 info 日志
- [ ] 同步过程中添加 debug 日志
- [ ] 异常捕获添加 error 日志

---

## 优先级 3 - 连接器和第三方集成（中优先级）

### 3.1 connector/crawl4ai/client.py

**问题**: Crawl4AI API调用缺少日志

**需要改进的地方**:
- [ ] API调用前后添加 debug 日志
- [ ] 异常捕获添加 error 日志

---

### 3.2 okx_market/client.py

**问题**: OKX API调用缺少日志

**需要改进的地方**:
- [ ] API调用前后添加 debug 日志
- [ ] 异常捕获添加 error 日志

---

### 3.3 amap/formatter.py & validator.py

**问题**: 数据处理函数缺少日志

**需要改进的地方**:
- [ ] 添加 logging 导入和初始化
- [ ] 复杂操作添加 debug 日志
- [ ] 异常添加 warning/error 日志

---

## 优先级 4 - 配置和初始化（低优先级）

### 4.1 notion/config.py 和 connector/crawl4ai/config.py

**问题**: 配置加载时缺少日志

**需要改进的地方**:
- [ ] 配置加载的 info/debug 日志
- [ ] 验证失败的 error 日志

---

## 日志级别使用指南

| 级别 | 使用场景 | 示例 |
|------|---------|------|
| DEBUG | 详细的执行步骤、参数值 | 工具初始化参数、API调用请求 |
| INFO | 重要的业务事件、统计信息 | 工具加载完成、同步开始/完成 |
| WARNING | 降级处理、可选功能不可用 | 可选工具加载失败、非关键异常 |
| ERROR | 关键操作失败、异常捕获 | 工具初始化失败、API错误 |

---

## 改进方案模板

### 基础模板

```python
import logging

logger = logging.getLogger(__name__)

def operation():
    """执行一个操作"""
    logger.debug("Starting operation with params: ...")

    try:
        # 执行操作
        result = do_something()
        logger.debug(f"Operation succeeded: {result}")
        return result
    except SpecificError as e:
        logger.error(f"Specific error occurred: {e}", exc_info=True)
        raise
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        raise
```

### 带初始化统计的模板

```python
def load_multiple_tools():
    """加载多个工具集"""
    logger.info("Starting to load tools...")

    all_tools = []
    stats = {"total": 0, "success": 0, "failed": 0}

    tool_sources = [
        ("Amap", load_amap_tools),
        ("Notion", load_notion_tools),
        ("OKX", load_okx_tools),
    ]

    for name, loader in tool_sources:
        logger.info(f"Loading {name} tools...")
        try:
            tools = loader()
            all_tools.extend(tools)
            stats["success"] += 1
            logger.info(f"Loaded {len(tools)} {name} tools")
        except Exception as e:
            logger.warning(f"Failed to load {name} tools: {e}")
            stats["failed"] += 1
        stats["total"] += 1

    logger.info(f"Tool loading complete: {stats['success']}/{stats['total']} succeeded, "
                f"total tools: {len(all_tools)}")
    return all_tools
```

---

## 预期收益

### 可观测性提升
- 能够追踪工具加载的完整过程
- 能够识别哪些工具加载失败及失败原因
- 能够监控异常发生的频率和类型

### 调试效率提升
- 使用 `--debug` 时能看到详细的工具操作过程
- 用户报告问题时能通过日志快速定位
- 性能问题时能通过日志识别瓶颈

### 维护成本降低
- 新加入的工具使用统一的日志模式
- 易于理解的执行流程日志
- 异常原因清晰可追踪

---

## 实施步骤

1. 第一阶段：改进优先级1的3个关键管理器
2. 第二阶段：改进优先级2的3个工具执行层
3. 第三阶段：改进优先级3-4的其他模块
4. 验证：运行 `python main.py --debug` 验证日志输出

---

## 文件检查清单

- [ ] sdk/manager.py - 添加工具加载日志
- [ ] connector/manager.py - 添加初始化和重新加载日志
- [ ] mcp/tool_adapter.py - 添加工具适配日志
- [ ] calculate/math_tools.py - 添加计算异常日志
- [ ] time/time_tool.py - 添加时间操作日志
- [ ] notion/sync_utils.py - 添加同步操作日志
- [ ] connector/crawl4ai/client.py - 添加爬虫API日志
- [ ] okx_market/client.py - 添加OKX API日志
- [ ] amap/formatter.py - 添加格式化日志
- [ ] amap/validator.py - 添加验证日志

