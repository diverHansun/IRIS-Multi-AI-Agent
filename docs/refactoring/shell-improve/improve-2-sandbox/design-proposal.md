# Shell 安全策略与效率优化 设计方案

> **文档定位**: 方案设计文档，定义 SecurityPolicy 架构、ShellExecutor 抽象、HITL 优化策略与 Shell B 清理方案。
>
> **关联文档**:
> [problem-analysis.md](./problem-analysis.md) — 问题诊断（安全审计、HITL 机制分析、死代码识别）
> [implementation-plan.md](./implementation-plan.md) — 实施步骤（修改清单、分阶段计划、测试方案）
>
> **前置改进**:
> [improve-1](../improve-1/) — Shell 工作目录优化（已完成）

---

## 1. 设计目标

1. 将 Shell B 中有价值的安全逻辑提取为独立可配置的 `SecurityPolicy`，注入 Shell A 的执行管道
2. 优化 HITL 审批策略：SecurityPolicy 活跃时允许自动审批，减少人工干预
3. 引入 `ShellExecutor` 抽象接口，将 subprocess 通信逻辑从 session 中分离
4. 删除 Shell B 死代码，统一 shell 执行路径
5. 保持完全向后兼容：配置缺失时行为与改造前一致

---

## 2. 设计原则

| 原则 | 应用 |
|------|------|
| **单一职责** *(SRP)* | `ShellExecutor` 管执行通信；`SecurityPolicy` 管安全判断；`PersistentShellSession` 管命令协议（marker、超时、截断）；`ShellToolMiddleware` 管生命周期 |
| **依赖倒置** *(DIP)* | `PersistentShellSession` 依赖 `ShellExecutor` 抽象接口，不直接依赖 subprocess |
| **开闭原则** *(OCP)* | 新增执行器类型（Docker、WSL）无需修改 middleware 或 session；新增安全规则无需修改 executor |
| **最小改动** | Session 的核心 execute() 逻辑（marker、deadline、截断）完全保留；middleware 层完全不需要改动 |
| **YAGNI** | 当前只实现 `DirectExecutor`；`DockerExecutor` 预留接口但不实现 |

---

## 3. 架构设计

### 3.1 架构总览

```
+----------------------------------------------+
|  ShellToolMiddleware  (生命周期管理，不变)     |
|  before_agent() / wrap_tool_call() / after_agent() |
+----------------------+-----------------------+
                       |
+----------------------+-----------------------+
|  PersistentShellSession  (命令协议管理，微改)  |
|  - marker 生成与检测                          |
|  - deadline / 超时控制                        |
|  - 输出截断 / session 重置                    |
|  - 委托 executor 进行实际 IO                  |
+----------------------+-----------------------+
                       |
        +--------------+--------------+
        |                             |
+-------+--------+         +----------+--------+
|  ShellExecutor (ABC)     |  SecurityPolicy    |
|  start() / stop()        |  validate(cmd)     |
|  is_alive()              |  filter_env(env)   |
|  send_command()          |                   |
|  read_output()           | STRICT_POLICY (内置)|
+-------+--------+         +-------------------+
        |
        |  当前只实现
        v
+-------+--------+
|  DirectExecutor |
|  subprocess.Popen|
|  + queue + threads|
+----------------+
        |
        |  未来预留
        v
+-------+--------+
|  DockerExecutor |   (Phase N，当前不实现)
|  docker-py      |
+----------------+
```

### 3.2 核心设计决策

#### 决策一: SecurityPolicy 置于 execute() 入口，而非 send_command()

**决策**: 在 `PersistentShellSession.execute()` 的最前端验证命令，早于 marker 生成。

**理由**:
- 拦截发生在命令写入 stdin 之前，**不需要等待**也不会消耗 shell 状态
- 拦截后返回 `CommandResult(output="Command blocked: ...")`，对 session 无副作用
- 避免 marker 已写入但命令被拦截导致 session 状态不一致

```
session.execute(command)
    |
    +-- [新] policy.validate(command)   <- 拦截点：若违规，立即返回错误 CommandResult
    |         (PolicyViolationError)
    |
    +-- 生成 marker
    +-- executor.send_command(full_command_with_marker)
    +-- 收集输出直到 marker 出现
```

