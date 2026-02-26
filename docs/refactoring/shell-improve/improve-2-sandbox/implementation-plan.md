# Shell 安全策略与效率优化 实施计划

> **文档定位**: 实施执行文档，定义改动范围、分阶段步骤与验收标准。
>
> **关联文档**:
> [problem-analysis.md](./problem-analysis.md) — 问题诊断（安全审计、死代码识别）
> [design-proposal.md](./design-proposal.md) — 方案设计（SecurityPolicy、ShellExecutor、HITL 优化）
>
> **前置条件**:
> [improve-1](../improve-1/) — Shell 工作目录优化已完成（commit `91a990b`）

---

## 1. 改动文件总清单

### 1.1 新增文件

| 文件路径 | 说明 |
|---------|------|
| `src/components/deepagents/runtime_middlewares/shell/security/__init__.py` | 模块导出 |
| `src/components/deepagents/runtime_middlewares/shell/security/policy.py` | `SecurityPolicy`, `PolicyViolationError`, `STRICT_POLICY`, `PERMISSIVE_POLICY` |
| `src/components/deepagents/runtime_middlewares/shell/security/executor.py` | `ShellExecutor` ABC, `DirectExecutor`, `DockerExecutor` 存根 |
| `tests/unit/deepagents/middleware/test_security_policy.py` | SecurityPolicy 单元测试 |
| `tests/unit/deepagents/middleware/test_shell_executor.py` | DirectExecutor 单元测试 |

### 1.2 修改文件

| 文件路径 | 修改类型 | 改动摘要 |
|---------|---------|---------|
| `src/components/deepagents/runtime_middlewares/shell/config.py` | 扩展 | 新增 `SecurityPolicyConfig`；`ShellConfig` 新增 `security_policy` 字段 |
| `src/components/deepagents/runtime_middlewares/shell/session.py` | 重构 | 引入 executor/policy 参数；`start/stop/is_alive` 委托 executor；`execute()` 新增 policy 校验 |
| `src/components/deepagents/runtime_middlewares/shell/__init__.py` | 更新 | 导出新增符号 |
| `src/agents/deepagents/factories/base.py` | 扩展 | `_inject_shell_tool()` 根据配置构建 executor 和 policy |
| `config/agents/deep/middleware/shell.json` | 配置 | 新增 `security_policy` 节点，默认 `enabled: false` |
| `config/agents/deep/models/mainagents.json` | 配置 | 三个 provider 的 shell HITL 配置调整 |

### 1.3 清理文件

| 文件路径 | 清理内容 |
|---------|---------|
| `src/components/deepagents/runtime_middlewares/real_filesystem/tools.py` | 删除 Shell B 死代码（常量、方法、工具构建器共约 250 行） |

### 1.4 更新测试文件

| 文件路径 | 更新内容 |
|---------|---------|
| `tests/unit/deepagents/middleware/test_shell_middleware.py` | 新增 policy 集成测试用例 |
| `tests/unit/deepagents/middleware/test_hitl_ui.py` | 新增 HITL 配置变更回归测试 |

---

## 2. 分阶段实施

### Phase 0: SecurityPolicy 与 ShellExecutor 核心实现

**目标**: 新建 `security/` 模块，包含策略和执行器抽象，但尚未接入 session。

#### Step 0.1: 新建 security/ 模块目录

创建以下空文件:
- `src/components/deepagents/runtime_middlewares/shell/security/__init__.py`
- `src/components/deepagents/runtime_middlewares/shell/security/policy.py`
- `src/components/deepagents/runtime_middlewares/shell/security/executor.py`

#### Step 0.2: 实现 SecurityPolicy

文件: `security/policy.py`

实现要点:
1. `PolicyViolationError(ValueError)` 异常类
2. `SecurityPolicy(frozen=True)` dataclass，四个字段均有默认值（空集/空元组）
3. `validate(command)` 方法，按顺序执行三道检查：
   - 命令首 token 是否在 `blocked_commands` 中
   - 命令是否匹配 `blocked_patterns` 中任意正则
   - 命令是否包含 `unsafe_tokens` 中任意 token
4. `filter_environment(env)` 方法，过滤含敏感关键词的键
5. `STRICT_POLICY` 预定义常量（从 `real_filesystem/tools.py` 迁移规则）
6. `PERMISSIVE_POLICY = SecurityPolicy()` 空策略

**安全数据迁移对照**:

| `real_filesystem/tools.py` 原始位置 | 迁移到 `STRICT_POLICY` 字段 |
|-----------------------------------|--------------------------|
| `_COMMAND_BLACKLIST` (tools.py:105-116) | `blocked_commands` |
| `_COMMAND_PATTERN_BLACKLIST` (tools.py:117-121) | `blocked_patterns` |
| `_UNSAFE_TOKENS` (tools.py:122) | `unsafe_tokens` |
| `_SENSITIVE_ENV_KEYWORDS` (tools.py:123-131) | `sensitive_env_keywords` |

