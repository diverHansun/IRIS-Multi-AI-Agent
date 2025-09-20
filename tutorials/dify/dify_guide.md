# Dify 集成开发指南

## 概述

本指南详细说明了如何将远程 Dify 平台的 Agent 框架集成到 Multi-AI-Agent 项目中，实现与 Dify 平台的网络连接和流式交互。Dify 是一个开源的 LLM 应用开发平台，提供了 Backend-as-a-Service 和 LLMOps 功能，可以快速构建和运行生成式 AI 应用。

## 最新确认事项

- 对接目标：支持文件与图片上传的对话 Agent，上传后需在同一会话流中引用资源。
- Dify API 服务端点：`https://api.dify.ai/v1`，默认写入配置并允许按环境覆盖。
- 鉴权方式：请求头 `Authorization: Bearer {API_KEY}`，其中密钥来源 .env 配置。
- 官方开发控制台：`https://cloud.dify.ai/app/ce8d36d5-0234-4ee2-87a9-fa4baa3a5769/develop`（需登录访问，用于核对最新接口参数）。
- API 密钥管理：密钥存储于 `.env`，并在 `.env.example` 中保留 `DIFY_API_KEY`、`DIFY_BASE_URL` 占位。API密钥已包含应用信息。
- 当前开发阶段：仅建立 `config/dify/` 目录，其余任务待实现。
- 运行环境：直接连接生产环境，不区分测试/生产配置。


## 功能需求

### 1. 核心功能
- **switch dify 命令**: 切换到 Dify Agent 模式
- **upload 命令**: 上传文件或图片到 Dify，单一入口 `upload` 默认弹出文件选择器，可一次性选择受支持的扩展名（TXT/MD/MARKDOWN/PDF/HTML/XLSX/XLS/DOCX/CSV/EML/MSG/PPTX/PPT/XML/EPUB/JPG/JPEG/PNG/GIF/WEBP/SVG）；超出列表时提示错误并中止上传。
- **流式输出**: 与 Dify 服务器进行实时流式交互
- **无模式切换**: Dify 模式下无需 llm/agent 模式切换

### 2. 技术特性
- 网络 API 请求连接
- 文件上传进度显示
- 流式响应处理
- 会话管理集成：复用 CLI `session_id` 作为 Dify `user` 标识，并在进程内维护最近一次 `conversation_id`。

## 开发框架

### 1. 项目结构扩展

```
config/
└── dify/
    ├── config.json       # Dify 配置
    └── README.md         # 配置说明

src/
└── components/
    └── dify/
        ├── __init__.py
        ├── client.py         # Dify API 客户端
        ├── control.py        # Dify 控制逻辑
        ├── upload.py         # 文件上传处理
        └── streaming.py      # 流式输出处理
```

### 2. 核心组件设计

#### 2.1 Dify 客户端 (client.py)
```python
class DifyClient:
    """Dify API 客户端"""
    
    def __init__(self, api_key: str, base_url: str, app_id: str):
        self.api_key = api_key
        self.base_url = base_url
        self.app_id = app_id
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
    async def chat_message(self, query: str, user_id: str, streaming: bool = True):
        """发送聊天消息"""
        pass
        
    async def upload_file(self, file_path: str, user_id: str, progress_callback=None):
        """上传文件"""
        pass
```

#### 2.2 Dify 控制模块 (control.py)
```python
class DifyControl:
    """Dify 控制逻辑"""
    
    def __init__(self, console, config_path="config/dify/config.json"):
        self.console = console
        self.config = self._load_config(config_path)
        self.client = None
        
    def _load_config(self, config_path):
        """加载配置"""
        pass
        
    async def initialize(self):
        """初始化 Dify 客户端"""
        pass
        
    async def handle_query(self, query: str, user_id: str):
        """处理查询"""
        pass
```

