# UI 优化计划文档

本目录包含 IRIS Multi-AI-Agent 项目的 CLI 界面优化计划文档。

## 文档列表

1. **[01-overview.md](01-overview.md)** - 概览和原则
   - 背景与目标
   - 对比分析总结
   - 优化原则与范围
   - 文档组织

2. **[02-color-system.md](02-color-system.md)** - 颜色系统规范
   - 现状分析
   - 品牌色与主题色设计
   - 颜色使用规范
   - 实施清单

3. **[03-typography.md](03-typography.md)** - 字体排版规范
   - 样式修饰符使用
   - 文本层级体系
   - 样式组合规则
   - 实施清单

4. **[04-icons-symbols.md](04-icons-symbols.md)** - 图标符号规范
   - 工具图标映射
   - 状态符号定义
   - 使用约束说明
   - 实施清单

5. **[05-components.md](05-components.md)** - Rich 组件规范
   - Panel 标准样式
   - Table 标准样式
   - Text 和 Markdown 使用
   - 实施清单

6. **[06-layout-spacing.md](06-layout-spacing.md)** - 布局间距规范
   - 缩进体系
   - 对齐宽度
   - 垂直间距规则
   - 实施清单

7. **[07-implementation.md](07-implementation.md)** - 实施计划
   - 文件清单
   - 详细实施步骤
   - 验证检查
   - 回滚方案

8. **[08-reference.md](08-reference.md)** - 快速参考
   - 颜色速查表
   - 图标速查表
   - 组件速查表
   - 常用代码片段

## 阅读顺序

### 首次阅读（了解完整计划）

按顺序阅读 01-07，最后查看 08 作为参考：

```
01-overview.md          # 理解背景和目标
    ↓
02-color-system.md      # 了解颜色设计
    ↓
03-typography.md        # 了解字体规范
    ↓
04-icons-symbols.md     # 了解图标系统
    ↓
05-components.md        # 了解组件规范
    ↓
06-layout-spacing.md    # 了解布局规范
    ↓
07-implementation.md    # 了解实施步骤
    ↓
08-reference.md         # 查阅时参考
```

### 实施时阅读

重点关注 07 和 08：

```
07-implementation.md    # 按步骤执行
    ↓
08-reference.md         # 随时查阅
```

### 快速查阅

直接查看：

```
08-reference.md         # 快速查找颜色、图标、代码片段
```

## 核心要点

### 1. 优化目标

本次优化**仅针对视觉表现层**，不修改业务逻辑：

- 建立统一的颜色系统
- 实现完整的图标体系
- 规范 Rich 组件使用
- 统一布局和间距

### 2. 设计决策

- **颜色方案**：保留品牌色（Logo），系统界面使用柔和配色
- **图标系统**：采用 emoji，仅限 `src/application/cli/` 目录
- **Panel 样式**：统一使用 `box.ROUNDED` 和 `padding=(0, 1)`
- **排版规范**：2 空格缩进，28 字符对齐

### 3. 关键约束

- Emoji **仅在** `src/application/cli/` 目录使用
- 颜色定义**集中在** `theme.py`
- 不修改核心业务逻辑
- 保持向后兼容

### 4. 实施范围

**需要修改的文件**：
```
src/application/cli/
├── theme.py          # 新建 - 主题配置
├── gui/
│   ├── logo.py       # 修改 - 更新颜色引用
│   └── render.py     # 修改 - 更新组件样式
└── main.py           # 修改 - 更新颜色引用
```

**不应修改的目录**：
- `src/components/` - 核心组件
- `src/llm/` - LLM 相关
- `src/application/services/` - 服务层

## 快速开始

### 开始实施

1. 完整阅读 [07-implementation.md](07-implementation.md)
2. 创建 `src/application/cli/theme.py`
3. 按步骤更新各文件
4. 执行验证检查

### 查阅规范

需要查找颜色、图标或代码示例时，直接查看 [08-reference.md](08-reference.md)。

### 理解设计

想深入了解某个设计决策时，查看对应的详细文档（02-06）。

## 预期效果

完成优化后：

**视觉层面**：
- 颜色使用统一、专业
- Panel 和 Table 风格现代化
- 图标清晰，识别度高
- 排版整齐，阅读流畅

**代码层面**：
- 样式定义集中管理
- 易于全局调整
- 便于后续扩展

**用户体验**：
- 视觉一致性提升
- 信息层级更清晰
- 品牌识别度保持
- 专业感增强

## 参考资料

- **官方 DeepAgents CLI**: `deepagents/libs/deepagents-cli/deepagents_cli/`
- **Rich 库文档**: https://rich.readthedocs.io/
- **当前项目 CLI**: `src/application/cli/`

## 维护说明

- 所有文档存放在 `docs/ui/` 目录
- 代码实现与文档保持同步
- 样式修改需同步更新相关文档

## 问题反馈

如在实施过程中遇到问题，请检查：

1. 是否按顺序完成了所有步骤
2. 是否正确导入了 `theme.py`
3. 是否遵守了使用约束（如 emoji 仅限 CLI 目录）
4. 验证清单是否全部通过

---

*最后更新：2025-01-25*
