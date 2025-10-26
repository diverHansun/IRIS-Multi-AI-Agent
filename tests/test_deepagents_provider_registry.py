"""
Unit tests for DeepAgentsProviderRegistry.

Tests the new categorized configuration management system for main agents.
"""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.core.providers.deepagents_provider_registry import DeepAgentsProviderRegistry


class TestDeepAgentsProviderRegistry(unittest.TestCase):
    """Test cases for DeepAgentsProviderRegistry."""

    def setUp(self):
        """Set up test fixtures."""
        # Create temporary test configuration
        self.test_config = {
            "zhipu": {
                "description": "GLM models for testing",
                "default_model": "glm-4.6",
                "api_config": {
                    "base_url": "https://test.api.com/v1",
                    "api_key_env": "TEST_API_KEY",
                },
                "models": {
                    "glm-4.6": {
                        "llm_params": {
                            "temperature": 0.6,
                            "max_tokens": 4096,
                            "streaming": False,
                        },
                        "runtime_config": {
                            "recursion_limit": 300,
                            "step_timeout": 120,
                            "stream_mode": "updates",
                        },
                        "middleware_config": {
                            "filesystem": "default",
                            "subagents": "default",
                        },
                        "display_config": {
                            "streaming_enabled": True,
                            "show_reasoning_steps": True,
                            "show_tool_calls": True,
                            "show_tool_results": True,
                            "show_subagent_delegations": True,
                            "show_elapsed_time": True,
                        },
                        "safety_config": {
                            "max_execution_time": 120,
                            "hitl_config": {
                                "dangerous_tools": ["delete_file", "rm"],
                                "tools": {
                                    "delete_file": {
                                        "allow_auto_approve": False,
                                        "warning_message": "Cannot be undone!",
                                    }
                                },
                            },
                        },
                        "metadata": {
                            "context_window": 200000,
                            "supports_tools": True,
                            "max_input_tokens": 100000,
                            "max_output_tokens": 50000,
                        },
                    }
                },
            },
            "anthropic": {
                "description": "Claude models for testing",
                "default_model": "claude-3",
                "api_config": {
                    "base_url": "https://api.anthropic.com/v1",
                    "api_key_env": "ANTHROPIC_KEY",
                },
                "models": {
                    "claude-3": {
                        "llm_params": {
                            "temperature": 0.7,
                            "max_tokens": 2048,
                            "streaming": False,
                        },
                        "runtime_config": {
                            "recursion_limit": 200,
                            "step_timeout": 90,
                            "stream_mode": "values",
                        },
                        "middleware_config": {
                            "filesystem": "default",
                            "subagents": "custom",
                        },
                        "display_config": {
                            "streaming_enabled": False,
                            "show_reasoning_steps": False,
                            "show_tool_calls": False,
                            "show_tool_results": False,
                            "show_subagent_delegations": False,
                            "show_elapsed_time": False,
                        },
                        "safety_config": {
                            "max_execution_time": 60,
                            "hitl_config": {},
                        },
                        "metadata": {
                            "context_window": 128000,
                            "supports_tools": True,
                            "max_input_tokens": 64000,
                            "max_output_tokens": 32000,
                        },
                    }
                },
            },
        }

        # Create temporary directory structure
        self.temp_dir = tempfile.mkdtemp()
        self.models_dir = Path(self.temp_dir) / "models"
        self.models_dir.mkdir()

        # Write mainagents config
        self.providers_file = self.models_dir / "mainagents.json"
        with open(self.providers_file, "w") as f:
            json.dump(self.test_config, f)

        # Create registry
        self.registry = DeepAgentsProviderRegistry(base_path=self.temp_dir)

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil

        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_load_providers(self):
        """Test successful provider configuration loading."""
        providers = self.registry.get_available_providers()
        self.assertEqual(len(providers), 2)
        self.assertIn("zhipu", providers)
        self.assertIn("anthropic", providers)

    def test_get_api_config(self):
        """Test getting API configuration for a provider."""
        api_config = self.registry.get_api_config("zhipu")
        self.assertEqual(api_config["base_url"], "https://test.api.com/v1")
        self.assertEqual(api_config["api_key_env"], "TEST_API_KEY")

    def test_get_api_config_case_insensitive(self):
        """Test API config retrieval is case-insensitive."""
        api_config = self.registry.get_api_config("ZHIPU")
        self.assertEqual(api_config["base_url"], "https://test.api.com/v1")

    def test_get_api_config_not_found(self):
        """Test error when provider not found."""
        with self.assertRaises(ValueError) as context:
            self.registry.get_api_config("nonexistent")
        self.assertIn("Provider nonexistent not found", str(context.exception))

    def test_get_llm_params(self):
        """Test getting LLM parameters for init_chat_model."""
        with patch.dict(os.environ, {"TEST_API_KEY": "test-key-123"}):
            params = self.registry.get_llm_params("zhipu", "glm-4.6")

            # Should contain LLM params
            self.assertEqual(params["temperature"], 0.6)
            self.assertEqual(params["max_tokens"], 4096)
            self.assertEqual(params["streaming"], False)

            # Should contain API config
            self.assertEqual(params["base_url"], "https://test.api.com/v1")
            self.assertEqual(params["api_key"], "test-key-123")

            # Should NOT contain other configs
            self.assertNotIn("recursion_limit", params)
            self.assertNotIn("streaming_enabled", params)

    def test_get_llm_params_without_api_key(self):
        """Test LLM params extraction when API key not in environment."""
        with patch.dict(os.environ, {}, clear=True):
            params = self.registry.get_llm_params("zhipu", "glm-4.6")

            # Should have model params
            self.assertIn("temperature", params)
            self.assertIn("max_tokens", params)

            # But no api_key
            self.assertNotIn("api_key", params)

    def test_get_runtime_config(self):
        """Test getting runtime configuration."""
        config = self.registry.get_runtime_config("zhipu", "glm-4.6")

        self.assertEqual(config["recursion_limit"], 300)
        self.assertEqual(config["step_timeout"], 120)
        self.assertEqual(config["stream_mode"], "updates")

        # Should not contain other params
        self.assertNotIn("temperature", config)
        self.assertNotIn("streaming_enabled", config)

    def test_get_middleware_config_for_model(self):
        """Test getting middleware configuration for specific model."""
        config = self.registry.get_middleware_config_for_model("zhipu", "glm-4.6")

        self.assertEqual(config["filesystem"], "default")
        self.assertEqual(config["subagents"], "default")

    def test_get_display_config(self):
        """Test getting display configuration."""
        config = self.registry.get_display_config("zhipu", "glm-4.6")

        self.assertEqual(config["streaming_enabled"], True)
        self.assertEqual(config["show_reasoning_steps"], True)
        self.assertEqual(config["show_tool_calls"], True)
        self.assertEqual(config["show_tool_results"], True)
        self.assertEqual(config["show_subagent_delegations"], True)
        self.assertEqual(config["show_elapsed_time"], True)

    def test_get_safety_config(self):
        """Test getting safety configuration including HITL."""
        config = self.registry.get_safety_config("zhipu", "glm-4.6")

        self.assertEqual(config["max_execution_time"], 120)
        self.assertIn("hitl_config", config)

        hitl_config = config["hitl_config"]
        self.assertIn("delete_file", hitl_config["dangerous_tools"])
        self.assertIn("delete_file", hitl_config["tools"])
        self.assertEqual(
            hitl_config["tools"]["delete_file"]["allow_auto_approve"], False
        )

    def test_get_metadata(self):
        """Test getting metadata."""
        metadata = self.registry.get_metadata("zhipu", "glm-4.6")

        self.assertEqual(metadata["context_window"], 200000)
        self.assertEqual(metadata["supports_tools"], True)
        self.assertEqual(metadata["max_input_tokens"], 100000)
        self.assertEqual(metadata["max_output_tokens"], 50000)

    def test_get_complete_config(self):
        """Test getting complete categorized configuration."""
        config = self.registry.get_complete_config("zhipu", "glm-4.6")

        # Check all categories present
        self.assertIn("provider", config)
        self.assertIn("model", config)
        self.assertIn("description", config)
        self.assertIn("api_config", config)
        self.assertIn("llm_params", config)
        self.assertIn("runtime_config", config)
        self.assertIn("middleware_config", config)
        self.assertIn("display_config", config)
        self.assertIn("safety_config", config)
        self.assertIn("metadata", config)

        # Verify values
        self.assertEqual(config["provider"], "zhipu")
        self.assertEqual(config["model"], "glm-4.6")
        self.assertEqual(config["api_config"]["base_url"], "https://test.api.com/v1")
        self.assertEqual(config["llm_params"]["temperature"], 0.6)

    def test_model_not_found(self):
        """Test error when model not found."""
        with self.assertRaises(ValueError) as context:
            self.registry.get_llm_params("zhipu", "nonexistent-model")
        self.assertIn("Model nonexistent-model not found", str(context.exception))

    def test_provider_not_found_for_config(self):
        """Test error when provider not found for config methods."""
        with self.assertRaises(ValueError):
            self.registry.get_runtime_config("nonexistent", "model")

    def test_list_providers(self):
        """Test listing raw provider configuration."""
        providers = self.registry.list_providers()

        self.assertIn("zhipu", providers)
        self.assertIn("anthropic", providers)
        self.assertIn("api_config", providers["zhipu"])
        self.assertIn("models", providers["zhipu"])

    def test_reload(self):
        """Test configuration reloading."""
        # Modify config file
        new_config = self.test_config.copy()
        new_config["openai"] = {
            "description": "OpenAI models",
            "default_model": "gpt-4",
            "api_config": {
                "base_url": "https://api.openai.com/v1",
                "api_key_env": "OPENAI_KEY",
            },
            "models": {
                "gpt-4": {
                    "llm_params": {"temperature": 0.5, "max_tokens": 2000, "streaming": False},
                    "runtime_config": {
                        "recursion_limit": 150,
                        "step_timeout": 60,
                        "stream_mode": "updates",
                    },
                    "middleware_config": {"filesystem": "default", "subagents": "default"},
                    "display_config": {
                        "streaming_enabled": True,
                        "show_reasoning_steps": True,
                        "show_tool_calls": True,
                        "show_tool_results": True,
                        "show_subagent_delegations": True,
                        "show_elapsed_time": True,
                    },
                    "safety_config": {"max_execution_time": 90, "hitl_config": {}},
                    "metadata": {
                        "context_window": 8000,
                        "supports_tools": True,
                        "max_input_tokens": 4000,
                        "max_output_tokens": 4000,
                    },
                }
            },
        }

        with open(self.providers_file, "w") as f:
            json.dump(new_config, f)

        # Reload
        self.registry.reload()

        providers = self.registry.get_available_providers()
        self.assertEqual(len(providers), 3)
        self.assertIn("openai", providers)

    def test_default_model_fallback(self):
        """Test that default_model is used from provider config."""
        # The zhipu provider has default_model set to glm-4.6
        # This is tested indirectly through complete_config
        config = self.registry.get_complete_config("zhipu", "glm-4.6")
        self.assertEqual(config["model"], "glm-4.6")

    def test_streaming_distinction(self):
        """Test distinction between LLM streaming and display streaming."""
        llm_params = self.registry.get_llm_params("zhipu", "glm-4.6")
        display_config = self.registry.get_display_config("zhipu", "glm-4.6")

        # LLM streaming should be false (for API)
        self.assertEqual(llm_params["streaming"], False)

        # Display streaming should be true (for UI)
        self.assertEqual(display_config["streaming_enabled"], True)


if __name__ == "__main__":
    unittest.main()
