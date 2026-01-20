# IRIS 命令行工具配置指南

## ✅ 已完成配置

本项目已成功配置 `iris` 命令行工具，现在可以在任何目录全局使用！

### 配置内容

1. **pyproject.toml 更新**：
   - 添加了 `[build-system]` 配置（使用 hatchling）
   - 添加了 `[tool.hatch.build.targets.wheel]` 指定打包 `src` 目录
   - 添加了 `[tool.uv]` 设置 `package = true`

2. **代码结构修复**：
   - 创建了缺失的 `src/agents/deepagents/managers/` 模块
   - 添加了 `DeepAgentManager` 和 `SubagentManager` 占位符实现
   - 解决了 `ModuleNotFoundError: No module named 'src.agents.deepagents'` 错误

3. **虚拟环境安装**：
   - 项目已通过 `uv sync` 安装到 `.venv` 虚拟环境
   - `iris` 入口点已正确创建

4. **全局工具安装**：
   - 项目已通过 `uv tool install` 安装为全局工具
   - 安装位置：`C:\Users\Hansun025\.local\bin\iris.exe`
   - PATH 已包含该目录

---

## 使用方式

### 方式1：全局使用（推荐）

在**任何目录**直接运行：

```powershell
iris
```

这会启动 Multi-AI-Agent 交互式界面。

**优点**：
- ✅ 无需激活虚拟环境
- ✅ 任何目录都可用
- ✅ 使用简单

**工作原理**：
使用 `uv tool install` 安装的独立环境，与项目虚拟环境隔离。

---

### 方式2：虚拟环境使用（开发模式）

如果你需要修改项目代码并立即测试：

```powershell
# 1. 激活虚拟环境
cd d:\Projects\Langchain\Muti-AI-Agent
.venv\Scripts\Activate.ps1

# 2. 运行 iris
iris

# 或直接使用完整路径（无需激活）
d:\Projects\Langchain\Muti-AI-Agent\.venv\Scripts\iris.exe
```

**优点**：
- ✅ 代码修改立即生效（可编辑安装）
- ✅ 适合开发调试

**工作原理**：
使用项目虚拟环境中的安装版本。

---

## 维护命令

### 更新全局工具

修改代码后，更新全局安装：

```powershell
uv tool install --force d:\Projects\Langchain\Muti-AI-Agent
```

### 更新虚拟环境

同步依赖到虚拟环境：

```powershell
cd d:\Projects\Langchain\Muti-AI-Agent
uv sync
```

### 卸载全局工具

```powershell
uv tool uninstall muti-ai-agent
```

### 查看已安装工具

```powershell
uv tool list
```

---

## 📋 验证安装

### 检查命令位置

```powershell
where iris
```

应该显示：
```
C:\Users\Hansun025\.local\bin\iris.exe
```

### 验证 PATH

```powershell
$env:Path -split ';' | Select-String 'local\\bin'
```

应该包含：
```
C:\Users\Hansun025\.local\bin
```

---

## ⚠️ 常见问题

### Q: 报错 "No module named src"

**原因**：使用了旧的 stub 或 PATH 配置不正确。

**解决**：
```powershell
# 1. 删除旧的安装
uv tool uninstall muti-ai-agent

# 2. 重新安装
uv tool install d:\Projects\Langchain\Muti-AI-Agent

# 3. 重启终端
```

### Q: 报错 "No module named 'src.agents.deepagents'"

**原因**：项目代码中引用了缺失的 DeepAgent 管理器模块（已修复）。

**解决**：
此问题已通过创建占位符模块解决。如果仍然遇到此错误：
```powershell
# 重新同步和安装
cd d:\Projects\Langchain\Muti-AI-Agent
uv sync
uv tool install --force d:\Projects\Langchain\Muti-AI-Agent
```

**注意**：`DeepAgentManager` 和 `SubagentManager` 当前为占位符实现。使用 Deep Agent 功能时可能会提示 `NotImplementedError`。这些功能需要进一步开发。

### Q: 修改代码后没有生效

**原因**：全局工具使用独立环境，不会自动更新。

**解决**：
- **方式1（推荐）**：使用虚拟环境模式开发
  ```powershell
  .venv\Scripts\Activate.ps1
  iris
  ```

- **方式2**：强制更新全局工具
  ```powershell
  uv tool install --force d:\Projects\Langchain\Muti-AI-Agent
  ```

### Q: 命令找不到

**检查 PATH**：
```powershell
# 临时添加（仅当前会话）
$env:Path = "C:\Users\Hansun025\.local\bin;$env:Path"

# 永久添加（需管理员权限或用户权限）
[Environment]::SetEnvironmentVariable(
    "Path",
    [Environment]::GetEnvironmentVariable("Path", "User") + ";C:\Users\Hansun025\.local\bin",
    "User"
)
```

然后重启终端。

---

## 项目配置文件说明

### pyproject.toml 关键配置

```toml
[project.scripts]
iris = "src.application.cli.main:main"  # 定义命令入口点

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src"]  # 指定打包目录

[tool.uv]
package = true  # 启用 uv 打包支持
```

这些配置确保：
- ✅ `iris` 命令正确链接到 `src.application.cli.main:main`
- ✅ 项目可以被正确打包和安装
- ✅ `src` 目录被包含在安装包中

---

## 完成！

现在你可以在任何目录直接运行 `iris` 命令了！

```powershell
# 打开新的 PowerShell 窗口
iris
```

享受你的 Multi-AI-Agent 吧！
