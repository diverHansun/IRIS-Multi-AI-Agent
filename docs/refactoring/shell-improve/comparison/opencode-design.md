# OpenCode Shell 安全设计深度分析

## 一、项目背景

OpenCode 是 SST 团队开源的 agent CLI，使用 TypeScript（Effect-TS 框架）编写，主要面向全栈开发场景。其 shell 安全设计走了一条与 Codex 完全不同的路：不依赖 OS 沙盒，而是通过语义解析和持久化权限规则，逐步建立信任。

核心源码：
- `packages/opencode/src/tool/shell.ts`：shell 工具主体
- `packages/opencode/src/permission/index.ts`：权限系统
- `packages/opencode/src/permission/arity.ts`：命令前缀语义识别

---

## 二、核心设计：语义解析 + 规则引擎

OpenCode 的思路是：**在执行命令之前，先理解命令要做什么，再对照已有规则决定是否需要询问用户**。

具体来说：

1. 用 `tree-sitter` 解析 bash 或 PowerShell 的抽象语法树（AST）
2. 遍历语法树，找出所有文件操作类命令（`rm`、`cp`、`mv`、`cat`、`chmod` 等）的路径参数
3. 对路径做静态展开（处理 `~`、`$HOME`、`$env:HOME` 等变量）
4. 把涉及到的路径与权限规则库对比，决定是否需要询问用户

---

## 三、AST 解析：为什么要解析语法树

简单的字符串匹配可以识别 `rm -rf .`，但识别不了：

```bash
TARGET=dist
rm -rf $TARGET
```

tree-sitter 把命令解析成语法树之后，可以访问命令的每个参数节点，做更精确的分析。

OpenCode 同时加载了 bash 和 PowerShell 两套语法解析器：

```typescript
const [bashLanguage, psLanguage] = await Promise.all([
    Language.load(bashPath),
    Language.load(psPath)
])
```

在执行前，先判断当前 shell 是 PowerShell 还是 bash，选择对应的解析器。

### 路径参数提取

对于文件操作类命令（FILES 集合），解析出所有路径参数，逐一做静态展开：

```typescript
// 处理 PowerShell 环境变量语法
.replace(/\$\{env:([^}]+)\}/gi, (_, key) => envValue(key) || "")
.replace(/\$env:([A-Za-z_][A-Za-z0-9_]*)/gi, (_, key) => envValue(key) || "")
// 处理 $HOME 和 ~
.replace(/\$(HOME|PWD|PSHOME)(?=$|[\\/])/gi, (_, key) => auto(key, cwd, shell) || "")
```

对于含有动态表达式（`$(...)` 命令替换、`$var` 变量引用等）的路径，由于静态分析无法确定实际值，标记为"动态路径"，会直接触发审批。

---

## 四、权限规则系统

### 规则的数据结构

每条规则是一个三元组：

```typescript
type Rule = {
    permission: string   // 权限类型，如 "shell"、"edit"
    pattern: string      // 路径模式，如 "/workspace/*"、"git *"
    action: "allow" | "deny" | "ask"
}
```

规则集是规则的有序数组，**越靠后的规则优先级越高**（最后匹配的规则生效）。

### 规则来源

规则来自两个地方：

**1. 静态配置（用户预先声明）**

在项目配置文件中可以预先授权或禁止某些操作：

```json
{
    "permission": {
        "shell": {
            "/workspace/*": "allow",
            "~/.ssh/*": "deny",
            "*": "ask"
        }
    }
}
```

**2. 动态学习（运行时积累）**

用户在审批时可以选择三种答复：

| 答复 | 效果 |
|---|---|
| `once`（本次允许） | 仅本次放行，不写入数据库 |
| `always`（总是允许） | 写入 `always` 模式列表，后续匹配自动放行 |
| `reject`（拒绝） | 拒绝本次，并取消本会话所有待审批请求 |

选择 `always` 后，OpenCode 把命令的前缀模式写入持久化数据库（SQLite）。例如批准了 `npm run dev`，会存入：

```json
{ "permission": "shell", "pattern": "npm run *", "action": "allow" }
```

这里的 `pattern` 是通过 `BashArity` 模块计算出来的：根据预定义的命令语义字典，`npm run` 的 arity（参数数量）是 3，所以 pattern 是 `npm run *` 而不是 `npm *`。

### BashArity：命令语义识别

这是 OpenCode 一个很有特色的设计。它维护了一个详细的命令词典，记录了每个命令"有语义意义的前缀"长度：

```typescript
const ARITY: Record<string, number> = {
    rm: 1,           // rm file.txt → pattern: "rm *"
    git: 2,          // git checkout → pattern: "git checkout *"
    "npm run": 3,    // npm run dev → pattern: "npm run *"
    docker: 2,       // docker run → pattern: "docker *"
    kubectl: 2,      // kubectl get → pattern: "kubectl *"
    // 覆盖了 200+ 常见命令
}
```

