# 颜色系统规范

## 目录
- 1. 现状分析
- 2. 优化目标
- 3. 设计方案
- 4. 使用规范
- 5. 实施清单

---

## 1. 现状分析

### 1.1 官方 DeepAgents 的做法

参考文件：`deepagents/libs/deepagents-cli/deepagents_cli/config.py:16-24`

官方定义了统一的颜色字典：

```python
COLORS = {
    "primary": "#10b981",      # 翠绿色 - Emerald 500
    "dim": "#6b7280",          # 灰色 - Gray 500
    "user": "#ffffff",         # 白色
    "agent": "#10b981",        # 翠绿色
    "thinking": "#34d399",     # 浅绿色 - Emerald 400
    "tool": "#fbbf24",         # 琥珀色 - Amber 400
}
```

**特点**：
- 颜色定义集中在一个字典
- 使用场景明确（primary/agent/tool）
- 只有 6 个核心颜色，简洁
- 采用 Hex 色值，支持深色终端

### 1.2 当前项目的现状

当前颜色定义分散在多处：

**Logo 颜色**（`src/application/cli/gui/logo.py:13-14`）：
```python
PRIMARY_COLOUR = "#C2FF62"     # Jasmine Green
SECONDARY_COLOUR = "#50B4FF"   # Sci-Fi Blue
```

**其他位置**：
- `render.py` 中硬编码：`border_style="cyan"`, `style="green"`
- `main.py` 中使用：`[yellow]`, `[red]`, `[bold red]`
- 没有统一的颜色配置文件

