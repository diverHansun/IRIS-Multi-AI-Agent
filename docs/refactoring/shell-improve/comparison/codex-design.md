# Codex Shell 安全设计深度分析

## 一、项目背景

Codex 是 OpenAI 开源的 agent CLI 工具，使用 Rust 编写核心执行层（`codex-rs`），主要面向代码编写和工程任务场景。其 shell 设计的核心目标是：在不依赖用户持续监控的情况下，让 agent 安全地执行任意 shell 命令。

源码位置：
- 执行层：`codex-rs/core/src/exec.rs`
- 安全评估：`codex-rs/core/src/safety.rs`
- 权限模型：`codex-rs/crates/protocol/src/permissions.rs`

---

## 二、核心设计：沙盒优先

Codex 的根本思路是：**不过滤命令，而是限制命令的实际影响范围**。

这个思路的逻辑链条如下：

```
语言模型可能产生任何命令
    ↓
无法穷举所有危险命令（黑名单永远不完整）
    ↓
与其过滤命令，不如让危险命令执行了也没效果
    ↓
使用 OS 内核沙盒：在内核层面拦截对受保护路径的写操作
    ↓
沙盒内执行 = 安全自动执行 = 用户无需参与审批
```

---

## 三、沙盒的三种平台实现

### 3.1 macOS：sandbox-exec（Seatbelt）

macOS 提供了名为 Seatbelt 的内核安全框架，可以通过 profile 文件精确声明进程允许做哪些操作。Codex 使用 `sandbox-exec` 命令启动 shell 子进程，并附加一个限制性 profile：

```scheme
; 允许读取任何文件（工具需要读代码库）
(allow file-read*)
; 只允许写 workspace 目录
(allow file-write* (subpath "/path/to/workspace"))
; 禁止写其他任何路径
(deny file-write* (with no-log))
```

效果：shell 进程可以读取任何文件，但只能写 workspace 目录下的文件。`rm -rf /` 会立即收到 Permission denied，而 `rm -rf dist/` 如果 dist 在 workspace 内则正常执行。

### 3.2 Linux：landlock + seccomp

Linux 5.13 引入了 landlock LSM（Linux Security Module），这是一种非特权的文件系统访问控制机制，进程可以在不需要 root 权限的情况下为自己设置文件访问限制。

Codex 使用 landlock 为 shell 子进程设置规则：
- workspace 目录：读写权限
- 其他路径：只读权限

同时配合 seccomp（Secure Computing Mode）过滤系统调用，防止绕过 landlock 的高级攻击手段。

### 3.3 Windows：Job Object + Restricted Token

Windows 没有 landlock 这样的机制，Codex 使用两种方案：

**方案 A（默认，Restricted Token）**：
- 创建一个权限受限的用户令牌（Restricted Token）
- 使用 `CreateProcessAsUserW` 以受限令牌启动 shell 进程
- 通过 Job Object 限制进程可写的目录范围

**方案 B（Elevated，需要管理员权限）**：
- 使用 Windows Job Object 的高级功能
- 支持更精细的读/写路径分割控制

两种方案都通过 `WindowsSandboxFilesystemOverrides` 结构来描述"额外需要拒绝写入的路径集合"，在启动子进程时一次性配置好。

---

## 四、审批模式（AskForApproval）

有了沙盒之后，Codex 可以提供多级审批策略，而不是简单地"总是询问用户"：

| 模式 | 说明 | 适用场景 |
|---|---|---|
| `Never` | 所有操作自动批准；如无沙盒则直接拒绝执行 | 完全信任环境（CI、Docker 内） |
| `OnFailure` | 先执行，如果沙盒检测到拒绝行为再询问用户 | 日常开发，偶尔需要干预 |
| `OnRequest` | agent 可以主动请求用户审批某些操作 | agent 自己判断哪些操作需要确认 |
| `UnlessTrusted` | 有沙盒时自动批准，无沙盒时必须问用户 | **推荐默认模式** |
| `Granular` | 按 `sandbox_approval` 标志在工具级别细粒度控制 | 高级用户自定义 |