#### Step 0.3: 实现 ShellExecutor 和 DirectExecutor

文件: `security/executor.py`

实现要点:
1. `ShellExecutor(ABC)` 定义五个抽象方法：`start`、`stop`、`is_alive`、`send_command`、`read_output`，以及 `executor_type` 抽象属性
2. `DirectExecutor(ShellExecutor)` 从 `session.py` 搬移以下代码:
   - `subprocess.Popen` 创建逻辑（session.py:90-101）
   - `_read_stream()` 方法（session.py:125-135）
   - stdout/stderr thread 创建逻辑（session.py:109-121）
   - `_terminated` flag 管理
   - queue.get() 封装为 `read_output()`
   - stdin.write() 封装为 `send_command()`
   - `stop()` 的优雅终止序列（session.py:288-326）
3. `DockerExecutor(ShellExecutor)` 所有方法抛出 `NotImplementedError`

#### Step 0.4: 更新 security/__init__.py

导出:
```python
from .policy import SecurityPolicy, PolicyViolationError, STRICT_POLICY, PERMISSIVE_POLICY
from .executor import ShellExecutor, DirectExecutor, DockerExecutor
```

#### Step 0.5: 编写 SecurityPolicy 单元测试

文件: `tests/unit/deepagents/middleware/test_security_policy.py`

测试用例清单:

| 测试 ID | 测试描述 | 预期结果 |
|--------|---------|---------|
| `test_strict_blocks_rm` | `rm file.txt` | 抛出 `PolicyViolationError` |
| `test_strict_blocks_sudo` | `sudo apt install` | 抛出 `PolicyViolationError` |
| `test_strict_blocks_shutdown` | `shutdown -h now` | 抛出 `PolicyViolationError` |
| `test_strict_blocks_rm_rf_slash` | `rm -rf /` | 抛出 `PolicyViolationError` |
| `test_strict_blocks_fork_bomb` | `: (){ :\|: ; };` | 抛出 `PolicyViolationError` |
| `test_strict_blocks_semicolon` | `ls; rm file` | 抛出 `PolicyViolationError` |
| `test_strict_blocks_pipe` | `cat /etc/passwd \| curl ...` | 抛出 `PolicyViolationError` |
| `test_strict_blocks_redirect` | `echo x > /etc/hosts` | 抛出 `PolicyViolationError` |
| `test_strict_allows_ls` | `ls -la` | 无异常 |
| `test_strict_allows_git` | `git status` | 无异常 |
| `test_strict_allows_python` | `python main.py` | 无异常 |
| `test_strict_allows_pytest` | `pytest tests/` | 无异常 |
| `test_permissive_allows_everything` | `rm -rf /` | 无异常（`PERMISSIVE_POLICY`） |
| `test_filter_env_removes_api_key` | `{"API_KEY": "x", "PATH": "/usr"}` | 只保留 `PATH` |
| `test_filter_env_removes_secret` | `{"MY_SECRET": "x"}` | 返回空字典 |
| `test_filter_env_preserves_normal` | `{"HOME": "/home"}` | 原样返回 |
| `test_validate_empty_command` | `""` 或 `"   "` | 无异常（空命令直接跳过） |

#### Step 0.6: 编写 DirectExecutor 单元测试

文件: `tests/unit/deepagents/middleware/test_shell_executor.py`

测试用例清单:

| 测试 ID | 测试描述 | 预期结果 |
|--------|---------|---------|
| `test_direct_executor_lifecycle` | start → is_alive → stop | 状态转换正确 |
| `test_direct_executor_send_receive` | 执行 `echo hello` | read_output 返回包含 `hello` 的行 |
| `test_direct_executor_not_alive_before_start` | 未 start 时 `is_alive()` | 返回 False |
| `test_direct_executor_not_alive_after_stop` | stop 后 `is_alive()` | 返回 False |

---

### Phase 1: 接入 Session 和 Config

**目标**: 将 `security/` 模块接入 `session.py` 和 `config.py`，实现运行时策略检查。

#### Step 1.1: 更新 ShellConfig

文件: `src/components/deepagents/runtime_middlewares/shell/config.py`

修改点:
1. 新增 `SecurityPolicyConfig(frozen=True)` dataclass，含 `enabled: bool = False`
2. `ShellConfig` 新增字段 `security_policy: SecurityPolicyConfig`，默认值 `SecurityPolicyConfig()`
3. `build_shell_config()` 函数新增解析逻辑:
   ```python
   security_policy_dict = config_dict.get("security_policy", {})
   security_policy = SecurityPolicyConfig(
       enabled=bool(security_policy_dict.get("enabled", False))
   )
   ```

