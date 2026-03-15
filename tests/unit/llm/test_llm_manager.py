"""
Unit tests for LLMManager after provider registry refactoring.

Validates:
- LLMProvider Enum removal (config-driven adapter routing)
- ADAPTER_REGISTRY mapping
- Dynamic API key loading from provider configs
- _resolve_adapter_type with fallback for legacy configs
- _provider_available for Ollama (no key needed)
- set_api_key validation
"""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.core.providers.llm_provider_registry import LLMProviderRegistry


class _EmptyConfigLoader:
    """Test helper that disables shared config lookups."""

    def load_shared_json(self, path: str):
        return {}


def _make_registry(config: dict) -> LLMProviderRegistry:
    """Create a test registry from a config dict."""
    temp_dir = tempfile.mkdtemp()
    config_file = Path(temp_dir) / "providers.json"
    with open(config_file, "w") as f:
        json.dump(config, f)
    return LLMProviderRegistry(
        config_path=str(config_file),
        config_loader=_EmptyConfigLoader(),
    )


TEST_CONFIG = {
    "schema_version": "2.0",
    "providers": {
        "zhipu": {
            "adapter": "zhipu",
            "name": "Zhipu AI",
            "api_key_env": "ZHIPU_API_KEY",
            "base_url": None,
            "base_url_env": None,
            "default_model": "glm-4.5-flash",
            "models": {
                "glm-4.5-flash": {
                    "name": "GLM-4.5-Flash",
                    "temperature": 0.5,
                    "max_tokens": 96000,
                    "context_window": 128000,
                    "supports_tools": True,
                    "streaming": True,
                }
            },
        },
        "openai": {
            "adapter": "openai",
            "name": "OpenAI",
            "api_key_env": "OPENAI_API_KEY",
            "base_url": "https://api.openai.com/v1",
            "base_url_env": "OPENAI_BASE_URL",
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
            "base_url_env": "TONGYI_BASE_URL",
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
    },
}


class TestAdapterRegistry(unittest.TestCase):
    """Test ADAPTER_REGISTRY module-level mapping."""

    def test_adapter_registry_has_three_entries(self):
        from src.llm.managers.llm_manager import ADAPTER_REGISTRY

        self.assertEqual(len(ADAPTER_REGISTRY), 3)
        self.assertIn("zhipu", ADAPTER_REGISTRY)
        self.assertIn("openai", ADAPTER_REGISTRY)
        self.assertIn("ollama", ADAPTER_REGISTRY)

    def test_adapter_registry_tuples(self):
        from src.llm.managers.llm_manager import ADAPTER_REGISTRY
        from src.llm.adapters import ZhipuAdapter, OpenAIAdapter, OllamaAdapter
        from src.llm.instances import ZhipuAILLM, OpenAILLM, OllamaLLM

        self.assertEqual(ADAPTER_REGISTRY["zhipu"], (ZhipuAdapter, ZhipuAILLM))
        self.assertEqual(ADAPTER_REGISTRY["openai"], (OpenAIAdapter, OpenAILLM))
        self.assertEqual(ADAPTER_REGISTRY["ollama"], (OllamaAdapter, OllamaLLM))


class TestLLMProviderEnumRemoved(unittest.TestCase):
    """Verify LLMProvider Enum no longer exists."""

    def test_no_llm_provider_enum(self):
        import src.llm.managers.llm_manager as mod
        self.assertFalse(hasattr(mod, "LLMProvider"))

    def test_no_llm_provider_in_managers_init(self):
        import src.llm.managers as mod
        self.assertFalse(hasattr(mod, "LLMProvider"))

    def test_no_llm_provider_in_llm_init(self):
        import src.llm as mod
        self.assertFalse(hasattr(mod, "LLMProvider"))


class TestLLMManagerNormaliseProvider(unittest.TestCase):
    """Test _normalise_provider returns lowercase string."""

    def setUp(self):
        from src.llm.managers.llm_manager import LLMManager
        self.manager = LLMManager.__new__(LLMManager)
        self.manager.provider_registry = _make_registry(TEST_CONFIG)
        self.manager._api_keys = {}

    def test_normalise_lowercase(self):
        result = self.manager._normalise_provider("zhipu")
        self.assertEqual(result, "zhipu")

    def test_normalise_uppercase(self):
        result = self.manager._normalise_provider("OPENAI")
        self.assertEqual(result, "openai")

    def test_normalise_mixed_case(self):
        result = self.manager._normalise_provider("Tongyi")
        self.assertEqual(result, "tongyi")

    def test_normalise_unknown_raises(self):
        with self.assertRaises(ValueError) as ctx:
            self.manager._normalise_provider("nonexistent")
        self.assertIn("not found", str(ctx.exception))


class TestLLMManagerResolveAdapterType(unittest.TestCase):
    """Test _resolve_adapter_type with adapter field and fallback."""

    def setUp(self):
        from src.llm.managers.llm_manager import LLMManager
        self.manager = LLMManager.__new__(LLMManager)
        self.manager.provider_registry = _make_registry(TEST_CONFIG)
        self.manager._api_keys = {}

    def test_adapter_from_config(self):
        config = {"adapter": "openai", "name": "Test"}
        self.assertEqual(self.manager._resolve_adapter_type("tongyi", config), "openai")

    def test_fallback_zhipu(self):
        config = {"name": "Zhipu"}  # no adapter field
        self.assertEqual(self.manager._resolve_adapter_type("zhipu", config), "zhipu")

    def test_fallback_ollama(self):
        config = {"name": "Ollama"}
        self.assertEqual(self.manager._resolve_adapter_type("ollama", config), "ollama")

    def test_fallback_unknown_defaults_to_openai(self):
        config = {"name": "Custom"}
        self.assertEqual(self.manager._resolve_adapter_type("deepseek", config), "openai")


class TestLLMManagerLoadApiKeys(unittest.TestCase):
    """Test dynamic API key loading from provider configs."""

    def setUp(self):
        from src.llm.managers.llm_manager import LLMManager
        self.manager = LLMManager.__new__(LLMManager)
        self.manager.provider_registry = _make_registry(TEST_CONFIG)
        self.manager._api_keys = {}

    @patch.dict(os.environ, {
        "ZHIPU_API_KEY": "test_zhipu_key",
        "OPENAI_API_KEY": "test_openai_key",
        "TONGYI_API_KEY": "test_tongyi_key",
    })
    def test_loads_all_configured_keys(self):
        self.manager._load_api_keys()
        self.assertEqual(self.manager._api_keys["zhipu"], "test_zhipu_key")
        self.assertEqual(self.manager._api_keys["openai"], "test_openai_key")
        self.assertEqual(self.manager._api_keys["tongyi"], "test_tongyi_key")

    @patch.dict(os.environ, {"ZHIPU_API_KEY": "your_key_here"})
    def test_skips_placeholder_keys(self):
        self.manager._load_api_keys()
        self.assertNotIn("zhipu", self.manager._api_keys)

    @patch.dict(os.environ, {}, clear=True)
    def test_no_keys_available(self):
        self.manager._load_api_keys()
        # Ollama has no api_key_env, so it should not appear either
        self.assertEqual(len(self.manager._api_keys), 0)


class TestLLMManagerProviderAvailable(unittest.TestCase):
    """Test _provider_available checks."""

    def setUp(self):
        from src.llm.managers.llm_manager import LLMManager
        self.manager = LLMManager.__new__(LLMManager)
        self.manager.provider_registry = _make_registry(TEST_CONFIG)
        self.manager._api_keys = {"zhipu": "key123"}

    def test_ollama_always_available(self):
        self.assertTrue(self.manager._provider_available("ollama"))

    def test_provider_with_key_available(self):
        self.assertTrue(self.manager._provider_available("zhipu"))

    def test_provider_without_key_unavailable(self):
        self.assertFalse(self.manager._provider_available("openai"))

    def test_unknown_provider_unavailable(self):
        self.assertFalse(self.manager._provider_available("nonexistent"))


class TestLLMManagerSetApiKey(unittest.TestCase):
    """Test set_api_key validation."""

    def setUp(self):
        from src.llm.managers.llm_manager import LLMManager
        self.manager = LLMManager.__new__(LLMManager)
        self.manager.provider_registry = _make_registry(TEST_CONFIG)
        self.manager._api_keys = {}

    def test_set_valid_key(self):
        self.manager.set_api_key("zhipu", "new_key")
        self.assertEqual(self.manager._api_keys["zhipu"], "new_key")

    def test_set_empty_key_raises(self):
        with self.assertRaises(ValueError):
            self.manager.set_api_key("zhipu", "")

    def test_set_key_for_ollama_ignored(self):
        self.manager.set_api_key("ollama", "some_key")
        self.assertNotIn("ollama", self.manager._api_keys)

    def test_set_key_unknown_provider_raises(self):
        with self.assertRaises(ValueError):
            self.manager.set_api_key("nonexistent", "key")


class TestLLMManagerResolveApiKey(unittest.TestCase):
    """Test _resolve_api_key with priority chain."""

    def setUp(self):
        from src.llm.managers.llm_manager import LLMManager
        self.manager = LLMManager.__new__(LLMManager)
        self.manager.provider_registry = _make_registry(TEST_CONFIG)
        self.manager._api_keys = {"zhipu": "cached_key"}

    def test_explicit_key_takes_priority(self):
        result = self.manager._resolve_api_key("zhipu", "explicit_key")
        self.assertEqual(result, "explicit_key")

    def test_cached_key_used(self):
        result = self.manager._resolve_api_key("zhipu", None)
        self.assertEqual(result, "cached_key")

    @patch.dict(os.environ, {"OPENAI_API_KEY": "env_key"})
    def test_env_fallback(self):
        result = self.manager._resolve_api_key("openai", None)
        self.assertEqual(result, "env_key")
        # Should also cache it
        self.assertEqual(self.manager._api_keys["openai"], "env_key")

    @patch.dict(os.environ, {}, clear=True)
    def test_no_key_raises(self):
        with self.assertRaises(ValueError) as ctx:
            self.manager._resolve_api_key("openai", None)
        self.assertIn("OPENAI_API_KEY", str(ctx.exception))


class TestLLMManagerCreateAdapter(unittest.TestCase):
    """Test _create_adapter routes to correct adapter class."""

    def setUp(self):
        from src.llm.managers.llm_manager import LLMManager
        self.manager = LLMManager.__new__(LLMManager)
        self.manager.provider_registry = _make_registry(TEST_CONFIG)
        self.manager._api_keys = {}

    def test_zhipu_adapter(self):
        from src.llm.adapters import ZhipuAdapter
        adapter = self.manager._create_adapter("zhipu", "glm-4.5-flash", "llm")
        self.assertIsInstance(adapter, ZhipuAdapter)
        self.assertEqual(adapter.provider, "zhipu")

    def test_openai_adapter(self):
        from src.llm.adapters import OpenAIAdapter
        adapter = self.manager._create_adapter("openai", "gpt-4o-mini", "llm")
        self.assertIsInstance(adapter, OpenAIAdapter)
        self.assertEqual(adapter.provider, "openai")

    def test_tongyi_uses_openai_adapter(self):
        from src.llm.adapters import OpenAIAdapter
        adapter = self.manager._create_adapter("tongyi", "qwen3-max", "llm")
        self.assertIsInstance(adapter, OpenAIAdapter)
        # provider should be "tongyi", not "openai"
        self.assertEqual(adapter.provider, "tongyi")

    def test_ollama_adapter(self):
        from src.llm.adapters import OllamaAdapter
        adapter = self.manager._create_adapter("ollama", "auto", "llm")
        self.assertIsInstance(adapter, OllamaAdapter)
        self.assertEqual(adapter.provider, "ollama")

    def test_unknown_adapter_type_raises(self):
        # Inject a config with unknown adapter type
        config = {
            "providers": {
                "bad": {
                    "adapter": "nonexistent",
                    "default_model": "x",
                    "models": {"x": {"name": "X"}},
                }
            }
        }
        self.manager.provider_registry = _make_registry(config)
        with self.assertRaises(ValueError) as ctx:
            self.manager._create_adapter("bad", "x", "llm")
        self.assertIn("Unknown adapter type", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