安全评估的决策树（`safety.rs` 中的 `assess_patch_safety` / `assess_exec_safety`）：

```
命令进来
    │
    ├── AskForApproval::UnlessTrusted
    │       ├── 有平台沙盒 → AutoApprove { sandbox_type }
    │       └── 无沙盒     → AskUser
    │
    ├── AskForApproval::Never
    │       ├── 有沙盒 → AutoApprove
    │       └── 无沙盒 → Reject（不降级为 AskUser）
    │
    ├── AskForApproval::OnFailure
    │       └── AutoApprove（先执行，失败了再说）
    │
    └── AskForApproval::OnRequest
            └── 看 agent 是否主动请求审批
```

---

## 五、Safety Check 的三种结果

```rust
pub enum SafetyCheck {
    AutoApprove {
        sandbox_type: SandboxType,
        user_explicitly_approved: bool,
    },
    AskUser,
    Reject {
        reason: String,
    },
}
```

- `AutoApprove`：可以直接执行，附带使用了哪种沙盒的信息
- `AskUser`：需要暂停，等待用户输入
- `Reject`：直接拒绝，不询问用户（通常是沙盒不可用但配置要求必须有沙盒的情况）

注意 `Reject` 和 `AskUser` 的区别：`Reject` 不给用户选择，因为允许执行本身就违反了用户的配置意图。

---

## 六、执行层细节

### 命令超时

默认超时时间为常量 `DEFAULT_EXEC_COMMAND_TIMEOUT_MS`（从代码来看约为 10 分钟）。超时后发送 SIGTERM，等待 IO drain 最多 2 秒，然后 SIGKILL。

输出上限为 `EXEC_OUTPUT_MAX_BYTES`，超过后截断（优先保留 stderr 尾部，因为错误信息通常在最后）。

### 输出聚合策略

Codex 分别保留 stdout 和 stderr，同时维护一个聚合后的 `aggregated_output`。聚合时优先分配空间给 stderr（因为报错信息比普通输出更重要），剩余空间给 stdout。

```rust
// 分配策略：1/3 给 stdout，2/3 留给可能的 stderr
let want_stdout = stdout.text.len().min(max_bytes / 3);
let want_stderr = stderr.text.len();
```

### 沙盒拒绝检测

执行成功返回后，Codex 还会检查输出内容中是否含有沙盒拒绝的特征词，以捕获"进程认为自己成功了但实际上被沙盒拦截"的边缘情况：

```rust
const SANDBOX_DENIED_KEYWORDS: [&str; 7] = [
    "operation not permitted",
    "permission denied",
    "read-only file system",
    "seccomp",
    "sandbox",
    "landlock",
    "failed to write file",
];
```

---

## 七、与本项目的核心差异

| 维度 | 本项目 | Codex |
|---|---|---|
| 安全边界在哪里 | 命令字符串过滤（软边界，可绕过） | OS 内核沙盒（硬边界，无法绕过） |
| 能否无人值守 | 不能（shell 永远需要人工审批） | 能（UnlessTrusted + 有沙盒时全自动） |
| 管道/重定向支持 | 禁止（`unsafe_tokens` 过滤） | 完全支持（沙盒兜底） |
| 跨平台沙盒 | 无 | macOS / Linux / Windows 三套实现 |
| 审批模式 | 1 档（始终审批） | 5 档 |

---

## 八、对本项目的借鉴意义

1. **沙盒是解放用户的根本手段**。本项目的 `DockerExecutor` 存根指向了正确方向——容器可以作为类沙盒环境。实现 DockerExecutor 后，可以把 `shell` 从 `dangerous_tools` 中移出，允许在容器模式下自动批准。

2. **Reject（强拒绝）与 AskUser（询问）的区分**值得学习。对于明确危险的操作（如沙盒外的系统写操作），直接拒绝并给出原因，而不是总是把决策推给用户，可以减少用户的决策疲劳。

3. **审批模式应该是可配置的**，而不是硬编码为"始终询问"。给不同使用场景不同的默认值，是 Codex 设计中很实用的工程决策。