#### 2.3 文件上传模块 (upload.py)
```python
class DifyUploader:
    """Dify 文件上传处理"""
    
    def __init__(self, client):
        self.client = client
        
    async def upload_file(self, file_path: str, user_id: str, progress_callback=None):
        """上传文件"""
        pass
        
    async def upload_with_progress(self, file_path: str, user_id: str):
        """带进度显示的文件上传"""
        pass
```

#### 2.4 流式输出模块 (streaming.py)
```python
class DifyStreaming:
    """Dify 流式输出处理"""
    
    def __init__(self, client):
        self.client = client
        
    async def stream_response(self, response):
        """处理流式响应"""
        pass
        
    async def display_stream(self, response, console):
        """显示流式输出"""
        pass
```

### 3. 配置管理

#### 3.1 Dify 配置 (config/dify/config.json)
```json
{
  "api_key": "your_dify_api_key",
  "base_url": "https://api.dify.ai/v1",
  "timeout": 30,
  "supported_file_types": [
    ".txt", ".md", ".markdown", ".pdf", ".html", ".xlsx", ".xls", ".docx", ".csv", ".eml", ".msg", ".pptx", ".ppt", ".xml", ".epub",
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg"
  ],
  "max_file_size": 10485760
}
```

## 实现细节

### 1. CLI 集成

在 `src/components/cli.py` 中添加 Dify 相关命令处理：

```python
# 在 AppState 类中添加
self.dify_mode = False  # Dify 模式标志
self.dify_client = None  # Dify 客户端实例

# 在主循环中添加命令处理
if query.strip().lower().startswith("switch dify"):
    # 切换到 Dify 模式
    from src.components.dify.control import init_dify_client
    result = await init_dify_client(ctx)
    if result["type"] == "success":
        ctx.dify_mode = True
        ctx.console.print("[green]已切换到 Dify 模式[/]")
    else:
        ctx.console.print(f"[red]切换失败: {result['message']}[/]")
    continue

if query.strip().lower().startswith("upload") and ctx.dify_mode:
    # 处理文件上传
    from src.components.dify.upload import handle_upload
    result = await handle_upload(ctx, query)
    continue

# 在查询处理部分添加 Dify 模式处理
if ctx.dify_mode:
    # Dify 模式处理
    from src.components.dify.control import handle_query
    result = await handle_query(ctx, query)
    continue
```

- `upload` 命令保持单一入口：无参数时在 Windows 中唤起系统文件资源管理器（Tk 对话框封装）供手动选择；若命令后携带路径则直接尝试上传该文件（仍会按扩展名执行校验）。
- Dify 相关命令建议封装在 Dify 控制层内部，不与主 CLI/GUI 的公共命令混用；通过模式开关或命名空间前缀保持隔离，避免对原有工作流造成影响。
- 切换到 Dify 模式后需初始化 `DifyControl`，并在会话状态中缓存最近一次 `conversation_id`（仅进程内维持即可）以支撑上下文续接。

### 2. 文件上传实现

在 `src/components/dify/upload.py` 中实现文件上传功能：

```python
async def upload_file(self, file_path: str, user_id: str, progress_callback=None):
    """上传文件到 Dify"""
    url = f"{self.base_url}/files/upload"
    
    # 检查文件是否存在
    if not os.path.exists(file_path):
        return {"error": "文件不存在"}
    
    # 获取文件大小
    file_size = os.path.getsize(file_path)
    
    # 创建上传表单
    form = aiohttp.FormData()
    form.add_field('file', 
                   open(file_path, 'rb'),
                   filename=os.path.basename(file_path))
    form.add_field('user', user_id)
    
    # 自定义上传进度处理
    async def upload_with_progress():
        uploaded = 0
        headers = {"Authorization": f"Bearer {self.api_key}"}
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=form, headers=headers) as response:
                if response.status == 200:
                    result = await response.json()
                    return result
                else:
                    error_text = await response.text()
                    return {"error": f"上传失败: {response.status}, {error_text}"}
    
    # 显示上传进度
    with Progress(
        "[progress.description]{task.description}",
        BarColumn(),
        "[progress.percentage]{task.percentage:>3.0f}%",
        TimeRemainingColumn(),
    ) as progress:
        task = progress.add_task(f"上传 {os.path.basename(file_path)}", total=100)
        
        # 启动上传任务
        result = await upload_with_progress()
        progress.update(task, completed=100)
        
        return result
```

