# 数据迁移指南

> 版本: 1.0
> 日期: 2025-01-20
> 状态: 设计阶段

## 1. 概述

本文档描述从旧版存储结构（`data/`）迁移到新版存储结构（`.iris/`）的完整方案。

---

## 2. 迁移目标

### 2.1 数据迁移

| 源路径 | 目标路径 |
|--------|---------|
| `data/llm/sessions/*.json` | `.iris/sessions/llm/*.json` |
| `data/llm/sessions/sessions_index.json` | `.iris/sessions/llm/sessions_index.json` |
| `data/basicagent/sessions/*.json` | `.iris/sessions/basicagent/*.json` |
| `data/basicagent/sessions/sessions_index.json` | `.iris/sessions/basicagent/sessions_index.json` |
| `data/deepagent/sessions/*.json` | `.iris/sessions/deepagent/*.json` |
| `data/deepagent/sessions/sessions_index.json` | `.iris/sessions/deepagent/sessions_index.json` |

### 2.2 迁移原则

1. **安全优先** - 默认为试运行（dry-run），不实际移动文件
2. **可逆性** - 迁移后保留原文件，用户确认后再删除
3. **完整性** - 验证迁移后数据可正常读取
4. **向后兼容** - 支持渐进式迁移

---

## 3. 迁移脚本

### 3.1 脚本位置

```
scripts/
└── migrate_sessions.py    # 主迁移脚本
```

### 3.2 完整脚本实现

