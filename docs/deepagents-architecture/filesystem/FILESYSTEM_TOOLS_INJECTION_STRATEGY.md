# 文件系统工具注入策略设计

## 背景

当前系统支持两种文件系统:
1. **虚拟文件系统** (Virtual Filesystem) - 内存中的沙盒环境,完全隔离
2. **真实文件系统** (Real Filesystem) - 访问宿主机真实文件,需要安全控制

## 问题分析

### 当前问题
虚拟文件系统工具在runtime.py中注入,但由于Python参数传递机制,工具实际上**没有被注册**到agent。

### 核心挑战
1. **互斥性**: 虚拟和真实文件系统不能同时使用(工具名称冲突)
2. **配置驱动**: 应该通过配置选择使用哪种文件系统
3. **统一接口**: 两种文件系统提供相似的工具(ls, read_file等)
4. **清晰性**: 工具注入逻辑应该易于理解和维护

## 设计方案

### 方案A: 在Factory中注入 (推荐)

**优点:**
- 集中管理所有工具
- 逻辑清晰,易于调试
- 配置检查在一个地方完成
- 支持条件性注入

**实现:**

```python
# src/agents/deepagents/factories/base.py

async def create_agent(self, ...):
    # 1. 获取基础工具
    tools = user_params.get("tools")
    if not tools:
        tool_manager = UnifiedToolManager(auto_register_defaults=True)
        await tool_manager.initialize_all()
        tools = tool_manager.get_all_tools()
    
    # 2. 注入文件系统工具 (基于配置)
    tools = self._inject_filesystem_tools(tools, resolved_middleware)
    
    # 3. 创建runtime
    runtime = create_deep_agent_runtime(
        tools=tools,  # 已包含文件系统工具
        middleware_config=resolved_middleware,
        ...
    )

def _inject_filesystem_tools(self, tools, middleware_config):
    """根据配置注入虚拟或真实文件系统工具."""
    fs_config = middleware_config.get("filesystem", {})
    
    if not fs_config.get("enabled", False):
        return tools
    
    # 检查配置中的filesystem类型
    # 选项1: 显式配置
    fs_type = fs_config.get("type", "virtual")  # "virtual" or "real"
    
    # 选项2: 根据配置参数推断
    # 如果有security配置 → 真实文件系统
    # 如果只有long_term_memory → 虚拟文件系统
    
    if fs_type == "virtual":
        from src.components.deepagents.runtime_middlewares.virtual_filesystem import VirtualFilesystemMiddleware
        middleware = VirtualFilesystemMiddleware(
            long_term_memory=fs_config.get("long_term_memory", False),
            tool_token_limit_before_evict=fs_config.get("tool_token_limit_before_evict"),
        )
    elif fs_type == "real":
        from src.components.deepagents.runtime_middlewares.real_filesystem import RealFilesystemMiddleware
        middleware = RealFilesystemMiddleware(
            project_root=fs_config.get("project_root"),
            security=fs_config.get("security", {}),
            performance=fs_config.get("performance", {}),
        )
    else:
        raise ValueError(f"Unknown filesystem type: {fs_type}")
    
    fs_tools = middleware.get_tools()
    tools.extend(fs_tools)
    
    return tools
```

### 方案B: 统一的FilesystemMiddleware抽象

创建一个工厂模式来选择中间件:

```python
# src/components/deepagents/runtime_middlewares/filesystem_factory.py

def create_filesystem_middleware(config: dict):
    """根据配置创建相应的文件系统中间件."""
    if not config.get("enabled", False):
        return None
    
    # 自动检测类型
    if "security" in config or "project_root" in config:
        # 真实文件系统
        from .real_filesystem import RealFilesystemMiddleware
        return RealFilesystemMiddleware(
            project_root=config.get("project_root"),
            security=config.get("security", {}),
            performance=config.get("performance", {}),
        )
    else:
        # 虚拟文件系统
        from .virtual_filesystem import VirtualFilesystemMiddleware
        return VirtualFilesystemMiddleware(
            long_term_memory=config.get("long_term_memory", False),
            tool_token_limit_before_evict=config.get("tool_token_limit_before_evict"),
        )

# 在factory中使用
middleware = create_filesystem_middleware(fs_config)
if middleware:
    tools.extend(middleware.get_tools())
```

### 方案C: 移除runtime中的工具注入逻辑

**完全移除** runtime.py 第65-68行的工具注入代码:

```python
# runtime.py - 删除这段代码
# filesystem_tools = filesystem_middleware.get_tools()
# if filesystem_tools:
#     tools = list(tools) if tools else []
#     tools.extend(filesystem_tools)
```

**理由:**
- Runtime的职责是创建执行图,不应该修改工具列表
- 工具列表应该在进入runtime之前就已经完整
- Middleware只负责管理状态和system prompt

## 配置方案

### 选项1: 显式type字段

```json
// virtual_filesystem.json
{
  "enabled": true,
  "type": "virtual",
  "long_term_memory": false,
  "tool_token_limit_before_evict": 20000
}

// real_filesystem.json
{
  "enabled": true,
  "type": "real",
  "project_root": "${AUTO_DETECT}",
  "security": { ... }
}
```

### 选项2: 分离配置文件 (当前方案)

```
config/agents/deep/middleware/filesystem/
├── virtual_filesystem.json  # 虚拟文件系统配置
└── real_filesystem.json     # 真实文件系统配置
```

Registry根据配置参数自动选择:
```python
def _load_middleware_config(self):
    # 尝试加载virtual_filesystem.json
    virtual_path = self.base_path / "middleware" / "filesystem" / "virtual_filesystem.json"
    real_path = self.base_path / "middleware" / "filesystem" / "real_filesystem.json"
    
    # 优先级: virtual > real
    if virtual_path.exists():
        fs_config = self._load_json(virtual_path)
        fs_config["_type"] = "virtual"
    elif real_path.exists():
        fs_config = self._load_json(real_path)
        fs_config["_type"] = "real"
    else:
        fs_config = {}
    
    return {"filesystem": fs_config}
```

### 选项3: 环境变量控制

```python
import os

fs_mode = os.getenv("FILESYSTEM_MODE", "virtual")  # "virtual" or "real"
```

## 推荐实现方案

**组合方案: B + 方案A的factory注入 + 配置选项2**

### 1. 创建统一工厂
```python
# filesystem_factory.py
def create_filesystem_middleware(config: dict):
    """智能选择文件系统类型."""
    ...
```

### 2. 在Factory中注入
```python
# base.py
def _inject_filesystem_tools(self, tools, middleware_config):
    from src.components.deepagents.runtime_middlewares.filesystem_factory import create_filesystem_middleware
    
    fs_middleware = create_filesystem_middleware(middleware_config.get("filesystem", {}))
    if fs_middleware:
        tools.extend(fs_middleware.get_tools())
    
    return tools
```

### 3. Runtime不再注入工具
移除runtime.py第65-68行的工具注入代码,只保留middleware创建用于状态管理。

## 工具命名策略

### 方案A: 相同工具名
虚拟和真实文件系统使用相同的工具名称:
- `list_files`, `read_file`, `write_file`, `edit_file`

**优点:** Agent不需要知道使用的是哪种文件系统
**缺点:** 不能同时使用两种文件系统

### 方案B: 带前缀的工具名
```
虚拟: vfs_ls, vfs_read_file, vfs_write_file, vfs_edit_file
真实: rfs_ls, rfs_read_file, rfs_write_file, rfs_edit_file
```

**优点:** 可以同时注册两种文件系统
**缺点:** Agent需要知道选择哪个前缀

### 推荐: 方案A (互斥使用)

理由:
1. 大多数场景只需要一种文件系统
2. 同时使用容易混淆
3. System prompt更简洁

## 实施步骤

### 阶段1: 修复虚拟文件系统工具注入 (立即)
1. 在factory中添加`_inject_filesystem_tools`方法
2. 移除runtime中的工具注入代码
3. 测试虚拟文件系统工具可用

### 阶段2: 实现真实文件系统 (未来)
1. 实现`RealFilesystemMiddleware`
2. 创建`filesystem_factory.py`
3. 更新`_inject_filesystem_tools`支持自动选择
4. 添加配置切换逻辑

### 阶段3: 优化和测试 (未来)
1. 添加单元测试
2. 添加集成测试
3. 文档更新

## 总结

**不应该**继续在runtime中注入工具,而应该:

1. **在Factory中集中管理工具注入**
2. **使用工厂模式选择文件系统类型**
3. **通过配置驱动文件系统选择**
4. **保持runtime职责单一** (只创建执行图)

这样可以:
- 清晰的架构
- 易于扩展(添加新的文件系统类型)
- 易于测试
- 易于配置