#### 决策二: ShellExecutor 接口使用流式协议

**决策**: 接口为 `send_command()` + `read_output()`，而非 `execute() -> Result`。

**理由**:
- Session 的 marker 检测、超时、截断、session 重置逻辑**完全保留**，不需要重新实现
- `send_command()` 只替换 `process.stdin.write()`；`read_output()` 只替换 `queue.get()`
- 修改量最小，风险最低

#### 决策三: HITL 配置随 SecurityPolicy 启用而松动

**决策**: 当 SecurityPolicy 启用时，将 shell 从 `dangerous_tools` 改为普通工具 + `allow_auto_approve: true`。

**理由**:
- SecurityPolicy 拦截了最危险的命令类别（`rm`、`sudo`、fork bomb、管道注入等）
- 剩余可执行命令的风险已大幅降低，不需要每次人工审批
- 用户可在会话内选择"自动审批"，大幅提升 agent 自主效率

---

## 4. SecurityPolicy 设计

### 4.1 接口定义

文件: `src/components/deepagents/runtime_middlewares/shell/security/policy.py`

```python
import re
from dataclasses import dataclass, field

class PolicyViolationError(ValueError):
    """命令被安全策略拦截。"""
    pass


@dataclass(frozen=True)
class SecurityPolicy:
    """Shell 命令安全过滤策略（纯策略，无副作用）。

    职责:
    - 验证命令字符串是否符合安全规则
    - 过滤环境变量中的敏感信息

    不负责:
    - 执行命令（由 executor 负责）
    - 审批决策（由 HITL 负责）
    - 日志记录（由调用方负责）
    """

    blocked_commands: frozenset = frozenset()
    blocked_patterns: tuple = ()
    unsafe_tokens: tuple = ()
    sensitive_env_keywords: tuple = ()

    def validate(self, command: str) -> None:
        """验证命令是否符合安全策略。

        Args:
            command: 原始命令字符串（不含 marker）

        Raises:
            PolicyViolationError: 命令违反安全策略时抛出，含具体原因
        """
        if not command or not command.strip():
            return

        # 1. 命令黑名单检测（取命令首 token）
        first_token = command.strip().split()[0].lower()
        if first_token in self.blocked_commands:
            raise PolicyViolationError(
                f"Command '{first_token}' is blocked by security policy."
            )

        # 2. 危险模式正则检测
        for pattern in self.blocked_patterns:
            if pattern.search(command):
                raise PolicyViolationError(
                    f"Command matches a blocked pattern: {pattern.pattern}"
                )

        # 3. 不安全 token 检测
        for token in self.unsafe_tokens:
            if token in command:
                raise PolicyViolationError(
                    f"Command contains unsafe token '{token}'. "
                    "Compound commands and redirections are not allowed."
                )

    def filter_environment(self, env: dict) -> dict:
        """过滤环境变量中的敏感信息。

        Args:
            env: 原始环境变量字典

        Returns:
            过滤后的新字典，不修改原字典
        """
        if not self.sensitive_env_keywords:
            return env
        return {
            k: v for k, v in env.items()
            if not any(kw in k.upper() for kw in self.sensitive_env_keywords)
        }
```

### 4.2 内置策略

文件: `src/components/deepagents/runtime_middlewares/shell/security/policy.py`（续）

```python
# 严格策略 — SecurityPolicy 启用时默认使用
# 从 Shell B (real_filesystem/tools.py) 迁移
STRICT_POLICY = SecurityPolicy(
    blocked_commands=frozenset({
        "rm", "sudo", "poweroff", "shutdown", "reboot",
        "halt", "mkfs", "dd", "chmod", "chown",
    }),
    blocked_patterns=(
        re.compile(r"rm\s+-rf\s+/"),
        re.compile(r"rm\s+-rf\s+~"),
        re.compile(r":\s*\(\)\s*{\s*:\s*\|\s*:\s*;\s*}\s*;"),  # fork bomb
    ),
    unsafe_tokens=(";", "&&", "||", "|", ">", ">>", "<", "<<", "`", "$("),
    sensitive_env_keywords=(
        "API_KEY", "SECRET", "TOKEN", "PASSWORD", "PASS", "AUTH", "PRIVATE_KEY",
    ),
)