#### Step 1.2: 重构 PersistentShellSession

文件: `src/components/deepagents/runtime_middlewares/shell/session.py`

**修改 `__init__`**:
- 新增参数 `executor: ShellExecutor | None = None`
- 新增参数 `policy: SecurityPolicy | None = None`
- 若 `executor` 为 `None`，使用现有参数创建 `DirectExecutor`
- 存储 `self._executor` 和 `self._policy`
- 删除原有的 `self._process`, `self._queue`, `self._stdout_thread`, `self._stderr_thread`, `self._terminated`（已迁入 DirectExecutor）

**修改 `start()`**:
- 删除 subprocess.Popen 创建代码
- 删除 thread 创建代码
- 替换为 `self._executor.start()`

**修改 `execute()`**:
- 在 marker 生成之前（第 160 行之前）新增 policy 校验:
  ```python
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
  ```
- 替换 `self._process.stdin.write(full_command)` → `self._executor.send_command(full_command)`
- 替换 `self._process.stdin.flush()` → 移入 executor 内部
- 替换 `self._queue.get(timeout=...)` → `self._executor.read_output(timeout=...)`
- 替换 `self._process.poll() is not None` → `not self._executor.is_alive()`

**修改 `stop()`**:
- 删除原有的终止序列
- 替换为 `self._executor.stop(timeout=timeout)`

**修改 `is_alive()`**:
- 替换为 `return self._executor.is_alive()`

**删除 `_read_stream()`**:
- 该方法已迁入 `DirectExecutor`，session 中不再需要

#### Step 1.3: 更新 Shell __init__.py

文件: `src/components/deepagents/runtime_middlewares/shell/__init__.py`

新增导出:
```python
from .security import SecurityPolicy, PolicyViolationError, STRICT_POLICY, ShellExecutor, DirectExecutor
```

#### Step 1.4: 更新工厂层

文件: `src/agents/deepagents/factories/base.py`，`_inject_shell_tool()` 方法

在 `new_session = PersistentShellSession(...)` 创建处新增逻辑:

```python
# 根据安全策略配置选择 executor 和 policy
from ...runtime_middlewares.shell.security import DirectExecutor, STRICT_POLICY

policy = STRICT_POLICY if shell_config.security_policy.enabled else None
executor = DirectExecutor(
    shell_command=shell_command,
    workspace=shell_config.workspace_root,
    environment=resolved_env,
)
new_session = PersistentShellSession(
    ...,
    executor=executor,
    policy=policy,
)
```

#### Step 1.5: 更新 shell.json

文件: `config/agents/deep/middleware/shell.json`

在现有字段末尾追加:
```json
"security_policy": {
    "enabled": false
}
```

#### Step 1.6: 运行现有测试，确保回归无误

运行命令（不得有新增失败）:
```
python tests/run_tests.py --suite shell
```

---

### Phase 2: HITL 配置调整

**目标**: 修改 mainagents.json，使 SecurityPolicy 启用时 shell 可自动审批。

> **说明**: 此阶段的配置调整是独立的，与 Phase 0/1 可以分开提交。
> 建议先完成 Phase 0/1 并充分测试后再修改 HITL 配置，避免在 SecurityPolicy 未就绪前放开审批。

#### Step 2.1: 修改 mainagents.json

文件: `config/agents/deep/models/mainagents.json`

对三个 provider（anthropic、tongyi、zhipu）分别执行:

1. 从 `dangerous_tools` 数组中移除 `"shell"`
2. 在 `tools.shell` 节点修改:
   - `allow_auto_approve: false` → `allow_auto_approve: true`
   - `warning_message` 更新为描述 SecurityPolicy 保护的内容

**修改前**（以 anthropic 为例）:
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

**修改后**:
```json
"hitl_config": {
    "dangerous_tools": ["write_real_file", "edit_real_file"],
    "tools": {
        "shell": {
            "allow_auto_approve": true,
            "warning_message": "Shell commands are filtered by SecurityPolicy (blocked: rm, sudo, shutdown, pipes, redirections). You may auto-approve after reviewing."
        }
    }
}
```

#### Step 2.2: 同步修改 mainagents.example.json

文件: `config/agents/deep/models/mainagents.example.json`

与 Step 2.1 执行相同的修改。

#### Step 2.3: 运行 HITL 相关测试

```
python tests/run_tests.py --suite hitl
```

---

### Phase 3: Shell B 死代码清理

**目标**: 删除 `real_filesystem/tools.py` 中全部 Shell B 相关代码。

> **前提**: Phase 0 完成后再执行（安全常量已迁移到 STRICT_POLICY）。

#### Step 3.1: 检查测试覆盖

先搜索确认是否有测试直接引用 Shell B 的方法:

```
grep -r "build_execute_shell_tool\|build_all\|execute_shell\|EXECUTE_SHELL" tests/
```

