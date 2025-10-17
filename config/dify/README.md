# Dify 配置说明

## 配置文件

`config.json` 包含了 Dify 集成的所有配置项。

## 配置项说明

### 基础配置
- `api_key`: Dify API 密钥，从环境变量 `DIFY_API_KEY` 读取（包含应用信息）
- `base_url`: Dify API 基础URL，默认为 `https://api.dify.ai/v1`，可通过环境变量 `DIFY_BASE_URL` 覆盖

### 超时配置
- `timeout`: 普通 API 请求超时时间（秒），默认 30
- `streaming_timeout`: 流式响应超时时间（秒），默认 300，适应 Agent 模式的长推理时间

### 显示配置
- `buffer_size`: 字符缓冲区大小，默认 200，影响刷新频率
- `delay_ms`: 每个块的显示延迟（毫秒），默认 10，控制输出速度
- `display_refresh_rate`: 每秒最大刷新次数，默认 50
- `max_content_length`: 最大响应长度，默认 1000000
- `rate_limit_per_second`: 每秒最大块数，默认 50，防止刷屏

### 文件上传配置
- `supported_file_types`: 支持的文件类型列表
- `max_file_size`: 最大文件大小（字节），默认 10485760（10MB）

### 重试配置
- `retry_attempts`: 网络失败重试次数，默认 3
- `retry_delay`: 重试延迟时间（秒），默认 1.0

## 环境变量

请在 `.env` 文件中配置以下环境变量：

```bash
DIFY_API_KEY=app-your-dify-api-key-here
DIFY_BASE_URL=https://api.dify.ai/v1
```

## Dify 配置获取方法

### 1. 获取 API 密钥

1. 访问 [Dify 官方网站](https://cloud.dify.ai)
2. 登录您的账户
3. 进入应用控制台
4. 选择您要使用的应用
5. 在应用设置中找到 "API 密钥" 部分
6. 复制 API 密钥到 `DIFY_API_KEY`

### 2. API 密钥说明

Dify 的 API 密钥格式通常以 `app-` 开头，已经包含了应用的相关信息，无需单独配置应用 ID。

### 3. 基础 URL 配置

- **官方云服务**: `https://api.dify.ai/v1` (默认)
- **自托管服务**: 根据您的部署地址修改

## 文件上传

支持的文件类型：
- 文档：TXT, MD, MARKDOWN, PDF, HTML, XLSX, XLS, DOCX, CSV, EML, MSG, PPTX, PPT, XML, EPUB
- 图片：JPG, JPEG, PNG, GIF, WEBP, SVG

最大文件大小：10MB

## 配置验证

配置完成后，可以通过以下方式验证：

1. 启动应用: `python main.py`
2. 执行 `switch dify` 命令
3. 如果配置正确，应该显示 "已切换到 Dify 模式"

## 安全注意事项

- ⚠️ **永远不要将 `.env` 文件提交到 Git 仓库**
- ⚠️ **定期更换 API 密钥**
- ⚠️ **仅在必要时分享配置信息**
- ⚠️ **使用适当的文件权限保护 `.env` 文件**

## 故障排除

### 配置文件不存在

如果提示 "配置文件不存在"，请检查：
- `.env` 文件是否在项目根目录
- 文件名是否正确（没有多余的扩展名）

### API 密钥无效

如果提示 "API 密钥格式无效"，请检查：
- Dify API 密钥应以 `app-` 开头
- 密钥中没有多余的空格或特殊字符

### 网络连接问题

如果提示 "连接测试失败"，请检查：
- 网络连接是否正常
- 防火墙是否阻止了连接
- API 基础 URL 是否正确