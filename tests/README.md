# Multi-AI-Agent 测试指南

## 概述

本测试套件为Multi-AI-Agent项目提供全面的质量保障，包括单元测试和集成测试。测试采用pytest框架，支持异步测试和模拟API调用。

## 测试结构

```
tests/
├── __init__.py              # 测试包初始化
├── conftest.py              # pytest配置和fixtures
├── test_config.py           # 测试配置
├── tests.md                # 本文档
├── unit/                    # 单元测试
│   ├── __init__.py
│   ├── test_config_loading.py      # 配置加载测试
│   └── test_memory_system.py       # 记忆系统测试
└── integration/             # 集成测试
    ├── __init__.py
    ├── test_agent_integration.py   # Agent集成测试
    └── test_ollama_integration.py  # Ollama专项测试
```

## 安装测试依赖

```bash
pip install pytest pytest-asyncio pytest-timeout
```

## 运行测试

### 运行所有测试
```bash
# 在项目根目录执行
pytest tests/ -v
```

### 运行特定类型的测试
```bash
# 只运行单元测试
pytest tests/unit/ -v

# 只运行集成测试
pytest tests/integration/ -v

# 运行特定测试文件
pytest tests/unit/test_config_loading.py -v
```

### 运行特定测试
```bash
# 运行特定测试方法
pytest tests/unit/test_memory_system.py::TestGlobalMemoryManager::test_add_session_message -v

# 运行Ollama相关测试
pytest tests/integration/test_ollama_integration.py -v
```

## 测试配置

### 环境变量
测试会自动进入测试模式，使用独立的测试数据目录，不会影响生产数据。

### API密钥配置
- 集成测试需要真实的API密钥才能运行
- 如果缺少API密钥，相关测试会自动跳过
- 在`.env`文件中配置API密钥：

```env
ZHIPU_API_KEY=your_zhipu_key
OPENAI_API_KEY=your_openai_key
TAVILY_API_KEY=your_tavily_key
```

### Ollama测试配置
Ollama测试需要本地运行Ollama服务：

1. **安装Ollama**：访问 [ollama.com](https://ollama.com) 下载安装
2. **启动服务**：`ollama serve`（通常自动启动）
3. **拉取模型**：`ollama pull gpt-oss:20b`

如果Ollama服务不可用，相关测试会自动跳过。

## 测试类型说明

### 单元测试 (unit/)

**test_config_loading.py**
- 测试配置文件加载
- 测试环境变量映射
- 测试可用配置获取

**test_memory_system.py**
- 测试全局记忆管理器
- 测试会话存储功能
- 测试消息持久化

### 集成测试 (integration/)

**test_agent_integration.py**
- 测试Agent创建和初始化
- 测试Agent与记忆系统集成
- 测试Agent工具调用功能
- 测试跨提供商记忆共享

**test_ollama_integration.py**
- 测试Ollama服务连接
- 测试Ollama LLM创建
- 测试Ollama Agent对话功能
- 测试Ollama模型自动切换

## 常见测试场景

### 1. 开发前验证
```bash
# 快速验证核心功能
pytest tests/unit/test_config_loading.py tests/unit/test_memory_system.py -v
```

### 2. 部署前验证
```bash
# 运行完整测试套件
pytest tests/ -v --tb=short
```

### 3. Ollama功能验证
```bash
# 确保Ollama服务正常
pytest tests/integration/test_ollama_integration.py -v
```

### 4. 特定Provider测试
```bash
# 测试智谱AI功能
pytest tests/integration/test_agent_integration.py::TestAgentIntegration::test_agent_creation_zhipu -v

# 测试OpenAI功能  
pytest tests/integration/test_agent_integration.py::TestAgentIntegration::test_agent_creation_openai -v
```

## 故障排除

### 常见问题

**1. 测试跳过 (SKIPPED)**
- 原因：缺少必要的API密钥或服务不可用
- 解决：配置对应的环境变量或启动相关服务

**2. 超时错误**
- 原因：网络连接慢或服务响应慢
- 解决：检查网络连接，或增加超时时间

**3. Ollama测试失败**
- 原因：Ollama服务未启动或模型未安装
- 解决：
  ```bash
  ollama serve
  ollama pull gpt-oss:20b
  ```

**4. 记忆测试失败**
- 原因：测试数据目录权限问题
- 解决：确保有写入权限，或清理测试数据目录

### 调试技巧

**详细输出**
```bash
pytest tests/ -v -s  # -s显示print输出
```

**只运行失败的测试**
```bash
pytest tests/ --lf  # last-failed
```

**显示完整错误信息**
```bash
pytest tests/ --tb=long
```

**停在第一个失败**
```bash
pytest tests/ -x
```

## 测试数据管理

- 测试数据存储在 `tests/test_data/` 目录
- 测试结束后会自动清理（可选）
- 不会影响生产环境的 `data/sessions/` 目录

## 持续集成

测试套件设计为支持CI/CD环境：
- 自动跳过不可用的服务
- 独立的测试数据环境
- 清晰的成功/失败状态

## 扩展测试

添加新测试时，请遵循以下原则：
1. 使用有意义的测试名称
2. 添加适当的超时设置
3. 处理服务不可用的情况
4. 保持测试的独立性
5. 添加必要的文档说明