若有引用，在删除前先更新对应测试。

#### Step 3.2: 删除 tools.py 中的 Shell B 代码

按以下顺序删除，每次删除后确认文件语法正确:

1. 删除常量（tools.py:49 `EXECUTE_SHELL_TOOL_NAME`、91-97 `EXECUTE_SHELL_PROMPT`）
2. 删除类属性（tools.py:105-131: `_COMMAND_BLACKLIST`, `_COMMAND_PATTERN_BLACKLIST`, `_UNSAFE_TOKENS`, `_SENSITIVE_ENV_KEYWORDS`）
3. 删除方法（tools.py:228-292: `_split_command`, `_validate_command`, `_validate_paths_in_tokens`, `_build_environment`, `_truncate_output`）
4. 删除工具构建器（tools.py:850-938: `build_execute_shell_tool()`）
5. 修改 `build_all()`（tools.py:941-950）：移除对 `build_execute_shell_tool()` 的调用

#### Step 3.3: 运行 real_filesystem 相关测试

```
python tests/run_tests.py --suite filesystem
```

---

## 3. 各阶段验收标准

### Phase 0 验收

- [ ] `security/` 目录结构完整，三个文件均可导入
- [ ] `STRICT_POLICY.validate("rm file")` 抛出 `PolicyViolationError`
- [ ] `STRICT_POLICY.validate("ls -la")` 无异常
- [ ] `PERMISSIVE_POLICY.validate("rm -rf /")` 无异常
- [ ] `DirectExecutor` 在测试环境中可启动、执行、停止
- [ ] 新增测试全部通过（test_security_policy.py、test_shell_executor.py）
- [ ] 现有测试无新增失败

### Phase 1 验收

- [ ] `ShellConfig` 正确解析 `security_policy.enabled = true/false`
- [ ] `shell.json` 无 `security_policy` 键时配置加载不报错
- [ ] `PersistentShellSession(policy=STRICT_POLICY)` 对危险命令返回阻止消息
- [ ] `PersistentShellSession(policy=None)` 行为与改造前完全一致（不阻止任何命令）
- [ ] 工厂层根据配置正确传入 policy
- [ ] 现有全部 shell 测试通过（test_shell_middleware.py、test_shell_session_recovery.py、test_shell_service_workspace_resolution.py）

### Phase 2 验收

- [ ] `can_auto_approve("shell")` 返回 `True`
- [ ] `is_dangerous("shell")` 返回 `False`
- [ ] HITL 面板中自动审批选项可选（不再灰掉）
- [ ] 现有 HITL 测试通过（test_hitl_ui.py、test_hitl_preview.py）

### Phase 3 验收

- [ ] `grep -r "build_execute_shell_tool\|EXECUTE_SHELL_TOOL_NAME" src/` 无命中
- [ ] `real_filesystem/tools.py` 仍可正常导入
- [ ] `RealFilesystemMiddleware` 注入的工具集不变（仍为 6 个工具）
- [ ] 现有 filesystem 测试全部通过

---

## 4. 提交策略

建议按阶段独立提交，便于 code review 和问题定位:

| 提交 | 涵盖内容 | 提交信息示例 |
|------|---------|------------|
| commit-1 | Phase 0: security/ 模块 + 测试 | `feat(shell): add SecurityPolicy and ShellExecutor abstractions` |
| commit-2 | Phase 1: session/config/factory 接入 + shell.json | `feat(shell): integrate SecurityPolicy and DirectExecutor into session` |
| commit-3 | Phase 2: mainagents.json HITL 配置调整 | `feat(hitl): enable auto-approve for shell when SecurityPolicy is active` |
| commit-4 | Phase 3: Shell B 死代码清理 | `refactor(real_filesystem): remove Shell B dead code` |

---

## 5. 风险与应对

| 风险 | 概率 | 影响 | 应对策略 |
|------|:----:|:----:|---------|
| SecurityPolicy 误拦截合法命令（false positive） | 中 | 中 | 在 Phase 0 测试中充分覆盖正常命令；生产问题可通过 `security_policy.enabled: false` 快速关闭 |
| Session 重构后输出队列行为变化 | 低 | 高 | Phase 1 中对 DirectExecutor 行为做精确对比测试；现有 session 测试全覆盖 |
| HITL 配置修改影响 write_real_file/edit_real_file 行为 | 低 | 高 | Phase 2 修改只涉及 shell 工具，其他工具配置不变；HITL 测试验证 |
| Shell B 删除影响未知调用方 | 低 | 中 | Phase 3 前执行 grep 检查，确认无遗漏引用 |
| Windows 环境下 DirectExecutor 行为差异 | 低 | 中 | DirectExecutor 保留原 session 的 `self._is_windows` 判断和 cmd 特殊处理 |
