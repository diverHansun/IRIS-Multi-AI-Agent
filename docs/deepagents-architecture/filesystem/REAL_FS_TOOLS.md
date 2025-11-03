# 真实文件系统危险功能实现设计

## 1. 概述

本文档讨论真实文件系统中间件的危险功能实现方案，包括：
- `write_real_file`：写入文件到真实文件系统
- `edit_real_file`：编辑真实文件系统中的文件
- `execute_shell`：执行 Shell 命令

**核心原则**：通过 HITL（Human-in-the-Loop）机制确保所有危险操作都需要用户明确批准。

---

## 2. 当前架构分析

### 2.1 现有安全机制

**真实文件系统中间件（只读）**：
- 路径白名单：`allowed_paths`
- 路径黑名单：`excluded_paths`（优先级最高）
- 文件类型限制：`allowed_extensions`
- 文件大小限制：`max_file_size`
- **只读限制**：当前不提供写入、编辑工具

**HITL 配置**（`mainagents.json`）：
```json
"safety_config": {
  "hitl_config": {
    "dangerous_tools": ["delete_file", "execute_shell", "rm", "sudo"],
    "tools": {
      "delete_file": {
        "allow_auto_approve": false,
        "warning_message": "This operation cannot be undone!"
      }
    }
  }
}
```

### 2.2 参考实现

**deepagents_cli 实现**（虚拟文件系统）：
- `write_file` 和 `edit_file` 通过 `InterruptOnConfig` 触发 HITL
- `FileOpTracker` 追踪文件操作并生成 diff 预览
- `build_approval_preview` 生成审批预览（包含 diff）
- 审批时显示文件变更的详细信息

**关键代码位置**：
- `deepagents_cli/file_ops.py`：文件操作追踪和 diff 生成
- `deepagents_cli/execution.py`：HITL 审批流程
- `deepagents_cli/agent.py`：工具中断配置

---

## 3. 设计方案讨论

### 3.1 write_real_file

**功能**：创建新文件或覆盖已有文件。

**安全策略**：
1. **路径安全检查**（复用现有机制）：
   - 必须在 `allowed_paths` 白名单内
   - 不能匹配 `excluded_paths` 黑名单
   - 路径规范化（防止目录遍历）

2. **HITL 审批**：
   - 必须配置为危险工具：`"write_real_file"` 加入 `dangerous_tools`
   - 审批预览包括：
     - 文件路径
     - 如果是覆盖，显示现有文件内容（`before_content`）
     - 新文件内容（`after_content`）
     - Diff（如果覆盖）
     - 文件大小和行数

3. **实现要点**：
   - 复用真实文件系统的路径解析和安全检查逻辑
   - 审批前读取现有文件内容（如果存在）用于 diff
   - 审批通过后执行写入操作
   - 写入后验证文件内容

**工具签名**：
```python
def write_real_file(
    file_path: str,
    content: str,
    encoding: str = "utf-8"
) -> dict:
    """Write content to a real file.
    
    Args:
        file_path: Path to file (must be in allowed_paths)
        content: File content to write
        encoding: File encoding (default: utf-8)
    
    Returns:
        Success status and file metadata
    """
```

---

### 3.2 edit_real_file

**功能**：在真实文件中执行字符串替换（类似虚拟文件系统的 `edit_file`）。

**安全策略**：
1. **路径安全检查**（同 write_real_file）
2. **文件存在性检查**：文件必须已存在
3. **HITL 审批**：
   - 必须配置为危险工具
   - 审批预览包括：
     - 文件路径
     - 原始文件内容（`before_content`）
     - 替换后的内容（`after_content`）
     - Diff（显示变更）
     - 匹配次数和变更行数

4. **实现要点**：
   - 读取现有文件内容
   - 使用 `perform_string_replacement`（参考 deepagents_cli）
   - 生成 diff 供审批
   - 审批通过后执行替换

**工具签名**：
```python
def edit_real_file(
    file_path: str,
    old_string: str,
    new_string: str,
    replace_all: bool = False,
    encoding: str = "utf-8"
) -> dict:
    """Edit a real file by replacing text.
    
    Args:
        file_path: Path to file (must exist and be in allowed_paths)
        old_string: Text to replace
        new_string: Replacement text
        replace_all: Replace all occurrences (default: False)
        encoding: File encoding (default: utf-8)
    
    Returns:
        Success status, occurrences matched, and file metadata
    """
```