# 宽松策略 — 不做任何过滤（未来 DockerExecutor 使用，容器本身提供隔离）
PERMISSIVE_POLICY = SecurityPolicy()
```

### 4.3 策略局限性说明

SecurityPolicy 能拦截的命令类别:

| 威胁类别 | 拦截机制 | 示例 |
|---------|---------|------|
| 系统破坏命令 | 命令黑名单 | `rm`, `dd`, `mkfs` |
| 提权操作 | 命令黑名单 | `sudo`, `chmod`, `chown` |
| 系统关机 | 命令黑名单 | `poweroff`, `shutdown`, `reboot` |
| 递归删除根目录 | 危险模式正则 | `rm -rf /`, `rm -rf ~` |
| Fork bomb | 危险模式正则 | `: (){ :|: ; };` |
| 命令链注入 | 不安全 token | `cmd1; cmd2`, `cmd1 && cmd2` |
| 管道滥用 | 不安全 token | `cat /etc/passwd \| curl ...` |
| 输出重定向 | 不安全 token | `> /etc/hosts` |
| 环境变量中的密钥泄露 | 敏感词过滤 | `API_KEY`, `SECRET`, `TOKEN` |

SecurityPolicy **无法拦截**的场景（设计边界，需用户知悉）:

| 场景 | 原因 |
|------|------|
| 安装恶意软件包 | `pip install`/`npm install` 不在黑名单，无法判断包安全性 |
| 读取用户目录敏感文件 | 文件路径验证需上下文，不适合静态分析 |
| 网络请求泄露数据 | `curl`/`wget` 是正常开发工具，不宜禁止 |

这些场景继续由 HITL 覆盖（用户仍可在会话内收到通知并干预）。

---

## 5. ShellExecutor 抽象设计

### 5.1 接口定义

文件: `src/components/deepagents/runtime_middlewares/shell/security/executor.py`

```python
from abc import ABC, abstractmethod

class ShellExecutor(ABC):
    """Shell 命令执行器的抽象接口。

    定义执行器的生命周期与 IO 协议。
    PersistentShellSession 依赖此接口，不依赖具体实现。

    设计约束:
    - 必须支持持久会话语义（cd/env 跨命令保持）
    - send_command/read_output 配对使用，配合 session 的 marker 协议
    - start/stop 管理执行环境生命周期
    """

    @abstractmethod
    def start(self) -> None:
        """启动执行环境（创建 subprocess 或容器）。"""
        ...

    @abstractmethod
    def stop(self, timeout: float = 5.0) -> None:
        """销毁执行环境。"""
        ...

    @abstractmethod
    def is_alive(self) -> bool:
        """检查执行环境是否可用。"""
        ...

    @abstractmethod
    def send_command(self, full_command: str) -> None:
        """向执行环境 stdin 写入命令（含 marker）。"""
        ...

    @abstractmethod
    def read_output(self, timeout: float = 0.1) -> tuple | None:
        """从执行环境读取一行输出。

        Returns:
            (stream_name, line) 元组，stream_name 为 "stdout" 或 "stderr"
            超时无输出返回 None
        """
        ...

    @property
    @abstractmethod
    def executor_type(self) -> str:
        """执行器类型标识（用于日志）。"""
        ...
