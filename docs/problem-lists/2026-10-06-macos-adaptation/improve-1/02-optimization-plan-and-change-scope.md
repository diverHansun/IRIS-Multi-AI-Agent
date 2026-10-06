# 实施方案与改动范围

## 方案选择

优先使用锁定依赖 + 项目 .venv：复现成本低，直接满足本机安装要求。另两个方案是 uv tool 创建额外环境，或 Docker 运行；前者重复环境，后者不符合本机虚拟环境目标，因此本轮不采用。

## Stage 1：环境与配置

运行 uv sync --python 3.11 --locked。将 shell.json/shell.example.json 的 shell_type 改为 auto，ShellConfig 在运行时按平台解析 auto（Windows cmd，macOS/Linux bash），service 层复用组件解析结果。修正 defaults.py 文件系统模板源路径；只补齐已有用户配置缺失的文件，不覆盖用户配置。

## Stage 2：迁移与启动

paths.py 统一分隔符。Dify upload.py 按当前平台解析上传参数，处理用户目录 ~，保留 Windows 引号路径支持。main.py 保留 --debug 参数与日志配置，调用正式 CLI 入口以获得相同的首次配置向导。

## Stage 3：可重复安装与验证

新增 scripts/setup-macos.sh：检测 macOS/uv，创建 Python 3.11 环境，同步锁定依赖，初始化 ~/.iris 并在不存在时创建权限为 600 的 .env；最后打印启动方式。脚本从自己的位置定位项目，支持路径空格，不改 shell 启动文件。README、IRIS_SETUP 增加 macOS 安装和启动说明。

## 文件与包范围

改动限于 Shell config/service、core/config 的 defaults/paths、Dify upload、main.py、安装脚本、上述文档以及相应测试。无依赖升级、引擎接口或存储协议变更。

## 兼容与回滚

auto 是新增可移植值；显式 cmd/powershell/bash 继续兼容原有行为。POSIX 实际运行 bash，终端本身可以是 zsh。配置初始化仍不覆盖已有文件；修改过的配置不会自动迁移。撤回本轮代码 diff 可恢复逻辑，.venv 可按 uv.lock 重建；用户 ~/.iris 数据保留。

## 本轮之外

远程模型对话、MCP 服务和 Crawl4AI Docker 服务需要对应密钥或服务端，本轮只验证本机可完成的启动与执行链路。不会自动下载 Ollama 模型。
