# Notion集成设置指南

## 概述

本模块提供了完整的Notion API集成功能，支持数据库查询、页面读取、全局搜索等操作。

## 功能特性

### 🗃️ 数据库操作
- **获取数据库信息**: 查看数据库结构、属性架构
- **查询数据库记录**: 获取数据库中的所有记录
- **条件查询**: 支持过滤条件的数据库查询
- **数据库搜索**: 在数据库内容中搜索关键词

### 📄 页面操作
- **获取页面信息**: 读取页面基本信息和属性
- **获取页面内容**: 获取页面的详细内容（包括所有文本块）
- **嵌套内容支持**: 自动处理嵌套的块结构
- **页面内搜索**: 在特定页面内容中搜索

### 🔍 搜索功能
- **全局搜索**: 在整个Notion工作区中搜索
- **专项搜索**: 专门搜索数据库或页面
- **智能结果处理**: 自动分类和格式化搜索结果

## 设置步骤

### 1. 创建Notion Integration

1. 访问 [Notion Integrations](https://www.notion.so/my-integrations)
2. 点击 "New integration"
3. 填写Integration基本信息：
   - **Name**: 例如 "AI Agent Integration"
   - **Logo**: 可选
   - **Associated workspace**: 选择你的工作区
4. 点击 "Submit" 创建

### 2. 获取Integration Token

1. 在创建成功的Integration页面中
2. 复制 "Internal Integration Token"
3. 这个token格式类似：`secret_xxx...`

### 3. 配置环境变量

将token设置为环境变量：

#### Windows (PowerShell)
```powershell
$env:NOTION_TOKEN="secret_your_token_here"
```

#### Windows (Command Prompt)
```cmd
set NOTION_TOKEN=secret_your_token_here
```

#### macOS/Linux
```bash
export NOTION_TOKEN="secret_your_token_here"
```

#### 使用.env文件
在项目根目录创建`.env`文件：
```
NOTION_TOKEN=secret_your_token_here
```

### 4. 授权访问页面和数据库

Integration创建后需要明确授权才能访问内容：

#### 授权单个页面
1. 打开要访问的Notion页面
2. 点击右上角的 "Share" 按钮
3. 在"Invite"部分搜索你的Integration名称
4. 选择Integration并设置权限（Read/Edit）
5. 点击 "Invite"

#### 授权数据库
1. 打开数据库页面
2. 按照上述步骤授权Integration访问

#### 授权整个工作区（推荐）
1. 在Notion中转到 "Settings & members"
2. 选择 "Connections"
3. 找到你的Integration
4. 授权访问相应的页面和数据库

## 使用方法

### 基本用法

```python
from src.tools.notion import get_notion_tools

# 获取所有Notion工具
tools = get_notion_tools()

# 在LangChain Agent中使用
agent = create_react_agent(llm, tools, prompt)
```

### 直接使用工具类

```python
from src.tools.notion import NotionDatabaseTools, NotionPageTools

# 数据库操作
db_tools = NotionDatabaseTools()
database_info = await db_tools.get_database_info("database_id")

# 页面操作
page_tools = NotionPageTools()
page_content = await page_tools.get_page_content("page_id")
```

### 获取页面/数据库ID

#### 从URL获取ID
Notion页面URL格式：
```
https://www.notion.so/Page-Title-32位ID?其他参数
```

例如：
```
https://www.notion.so/My-Database-a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6
```
数据库ID就是：`a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6`

#### 使用分享链接
1. 点击页面的"Share"按钮
2. 选择"Copy link"
3. 从链接中提取32位ID

## 可用工具列表

### 数据库工具
- `notion_get_database_info`: 获取数据库信息和架构
- `notion_query_database`: 查询数据库记录
- `notion_get_database_summary`: 获取数据库摘要

### 页面工具
- `notion_get_page_info`: 获取页面基本信息
- `notion_get_page_content`: 获取页面详细内容
- `notion_get_page_summary`: 获取页面摘要
- `notion_search_page_content`: 搜索页面内容

### 搜索工具
- `notion_search`: 全局搜索
- `notion_search_databases`: 搜索数据库
- `notion_search_pages`: 搜索页面

## 示例用法

### Agent指令示例

```
用户: "请查看我的项目数据库信息"
Agent: 我来为您获取项目数据库的信息。

用户: "在我的笔记页面中搜索'机器学习'"
Agent: 我来在您的笔记页面中搜索相关内容。

用户: "获取今日任务数据库的所有记录"
Agent: 我来查询您的任务数据库。
```

## 故障排除

### 常见错误

#### 1. "Notion token未提供"
- 确保设置了`NOTION_TOKEN`环境变量
- 检查token格式是否正确（以`secret_`开头）

#### 2. "API请求失败: 401"
- Token可能无效或过期
- 重新生成Integration token

#### 3. "API请求失败: 403"
- Integration没有访问页面/数据库的权限
- 按照上述步骤重新授权

#### 4. "页面/数据库未找到"
- 检查ID是否正确
- 确保Integration有访问权限

### 调试技巧

1. **启用调试日志**:
```python
import logging
logging.getLogger('src.tools.notion').setLevel(logging.DEBUG)
```

2. **检查配置状态**:
```python
from src.tools.notion import check_configuration
print(check_configuration())
```

3. **测试连接**:
```python
from src.tools.notion import NotionClient

client = NotionClient()
# 尝试搜索测试连接
result = await client.search("test", page_size=1)
```

## 安全注意事项

1. **保护Token**: 不要在代码中硬编码token
2. **最小权限原则**: 只授权必要的页面和数据库访问权限
3. **定期轮换**: 定期更新Integration token
4. **环境隔离**: 生产环境和开发环境使用不同的Integration

## 技术规范

- **API版本**: 2022-06-28
- **Python版本**: 3.7+
- **异步支持**: 完全支持asyncio
- **错误处理**: 完整的异常处理机制
- **日志记录**: 详细的操作日志

## 更新日志

### v1.0.0
- 初始版本发布
- 支持数据库、页面、搜索功能
- LangChain集成
- 完整的错误处理和日志记录

## 联系支持

如果遇到问题，请：
1. 检查本文档的故障排除部分
2. 查看项目的issue tracking
3. 确保使用最新版本的代码