```

### 5.2 DirectExecutor 设计

文件: `src/components/deepagents/runtime_middlewares/shell/security/executor.py`

`DirectExecutor` 将当前 `PersistentShellSession` 中的 subprocess/queue/thread 逻辑**原样搬移**，行为与改造前完全一致。

关键迁移对应关系:

| 原 session.py 代码 | 迁移至 DirectExecutor | 行号参考 |
|-------------------|----------------------|---------|
| `self._process = subprocess.Popen(...)` | `DirectExecutor.start()` | session.py:90-101 |
| `self._stdout_thread = Thread(...)` | `DirectExecutor.start()` | session.py:109-121 |
| `self._read_stream()` | `DirectExecutor._read_stream()` | session.py:125-135 |
| `self._process.stdin.write(cmd)` | `DirectExecutor.send_command()` | session.py:178-179 |
| `self._queue.get(timeout=...)` | `DirectExecutor.read_output()` | session.py:200 |
| `self._process.poll()` | `DirectExecutor.is_alive()` 反向 | session.py:147 |
| `self._process.stdin.write("exit\n")` | `DirectExecutor.stop()` | session.py:305-309 |

SecurityPolicy 在 `send_command()` 内不调用。Policy 检查由 session.execute() 在调用 send_command 之前完成（见第 3.2 节决策一）。

### 5.3 DockerExecutor（预留，不实现）

文件: `src/components/deepagents/runtime_middlewares/shell/security/executor.py` 中的存根

```python
class DockerExecutor(ShellExecutor):
    """容器内执行命令（完全隔离）。预留接口，暂不实现。

    实现时: 使用 docker-py，在容器内启动持久 bash 会话，
    通过 stdin/stdout 与 PersistentShellSession 通信。
    配合 PERMISSIVE_POLICY（容器本身提供隔离，无需命令过滤）。
    """

    def start(self) -> None:
        raise NotImplementedError("DockerExecutor is not yet implemented.")

    # 其余方法同上
```

---

## 6. PersistentShellSession 改造设计

### 6.1 改造范围

改造目标: **最小化修改**，只替换 IO 层调用，保留全部命令协议逻辑。

**不变的部分**（约 150 行）:
- `CommandResult` dataclass
- `execute()` 的 marker 生成逻辑（session.py:160-169）
- `execute()` 的 deadline 管理和超时检测（session.py:190-206）
- `execute()` 的 marker 检测与 exit code 提取（session.py:208-217）
- `execute()` 的输出截断逻辑（session.py:225-235）
- `execute()` 的 session 重置逻辑（session.py:242-253）
- `execute()` 的输出组合与格式化（session.py:255-286）

**变化的部分**（约 40 行）:
- `__init__`：接受可选的 `executor` 参数；若未提供则创建 `DirectExecutor`
- `start()`：调用 `self._executor.start()` 替代直接创建 subprocess
- `stop()`：调用 `self._executor.stop()` 替代直接终止 subprocess
- `is_alive()`：调用 `self._executor.is_alive()`
- `execute()` 入口：新增 `policy.validate(command)` 调用（若 session 持有 policy）
- `execute()` 内部：`send_command()` 和 `read_output()` 替换直接的 stdin/queue 操作

### 6.2 改造前后对比

**改造前** session.py 核心代码:

```python
class PersistentShellSession:
    def __init__(self, workspace, shell_command, environment, ...):
        self._process: Optional[subprocess.Popen] = None
        self._queue: queue.Queue = queue.Queue()
        self._stdout_thread: Optional[Thread] = None
        self._stderr_thread: Optional[Thread] = None
        self._terminated = False

    def start(self):
        self._process = subprocess.Popen(
            self._shell_command, stdin=PIPE, stdout=PIPE, stderr=PIPE,
            cwd=str(self._workspace), text=True, env=self._environment, ...
        )
        self._stdout_thread = Thread(target=self._read_stream, ...)
        self._stderr_thread = Thread(target=self._read_stream, ...)

    def execute(self, command):
        # ... marker 生成 ...
        self._process.stdin.write(full_command)      # <- 替换
        self._process.stdin.flush()
        while True:
            stream_name, line = self._queue.get(timeout=...) # <- 替换
            if self._process.poll() is not None:     # <- 替换
                break
```

**改造后** session.py 核心代码:

```python
class PersistentShellSession:
    def __init__(self, workspace, shell_command, environment, ...,
                 executor=None, policy=None):
        self._executor = executor or DirectExecutor(
            shell_command, workspace, environment
        )
        self._policy = policy  # 可选，None 表示不过滤

    def start(self):
        self._executor.start()  # 生命周期委托

    def execute(self, command):
        # [新增] 安全策略检查，发生在 marker 生成之前
        if self._policy:
            try:
                self._policy.validate(command)
            except PolicyViolationError as exc:
                return CommandResult(
                    output=f"Command blocked by security policy: {exc}",
                    exit_code=None, timed_out=False,
                    truncated_by_lines=False, truncated_by_bytes=False,
                    duration=0.0,
                )

        # ... marker 生成（不变）...
        self._executor.send_command(full_command)    # <- 替换 stdin.write
        while True:
            result = self._executor.read_output(timeout=...) # <- 替换 queue.get
            if result is None:
                if not self._executor.is_alive():    # <- 替换 process.poll
                    break
                continue
            stream_name, line = result
            # ... 后续逻辑不变 ...