**问题**：
1. 颜色分散，难以统一修改
2. 缺少功能色定义（成功/警告/错误）
3. 硬编码导致风格不一致
4. Jasmine Green (#C2FF62) 过亮，长时间使用易疲劳

### 1.3 差距分析

| 对比项 | 官方 | 当前项目 | 差距 |
|-------|-----|---------|-----|
| 颜色定义位置 | 集中在 config.py | 分散在多个文件 | 需要集中管理 |
| 颜色数量 | 6 个核心色 | 未明确定义 | 需要建立色板 |
| 场景映射 | 清晰（primary/tool/dim） | 缺失 | 需要明确用途 |
| 品牌识别 | 单一绿色系 | Jasmine + Blue 双色 | 需要保留品牌 |

---

## 2. 优化目标

1. **建立集中的颜色管理系统**
   - 创建 `theme.py` 统一定义所有颜色
   - 所有文件通过 `from theme import COLORS` 引用

2. **保持品牌识别度**
   - Logo 保留 Jasmine Green 和 Sci-Fi Blue
   - 系统界面可使用更柔和的配色

3. **完善功能色体系**
   - 明确定义成功/警告/错误/信息色
   - 覆盖所有使用场景

4. **提升专业感**
   - 调整过亮的颜色
   - 增强深色终端的可读性

5. **便于主题切换**
   - 未来可轻松支持浅色/深色主题

---

## 3. 设计方案

### 3.1 颜色分类

将颜色分为三类：

1. **品牌色**（Brand Colors）- 用于 Logo 和品牌识别
2. **主题色**（Theme Colors）- 用于系统界面
3. **功能色**（Semantic Colors）- 用于状态和反馈

### 3.2 颜色定义

创建 `src/application/cli/theme.py`：

```python
# 品牌色 - 仅用于 Logo 和启动页
BRAND_COLORS = {
    "jasmine": "#C2FF62",      # Jasmine Green - 品牌主色
    "scifi_blue": "#50B4FF",   # Sci-Fi Blue - 品牌次色
}

# 主题色 - 用于系统界面
COLORS = {
    # 主色调
    "primary": "#A8E650",      # 柔和的茉莉绿（调暗版）
    "secondary": "#50B4FF",    # 科幻蓝

    # 功能色
    "success": "#34d399",      # 成功 - Emerald 400
    "warning": "#fbbf24",      # 警告 - Amber 400
    "error": "#ef4444",        # 错误 - Red 500
    "info": "#3b82f6",         # 信息 - Blue 500

    # 文本色
    "text_primary": "#ffffff", # 主文本 - 白色
    "text_dim": "#6b7280",     # 次要文本 - Gray 500

    # 角色色
    "user": "#ffffff",         # 用户输入
    "agent": "#A8E650",        # Agent 输出（柔和茉莉绿）
    "tool": "#fbbf24",         # 工具调用（琥珀色）
}
```

### 3.3 颜色选择理由

| 颜色 | 色值 | 理由 |
|-----|------|------|
| `#A8E650` | 柔和茉莉绿 | 比 #C2FF62 暗 20%，保留品牌感，减少眼疲劳 |
| `#50B4FF` | 科幻蓝 | 保留原品牌色，对比度好 |
| `#34d399` | Emerald 400 | 借鉴官方，表示成功状态 |
| `#fbbf24` | Amber 400 | 借鉴官方，工具/操作色 |
| `#ef4444` | Red 500 | 标准错误色 |
| `#6b7280` | Gray 500 | 借鉴官方，次要信息色 |

### 3.4 颜色映射表

从旧配色迁移到新配色：

| 旧用法 | 新用法 | 说明 |
|-------|--------|------|
| `PRIMARY_COLOUR` | `BRAND_COLORS["jasmine"]` | Logo 专用 |
| `SECONDARY_COLOUR` | `BRAND_COLORS["scifi_blue"]` | Logo 专用 |
| `style="cyan"` | `style=COLORS["info"]` | 信息提示 |
| `style="green"` | `style=COLORS["success"]` | 成功状态 |
| `[yellow]` | `style=COLORS["warning"]` | 警告信息 |
| `[red]` | `style=COLORS["error"]` | 错误信息 |
| `[dim]` | `style=COLORS["text_dim"]` | 次要文本 |

---

## 4. 使用规范

### 4.1 使用场景

| 场景 | 使用颜色 | 示例 |
|-----|---------|------|
| 标题/重要信息 | `primary` | 命令帮助的标题 |
| Agent 回复 | `agent` | AI 输出的文本 |
| 用户输入 | `user` | 提示符 |
| 工具调用 | `tool` | 工具名称和参数 |
| 成功消息 | `success` | "操作成功" |
| 警告提示 | `warning` | "注意：xxx" |
| 错误信息 | `error` | "错误：xxx" |
| 次要信息 | `text_dim` | 提示文本、路径 |
| Panel 边框 | `info` 或 `primary` | Panel 的 border_style |

### 4.2 禁止的用法

1. **不要硬编码颜色名称**
   ```python
   # 错误
   console.print("text", style="cyan")

   # 正确
   console.print("text", style=COLORS["info"])
   ```

2. **不要在 Logo 外使用品牌色**
   ```python
   # 错误 - 系统界面使用品牌色
   console.print("text", style=BRAND_COLORS["jasmine"])

   # 正确 - 使用主题色
   console.print("text", style=COLORS["primary"])
   ```

3. **不要混用 Rich 内置色和自定义色**
   ```python
   # 不推荐
   console.print("error", style="red")

   # 推荐
   console.print("error", style=COLORS["error"])
   ```

### 4.3 组合使用

支持样式修饰符与颜色组合：

```python
# bold + 颜色
console.print("标题", style=f"bold {COLORS['primary']}")

# dim + 颜色
console.print("提示", style=f"dim {COLORS['text_dim']}")

# 背景色（diff 场景）
deletion_style = f"white on {COLORS['error']}"
addition_style = f"white on {COLORS['success']}"
```

---

## 5. 实施清单

### 5.1 创建主题文件

- [ ] 创建 `src/application/cli/theme.py`
- [ ] 定义 `BRAND_COLORS` 字典
- [ ] 定义 `COLORS` 字典
- [ ] 添加颜色说明注释

### 5.2 更新 Logo 模块

- [ ] 修改 `src/application/cli/gui/logo.py`
- [ ] 从 `theme.py` 导入 `BRAND_COLORS`
- [ ] 更新 `PRIMARY_COLOUR` 引用
- [ ] 更新 `SECONDARY_COLOUR` 引用

### 5.3 更新渲染模块

- [ ] 修改 `src/application/cli/gui/render.py`
- [ ] 从 `theme.py` 导入 `COLORS`
- [ ] 替换所有硬编码的颜色名称
- [ ] 更新 Panel `border_style` 参数
- [ ] 更新 Table 列的 `style` 参数

### 5.4 更新主循环

- [ ] 修改 `src/application/cli/main.py`
- [ ] 从 `theme.py` 导入 `COLORS`
- [ ] 替换所有内联颜色标记（如 `[yellow]`）

### 5.5 更新其他 CLI 文件

- [ ] 检查 `src/application/cli/gui/interact.py`
- [ ] 检查 `src/application/cli/state.py`
- [ ] 确保所有 console.print 使用统一颜色

### 5.6 验证

- [ ] 启动 CLI，检查 Logo 颜色是否正确
- [ ] 运行各种命令，检查颜色一致性
- [ ] 在深色终端测试可读性
- [ ] 确认无硬编码颜色残留

---

## 附录：颜色预览

### 主题色效果预览

在支持真彩色的终端中：

- **Primary** (#A8E650): 柔和的茉莉绿，适合长时间阅读
- **Secondary** (#50B4FF): 明亮的蓝色，适合强调
- **Success** (#34d399): 清新的绿色，表示成功
- **Warning** (#fbbf24): 醒目的琥珀色，表示警告
- **Error** (#ef4444): 鲜明的红色，表示错误
- **Info** (#3b82f6): 专业的蓝色，表示信息

### 与官方颜色的对比

| 用途 | 官方 DeepAgents | 我们的项目 | 说明 |
|-----|----------------|-----------|------|
| 主色调 | #10b981 翠绿 | #A8E650 柔和茉莉绿 | 保留品牌特色 |
| 工具色 | #fbbf24 琥珀 | #fbbf24 琥珀 | 借鉴官方 |
| 暗文本 | #6b7280 灰色 | #6b7280 灰色 | 借鉴官方 |
| 成功色 | #34d399 浅绿 | #34d399 浅绿 | 借鉴官方 |

---

## 下一步

阅读 `03-typography.md` 了解字体样式规范。
