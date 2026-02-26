# Shell 安全策略与效率优化 问题分析

> **文档定位**: 问题诊断文档，审计现有 shell 安全机制、识别死代码、分析安全缺口与效率瓶颈。
>
> **关联文档**:
> [design-proposal.md](./design-proposal.md) — 方案设计（SecurityPolicy 架构、HITL 优化、ShellExecutor 抽象）
> [implementation-plan.md](./implementation-plan.md) — 实施步骤（修改清单、分阶段计划、测试方案）
>
> **前置改进**:
> [improve-1](../improve-1/) — Shell 工作目录优化（已完成）

---

## 术语约定

| 术语 | 含义 | 代码对应 |
|------|------|---------|
| **Shell A** | 持久 shell 会话中间件（唯一在用的 shell） | `runtime_middlewares/shell/` 模块 |
| **Shell B** | 一次性 shell 工具（死代码） | `real_filesystem/tools.py` 中的 `execute_shell` |
| **SecurityPolicy** | 命令安全过滤策略（可插拔） | 本次新增 |
| **HITL** | Human-in-the-Loop，人工审批 | `hitl/handler.py`、`hitl/session_manager.py` |
| **ShellExecutor** | Shell 命令执行器的抽象接口 | 本次新增 |
| **DirectExecutor** | 直接在宿主机执行命令（当前行为的封装） | 本次新增 |

---

## 1. 问题现象

当前 deep agent 使用 shell 工具执行命令时，存在以下安全和架构问题：

1. **Shell A（唯一在用的 shell）没有任何命令过滤**，完全依赖 HITL 人工审批
2. **Shell B（有安全过滤的 shell）是死代码**，从未被注入到 agent 中
3. **每次 shell 调用都必须 HITL 审批**，严重影响 agent 自主效率
4. **安全逻辑散落在死代码中无法复用**，Shell A 与 Shell B 安全能力断裂

**期望行为**: 将 Shell B 中有价值的安全逻辑提取为独立的 SecurityPolicy，注入 Shell A 的执行管道中，同时优化 HITL 审批策略，在安全策略保护下允许自动审批，提升 agent 自主效率。

---

## 2. 两套 Shell 全面审计

### 2.1 Shell A -- `ShellToolMiddleware`（持久 shell 会话）

**代码位置**: `src/components/deepagents/runtime_middlewares/shell/`

**注入路径**（唯一激活的 shell）:

```
BaseDeepAgentFactory.create_agent()                          [base.py:82-87]
    |
    +-- _inject_shell_tool(tools, resolved_middleware, project_context)
            |
            +-- build_shell_config(shell_config, project_root)   [config.py]
            +-- ShellToolMiddleware(config)                       [middleware.py]
            +-- shell_middleware.get_tools() -> [ShellTool]       工具名: "shell"
```

**运行时调用链**:

```
Agent 调用 "shell"
    -> HITL 拦截（dangerous_tools 包含 "shell"，allow_auto_approve=false）
    -> 用户 approve
    -> ShellToolMiddleware.wrap_tool_call()                    [middleware.py:170-178]
        -> _execute_shell_tool(request)                        [middleware.py:230-244]
            -> _execute_command(session, command, timeout)      [middleware.py:246-269]
                -> session.execute(command)                     [session.py:137-286]
                    -> subprocess.Popen (持久进程) stdin/stdout [session.py:90-101]
```

**安全机制审计**:

| 安全维度 | 状态 | 说明 |
|---------|:----:|------|
| 命令黑名单 | 无 | 无任何命令过滤 |
| 危险模式检测 | 无 | 不检测 `rm -rf /` 等危险模式 |
| 管道/重定向限制 | 无 | `|`, `>`, `&&` 等全部允许 |
| 路径白名单 | 无 | 命令参数中的路径不做限制 |
| 环境变量过滤 | 无 | 宿主机环境变量全部传递（含敏感信息） |
| HITL 审查 | 有 | 标记为 dangerous，每次审批 |
| 输出限制 | 有 | `max_output_lines` / `max_output_bytes` |
| 超时控制 | 有 | `command_timeout` |
| 会话重置 | 有 | 超时/截断后自动重建 session |

**结论**: Shell A 的唯一安全屏障是 HITL。一旦用户 approve，命令在宿主机上无限制执行。

### 2.2 Shell B -- `execute_shell`（一次性 shell 工具）

**代码位置**: `src/components/deepagents/runtime_middlewares/real_filesystem/tools.py`

**注入路径分析**:

```
RealFilesystemMiddleware.__init__()                          [middleware.py:33-59]
    |
    +-- factory = RealFilesystemToolFactory(options)
    |
    +-- builders = [                      <-- 注意: 没有 build_execute_shell_tool!
    |       factory.build_list_tool,       已注入
    |       factory.build_read_tool,       已注入
    |       factory.build_write_tool,      已注入
    |       factory.build_edit_tool,       已注入
    |       factory.build_glob_tool,       已注入
    |       factory.build_grep_tool,       已注入
    |   ]                                 <-- build_execute_shell_tool 缺失！
    |
    +-- self.tools = [builder() for builder in builders]
```

**死代码证据**:

1. `build_execute_shell_tool()` 定义于 `tools.py:850`，但 `RealFilesystemMiddleware.__init__` 的 `builders` 列表中没有包含它
2. `build_all()` 方法（`tools.py:941`）包含了 `build_execute_shell_tool()`，但 **`build_all()` 在整个代码库中没有被任何代码调用**
3. 全局搜索 `build_execute_shell_tool` 只有两处命中，均在 `tools.py` 文件自身内部

**Shell B 的安全机制**（虽然未使用，但有迁移价值）:

| 安全维度 | 实现 | 代码位置 |
|---------|------|---------|
| 命令黑名单 | `_COMMAND_BLACKLIST`: rm, sudo, shutdown 等 10 个命令 | tools.py:105-116 |
| 危险模式检测 | `_COMMAND_PATTERN_BLACKLIST`: `rm -rf /`, fork bomb | tools.py:117-121 |
| 不安全 token 禁止 | `_UNSAFE_TOKENS`: `;`, `&&`, `\|`, `>` 等 | tools.py:122 |
| 路径白名单验证 | `_validate_paths_in_tokens()`: 命令参数路径限制 | tools.py:252-267 |
| 环境变量过滤 | `_SENSITIVE_ENV_KEYWORDS`: API_KEY, SECRET 等 | tools.py:123-131 |

### 2.3 对比总结

```
Shell A (在用):              Shell B (死代码):
+------------------+        +------------------+
|  持久 session     |        |  一次性 subprocess |
|  cd/env 跨命令保持 |        |  不保持状态       |
|  无命令过滤       |        |  命令黑名单       |
|  无管道限制       |        |  禁止管道重定向    |
|  无路径验证       |        |  路径白名单       |
|  无环境变量过滤   |        |  敏感变量过滤     |
|  HITL 审查       |        |  从未被注入       |
|  直接 subprocess  |        |  直接 subprocess  |
+------------------+        +------------------+
     使用中                      从未使用
```

**核心矛盾**: 有安全能力的 shell 从未被使用，在用的 shell 没有安全能力。

---

## 3. HITL 审批机制审计

### 3.1 当前配置

文件: `config/agents/deep/models/mainagents.json`

所有三个 provider（anthropic, tongyi, zhipu）均配置 shell 为 dangerous：

```json
"hitl_config": {
    "dangerous_tools": ["shell", "write_real_file", "edit_real_file"],
    "tools": {
        "shell": {
            "allow_auto_approve": false,
            "warning_message": "Shell commands can change or destroy host data."
        }
    }
}
```

### 3.2 HITL 决策链路

**配置生效路径**:

```
mainagents.json
    |
    v
BaseDeepAgentFactory._build_interrupt_config(hitl_config)   [base.py:347-361]
    |
    +-- dangerous_tools -> interrupt_on["shell"] = {"allowed_decisions": [...]}
    +-- tools.shell.allow_auto_approve = false
    +-- tools.shell.warning_message -> interrupt_on["shell"]["description"]
    |
    v
Runtime(interrupt_on=interrupt_on)                           [runtime.py:42]
    |
    v
HumanInTheLoopMiddleware(interrupt_on=interrupt_on)          [runtime.py:153-154]
```

**运行时审批流程**:

```
Agent 调用 shell
    |
    +-- interrupt_on["shell"] 存在 -> 触发 LangGraph Interrupt
    |
    +-- handle_hitl_interrupt()                              [handler.py:26-63]
    |       |
    |       +-- is_auto_approved("shell")                    [session_manager.py:17-19]
    |       |   -> False（auto_approved_tools 不含 "shell"）
    |       |
    |       +-- can_auto_approve("shell")                    [session_manager.py:21-28]
    |       |   -> False（"shell" 在 dangerous_tools 中，第 23 行直接返回 False）
    |       |
    |       +-- is_dangerous("shell")                        [session_manager.py:41-43]
    |       |   -> True（"shell" 在 dangerous_tools 集合中）
    |       |
    |       +-- _build_options(allowed, can_auto=False, is_dangerous=True)
    |       |                                                [handler.py:206-253]
    |       |   -> 选项 [2] 被灰掉: "Tool is security-sensitive"
    |       |      条件: can_auto and not is_dangerous       [handler.py:228]
    |       |
    |       +-- 显示审批面板:
    |           [1] Yes           <- 可选
    |           [2] Auto-approve  <- 灰掉 (Tool is security-sensitive)
    |           [3] No            <- 可选
    |           [4] Instructions  <- 可选
    |
    +-- 用户选择 "1" -> approve -> 继续执行
```

### 3.3 自动审批的双重阻断

自动审批被两个独立条件阻断:

| 阻断条件 | 代码位置 | 当前值 | 作用 |
|---------|---------|--------|------|
| `can_auto_approve()` | `session_manager.py:21-28` | `False` | 一旦工具在 `dangerous_tools` 中，第 23 行直接返回 `False`，即使 `allow_auto_approve` 为 `True` 也无效 |
| `is_dangerous()` | `session_manager.py:41-43` | `True` | `handler.py:228` 中 `can_auto and not is_dangerous` 决定选项 [2] 是否可用 |

**关键发现**: `can_auto_approve()` 的实现中，`dangerous_tools` 检查**优先于** `tool_settings` 检查。这意味着仅修改 `allow_auto_approve` 为 `true` 是不够的，必须同时处理 `dangerous_tools` 的逻辑。

```python
# session_manager.py:21-28
def can_auto_approve(self, tool_name: str) -> bool:
    if tool_name in self.dangerous_tools:  # <-- 第一道关卡，直接返回 False
        return False
    settings = self.tool_settings.get(tool_name)
    if settings is None:
        return True
    return settings.get("allow_auto_approve", True)  # <-- 第二道关卡，被第一道拦截
```

### 3.4 效率问题

当 agent 需要连续执行多个 shell 命令时（如安装依赖 -> 编译 -> 运行测试），
用户必须逐一审批每个命令，严重打断工作流。

典型场景: agent 编写代码后运行测试，需要 3-5 次 shell 调用，
每次都中断等待用户审批，总审批时间可能超过实际执行时间。

---

## 4. 安全风险分析

### 4.1 当前风险（无 SecurityPolicy）

| 风险场景 | 严重性 | 当前防护 | 防护充分性 |
|---------|:------:|---------|:---------:|
| `rm -rf /` 或递归删除 | 致命 | 仅 HITL | 用户可能误批 |
| 安装恶意软件包 (`pip install malware`) | 高 | 仅 HITL | 用户难以判断包安全性 |
| 读取/泄露敏感文件 (`cat ~/.ssh/id_rsa`) | 高 | 仅 HITL | 用户可能不注意路径 |
| 修改系统配置 | 高 | 仅 HITL | 需要用户判断影响 |
| 网络请求泄露数据 (`curl` + API 密钥) | 高 | 仅 HITL | 环境变量未过滤 |
| Fork bomb / 资源耗尽 | 中 | 超时机制 | 超时前已产生影响 |
| 长时间占用进程 | 低 | 超时机制 | 有效 |

### 4.2 SecurityPolicy 可缓解的风险

| 风险场景 | SecurityPolicy 防护 |
|---------|-------------------|
| `rm -rf /` 或递归删除 | 命令黑名单拦截 `rm`；危险模式正则匹配 `rm -rf /` |
| `sudo` 提权执行 | 命令黑名单拦截 `sudo` |
| Fork bomb | 危险模式正则匹配 fork bomb 特征 |
| 命令链注入 (`cmd1; cmd2`) | 不安全 token 检测拦截 `;`, `&&`, `\|\|` 等 |
| 环境变量泄露 | 敏感环境变量过滤（API_KEY, SECRET, TOKEN 等） |
| 系统控制命令 | 命令黑名单拦截 `poweroff`, `shutdown`, `reboot` 等 |

**SecurityPolicy 不能缓解的风险**（仍需 HITL 或更高级隔离）:

| 风险场景 | 原因 |
|---------|------|
| 安装恶意软件包 | `pip install` 不在黑名单中，且策略无法判断包的安全性 |
| 读取/泄露非系统敏感文件 | 文件路径验证需要复杂的上下文判断 |
| 网络请求泄露数据 | `curl`/`wget` 是有效开发工具，不宜一刀切禁止 |