```

---

## 7. HITL 配置优化设计

### 7.1 现状分析

参见 [problem-analysis.md](./problem-analysis.md) 第 3.3 节，自动审批被两个独立条件阻断:

1. `can_auto_approve()` 中，工具在 `dangerous_tools` 时直接返回 `False`
2. `_build_options()` 中，`can_auto and not is_dangerous` 才显示自动审批选项

### 7.2 变更策略

**核心思路**: 当 SecurityPolicy 启用时，shell 不再列入 `dangerous_tools`，而是作为普通工具配置 `allow_auto_approve: true`。SecurityPolicy 本身承担自动防护职责，HITL 退为可选的用户干预机制。

**配置变更**（`config/agents/deep/models/mainagents.json`）:

```json
// SecurityPolicy 启用时（三个 provider 均需同步修改）
"hitl_config": {
    "dangerous_tools": ["write_real_file", "edit_real_file"],  // shell 从此列表移除
    "tools": {
        "shell": {
            "allow_auto_approve": true,   // 从 false 改为 true
            "warning_message": "Shell commands are filtered by SecurityPolicy. Blocked: rm, sudo, shutdown, pipes, redirections."
        },
        "write_real_file": { ... },
        "edit_real_file": { ... }
    }
}
```

**效果变化**:

| 配置项 | 改造前 | 改造后 |
|--------|--------|--------|
| shell 在 `dangerous_tools` 中 | 是 | 否 |
| `is_dangerous("shell")` | True | False |
| `can_auto_approve("shell")` | False | True |
| 自动审批选项是否可用 | 灰掉 | 可选 |
| 首次调用是否仍触发 HITL | 是 | 是（用户仍然知情） |
| 用户可否选择"记住，自动批准" | 否 | 是 |

### 7.3 用户体验变化

**改造前** 执行 5 次 shell 命令:

```
[1] shell: pip install pytest   -> HITL 中断 -> 用户手动批准
[2] shell: pytest tests/        -> HITL 中断 -> 用户手动批准
[3] shell: git add .            -> HITL 中断 -> 用户手动批准
[4] shell: git commit -m "..."  -> HITL 中断 -> 用户手动批准
[5] shell: git push             -> HITL 中断 -> 用户手动批准
总计: 5 次人工干预
```

**改造后** 执行 5 次 shell 命令:

```
[1] shell: pip install pytest   -> HITL 中断 -> 用户选择"自动审批"
[2] shell: pytest tests/        -> 自动放行
[3] shell: git add .            -> 自动放行
[4] shell: git commit -m "..."  -> 自动放行
[5] shell: git push             -> 自动放行
总计: 1 次人工干预

若命令违规:
[?] shell: rm -rf /             -> SecurityPolicy 拦截 -> 返回错误消息 -> 无需 HITL
```

### 7.4 工厂层配置传递

`BaseDeepAgentFactory._inject_shell_tool()` 无需动态修改 HITL 配置。HITL 配置的调整直接在 `mainagents.json` 中完成，因为 SecurityPolicy 的启用与否由 `shell.json` 的 `security_policy.enabled` 控制，属于两个独立的配置维度。

---

## 8. 配置设计

### 8.1 ShellConfig 扩展

文件: `src/components/deepagents/runtime_middlewares/shell/config.py`

新增 `SecurityPolicyConfig` 数据类:

```python
@dataclass(frozen=True)
class SecurityPolicyConfig:
    """安全策略配置。"""

    enabled: bool = False
    # 未来扩展: 自定义黑名单、自定义模式等
    # custom_blocked_commands: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        pass  # 无额外约束，预留扩展点