---

### 3.3 execute_shell

**功能**：执行 Shell 命令（bash/sh 等）。

**安全策略**：
1. **命令限制**：
   - 黑名单命令：`rm -rf /`, `sudo`, `chmod 777`, 等
   - 禁止修改敏感目录的命令
   - 禁止网络相关命令（可选，根据配置）

2. **路径限制**：
   - 工作目录必须在 `allowed_paths` 内
   - 禁止访问 `excluded_paths` 内的文件

3. **HITL 审批**：
   - 必须配置为危险工具
   - 审批预览包括：
     - 完整命令
     - 工作目录
     - 命令描述（如果 Agent 提供）
     - 警告信息（针对高风险命令）

4. **执行限制**：
   - 超时控制（默认 30 秒）
   - 输出大小限制（防止内存溢出）
   - 资源限制（CPU、内存）

**工具签名**：
```python
def execute_shell(
    command: str,
    working_directory: str | None = None,
    timeout: int = 30,
    description: str | None = None
) -> dict:
    """Execute a shell command.
    
    Args:
        command: Shell command to execute
        working_directory: Working directory (must be in allowed_paths)
        timeout: Execution timeout in seconds (default: 30)
        description: Human-readable description of what the command does
    
    Returns:
        Command output, exit code, and execution metadata
    """
```

**注意事项**：
- 执行前验证工作目录在白名单内
- 使用 `subprocess.run` 并设置超时
- 捕获 stdout、stderr 和 exit code
- 错误时返回详细错误信息

---

## 4. HITL 集成方案

### 4.1 配置扩展

在 `mainagents.json` 中添加新工具配置：

```json
"safety_config": {
  "hitl_config": {
    "dangerous_tools": [
      "delete_file", 
      "execute_shell", 
      "write_real_file",
      "edit_real_file",
      "rm", 
      "sudo"
    ],
    "tools": {
      "write_real_file": {
        "allow_auto_approve": false,
        "warning_message": "This will write to the real filesystem!"
      },
      "edit_real_file": {
        "allow_auto_approve": false,
        "warning_message": "This will modify a real file!"
      },
      "execute_shell": {
        "allow_auto_approve": false,
        "warning_message": "This will execute a shell command on the host system!"
      }
    }
  }
}
```

### 4.2 审批预览生成

复用 `FileOpTracker` 和 `build_approval_preview` 的逻辑：

**对于 write_real_file**：
```python
def build_write_real_file_preview(args: dict, assistant_id: str | None) -> ApprovalPreview:
    file_path = args.get("file_path")
    content = args.get("content", "")
    physical_path = resolve_physical_path(file_path, assistant_id)
    
    before = _safe_read(physical_path) if physical_path and physical_path.exists() else ""
    after = content
    diff = compute_unified_diff(before or "", after, display_path, max_lines=800)
    
    details = [
        f"File: {file_path}",
        "Action: Write to real filesystem",
        f"Lines: {_count_lines(after)}",
        f"Bytes: {len(after.encode('utf-8'))}"
    ]
    if before:
        details.append("⚠️  This will overwrite existing file!")
    
    return ApprovalPreview(
        title=f"Write {display_path}",
        details=details,
        diff=diff,
        diff_title=f"Diff {display_path}"
    )
```

**对于 edit_real_file**：
- 读取现有文件内容
- 执行替换操作（模拟）
- 生成 diff
- 显示匹配次数和变更行数

**对于 execute_shell**：
```python
def build_execute_shell_preview(args: dict) -> ApprovalPreview:
    command = args.get("command", "")
    working_dir = args.get("working_directory")
    
    # 检查命令风险
    high_risk_keywords = ["rm -rf", "sudo", "chmod 777", "format"]
    is_risky = any(keyword in command for keyword in high_risk_keywords)
    
    details = [
        f"Command: {command}",
        f"Working Directory: {working_dir or '(current)'}"
    ]
    if is_risky:
        details.append("⚠️  High-risk command detected!")
    
    return ApprovalPreview(
        title="Execute Shell Command",
        details=details,
        diff=None
    )
```

### 4.3 HITL Handler 扩展

在 `src/application/services/agent/deep/hitl/handler.py` 中：

1. 检测危险工具调用（`write_real_file`, `edit_real_file`, `execute_shell`）
2. 调用对应的预览生成函数
3. 在审批提示中显示预览和 diff
4. 等待用户决策后继续执行或拒绝