上传实现需根据文件类型设置 `FormData` 的 `content_type`，并在调用前校验是否超出 `config/dify/config.json` 中的 `supported_file_types` 与 `max_file_size`。当前实现保持单一 `upload` 命令；如未来需要区分图片命令，可在请求中额外附带 `type=image` 或自定义 `metadata` 以便 Dify 在对话中区分资源用途。

### 3. 流式输出实现

在 `src/components/dify/streaming.py` 中实现流式输出处理：

```python
async def chat_message(self, query: str, user_id: str, streaming: bool = True):
    """发送聊天消息"""
    url = f"{self.base_url}/chat-messages"
    
    payload = {
        "inputs": {},
        "query": query,
        "response_mode": "streaming" if streaming else "blocking",
        "user": user_id
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload, headers=self.headers) as response:
            if streaming:
                return response  # 返回响应对象以便流式处理
            else:
                if response.status == 200:
                    return await response.json()
                else:
                    error_text = await response.text()
                    return {"error": f"请求失败: {response.status}, {error_text}"}

async def stream_response(self, response, console):
    """处理流式响应"""
    async for line in response.content:
        if line.startswith(b'data: '):
            try:
                data = json.loads(line[6:])
                if 'answer' in data:
                    console.print(data['answer'], end="")
                elif 'event' in data and data['event'] == 'message':
                    console.print(data.get('content', ''), end="")
            except json.JSONDecodeError:
                pass
    console.print()  # 打印换行
```

聊天请求参数说明：
- `inputs`：键值对，填充应用配置的变量（按需留空）。
- `query`：用户本轮提问。
- `response_mode`：`blocking` 或 `streaming`，流式模式需结合 `stream_response` 逐行解析。
- `user`：复用 CLI `session_id` 作为 Dify 用户标识。
- `conversation_id`：可选字段，用于续接先前的会话上下文；控制层在成功响应后于进程内缓存该值即可。

请求示例（blocking）：
```json
{
  "inputs": {},
  "query": "你好，请介绍一下当前开发计划",
  "response_mode": "blocking",
  "user": "<session_id>",
  "conversation_id": "<optional_conversation_id>"
}
```

阻塞模式响应示例：
```json
{
  "event": "message",
  "answer": "...",
  "conversation_id": "conv-xxxx",
  "message_id": "msg-xxxx"
}
```

根据官方《Developing with APIs》文档，首次调用请留空 `conversation_id`，由服务端返回值在后续请求中复用；API 创建的对话与 Web 端互不共享。

流式响应常见事件：
- `event: message`：输出中间文本片段，可能同时返回 `answer` 与 `content`。
- `event: message_end`：表示该轮回复结束，附带最终 `answer` 与 `conversation_id`。
- `event: error`：发生错误时返回，需要在 CLI 中解析 `error` 字段并提示用户重试。

### 4. 上传命令实现

在 `src/components/dify/upload.py` 中实现文件上传命令：