```

`ShellConfig` 新增字段:

```python
@dataclass(frozen=True)
class ShellConfig:
    # ... 现有字段不变 ...
    security_policy: SecurityPolicyConfig = field(
        default_factory=SecurityPolicyConfig
    )
```

### 8.2 shell.json 配置扩展

文件: `config/agents/deep/middleware/shell.json`

```json
{
    "enabled": true,
    "workspace_root": "auto",
    "shell_type": "cmd",
    "command_timeout": 30.0,
    "startup_timeout": 10.0,
    "termination_timeout": 5.0,
    "max_output_lines": 100,
    "max_output_bytes": 1048576,
    "environment": {},
    "startup_commands": [],
    "security_policy": {
        "enabled": false
    }
}
```

> **向后兼容**: `security_policy` 键缺失时默认 `SecurityPolicyConfig(enabled=False)`，
> 即不做任何命令过滤，行为与改造前完全一致。

### 8.3 三层配置覆盖

遵循项目现有的三层配置体系:

```
内置配置 (config/agents/deep/middleware/shell.json)
    security_policy.enabled = false   <- 默认不启用

用户配置 (~/.iris/agents/deep/middleware/shell.json)
    security_policy.enabled = true    <- 用户全局启用

项目配置 (<project>/.iris/agents/deep/middleware/shell.json)
    security_policy.enabled = false   <- 项目覆盖（如需执行管道命令的项目）
```

---

## 9. 文件结构变更

### 9.1 新增文件

```
src/components/deepagents/runtime_middlewares/shell/
├── __init__.py                    # 更新: 导出 SecurityPolicy, ShellExecutor 等
├── config.py                      # 修改: 新增 SecurityPolicyConfig
├── middleware.py                   # 不变
├── session.py                     # 修改: 引入 executor 参数和 policy 检查
├── tool.py                        # 不变
│
└── security/                      # 新增模块（原 sandbox/ 改名，定位更准确）
    ├── __init__.py                # 导出: SecurityPolicy, PolicyViolationError,
    │                              #        ShellExecutor, DirectExecutor,
    │                              #        STRICT_POLICY, PERMISSIVE_POLICY
    ├── policy.py                  # SecurityPolicy, PolicyViolationError, 内置策略
    └── executor.py                # ShellExecutor ABC, DirectExecutor, DockerExecutor 存根