---

## 5. 实现位置

### 5.1 工具实现

**文件位置**：
```
src/components/deepagents/runtime_middlewares/real_filesystem/
  ├── middleware.py          # 扩展 RealFilesystemMiddleware
  ├── tools.py               # 新增 write_real_file, edit_real_file, execute_shell
  └── utils.py               # 路径安全检查、diff 生成等工具函数
```

### 5.2 HITL 集成

**文件位置**：
```
src/application/services/agent/deep/hitl/
  ├── handler.py             # 扩展审批流程，支持新工具
  ├── file_ops.py            # 扩展 FileOpTracker，支持真实文件系统操作
  └── preview.py             # 新增预览生成函数
```

### 5.3 配置更新

**文件位置**：
- `config/agents/deep/models/mainagents.json`：添加危险工具配置
- `config/agents/deep/middleware/filesystem/real_filesystem.json`：可选，添加写入相关配置

---

## 6. 安全考虑

### 6.1 路径安全

- **绝对路径解析**：所有路径必须规范化并验证在白名单内
- **符号链接处理**：避免跟随符号链接绕过白名单（`follow_symlinks: false`）
- **目录遍历防护**：拒绝包含 `../` 的路径

### 6.2 命令执行安全

- **命令黑名单**：禁止执行高风险命令
- **工作目录限制**：必须在白名单内
- **资源限制**：超时、输出大小限制、内存限制

### 6.3 审计日志

- 记录所有真实文件系统写入操作
- 记录 Shell 命令执行历史
- 记录审批决策（批准/拒绝）

---

## 7. 实施优先级

### 阶段一：基础写入功能
1. 实现 `write_real_file`
2. 集成 HITL 审批
3. 实现 diff 预览

### 阶段二：编辑功能
1. 实现 `edit_real_file`
2. 集成字符串替换逻辑
3. 完善 diff 预览

### 阶段三：Shell 执行
1. 实现 `execute_shell`
2. 命令安全验证
3. 超时和资源限制

---

## 8. 测试策略

### 8.1 单元测试

- 路径安全检查
- 文件写入和编辑操作
- Diff 生成准确性
- Shell 命令执行和超时

### 8.2 集成测试

- HITL 审批流程
- 文件操作追踪
- 错误处理和回滚

### 8.3 安全测试

- 路径遍历攻击
- 命令注入攻击
- 符号链接绕过
- 权限绕过尝试

---

## 9. 与虚拟文件系统的对比

| 特性 | 虚拟文件系统 | 真实文件系统（只读） | 真实文件系统（写入） |
|------|-------------|-------------------|-------------------|
| 存储位置 | Agent 状态（内存） | 宿主机文件系统 | 宿主机文件系统 |
| 写入能力 | ✅ 支持 | ❌ 不支持 | ✅ 支持（需 HITL） |
| 编辑能力 | ✅ 支持 | ❌ 不支持 | ✅ 支持（需 HITL） |
| 删除能力 | ✅ 支持 | ❌ 不支持 | ❓ 待定 |
| 安全性 | 高（沙箱） | 高（只读） | 中等（需审批） |
| 持久性 | 会话级别 | 永久 | 永久 |

---

## 10. 开放问题

1. **是否支持删除文件**（`delete_real_file`）？
   - 建议：初期不实现，后续根据需求决定

2. **是否支持创建目录**（`mkdir_real`）？
   - 建议：可以作为 `execute_shell` 的用例，或单独实现

3. **Shell 命令的输出大小限制**？
   - 建议：默认 1MB，可配置

4. **是否支持批量操作**？
   - 建议：初期不支持，每个操作单独审批

5. **错误回滚机制**？
   - 建议：写入前备份文件，失败时恢复

---

## 11. 参考资源

- `deepagents_cli-0.0.7/deepagents_cli/file_ops.py`：文件操作追踪和 diff 生成
- `deepagents_cli-0.0.7/deepagents_cli/execution.py`：HITL 审批流程
- `src/application/services/agent/deep/hitl/handler.py`：HITL Handler 实现
- `docs/deepagents-cli/02-file-operation-tracking.md`：文件操作追踪设计
- `docs/deepagents-architecture/filesystem/03-真实文件系统实现细节.md`：真实文件系统只读实现

