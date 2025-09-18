# MCP配置目录

本目录包含Model Context Protocol (MCP) 相关的配置文件。

## 文件说明

### mcp.toml
主配置文件，定义启用的MCP服务器及其参数。

### mcp.toml.example  
配置示例文件，展示各种MCP服务器的配置方法。

## 使用方法

1. 复制示例文件：
   ```bash
   copy mcp.toml.example mcp.toml
   ```

2. 根据需要编辑 `mcp.toml` 配置

3. 在CLI中使用MCP命令：
   ```bash
   mcp status     # 查看MCP状态
   mcp tools      # 查看可用工具
   mcp reload     # 重新加载配置
   ```

## 注意事项

- `mcp.toml` 文件已加入 `.gitignore`，不会被版本控制
- 请参考 `mcp.toml.example` 了解配置格式
- 更多详情请查看 `tutorials/mcp_guide.md`