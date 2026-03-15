"""
Unit tests for LLM adapter provider_name parameter.

Validates that adapters accept provider_name and store it as lowercase,
enabling config-driven routing (e.g., tongyi -> OpenAIAdapter with provider="tongyi").
"""

import json
import tempfile
import unittest
from pathlib import Path

from src.core.providers.llm_provider_registry import LLMProviderRegistry
from src.llm.adapters.base import LLMAdapter
from src.llm.adapters.openai_adapter import OpenAIAdapter
from src.llm.adapters.zhipu_adapter import ZhipuAdapter
from src.llm.adapters.ollama_adapter import OllamaAdapter


class _EmptyConfigLoader:
    def load_shared_json(self, path: str):
        return {}


def _make_registry(config: dict) -> LLMProviderRegistry:
    temp_dir = tempfile.mkdtemp()
    config_file = Path(temp_dir) / "providers.json"
    with open(config_file, "w") as f:
        json.dump(config, f)
    return LLMProviderRegistry(
        config_path=str(config_file),
        config_loader=_EmptyConfigLoader(),
    )


TEST_CONFIG = {
    "providers": {
        "zhipu": {
            "adapter": "zhipu",
            "name": "Zhipu AI",
            "api_key_env": "ZHIPU_API_KEY",
            "default_model": "glm-4.5-flash",
            "models": {
                "glm-4.5-flash": {
                    "name": "GLM-4.5-Flash",
                    "temperature": 0.5,
                    "max_tokens": 96000,
                    "context_window": 128000,
                    "supports_tools": True,
                    "streaming": True,
                    "thinking_mode": True,
                }
            },
        },
        "openai": {
            "adapter": "openai",
            "name": "OpenAI",
            "api_key_env": "OPENAI_API_KEY",
            "base_url": "https://api.openai.com/v1",
            "default_model": "gpt-4o-mini",
            "models": {
                "gpt-4o-mini": {
                    "name": "GPT-4o-mini",
                    "temperature": 0.1,
                    "max_tokens": 16384,
                    "context_window": 131072,
                    "supports_tools": True,
                    "streaming": True,
                }
            },
        },
        "tongyi": {
            "adapter": "openai",
            "name": "Tongyi Qwen",
            "api_key_env": "TONGYI_API_KEY",
            "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "default_model": "qwen3-max",
            "models": {
                "qwen3-max": {
                    "name": "Qwen3 Max",
                    "temperature": 0.6,
                    "max_tokens": 4096,
                    "context_window": 128000,
                    "supports_tools": True,
                    "streaming": True,
                }
            },
        },
        "ollama": {
            "adapter": "ollama",
            "name": "Ollama",
            "api_key_env": None,
            "base_url": "http://localhost:11434",
            "base_url_env": "OLLAMA_BASE_URL",
            "default_model": "auto",
            "models": {
                "auto": {
                    "name": "Auto-detect",
                    "temperature": 0.1,
                    "max_tokens": 4096,
                    "context_window": 8192,
                    "supports_tools": True,
                    "streaming": True,
                }
            },
        },
    }
}


class TestAdapterProviderLowercase(unittest.TestCase):
    """Verify that base class stores provider as lowercase."""

    def setUp(self):
        self.registry = _make_registry(TEST_CONFIG)

    def test_zhipu_adapter_stores_lowercase(self):
        adapter = ZhipuAdapter(
            model="glm-4.5-flash",
            provider_registry=self.registry,
        )
        self.assertEqual(adapter.provider, "zhipu")

    def test_openai_adapter_stores_lowercase(self):
        adapter = OpenAIAdapter(
            model="gpt-4o-mini",
            provider_registry=self.registry,
        )
        self.assertEqual(adapter.provider, "openai")

    def test_ollama_adapter_stores_lowercase(self):
        adapter = OllamaAdapter(
            model="auto",
            provider_registry=self.registry,
        )
        self.assertEqual(adapter.provider, "ollama")


class TestAdapterProviderNameParam(unittest.TestCase):
    """Test that provider_name parameter overrides the default."""

    def setUp(self):
        self.registry = _make_registry(TEST_CONFIG)

    def test_openai_adapter_default_provider(self):
        adapter = OpenAIAdapter(
            model="gpt-4o-mini",
            provider_registry=self.registry,
        )
        self.assertEqual(adapter.provider, "openai")

    def test_openai_adapter_with_tongyi_provider(self):
        adapter = OpenAIAdapter(
            model="qwen3-max",
            provider_registry=self.registry,
            provider_name="tongyi",
        )
        self.assertEqual(adapter.provider, "tongyi")
        self.assertEqual(adapter.model, "qwen3-max")
        # Config should come from tongyi, not openai
        self.assertEqual(adapter._provider_config["name"], "Tongyi Qwen")

    def test_zhipu_adapter_default_provider(self):
        adapter = ZhipuAdapter(
            model="glm-4.5-flash",
            provider_registry=self.registry,
        )
        self.assertEqual(adapter.provider, "zhipu")

    def test_ollama_adapter_default_provider(self):
        adapter = OllamaAdapter(
            model="auto",
            provider_registry=self.registry,
        )
        self.assertEqual(adapter.provider, "ollama")


class TestAdapterGetLlmParams(unittest.TestCase):
    """Test that adapters return correct params using provider_name config."""

    def setUp(self):
        self.registry = _make_registry(TEST_CONFIG)

    def test_tongyi_adapter_params(self):
        adapter = OpenAIAdapter(
            model="qwen3-max",
            provider_registry=self.registry,
            provider_name="tongyi",
        )
        params = adapter.get_llm_params()
        self.assertEqual(params["model"], "qwen3-max")

    def test_zhipu_thinking_mode(self):
        adapter = ZhipuAdapter(
            model="glm-4.5-flash",
            provider_registry=self.registry,
        )
        # glm-4.5-flash is not in the thinking_mode check list
        # but model config has thinking_mode: true
        params = adapter.get_llm_params()
        self.assertEqual(params["model"], "glm-4.5-flash")


class TestAdapterModelInfo(unittest.TestCase):
    """Test get_model_info returns correct provider name."""

    def setUp(self):
        self.registry = _make_registry(TEST_CONFIG)

    def test_tongyi_model_info(self):
        adapter = OpenAIAdapter(
            model="qwen3-max",
            provider_registry=self.registry,
            provider_name="tongyi",
        )
        info = adapter.get_model_info()
        self.assertEqual(info["provider"], "tongyi")
        self.assertEqual(info["model"], "qwen3-max")


if __name__ == "__main__":
    unittest.main()