> **结论**: SecurityPolicy 提供了一层自动化安全网，能拦截最明显的危险操作，
> 配合 HITL 可选审批形成分级防护体系。

---

## 5. Shell B 死代码影响分析

### 5.1 Shell B 的代码清单

以下是 Shell B 在 `real_filesystem/tools.py` 中的代码，均为死代码：

| 代码 | 行号 | 类型 | 处置方式 |
|------|------|------|---------|
| `EXECUTE_SHELL_TOOL_NAME` | 49 | 常量 | 删除 |
| `EXECUTE_SHELL_PROMPT` | 91-97 | 常量 | 删除 |
| `_COMMAND_BLACKLIST` | 105-116 | 类属性 | 迁移到 SecurityPolicy |
| `_COMMAND_PATTERN_BLACKLIST` | 117-121 | 类属性 | 迁移到 SecurityPolicy |
| `_UNSAFE_TOKENS` | 122 | 类属性 | 迁移到 SecurityPolicy |
| `_SENSITIVE_ENV_KEYWORDS` | 123-131 | 类属性 | 迁移到 SecurityPolicy |
| `_split_command()` | 228-242 | 方法 | 删除（Shell A 不使用 shlex 解析） |
| `_validate_command()` | 244-250 | 方法 | 迁移逻辑到 SecurityPolicy.validate() |
| `_validate_paths_in_tokens()` | 252-267 | 方法 | 删除（Shell A 是持久会话，不做 token 级路径验证） |
| `_build_environment()` | 269-282 | 方法 | 迁移逻辑到 SecurityPolicy.filter_environment() |
| `_truncate_output()` | 284-292 | 静态方法 | 删除（Shell A session 已有输出截断机制） |
| `build_execute_shell_tool()` | 850-938 | 方法 | 删除 |
| `build_all()` 中的引用 | 949 | 方法引用 | 移除 `build_execute_shell_tool()` 引用 |

### 5.2 删除影响评估

| 影响项 | 评估 | 说明 |
|--------|:----:|------|
| 现有运行时功能 | 无影响 | Shell B 从未被注入，删除无行为变化 |
| 测试覆盖 | 需检查 | 可能存在直接调用 `build_all()` 的测试 |
| 安全逻辑复用 | 需迁移 | 黑名单等安全逻辑应迁移到 SecurityPolicy |
| `build_all()` 方法 | 需更新 | 移除 `build_execute_shell_tool()` 引用 |
| 导入语句 | 无影响 | `shlex`, `subprocess` 等仍被其他方法使用 |

### 5.3 可复用的安全逻辑

以下安全逻辑应从 Shell B 迁移到新的 SecurityPolicy 模块:

| Shell B 原始位置 | 迁移目标 |
|-----------------|---------|
| `_COMMAND_BLACKLIST` | `SecurityPolicy.blocked_commands` |
| `_COMMAND_PATTERN_BLACKLIST` | `SecurityPolicy.blocked_patterns` |
| `_UNSAFE_TOKENS` | `SecurityPolicy.unsafe_tokens` |
| `_SENSITIVE_ENV_KEYWORDS` | `SecurityPolicy.sensitive_env_keywords` |
| `_validate_command()` 逻辑 | `SecurityPolicy.validate()` |
| `_build_environment()` 逻辑 | `SecurityPolicy.filter_environment()` |

**不迁移的逻辑**:
- `_split_command()`: Shell A 是持久会话，命令以完整字符串写入 stdin，不需要 shlex 解析
- `_validate_paths_in_tokens()`: 基于 shlex token 的路径验证，不适用于持久会话
- `_truncate_output()`: Shell A 的 `PersistentShellSession.execute()` 已有独立的输出截断机制

---

## 6. 问题总结

```
[P1] Shell A 无命令过滤       <-- 唯一在用的 shell，安全性只靠 HITL
     +
[P2] Shell B 是死代码         <-- 有安全逻辑但从未被使用，增加维护负担
     +
[P3] 每次都要 HITL 审批       <-- allow_auto_approve=false 且 dangerous_tools 双重阻断
     +
[P4] 安全逻辑散落无法复用     <-- 黑名单硬编码在 Shell B 中，Shell A 用不到
     +
[P5] session 执行逻辑与通信紧耦合 <-- subprocess 管理直接写在 session 中，无法替换执行后端
     ===========================
     -> 安全性不足 + 效率低下 + 架构不统一
```

修复方案见 [design-proposal.md](./design-proposal.md)。
