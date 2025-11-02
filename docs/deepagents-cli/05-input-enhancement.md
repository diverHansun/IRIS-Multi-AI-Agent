# 用户输入增强实施文档

## deepagents-cli官方代码的优点

### 1. @文件引用语法

官方实现了简洁的文件引用语法：

- **语法设计**：使用 `@文件名` 或 `@路径` 引用文件
- **自动注入**：引用的文件内容自动注入到提示词上下文中
- **路径解析**：支持相对路径和绝对路径，自动解析到工作目录
- **大小限制**：对单个文件限制50KB，超过部分截断并提示

### 2. 文件内容格式化

引用文件的内容格式化清晰：

- **结构化展示**：每个文件使用Markdown格式展示
- **路径信息**：显示文件名和完整路径
- **代码块包装**：文件内容使用代码块包裹，保持格式
- **错误处理**：文件不存在或读取失败时给出明确提示

### 3. 多文件支持

支持在一条输入中引用多个文件：

- **批量解析**：使用正则表达式提取所有 `@文件` 引用
- **顺序处理**：按引用顺序处理文件，保持上下文连贯
- **独立错误处理**：单个文件失败不影响其他文件

### 4. 输入解析集成

文件引用解析无缝集成到执行流程：

- **预处理阶段**：在传递给agent前完成解析和注入
- **提示词组装**：将文件内容作为上下文添加到用户输入中
- **透明处理**：用户无感知，agent直接收到完整上下文

## 我们现有代码的优点和不足

### 优点

1. **查询处理框架**：`handle_deep_agent_query` 已有清晰的查询处理流程
2. **上下文注入机制**：可以通过多种方式向agent提供上下文
3. **文件系统访问**：可以通过真实文件系统或虚拟文件系统访问文件

### 不足

1. **缺少文件引用语法**：没有实现 `@文件` 这样的快捷引用语法
2. **手动文件读取**：用户需要手动使用工具读取文件，不够便捷
3. **上下文组装缺失**：没有自动将文件内容注入到提示词中的机制

## 实施方案

### 实施步骤

#### 第一步：实现文件引用解析

**文件路径**：`src/application/services/agent/deep/input/parser.py`（新建）

**核心函数**：`parse_file_mentions(text: str) -> tuple[str, list[Path]]`

**功能**：
- 使用正则表达式匹配 `@文件路径` 模式
- 支持转义空格：`@file\ name.txt` → `file name.txt`
- 解析路径：支持相对路径和绝对路径
- 验证文件存在性和可读性
- 返回清理后的文本和文件路径列表

**正则表达式**：
```python
pattern = r"@((?:[^\s@]|(?<=\\)\s)+)"
```

#### 第二步：实现文件内容读取和格式化

**文件路径**：`src/application/services/agent/deep/input/parser.py`

**新增函数**：`format_file_context(file_path: Path) -> str`

**功能**：
- 读取文件内容（限制50KB）
- 格式化为Markdown结构
- 处理读取错误（文件不存在、权限问题等）
- 超过大小限制时截断并添加提示

**格式化结构**：
```markdown
### 文件名
Path: `完整路径`
```
文件内容
```
```

#### 第三步：集成到查询处理流程

**文件路径**：`src/application/services/agent/deep/streaming/conversation.py`

**修改 `handle_deep_agent_query` 函数**：
- 在函数开始处调用 `parse_file_mentions(user_input)`
- 如果有文件引用，读取文件内容并格式化
- 将文件内容作为上下文添加到提示词中
- 组装最终的查询文本

**代码结构**：
```python
async def handle_deep_agent_query(ctx, query: str) -> str:
    # 解析文件引用
    prompt_text, mentioned_files = parse_file_mentions(query)
    
    if mentioned_files:
        context_parts = [prompt_text, "\n\n## Referenced Files\n"]
        for file_path in mentioned_files:
            context_parts.append(format_file_context(file_path))
        final_query = "\n".join(context_parts)
    else:
        final_query = prompt_text
    
    # 继续原有的查询处理流程
```

#### 第四步：错误处理和用户提示

**文件路径**：`src/application/services/agent/deep/input/parser.py`

**错误处理**：
- 文件不存在：警告并跳过该文件引用
- 文件过大：截断并添加提示信息
- 读取权限错误：显示明确的错误信息
- 路径解析失败：提示路径格式错误

**提示信息**：
- 使用console输出警告信息
- 不阻塞查询处理，继续处理其他文件和查询

#### 第五步：路径解析增强

**文件路径**：`src/application/services/agent/deep/input/parser.py`

**路径解析逻辑**：
- 支持 `~` 用户目录展开
- 相对路径解析到当前工作目录
- 绝对路径直接使用
- 支持包含空格的路径（使用转义或引号）

### 文件创建清单

1. **新建文件**：`src/application/services/agent/deep/input/parser.py`
2. **新建文件**：`src/application/services/agent/deep/input/__init__.py`

### 文件修改清单

1. **修改文件**：`src/application/services/agent/deep/streaming/conversation.py`

### 配置项（可选）

在配置中添加文件引用的限制：

```json
{
  "input_enhancement": {
    "max_file_size_kb": 50,
    "max_files_per_query": 10,
    "allowed_file_extensions": [".txt", ".md", ".py", ".js", ".json"]
  }
}
```

### 使用示例

**输入**：
```
分析 @src/main.py 和 @config/settings.json 中的配置问题
```

**处理后**：
```
分析以下文件中的配置问题

## Referenced Files

### main.py
Path: `src/main.py`
```python
// 文件内容
```

### settings.json
Path: `config/settings.json`
```json
// 文件内容
```
```

### 注意事项

1. **安全性**：限制文件大小和数量，防止恶意输入
2. **性能**：文件读取操作要快速，大文件考虑异步处理
3. **路径安全**：防止路径遍历攻击（如 `../../etc/passwd`）
4. **编码处理**：正确处理不同编码的文件（UTF-8、GBK等）
5. **文件类型限制**：可选择性限制允许的文件扩展名
6. **错误恢复**：单个文件失败不应影响整个查询处理