```python
async def handle_upload(ctx, query):
    """处理上传命令"""
    parts = query.strip().split()
    
    if len(parts) < 2:
        # 显示文件选择对话框
        import tkinter as tk
        from tkinter import filedialog
        
        root = tk.Tk()
        root.withdraw()
        file_path = filedialog.askopenfilename(
            title="选择要上传的文件",
            filetypes=[
                ("所有支持的文件", "*.txt *.md *.markdown *.pdf *.html *.xlsx *.xls *.docx *.csv *.eml *.msg *.pptx *.ppt *.xml *.epub *.jpg *.jpeg *.png *.gif *.webp *.svg"),
                ("文档", "*.txt *.md *.markdown *.pdf *.html *.xlsx *.xls *.docx *.csv *.xml *.epub"),
                ("图片", "*.jpg *.jpeg *.png *.gif *.webp *.svg"),
                ("所有文件", "*.*")
            ]
        )
        root.destroy()
        
        if not file_path:
            ctx.console.print("[yellow]已取消上传[/]")
            return {"type": "cancel"}
    else:
        # 使用命令行指定的文件路径
        file_path = " ".join(parts[1:])
    
    # 检查文件是否存在
    if not os.path.exists(file_path):
        ctx.console.print(f"[red]文件不存在: {file_path}[/]")
        return {"type": "error", "message": "文件不存在"}
    
    # 上传文件
    ctx.console.print(f"[dim]开始上传: {os.path.basename(file_path)}[/]")
    
    result = await ctx.dify_client.upload_file(file_path, ctx.session_id)
    
    if "error" in result:
        ctx.console.print(f"[red]上传失败: {result['error']}[/]")
        return {"type": "error", "message": result["error"]}
    else:
        ctx.console.print(f"[green]上传成功: {os.path.basename(file_path)}[/]")
        ctx.console.print(f"[dim]文件ID: {result['id']}[/]")
        return {"type": "success", "payload": result}
```

默认在 Windows 环境下通过 Tkinter 调起系统文件资源管理器对话框，确保用户可视化选择文件；如需跨平台兼容需后续补充对应的 GUI 方案。

上传命令采用统一入口：无参数时弹出选择器；如命令后附带路径则直接读取指定文件。所有文件将按扩展名校验，若不在支持列表（TXT/MD/MARKDOWN/PDF/HTML/XLSX/XLS/DOCX/CSV/EML/MSG/PPTX/PPT/XML/EPUB/JPG/JPEG/PNG/GIF/WEBP/SVG）则提示错误并终止流程。

Dify 上传接口关键表单字段：
- `file`：二进制文件内容。
- `user`：复用 CLI `session_id`，用于标识资源归属。
- `type`（可选）：当资源为图片时建议传 `image`，其他文件可留空或设置为 `file`。
- `metadata`（可选）：补充文件用途、原始路径等上下文，便于在对话结果中引用。

根据官方文档，上传接口当前支持的图片格式为 JPG/JPEG/PNG/GIF/WEBP/SVG，文本与文档类文件请遵循配置清单。上传资源仅对当前用户可见，需在后续对话中明确引用文件 ID。

上传成功响应示例：
```json
{
  "id": "file-xxxx",
  "name": "demo.pdf",
  "size": 12345,
  "type": "file"
}
```

控制层需在收到响应后记录文件 `id`，以便在后续聊天请求的 `inputs` 或消息内容中引用。

## 开发计划

### 阶段 1: 基础架构 (1-2 天)

#### 1.1 配置结构
- [x] 创建 `config/dify` 目录
- [ ] 创建 `config.json` 配置文件
- [ ] 编写配置说明文档

#### 1.2 客户端实现
- [ ] 创建 `src/components/dify/client.py`
- [ ] 实现基础 API 请求功能
- [ ] 实现认证和错误处理

#### 1.3 控制逻辑
- [ ] 创建 `src/components/dify/control.py`
- [ ] 实现配置加载功能
- [ ] 实现客户端初始化逻辑

#### 1.4 模块化结构
- [ ] 创建 `src/components/dify/__init__.py`
- [ ] 创建 `src/components/dify/upload.py`
- [ ] 创建 `src/components/dify/streaming.py`

### 阶段 2: CLI 集成 (1-2 天)

#### 2.1 命令处理
- [ ] 在 `cli.py` 中添加 Dify 模式标志
- [ ] 实现 `switch dify` 命令处理
- [ ] 集成 Dify 查询处理