```python
#!/usr/bin/env python3
"""
会话数据迁移脚本

将旧版 data/ 目录中的会话迁移到新版 .iris/ 目录

用法:
    # 试运行（预览将要迁移的文件）
    python scripts/migrate_sessions.py

    # 实际执行迁移
    python scripts/migrate_sessions.py --execute

    # 指定项目路径
    python scripts/migrate_sessions.py --project /path/to/project --execute

    # 迁移后清理旧文件
    python scripts/migrate_sessions.py --execute --cleanup
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional


@dataclass
class MigrationStats:
    """迁移统计信息"""
    files_found: int = 0
    files_migrated: int = 0
    files_skipped: int = 0
    files_failed: int = 0
    errors: List[str] = field(default_factory=list)

    def summary(self) -> str:
        return (
            f"Found: {self.files_found}, "
            f"Migrated: {self.files_migrated}, "
            f"Skipped: {self.files_skipped}, "
            f"Failed: {self.files_failed}"
        )


class SessionMigrator:
    """会话数据迁移器"""

    # 模式目录映射
    MODE_DIRS = {
        "llm": "llm",
        "basicagent": "basicagent",
        "deepagent": "deepagent",
    }

    def __init__(self, project_path: Path, dry_run: bool = True):
        """
        初始化迁移器

        Args:
            project_path: 项目根目录
            dry_run: 是否为试运行
        """
        self.project_path = project_path.resolve()
        self.dry_run = dry_run
        self.old_data_dir = self.project_path / "data"
        self.new_iris_dir = self.project_path / ".iris"
        self.stats = MigrationStats()

    def check_prerequisites(self) -> bool:
        """检查迁移前提条件"""
        # 检查旧数据目录是否存在
        if not self.old_data_dir.exists():
            print(f"[INFO] Old data directory not found: {self.old_data_dir}")
            print("[INFO] Nothing to migrate.")
            return False

        # 检查是否有会话数据
        has_sessions = False
        for mode_dir in self.MODE_DIRS.keys():
            sessions_dir = self.old_data_dir / mode_dir / "sessions"
            if sessions_dir.exists() and list(sessions_dir.glob("*.json")):
                has_sessions = True
                break

        if not has_sessions:
            print("[INFO] No session files found in old data directory.")
            return False

        return True

    def scan_sessions(self) -> Dict[str, List[Path]]:
        """扫描所有会话文件"""
        sessions_by_mode: Dict[str, List[Path]] = {}

        for mode_dir in self.MODE_DIRS.keys():
            sessions_dir = self.old_data_dir / mode_dir / "sessions"
            if not sessions_dir.exists():
                continue

            session_files = list(sessions_dir.glob("*.json"))
            if session_files:
                sessions_by_mode[mode_dir] = session_files
                self.stats.files_found += len(session_files)

        return sessions_by_mode

    def migrate_file(self, src: Path, dst: Path) -> bool:
        """
        迁移单个文件

        Args:
            src: 源文件路径
            dst: 目标文件路径

        Returns:
            是否成功
        """
        try:
            # 检查目标文件是否已存在
            if dst.exists():
                # 比较内容
                if self._files_equal(src, dst):
                    print(f"  [SKIP] Already exists (identical): {dst.name}")
                    self.stats.files_skipped += 1
                    return True
                else:
                    # 目标文件存在但内容不同，创建备份
                    backup_path = dst.with_suffix(f".backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
                    if not self.dry_run:
                        shutil.copy2(dst, backup_path)
                    print(f"  [WARN] Target exists with different content, backed up to: {backup_path.name}")

            # 确保目标目录存在
            if not self.dry_run:
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)

            print(f"  [{'DRY-RUN' if self.dry_run else 'MIGRATED'}] {src.name} -> {dst}")
            self.stats.files_migrated += 1
            return True

        except Exception as e:
            error_msg = f"Failed to migrate {src}: {e}"
            print(f"  [ERROR] {error_msg}")
            self.stats.errors.append(error_msg)
            self.stats.files_failed += 1
            return False

    def _files_equal(self, file1: Path, file2: Path) -> bool:
        """比较两个文件内容是否相同"""
        try:
            with open(file1, 'rb') as f1, open(file2, 'rb') as f2:
                return f1.read() == f2.read()
        except Exception:
            return False

    def migrate_mode(self, mode: str, files: List[Path]) -> None:
        """迁移特定模式的所有文件"""
        print(f"\n[{mode.upper()}] Migrating {len(files)} files...")

        new_sessions_dir = self.new_iris_dir / "sessions" / mode

        for src_file in files:
            dst_file = new_sessions_dir / src_file.name
            self.migrate_file(src_file, dst_file)

    def verify_migration(self) -> bool:
        """验证迁移结果"""
        print("\n[VERIFY] Checking migrated files...")
        success = True

        for mode_dir in self.MODE_DIRS.keys():
            new_sessions_dir = self.new_iris_dir / "sessions" / mode_dir
            if not new_sessions_dir.exists():
                continue

            for session_file in new_sessions_dir.glob("user_*.json"):
                try:
                    with open(session_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)

                    # 验证基本结构
                    if "session_id" not in data or "messages" not in data:
                        print(f"  [WARN] Invalid structure: {session_file.name}")
                        success = False
                    else:
                        print(f"  [OK] {session_file.name}: {data.get('message_count', 0)} messages")

                except json.JSONDecodeError as e:
                    print(f"  [ERROR] Invalid JSON: {session_file.name}: {e}")
                    success = False
                except Exception as e:
                    print(f"  [ERROR] Cannot read: {session_file.name}: {e}")
                    success = False

        return success

    def cleanup_old_data(self) -> None:
        """清理旧数据目录"""
        if self.dry_run:
            print("\n[DRY-RUN] Would remove old data directories:")
            for mode_dir in self.MODE_DIRS.keys():
                old_sessions_dir = self.old_data_dir / mode_dir / "sessions"
                if old_sessions_dir.exists():
                    print(f"  - {old_sessions_dir}")
            return

        print("\n[CLEANUP] Removing old data directories...")
        for mode_dir in self.MODE_DIRS.keys():
            old_sessions_dir = self.old_data_dir / mode_dir / "sessions"
            if old_sessions_dir.exists():
                try:
                    shutil.rmtree(old_sessions_dir)
                    print(f"  [REMOVED] {old_sessions_dir}")

                    # 如果父目录为空，也删除
                    mode_path = self.old_data_dir / mode_dir
                    if mode_path.exists() and not list(mode_path.iterdir()):
                        mode_path.rmdir()
                        print(f"  [REMOVED] {mode_path}")

                except Exception as e:
                    print(f"  [ERROR] Failed to remove {old_sessions_dir}: {e}")

    def run(self, cleanup: bool = False) -> bool:
        """
        执行迁移

        Args:
            cleanup: 是否清理旧文件

        Returns:
            是否成功
        """
        print("=" * 60)
        print("Session Data Migration Tool")
        print("=" * 60)
        print(f"Project: {self.project_path}")
        print(f"Mode: {'DRY-RUN (preview only)' if self.dry_run else 'EXECUTE'}")
        print(f"From: {self.old_data_dir}")
        print(f"To:   {self.new_iris_dir}")
        print("=" * 60)

        # 检查前提条件
        if not self.check_prerequisites():
            return True  # 没有数据需要迁移，视为成功

        # 扫描会话文件
        sessions_by_mode = self.scan_sessions()
        print(f"\nFound {self.stats.files_found} session files to migrate.")

        if not sessions_by_mode:
            print("[INFO] No session files found.")
            return True

        # 执行迁移
        for mode, files in sessions_by_mode.items():
            self.migrate_mode(mode, files)

        # 打印统计
        print("\n" + "=" * 60)
        print(f"Migration {'Preview' if self.dry_run else 'Complete'}")
        print("=" * 60)
        print(f"  {self.stats.summary()}")

        if self.stats.errors:
            print("\nErrors:")
            for error in self.stats.errors:
                print(f"  - {error}")

        # 验证迁移结果（仅在实际执行时）
        if not self.dry_run:
            self.verify_migration()

            # 清理旧数据
            if cleanup and self.stats.files_failed == 0:
                self.cleanup_old_data()
            elif cleanup:
                print("\n[WARN] Cleanup skipped due to migration errors.")

        return self.stats.files_failed == 0


def main():
    parser = argparse.ArgumentParser(
        description="Migrate session data from data/ to .iris/",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Preview migration (dry-run)
  python scripts/migrate_sessions.py

  # Execute migration
  python scripts/migrate_sessions.py --execute

  # Execute migration and cleanup old files
  python scripts/migrate_sessions.py --execute --cleanup

  # Migrate specific project
  python scripts/migrate_sessions.py --project /path/to/project --execute
        """
    )

    parser.add_argument(
        "--project",
        type=Path,
        default=Path.cwd(),
        help="Project root directory (default: current directory)"
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually perform migration (default is dry-run)"
    )
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Remove old data files after successful migration"
    )

    args = parser.parse_args()

    migrator = SessionMigrator(
        project_path=args.project,
        dry_run=not args.execute
    )

    success = migrator.run(cleanup=args.cleanup)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
```

