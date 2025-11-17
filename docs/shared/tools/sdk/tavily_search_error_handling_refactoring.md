# Tavily Search 错误处理重构文档

## 概述

本文档记录了 Tavily Search SDK 的企业级错误处理重构方案，遵循 KISS、DRY、SOLID 原则。

## 重构目标

1. **统一错误处理**：所有 9 个 Tavily 工具使用一致的错误处理逻辑
2. **自动重试机制**：对瞬时错误（网络、超时）自动重试，指数退避
3. **详细错误分类**：14 种错误类型，提供针对性建议
4. **结构化响应**：标准化的错误响应格式，便于调试和监控
5. **对话不中断**：返回错误信息而非抛出异常

## 架构设计

### 核心组件

#### 1. TavilyErrorType (枚举)
```python
class TavilyErrorType(Enum):
    CONFIGURATION_ERROR = "configuration_error"
    TIMEOUT = "timeout"
    CONNECT_TIMEOUT = "connect_timeout"
    READ_TIMEOUT = "read_timeout"
    NETWORK_ERROR = "network_error"
    SSL_ERROR = "ssl_error"
    PROXY_ERROR = "proxy_error"
    AUTHENTICATION_ERROR = "authentication_error"  # 401
    FORBIDDEN = "forbidden"  # 403
    NOT_FOUND = "not_found"  # 404
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"  # 429
    SERVER_ERROR = "server_error"  # 5xx
    BAD_REQUEST = "bad_request"  # 400
    VALIDATION_ERROR = "validation_error"
    TOO_MANY_REDIRECTS = "too_many_redirects"
    UNKNOWN_ERROR = "unknown_error"
```

#### 2. TavilyErrorResponse (数据类)
```python
@dataclass
class TavilyErrorResponse:
    status: str = "error"
    error_type: str = ""
    message: str = ""
    suggestion: str = ""
    details: Optional[Dict[str, Any]] = None
    retry_after: Optional[int] = None
```

#### 3. RetryStrategy (重试策略)
```python
class RetryStrategy:
    # 可重试的异常类型
    RETRIABLE_EXCEPTIONS = (
        Timeout, ConnectTimeout, ReadTimeout,
        ConnectionError, ProxyError
    )

    # 指数退避算法
    def calculate_backoff_delay(attempt, initial=1.0, factor=2.0, max=60.0):
        return min(initial * (factor ** attempt), max)

    # 执行带重试的操作
    def execute_with_retry(func, max_retries=3, ...):
        # 自动重试逻辑
```

#### 4. TavilyErrorHandler (错误处理器)
```python
class TavilyErrorHandler:
    @staticmethod
    def handle_timeout_error(error, timeout_seconds) -> Dict

    @staticmethod
    def handle_http_error(error: HTTPError) -> Dict

    @staticmethod
    def handle_network_error(error: Exception) -> Dict

    @staticmethod
    def handle_validation_error(error: ValueError) -> Dict

    @classmethod
    def handle_error(error, operation, timeout_seconds) -> Dict
```

## 重构模式

### 重构前（旧代码）
```python
@tool
def tavily_search_basic(query: str) -> Dict[str, Any]:
    try:
        config = get_config()
        if not config.is_available():
            return {"error": "API key not configured"}

        search_tool = TavilySearch(...)
        results = search_tool.invoke({"query": query})
        return results

    except Exception as e:
        logger.error(f"Search failed: {e}")
        return {"error": f"Search failed: {str(e)}"}
```

**问题**：
- ❌ 粗粒度异常捕获
- ❌ 无重试机制
- ❌ 错误消息缺少上下文
- ❌ 未区分错误类型

### 重构后（新代码）
```python
@tool
def tavily_search_basic(query: str) -> Dict[str, Any]:
    config = get_config()

    # 配置检查
    if not config.is_available():
        return TavilyErrorHandler.handle_configuration_error()

    try:
        logger.info(f"Executing Tavily search: {query}")

        # 内部函数用于重试
        def _do_search():
            search_tool = TavilySearch(...)
            return search_tool.invoke({"query": query})

        # 自动重试
        results = RetryStrategy.execute_with_retry(
            _do_search,
            max_retries=config.api.max_retries,
            initial_delay=config.api.retry_delay,
            operation_name="tavily_search_basic"
        )

        return create_success_response(results, operation="search")

    except Exception as e:
        return TavilyErrorHandler.handle_error(
            e,
            operation="search",
            timeout_seconds=config.api.timeout
        )
```

**改进**：
- ✅ 统一配置检查
- ✅ 自动重试机制（3次，指数退避）
- ✅ 详细错误分类和建议
- ✅ 结构化错误响应
- ✅ 保留调用上下文（operation, timeout）

## 9 个工具重构清单

### Search Tools (3个)
- [x] `tavily_search_basic` - 基础搜索
- [x] `tavily_search_advanced` - 高级搜索
- [x] `tavily_search_news` - 新闻搜索

### Extract Tools (2个)
- [ ] `tavily_extract_url` - 单 URL 提取
- [ ] `tavily_extract_batch` - 批量 URL 提取

### Map Tools (2个)
- [ ] `tavily_map_website` - 网站映射
- [ ] `tavily_map_with_filter` - 过滤映射

### Crawl Tools (2个)
- [ ] `tavily_crawl_basic` - 基础爬取
- [ ] `tavily_crawl_targeted` - 目标爬取

## 错误响应示例

### 1. 配置错误
```json
{
  "status": "error",
  "error_type": "configuration_error",
  "message": "Tavily API key not configured",
  "suggestion": "Set TAVILY_API_KEY environment variable with your API key"
}
```

