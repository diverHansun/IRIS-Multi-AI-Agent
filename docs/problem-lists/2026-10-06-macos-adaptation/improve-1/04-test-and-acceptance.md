# 测试与验收标准

遵循现有 pytest 单元/集成目录结构，不另建项目测试体系。

| ID | 场景 | 验证 |
| --- | --- | --- |
| A1 | 原生虚拟环境 | uv sync --python 3.11 --locked 成功；.venv/bin/python 显示 arm64 与虚拟环境路径；uv pip check 无冲突 |
| A2 | Shell 平台解析 | auto 在 POSIX 解析为 bash，Windows 分支解析为 cmd；显式配置保持兼容；真实 shell 执行与状态保留成功 |
| A3 | 路径迁移 | Windows 分隔符配置引用可找到文件；POSIX 引号/空格/中文/转义/~ 上传路径正确 |
| A4 | 首次配置 | 临时目录初始化后 real_filesystem.json 和 virtual_filesystem.json 均存在；重复初始化保留用户修改 |
| A5 | 本机启动 | .venv/bin/iris 显示首次配置向导；python main.py --help 成功；关键 CLI/配置/文件系统回归通过 |
| A6 | 安装可重复 | bash -n scripts/setup-macos.sh；在本机运行脚本两次不覆盖用户配置；文档中的启动命令可执行 |

新增回归测试先在基线上运行，确认相应断言失败，再修代码。外部服务不使用虚构密钥验证。全量测试如有基线失败，逐项与 HEAD 对照，写入 05 而不掩盖。

风险关注：含空格路径的 shell 引用、Windows 反斜线、已有配置被覆盖、service 与实际 Shell 元数据不一致。Windows 可验证配置分支，但实际 Windows 进程需在 Windows 上验证。