```

### 9.2 删除的代码

文件: `src/components/deepagents/runtime_middlewares/real_filesystem/tools.py`

| 删除项 | 行号 | 理由 |
|--------|------|------|
| `EXECUTE_SHELL_TOOL_NAME` | 49 | Shell B 工具名（死代码） |
| `EXECUTE_SHELL_PROMPT` | 91-97 | Shell B 工具描述（死代码） |
| `_COMMAND_BLACKLIST` | 105-116 | 已迁移到 `STRICT_POLICY` |
| `_COMMAND_PATTERN_BLACKLIST` | 117-121 | 已迁移到 `STRICT_POLICY` |
| `_UNSAFE_TOKENS` | 122 | 已迁移到 `STRICT_POLICY` |
| `_SENSITIVE_ENV_KEYWORDS` | 123-131 | 已迁移到 `STRICT_POLICY` |
| `_split_command()` | 228-242 | Shell B 专用死代码，不迁移 |
| `_validate_command()` | 244-250 | 逻辑已迁移到 `SecurityPolicy.validate()` |
| `_validate_paths_in_tokens()` | 252-267 | Shell B 专用死代码，不迁移 |
| `_build_environment()` | 269-282 | 逻辑已迁移到 `SecurityPolicy.filter_environment()` |
| `_truncate_output()` | 284-292 | Shell B 专用死代码，Shell A 有独立实现 |
| `build_execute_shell_tool()` | 850-938 | Shell B 工具构建器（死代码） |
| `build_all()` 中的引用 | 949 | 移除对 `build_execute_shell_tool()` 的引用 |

**保留**: `build_all()` 方法本身保留，仅移除其中对 `build_execute_shell_tool()` 的调用。

### 9.3 修改的文件汇总

| 文件 | 修改内容 | 影响范围 |
|------|---------|---------|
| `shell/config.py` | 新增 `SecurityPolicyConfig`；`ShellConfig.security_policy` 字段；`build_shell_config()` 解析新字段 | 配置层 |
| `shell/session.py` | `__init__` 接受 `executor`/`policy`；`start/stop/is_alive` 委托 executor；`execute()` 新增 policy 校验 | 会话层 |
| `shell/__init__.py` | 导出新增符号 | 导出 |
| `factories/base.py` | `_inject_shell_tool()` 根据 `security_policy.enabled` 构建 executor 和 policy，传入 session | 工厂层 |
| `config/agents/deep/middleware/shell.json` | 新增 `security_policy` 节点 | 配置文件 |
| `config/agents/deep/models/mainagents.json` | shell 从 `dangerous_tools` 移除；`allow_auto_approve` 改 `true` | HITL 配置 |
| `real_filesystem/tools.py` | 删除 Shell B 全部死代码 | 清理 |

---

## 10. 错误处理

### 10.1 SecurityPolicy 拦截

`PolicyViolationError` 被 `session.execute()` 捕获，返回对 agent 可读的错误消息:

```
Command blocked by security policy: Command 'rm' is blocked by security policy.
```

Agent 收到此消息后，会重新规划执行路径（如用 Python 代码替代 shell 命令）。
**不触发 HITL**，不中断 session，对 shell 进程无副作用。

### 10.2 SecurityPolicy 配置错误

`SecurityPolicyConfig.__post_init__()` 在配置加载时校验参数合法性，
配置错误在 `ShellToolMiddleware` 创建时即报错（fail-fast）。

### 10.3 executor.start() 失败

executor 启动失败（如 shell 命令不存在）的错误处理路径与改造前完全一致，
由 `_get_or_create_session()` 中的现有 try/except 处理。

---

## 11. 向后兼容性分析

| 场景 | 改造前 | 改造后 | 兼容 |
|------|--------|--------|:----:|
| `shell.json` 无 `security_policy` | N/A | 默认 `enabled=False` | 是 |
| `security_policy.enabled = false` | 无策略 | DirectExecutor 无 policy | 是 |
| `security_policy.enabled = true` | N/A | DirectExecutor + STRICT_POLICY | 是（新功能） |
| Shell A HITL 审批（策略未启用） | 每次审批 | 每次审批（不变） | 是 |
| Shell A HITL 审批（策略启用） | 每次审批 | 首次后可自动（需 mainagents.json 同步） | 是（新功能） |
| Shell B dead code 调用 | 不可能 | 已删除 | 是 |
| `build_all()` 调用 | 含 execute_shell | 不含 execute_shell | 是 |

---

## 12. 测试策略

### 12.1 SecurityPolicy 单元测试

文件: `tests/unit/deepagents/middleware/test_security_policy.py`

覆盖点:
- `STRICT_POLICY.validate()` 对各类危险命令正确拦截
- `STRICT_POLICY.validate()` 对正常命令不误拦截（false positive）
- `PERMISSIVE_POLICY.validate()` 对任何命令均通过
- `filter_environment()` 过滤正确的键，保留无关键

### 12.2 DirectExecutor 单元测试

文件: `tests/unit/deepagents/middleware/test_shell_executor.py`

覆盖点:
- `start()/stop()/is_alive()` 生命周期
- `send_command()/read_output()` 基本通信
- 行为与原 PersistentShellSession 的 subprocess 代码一致

### 12.3 Session 集成测试

更新 `tests/unit/deepagents/middleware/test_shell_middleware.py`:
- 传入 `policy=STRICT_POLICY` 时危险命令被拦截，返回错误 CommandResult
- `policy=None` 时行为与改造前完全一致
- 传入自定义 executor（Mock）时 session 正确委托

### 12.4 HITL 配置回归测试

更新 `tests/unit/deepagents/middleware/test_hitl_ui.py`:
- mainagents.json 修改后 `can_auto_approve("shell")` 正确返回 True
- `is_dangerous("shell")` 正确返回 False
- 自动审批选项在 UI 中可用

实施步骤见 [implementation-plan.md](./implementation-plan.md)。
