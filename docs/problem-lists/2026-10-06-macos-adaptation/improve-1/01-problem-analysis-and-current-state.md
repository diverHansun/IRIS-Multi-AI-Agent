# 现状与问题

基线：6c32e00，分析日期 2026-10-06。机器为 Darwin arm64，macOS 26.6.2；uv 0.11.23，已有 Python 3.11.15 和 3.13.14。

## 职责与架构

项目是 Python CLI；pyproject.toml 注册 iris 入口，application 层编排服务，components 层执行工具，core/config 层初始化配置。平台适配可在现有边界内完成，无须新增架构层。

## 数据模型与配置流

config/ 模板经 ConfigInitializer 复制到 ~/.iris，ConfigLoader 按项目、用户、内置顺序读取。ShellConfig 把 shell_type、workspace_root 转成运行配置。

## 关键用例与问题

| ID | 现状证据 | 用户影响 |
| --- | --- | --- |
| P1 | config/agents/deep/middleware/shell.json 与 shell.example.json 写死 cmd；shell_service.py 也默认 cmd；ShellConfig 实际在 POSIX 启动 bash | 配置描述与实际执行环境不一致 |
| P2 | src/application/services/dify/upload.py::_resolve_file_paths 固定 shlex.split(posix=False) | macOS 带引号、空格、反斜线转义或 ~ 的路径解析错误 |
| P3 | src/core/config/defaults.py 的文件系统复制源写 real_filesystem.json/virtual_filesystem.json，但仓库模板为 real_files.example.json/virtual_files.example.json | 首次安装漏复制 DeepAgent 文件系统配置 |
| P4 | src/core/config/paths.py::_normalize_relative_path 使用当前平台 Path 分割 | Windows 反斜线路径迁移到 macOS 时不能正确查找配置 |
| P5 | main.py 直接 asyncio.run(run())，绕开 iris 入口的首次初始化向导 | 源码启动与安装入口行为不一致 |

## 非功能约束与测试

依赖沿用 uv.lock，先验证 Python 3.11 ARM64 安装；真实密钥与会话不写入 Git。现有 Shell、配置、CLI 集成测试可复用，但没有覆盖上述 macOS 路径与模板缺失场景。

## 文档与实现差距

README 已提及 Linux/Mac 安装，IRIS_SETUP.md 前置条件仍为 Windows + PowerShell。两处尚未给出直接在项目虚拟环境启动的 macOS 流程。

## SWE 审视

依据 learn-swe 的复杂度管理与 KISS 原则：平台分支集中在 Shell 配置和路径解析边界，复用原有配置初始化；不要增加独立 Mac 引擎、重写会话格式或升级全部依赖。既有分层和 pathlib 用法可以保留。当前主要债务是跨层默认值不一致，以及配置模板命名缺少首次安装验证。
