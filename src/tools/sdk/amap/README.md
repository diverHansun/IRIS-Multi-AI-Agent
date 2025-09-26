# 高德地图工具模块

## 概述

本模块基于高德地图Web服务API提供地点搜索和路径规划功能，专为中文环境优化，并集成到LangChain工具系统中。

## 模块结构

```
amap/
├── __init__.py              # 包初始化文件，导出所有模块
├── client.py                # 高德地图API客户端，负责API调用和错误处理
├── search.py                # 搜索相关工具函数
├── route.py                 # 路线规划相关工具函数
├── geocode.py               # 地理编码相关工具函数
├── formatter.py             # 结果格式化模块
├── validator.py             # 坐标验证模块
├── constants.py             # 常量定义模块
├── exceptions.py            # 异常定义模块
├── provider.py              # 服务提供者，整合各个模块功能
└── test.py                  # 测试模块
```

## 功能特性

### API调用优化
- 连接池支持，提高性能
- 重试机制，增强稳定性
- 超时设置优化
- 错误处理优化

### 搜索功能
- 地点搜索 (`amap_search_place`)
- 附近搜索 (`amap_search_nearby`)
- 城市内搜索 (`amap_search_in_city`)

### 路线规划功能
- 驾车路线规划 (`amap_route_driving`)
- 步行路线规划 (`amap_route_walking`)
- 公共交通路线规划 (`amap_route_transit`)
- 地铁路线规划 (`amap_route_subway`)
- 公交路线规划 (`amap_route_bus`)

## 安装和配置

1. 确保已安装所有依赖包：
   ```
   pip install -r requirements.txt
   ```

2. 在环境变量中设置高德地图API Key：
   ```
   AMAP_API_KEY=your_api_key_here
   ```

## 使用方法

### 基本使用

```python
from src.tools.amap import get_available_amap_tools

# 获取可用工具
tools = get_available_amap_tools()

# 使用工具
for tool in tools:
    if tool.name == "amap_search_place":
        result = tool.func("星巴克")
        print(result)
```

### 高级使用

```python
from src.tools.amap import AmapServiceProvider

# 创建服务提供者
provider = AmapServiceProvider(api_key="your_api_key")

# 直接调用API
if provider.is_available:
    # 搜索地点
    data = provider.search_places("星巴克")
    
    # 格式化结果
    result = provider.format_place_results(data, "星巴克")
    print(result)
```

## 工具列表

- `amap_search_place`: 搜索地点POI
- `amap_search_nearby`: 搜索附近地点
- `amap_search_in_city`: 在指定城市内搜索地点
- `amap_route_driving`: 规划驾车路线
- `amap_route_walking`: 规划步行路线
- `amap_route_transit`: 规划公共交通路线
- `amap_route_subway`: 规划地铁路线
- `amap_route_bus`: 规划公交路线

## 错误处理

模块定义了以下自定义异常：

- `AmapApiError`: 高德地图API基础异常
- `AmapApiRateLimitError`: 频率限制异常
- `AmapApiParamError`: 参数错误异常

## 测试

运行测试：
```python
from src.tools.amap.test import test_amap_tools

# 运行测试
test_amap_tools(api_key="your_api_key")
```

## 向后兼容性

为了保持向后兼容，原有的 `amap_search.py` 文件仍然可用，但建议使用新的模块结构。