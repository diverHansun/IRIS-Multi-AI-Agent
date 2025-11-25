"""
CLI 视觉主题配置。

集中管理颜色、符号、组件样式、缩进与辅助样式函数，便于全局统一调整。
按需求禁用 emoji，符号使用 ASCII/基础 Unicode 字符。
"""

from rich import box

# ========== 颜色系统 ==========

# 品牌色（仅用于 Logo）
BRAND_COLORS = {
    "jasmine": "#C2FF62",      # Jasmine Green
    "scifi_blue": "#50B4FF",   # Sci-Fi Blue
}

# 主题色（界面与状态）
COLORS = {
    # 主色调
    "primary": "#A8E650",
    "secondary": "#50B4FF",

    # 功能色
    "success": "#34d399",
    "warning": "#fbbf24",
    "error": "#ef4444",
    "info": "#3b82f6",

    # 文本色
    "text_primary": "#ffffff",
    "text_dim": "#6b7280",

    # 角色色
    "user": "#ffffff",
    "agent": "#A8E650",
    "tool": "#fbbf24",
}

# ========== 符号体系（无 emoji） ==========

# 工具符号（ASCII 降级版）
TOOL_ICONS = {
    "read_file": "[R]",
    "write_file": "[W]",
    "edit_file": "[E]",
    "list_files": "[LS]",
    "glob": "[GLOB]",
    "grep": "[GREP]",
    "shell": "[!]",
    "execute": "[RUN]",
    "web_search": "[WEB]",
    "http_request": "[HTTP]",
    "task": "[AGENT]",
    "write_todos": "[TODO]",
    "default": "[*]",
}

# 状态符号
STATUS_SYMBOLS = {
    "completed": "[OK]",
    "in_progress": "[..]",
    "pending": "[ ]",
    "failed": "[X]",
}

# 装饰符号
DECORATIVE_SYMBOLS = {
    "bullet": "•",
    "record": "•",
    "branch": "|-",
    "checkmark": "[OK]",
    "warning": "!!",
}

# ========== 组件样式 ==========

PANEL_DEFAULTS = {
    "box": box.ROUNDED,
    "padding": (0, 1),
}

PANEL_STYLES = {
    "info": "blue",
    "success": "green",
    "warning": "yellow",
    "error": "red",
    "primary": "cyan",
}

TABLE_COLUMN_STYLES = {
    "id": "green",
    "status": "cyan",
    "count": "magenta",
    "time": "yellow",
}

# ========== 布局间距 ==========

INDENT = {
    "none": "",
    "small": "  ",      # 2 空格
    "medium": "    ",   # 4 空格
    "large": "      ",  # 6 空格
}

ALIGNMENT = {
    "command": 28,      # 命令语法列对齐宽度
    "label": 12,        # 标签对齐宽度
}

# ========== 辅助样式函数 ==========


def get_title_style() -> str:
    """获取标题样式。"""
    return f"bold {COLORS['primary']}"


def get_caption_style() -> str:
    """获取辅助文本样式。"""
    return f"dim {COLORS['text_dim']}"


def get_success_style() -> str:
    """获取成功消息样式。"""
    return f"bold {COLORS['success']}"


def get_warning_style() -> str:
    """获取警告消息样式。"""
    return f"bold {COLORS['warning']}"


def get_error_style() -> str:
    """获取错误消息样式。"""
    return f"bold {COLORS['error']}"