#### 2.2 模式切换
- [ ] 实现 Dify 模式与普通模式的切换
- [ ] 添加模式状态显示
- [ ] 实现模式特定的帮助信息

### 阶段 3: 文件上传 (2-3 天)

#### 3.1 上传功能
- [ ] 实现文件选择对话框
- [ ] 实现文件上传 API 调用
- [ ] 添加文件类型验证

#### 3.2 进度显示
- [ ] 实现上传进度跟踪
- [ ] 集成 Rich 进度条显示
- [ ] 添加上传结果反馈

### 阶段 4: 流式输出 (1-2 天)

#### 4.1 流式处理
- [ ] 实现 SSE 流式响应处理
- [ ] 添加实时显示功能
- [ ] 处理流式响应错误

#### 4.2 会话管理
- [ ] 集成会话 ID 管理
- [ ] 保持会话上下文
- [ ] 实现会话持久化

## API 集成细节

> 参考文档：Dify 官方指南《Developing with APIs》([链接](https://docs.dify.ai/en/guides/application-publishing/developing-with-apis))，涵盖应用接入流程、聊天消息接口与文件上传说明。以下小节结合该文档与项目需求进行实现指引。

### 1. 认证方式

```python
headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json"
}
```

所有请求默认指向生产环境基础 URL `https://api.dify.ai/v1`，并在 `Authorization` 头中携带 `.env` 配置的密钥。

### 2. 聊天消息 API

```python
async def send_chat_message(query, user_id, streaming=True):
    url = f"{base_url}/chat-messages"
    payload = {
        "inputs": {},
        "query": query,
        "response_mode": "streaming" if streaming else "blocking",
        "user": user_id
    }
    
    # API 调用实现...
```

### 3. 文件上传 API

```python
async def upload_file(file_path, user_id):
    url = f"{base_url}/files/upload"
    
    form = aiohttp.FormData()
    form.add_field('file', 
                  open(file_path, 'rb'),
                  filename=os.path.basename(file_path))
    form.add_field('user', user_id)
    
    # 上传实现...
```

## 配置要求

### 1. 环境变量
在仓库中提供 `.env.example`，保留以下占位项，开发者复制为 `.env` 后填入真实值：（目前仅配置生产环境，所有调用默认指向线上服务）
```bash
# .env 文件
DIFY_API_KEY=app-dify-example-key  # API密钥包含应用信息
DIFY_BASE_URL=https://api.dify.ai/v1  # 默认端点，可按环境覆盖
```

### 2. 依赖包
```txt
# requirements.txt 新增
aiohttp>=3.8.0
rich>=13.0.0
```

## 注意事项

### 1. 网络依赖
- Dify 模式完全依赖网络连接
- 需要稳定的网络环境
- 建议添加网络状态检测和重试机制

### 2. API 限制
- 注意 Dify API 调用频率限制
- 实现适当的重试和退避策略
- 监控 API 使用量

### 3. 文件上传
- 支持的文件类型: TXT、MARKDOWN、PDF、HTML、XLSX、XLS、DOCX、CSV、EML、MSG、PPTX、PPT、XML、EPUB、JPG、JPEG、PNG、GIF、WEBP、SVG
- 文件大小限制: 默认 10MB
- 上传文件仅对当前用户可用

### 4. 用户体验
- 提供清晰的模式切换指示
- 实现直观的进度显示
- 添加适当的错误提示

## 待确认事项

- Dify API 密钥格式确认：通常以 `app-` 开头，包含应用信息，无需单独配置应用 ID。

## 总结

本开发指南提供了将远程 Dify 平台集成到 Multi-AI-Agent 项目的完整方案，包括配置结构、API 集成、文件上传和流式输出功能。通过分阶段开发，可以逐步实现所有功能需求，最终为用户提供完整的 Dify 集成体验。

关键成功因素:
1. 稳定的网络连接处理
2. 流畅的用户体验
3. 完善的错误处理
4. 清晰的进度反馈
5. 灵活的配置管理