### 2. 超时错误
```json
{
  "status": "error",
  "error_type": "read_timeout",
  "message": "Request timed out after 30s waiting for response",
  "suggestion": "Try a simpler query or increase timeout setting",
  "details": {"timeout_seconds": 30}
}
```

### 3. Rate Limit 错误
```json
{
  "status": "error",
  "error_type": "rate_limit_exceeded",
  "message": "API rate limit exceeded",
  "suggestion": "Wait before retrying, or upgrade your Tavily plan for higher limits",
  "details": {"status_code": 429},
  "retry_after": 60
}
```

### 4. 网络错误
```json
{
  "status": "error",
  "error_type": "network_error",
  "message": "Network connection failed",
  "suggestion": "Check internet connection, firewall, and DNS settings"
}
```

### 5. 认证错误
```json
{
  "status": "error",
  "error_type": "authentication_error",
  "message": "Invalid or missing API key",
  "suggestion": "Verify TAVILY_API_KEY environment variable is correct"
}
```

## 重试逻辑说明

### 可重试的错误
- **网络超时**：ConnectTimeout, ReadTimeout, Timeout
- **连接错误**：ConnectionError
- **代理错误**：ProxyError
- **HTTP 429**：Rate Limit (使用 Retry-After 头)
- **HTTP 5xx**：服务器错误

### 不可重试的错误
- **HTTP 401**：认证错误（API key 无效）
- **HTTP 403**：权限错误
- **HTTP 400**：参数错误
- **HTTP 404**：资源不存在
- **SSL错误**：证书验证失败

### 重试参数
```python
max_retries = 3  # 最大重试次数
initial_delay = 1.0  # 初始延迟（秒）
backoff_factor = 2.0  # 退避因子
max_delay = 60.0  # 最大延迟（秒）

# 实际延迟序列
# 第1次重试：1.0s
# 第2次重试：2.0s
# 第3次重试：4.0s
```

## 设计原则遵循

### KISS (简单至上)
- 统一的错误处理模式
- 清晰的函数命名和结构
- 避免过度抽象

### DRY (杜绝重复)
- 单一的错误处理器类
- 统一的重试策略
- 可重用的错误响应结构

### SOLID
- **单一职责**：每个类只负责一项任务
  - `RetryStrategy`：重试逻辑
  - `TavilyErrorHandler`：错误处理
  - `TavilyErrorResponse`：响应结构
- **开放封闭**：易于扩展新错误类型，无需修改核心逻辑
- **依赖倒置**：工具函数依赖抽象的错误处理接口

### YAGNI (精益求精)
- 只处理实际遇到的错误类型
- 不实现暂不需要的功能（如缓存、metrics）

## 测试策略

### 单元测试覆盖

1. **TavilyErrorHandler 测试**
   - 测试所有错误类型的分类
   - 验证错误消息和建议的正确性
   - 测试 HTTP 状态码映射

2. **RetryStrategy 测试**
   - 测试指数退避计算
   - 测试可重试/不可重试错误判断
   - 测试最大重试次数限制

3. **工具函数测试**
   - 模拟各种异常场景
   - 验证重试行为
   - 确保返回结构化响应

### 集成测试

1. **真实 API 调用测试**（需要 API key）
   - 正常搜索流程
   - 超时场景
   - Rate limit 场景

2. **错误场景测试**
   - 无效 API key
   - 网络断开
   - 服务不可用

## 性能影响

### 重试机制开销
- **最坏情况**：3次重试 = 1s + 2s + 4s = 7s 额外延迟
- **典型情况**：无重试，零开销
- **优化**：只对可恢复错误重试

### 内存开销
- 错误处理器：静态类，无内存开销
- 错误响应：每次 ~200 bytes
- 整体影响：可忽略

## 向后兼容性

### 响应格式变化
**旧格式**：
```json
{"error": "Search failed: timeout"}
```

**新格式**：
```json
{
  "status": "error",
  "error_type": "timeout",
  "message": "Search timed out after 30s",
  "suggestion": "Try a simpler query"
}
```

### 兼容性处理
- 新格式包含 `status: "error"` 字段
- 客户端可通过检查 `status` 或 `error_type` 字段判断错误
- 建议客户端升级以利用详细错误信息

## 监控和日志

### 日志级别
- **INFO**：正常操作（搜索开始）
- **WARNING**：重试尝试
- **ERROR**：最终失败（包含完整堆栈）

### 日志示例
```
INFO: Executing Tavily search: "python tutorials"
WARNING: tavily_search_basic attempt 1 failed: ConnectTimeout. Retrying in 1.0s...
WARNING: tavily_search_basic attempt 2 failed: ConnectTimeout. Retrying in 2.0s...
ERROR: tavily_search_basic failed after 3 attempts: ConnectTimeout('...')
ERROR: Tavily search error: ConnectTimeout: ... [full traceback]
```

## 未来改进方向

1. **Metrics 收集**
   - 错误率统计
   - 重试成功率
   - 平均响应时间

2. **缓存机制**
   - 相同查询的结果缓存
   - 降低 API 调用频率

3. **断路器模式**
   - 快速失败机制
   - 避免级联故障

4. **自适应超时**
   - 根据历史响应时间调整
   - 动态优化等待时间

## 参考资料

- [requests 异常文档](https://requests.readthedocs.io/en/latest/user/quickstart/#errors-and-exceptions)
- [指数退避算法](https://en.wikipedia.org/wiki/Exponential_backoff)
- [HTTP 状态码规范](https://developer.mozilla.org/en-US/docs/Web/HTTP/Status)
- [Tavily API 文档](https://docs.tavily.com/)
