"""
pytest配置文件

提供测试运行时的全局配置和fixtures
"""

import pytest
import asyncio
import os
import sys
from pathlib import Path

# 将src目录添加到Python路径
ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR / "src"))


@pytest.fixture(scope="session")
def event_loop():
    """创建用于整个测试会话的事件循环"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def test_env():
    """测试环境配置"""
    # 确保测试时不会影响生产数据
    os.environ["TEST_MODE"] = "1"
    
    # 设置测试专用的数据目录
    test_data_dir = ROOT_DIR / "tests" / "test_data"
    test_data_dir.mkdir(exist_ok=True)
    os.environ["DATA_DIR"] = str(test_data_dir)
    
    yield {
        "root_dir": ROOT_DIR,
        "test_data_dir": test_data_dir
    }
    
    # 清理测试数据（可选）
    # import shutil
    # if test_data_dir.exists():
    #     shutil.rmtree(test_data_dir)


@pytest.fixture
def mock_api_keys():
    """模拟API密钥"""
    return {
        "zhipu_api_key": "test_zhipu_key_123",
        "openai_api_key": "test_openai_key_123",
        "tavily_api_key": "test_tavily_key_123",
        "amap_api_key": "test_amap_key_123",
        "notion_token": "test_notion_token_123"
    }


@pytest.fixture
def sample_session_data():
    """示例会话数据"""
    return {
        "session_id": "test_session_001",
        "messages": [
            {"role": "human", "content": "你好"},
            {"role": "ai", "content": "你好！有什么我可以帮助你的吗？"}
        ]
    }