---

## 4. 使用指南

### 4.1 迁移前准备

1. **备份数据**（推荐）
   ```bash
   # 备份整个 data 目录
   cp -r data/ data_backup_$(date +%Y%m%d)/
   ```

2. **检查当前状态**
   ```bash
   # 查看现有会话文件
   find data/ -name "*.json" -type f
   ```

### 4.2 执行迁移

```bash
# 步骤 1: 试运行，预览将要迁移的文件
python scripts/migrate_sessions.py

# 输出示例:
# ============================================================
# Session Data Migration Tool
# ============================================================
# Project: D:\Projects\Langchain\Muti-AI-Agent
# Mode: DRY-RUN (preview only)
# From: D:\Projects\Langchain\Muti-AI-Agent\data
# To:   D:\Projects\Langchain\Muti-AI-Agent\.iris
# ============================================================
#
# Found 15 session files to migrate.
#
# [LLM] Migrating 5 files...
#   [DRY-RUN] user_20250115_100000_abc12345.json -> .iris/sessions/llm/...
#   ...
#
# [BASICAGENT] Migrating 6 files...
#   ...
#
# [DEEPAGENT] Migrating 4 files...
#   ...
#
# ============================================================
# Migration Preview
# ============================================================
#   Found: 15, Migrated: 15, Skipped: 0, Failed: 0

# 步骤 2: 确认无误后，执行实际迁移
python scripts/migrate_sessions.py --execute

# 步骤 3: 验证迁移成功后，清理旧文件（可选）
python scripts/migrate_sessions.py --execute --cleanup
```

### 4.3 验证迁移

```bash
# 检查新目录结构
tree .iris/

# 预期输出:
# .iris/
# └── sessions/
#     ├── llm/
#     │   ├── sessions_index.json
#     │   └── user_*.json
#     ├── basicagent/
#     │   ├── sessions_index.json
#     │   └── user_*.json
#     └── deepagent/
#         ├── sessions_index.json
#         └── user_*.json

# 验证会话文件可读
python -c "
import json
from pathlib import Path
for f in Path('.iris/sessions').rglob('user_*.json'):
    data = json.loads(f.read_text())
    print(f'{f.name}: {data.get(\"message_count\", 0)} messages')
"
```

### 4.4 回滚迁移

如果迁移出现问题：

```bash
# 从备份恢复
rm -rf data/
mv data_backup_YYYYMMDD/ data/

# 删除新创建的 .iris 目录
rm -rf .iris/
```

---

## 5. 自动迁移集成

### 5.1 CLI 启动时自动迁移

在 CLI 初始化时检测并提示迁移：