这意味着用户批准了 `git commit`，不会自动批准 `git push`（因为它们的语义前缀不同，一个是写本地仓库，一个是写远程）。

---

## 五、审批流程详解

以下是一次完整的审批流程：

```
agent 调用 shell("rm -rf dist/")
    │
    ▼
1. tree-sitter 解析为 AST
    │
    ▼
2. 识别出 rm 命令，路径参数 "dist/"
    │
    ▼
3. 展开为绝对路径 "/workspace/my-project/dist/"
    │
    ▼
4. 路径不在 agent 实例的 workspace 内（注：dist/ 实际在 workspace 内，这里举假设）
   → 触发 ask({
       permission: "shell",
       patterns: ["/workspace/my-project/dist/"],
       always: ["rm *"]   // BashArity 计算出的授权粒度
     })
    │
    ▼
5. 权限系统检查规则库
   → 没有匹配规则 → 发布 permission.asked 事件
    │
    ▼
6. 用户界面弹出审批请求
    │
    ▼
7a. 用户选择 "always"
    → 写入规则：{ permission: "shell", pattern: "rm *", action: "allow" }
    → 本次放行
    → 同会话中其他匹配此模式的 pending 请求也一并放行

7b. 用户选择 "once"
    → 本次放行，不写规则

7c. 用户选择 "reject"
    → 拒绝，并取消同会话所有 pending 请求
```

---

## 六、会话内批量放行

OpenCode 权限系统有一个很实用的优化：当用户选择 `always` 时，不只是写入数据库，还会立刻扫描同一会话内所有其他处于等待状态的请求，把能被新规则覆盖的请求全部自动放行。

```typescript
// 用户回复 "always" 之后
for (const [id, item] of pending.entries()) {
    if (item.info.sessionID !== existing.info.sessionID) continue
    const ok = item.info.patterns.every(
        (pattern) => evaluate(item.info.permission, pattern, approved).action === "allow"
    )
    if (!ok) continue
    // 自动放行
    Deferred.succeed(item.deferred, undefined)
}
```

这对于批量操作（比如 agent 同时发出 20 个 shell 调用）很有用：用户只需审批第一个，后面相似的自动通过。

---

## 七、Shell 执行层

OpenCode 使用 Effect 框架的 `ChildProcess` 模块执行命令。每次调用是独立进程（非持久化），通过三路竞争（exit / abort / timeout）决定命令结束：

```typescript
const exit = yield* Effect.raceAll([
    handle.exitCode.pipe(Effect.map(code => ({ kind: "exit", code }))),
    abort.pipe(Effect.map(() => ({ kind: "abort", code: null }))),
    timeout.pipe(Effect.map(() => ({ kind: "timeout", code: null }))),
])
```

默认超时为 2 分钟（可通过命令参数覆盖），超时后强制 kill 进程，给 3 秒等待优雅退出，否则强杀。

输出超过限制时，把完整输出写入临时文件，在返回给 agent 的内容中包含文件路径，让 agent 可以通过其他工具读取完整内容。

---

## 八、与本项目的核心差异

| 维度 | 本项目 | OpenCode |
|---|---|---|
| 安全策略 | 命令字符串黑名单 | AST 解析 + 路径级规则引擎 |
| 审批粒度 | tool 级（shell 工具整体） | 命令前缀 / 路径模式级 |
| 规则记忆 | 会话级，tool-name 粒度；shell 被排除在自动审批外 | 持久化到 SQLite，命令前缀粒度 |
| 解析能力 | 无（纯字符串匹配） | tree-sitter 语法树解析 |
| 多次调用批量放行 | 不支持 | 支持（同会话内匹配规则的 pending 请求自动放行） |
| 管道/重定向 | 禁止 | 允许（视为独立命令节点处理） |

---

## 九、对本项目的借鉴意义

1. **权限记忆应该按命令模式而不是按工具名**。目前 `SessionHITLManager` 的粒度是 `tool_name`（如 `"shell"`），这太粗了。用户批准了 `git status` 不等于批准了 `rm -rf .`。借鉴 BashArity 的思路，按命令前缀模式建立白名单是更合理的方向。

2. **"总是允许"的回复应该触发批量放行**。当前 HITL 每次只处理一个 interrupt。对于 agent 连续发出多个 shell 调用的场景，这会造成不必要的多次打断。

3. **AST 解析是提升精度的长期投资**。短期内可以用更简单的方式（如命令前缀识别 + 路径前缀匹配）实现 70% 的效果，不必一开始就引入完整的语法树解析器。

4. **三档答复（once / always / reject）比两档（approve / reject）更实用**。当前 HITL 只有批准/拒绝，没有"本会话内总是允许"这个选项。增加这个选项可以显著减少重复审批。
