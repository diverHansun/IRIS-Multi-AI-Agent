"""
Unit tests for LLMProviderRegistry.

Validates lowercase key normalization, adapter field support,
and backward compatibility with legacy UPPERCASE configs.
"""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.core.providers.llm_provider_registry import LLMProviderRegistry


class _EmptyConfigLoader:
    """Test helper that disables shared config lookups."""

    def load_shared_json(self, path: str):
        return {}


class TestLLMProviderRegistryKeysLowercase(unittest.TestCase):
    """Test that registry normalises all keys to lowercase."""

    def setUp(self):
        self.test_config = {
            "schema_version": "2.0",
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
                        }
                    },
                },
                "ollama": {
                    "adapter": "ollama",
                    "name": "Ollama",
                    "api_key_env": None,
                    "default_model": "auto",
                    "models": {
                        "auto": {"name": "Auto-detect", "temperature": 0.1}
                    },
                },
            },
        }

        self.temp_dir = tempfile.mkdtemp()
        self.config_file = Path(self.temp_dir) / "providers.json"
        with open(self.config_file, "w") as f:
            json.dump(self.test_config, f)

        self.registry = LLMProviderRegistry(
            config_path=str(self.config_file),
            config_loader=_EmptyConfigLoader(),
        )

    def test_all_keys_are_lowercase(self):
        providers = self.registry.list_providers()
        for key in providers.keys():
            self.assertEqual(key, key.lower(), f"Key '{key}' is not lowercase")

    def test_get_provider_config_case_insensitive(self):
        for query in ("zhipu", "ZHIPU", "Zhipu"):
            config = self.registry.get_provider_config(query)
            self.assertIsNotNone(config, f"Failed to find provider with query '{query}'")
            self.assertEqual(config["name"], "Zhipu AI")

    def test_tongyi_provider_exists(self):
        config = self.registry.get_provider_config("tongyi")
        self.assertIsNotNone(config)
        self.assertEqual(config["adapter"], "openai")
        self.assertEqual(config["default_model"], "qwen3-max")

    def test_tongyi_model_config(self):
        model = self.registry.get_model_config("tongyi", "qwen3-max")
        self.assertIsNotNone(model)
        self.assertEqual(model["name"], "Qwen3 Max")
        self.assertAlmostEqual(model["temperature"], 0.6)

    def test_ollama_no_api_key(self):
        config = self.registry.get_provider_config("ollama")
        self.assertIsNone(config.get("api_key_env"))

    def test_adapter_field_present(self):
        for name in ("zhipu", "openai", "tongyi", "ollama"):
            config = self.registry.get_provider_config(name)
            self.assertIn("adapter", config, f"Provider '{name}' missing adapter field")

    def test_provider_count(self):
        providers = self.registry.list_providers()
        self.assertEqual(len(providers), 4)

    def test_get_llm_config(self):
        config = self.registry.get_llm_config("tongyi", "qwen3-max")
        self.assertEqual(config["model"], "qwen3-max")
        self.assertAlmostEqual(config["temperature"], 0.6)

    def test_get_model_info(self):
        info = self.registry.get_model_info("openai", "gpt-4o-mini")
        self.assertEqual(info["provider"], "openai")
        self.assertEqual(info["model"], "gpt-4o-mini")

    def test_validate_model(self):
        self.assertTrue(self.registry.validate_model("zhipu", "glm-4.5-flash"))
        self.assertFalse(self.registry.validate_model("zhipu", "nonexistent"))

    def test_unknown_provider_returns_none(self):
        config = self.registry.get_provider_config("nonexistent")
        self.assertIsNone(config)


class TestLLMProviderRegistryLegacyFormat(unittest.TestCase):
    """Test backward compatibility with old UPPERCASE key format."""

    def setUp(self):
        self.legacy_config = {
            "schema_version": "1.0",
            "providers": {
                "ZHIPU": {
                    "name": "Zhipu AI",
                    "api_key_env": "ZHIPU_API_KEY",
                    "default_model": "glm-4.5-flash",
                    "models": {
                        "glm-4.5-flash": {
                            "name": "GLM-4.5-Flash",
                            "temperature": 0.5,
                        }
                    },
                },
                "OPENAI": {
                    "name": "OpenAI",
                    "api_key_env": "OPENAI_API_KEY",
                    "default_model": "gpt-4o-mini",
                    "models": {
                        "gpt-4o-mini": {
                            "name": "GPT-4o-mini",
                            "temperature": 0.1,
                        }
                    },
                },
            },
        }

        self.temp_dir = tempfile.mkdtemp()
        self.config_file = Path(self.temp_dir) / "providers.json"
        with open(self.config_file, "w") as f:
            json.dump(self.legacy_config, f)

        self.registry = LLMProviderRegistry(
            config_path=str(self.config_file),
            config_loader=_EmptyConfigLoader(),
        )

    def test_uppercase_keys_normalised_to_lowercase(self):
        providers = self.registry.list_providers()
        self.assertIn("zhipu", providers)
        self.assertIn("openai", providers)
        self.assertNotIn("ZHIPU", providers)
        self.assertNotIn("OPENAI", providers)

    def test_legacy_config_no_adapter_field(self):
        config = self.registry.get_provider_config("zhipu")
        self.assertIsNotNone(config)
        # No adapter field in legacy config -- that's expected
        self.assertNotIn("adapter", config)

    def test_lookup_works_with_any_case(self):
        for query in ("zhipu", "ZHIPU", "Zhipu"):
            config = self.registry.get_provider_config(query)
            self.assertIsNotNone(config)


class TestLLMProviderRegistryBaseUrl(unittest.TestCase):
    """Test base_url resolution with env var priority."""

    def setUp(self):
        self.config = {
            "providers": {
                "tongyi": {
                    "adapter": "openai",
                    "api_key_env": "TONGYI_API_KEY",
                    "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                    "base_url_env": "TONGYI_BASE_URL",
                    "default_model": "qwen3-max",
                    "models": {
                        "qwen3-max": {"name": "Qwen3 Max", "temperature": 0.6}
                    },
                }
            }
        }

        self.temp_dir = tempfile.mkdtemp()
        self.config_file = Path(self.temp_dir) / "providers.json"
        with open(self.config_file, "w") as f:
            json.dump(self.config, f)

        self.registry = LLMProviderRegistry(
            config_path=str(self.config_file),
            config_loader=_EmptyConfigLoader(),
        )

    def test_base_url_from_config(self):
        config = self.registry.get_provider_config("tongyi")
        url = self.registry._resolve_base_url(config)
        self.assertEqual(url, "https://dashscope.aliyuncs.com/compatible-mode/v1")

    @patch.dict(os.environ, {"TONGYI_BASE_URL": "https://custom.url/v1"})
    def test_base_url_env_overrides_config(self):
        config = self.registry.get_provider_config("tongyi")
        url = self.registry._resolve_base_url(config)
        self.assertEqual(url, "https://custom.url/v1")


if __name__ == "__main__":
    unittest.main()