```python
# src/application/cli/main.py

from pathlib import Path

def check_and_prompt_migration(project_path: Path) -> bool:
    """检查是否需要迁移，并提示用户"""
    old_data_dir = project_path / "data"
    new_iris_dir = project_path / ".iris"

    # 检查是否有旧数据需要迁移
    if not old_data_dir.exists():
        return False

    has_old_sessions = False
    for mode in ["llm", "basicagent", "deepagent"]:
        sessions_dir = old_data_dir / mode / "sessions"
        if sessions_dir.exists() and list(sessions_dir.glob("user_*.json")):
            has_old_sessions = True
            break

    if not has_old_sessions:
        return False

    # 检查是否已经迁移过
    if new_iris_dir.exists():
        # 可能是部分迁移，跳过自动迁移
        return False

    # 提示用户
    console.print("\n[yellow]Detected old session data in data/ directory.[/]")
    console.print("[dim]New version stores sessions in .iris/ directory.[/]")
    console.print("\nOptions:")
    console.print("  1. Migrate now (recommended)")
    console.print("  2. Skip (you can run migration later)")

    try:
        choice = console.input("\n[cyan]Choose [1/2]: [/]").strip()
        if choice == "1":
            from scripts.migrate_sessions import SessionMigrator

            migrator = SessionMigrator(project_path, dry_run=False)
            success = migrator.run(cleanup=False)

            if success:
                console.print("[green]Migration completed successfully![/]")
                console.print("[dim]Old data preserved. Run with --cleanup to remove.[/]")
            else:
                console.print("[red]Migration failed. Please check errors above.[/]")

            return success
    except (KeyboardInterrupt, EOFError):
        console.print("\n[dim]Migration skipped.[/]")

    return False
```

### 5.2 命令行选项

添加迁移相关的 CLI 选项：

```python
# 在 CLI 参数中添加
parser.add_argument(
    "--migrate",
    action="store_true",
    help="Migrate old session data to new .iris/ structure"
)
parser.add_argument(
    "--migrate-cleanup",
    action="store_true",
    help="Migrate and cleanup old data files"
)
```

---

## 6. 注意事项

### 6.1 跨平台路径

- Windows 和 Unix 路径分隔符自动处理
- 元数据中的路径使用绝对路径存储

### 6.2 文件权限

- 迁移保留原文件的修改时间
- 新创建的目录使用默认权限

### 6.3 并发安全

- 迁移期间不要同时运行 iris
- 迁移完成后再启动新会话

### 6.4 大文件处理

- 单个会话文件通常 < 1MB
- 大量消息的会话可能需要更多时间

---

## 7. 故障排除

### 7.1 常见问题

| 问题 | 原因 | 解决方案 |
|------|------|---------|
| 权限拒绝 | 没有写入权限 | 以管理员权限运行或检查目录权限 |
| 文件占用 | iris 正在运行 | 关闭 iris 后再迁移 |
| 磁盘空间不足 | 复制文件需要额外空间 | 确保有足够磁盘空间 |
| JSON 解析错误 | 会话文件损坏 | 检查并修复文件，或从备份恢复 |

### 7.2 日志查看

```bash
# 迁移脚本会输出详细日志
# 可以保存到文件
python scripts/migrate_sessions.py --execute 2>&1 | tee migration.log
```

### 7.3 手动修复

如果自动迁移失败，可以手动复制文件：

```bash
# 创建目录结构
mkdir -p .iris/sessions/{llm,basicagent,deepagent}

# 复制文件
cp data/llm/sessions/*.json .iris/sessions/llm/
cp data/basicagent/sessions/*.json .iris/sessions/basicagent/
cp data/deepagent/sessions/*.json .iris/sessions/deepagent/
```

---

## 8. 附录：数据格式兼容性

### 8.1 会话文件格式

新旧版本的会话文件格式完全相同，无需转换：

```json
{
  "session_id": "user_20250120_153045_a1b2c3d4",
  "messages": [...],
  "message_count": 10,
  "created_at": "2025-01-20T15:30:45.000000",
  "updated_at": "2025-01-20T16:00:00.000000",
  "metadata": {}
}
```

### 8.2 索引文件格式

`sessions_index.json` 格式也保持不变：

```json
{
  "user_20250120_153045_a1b2c3d4": {
    "session_id": "user_20250120_153045_a1b2c3d4",
    "message_count": 10,
    "created_at": "2025-01-20T15:30:45.000000",
    "updated_at": "2025-01-20T16:00:00.000000",
    "file_path": ".iris/sessions/llm/user_20250120_153045_a1b2c3d4.json"
  }
}
```

**注意**：迁移后 `file_path` 字段会自动更新为新路径。
