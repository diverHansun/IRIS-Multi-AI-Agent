"""
Unit tests for SubAgentsProviderRegistry.

Tests the new subagent configuration management system.
"""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from src.core.providers.subagents_provider_registry import SubAgentsProviderRegistry


class TestSubAgentsProviderRegistry(unittest.TestCase):
    """Test cases for SubAgentsProviderRegistry."""

    def setUp(self):
        """Set up test fixtures."""
        # Create temporary test configuration
        self.test_config = {
            "research": {
                "name": "research",
                "description": "Test research specialist",
                "llm_config": {
                    "provider": "zhipu",
                    "model": "glm-4.6",
                    "api_config": {
                        "base_url": "https://test.api.com",
                        "api_key_env": "TEST_API_KEY",
                    },
                    "model_params": {
                        "temperature": 0.7,
                        "max_tokens": 2000,
                        "streaming": False,
                    },
                },
                "agent_config": {
                    "tools": [],
                    "middleware": [],
                    "checkpointer": False,
                },
                "runtime_limits": {
                    "max_execution_time": 60,
                    "recursion_limit": 30,
                },
                "display_config": {
                    "streaming_enabled": False,
                    "show_reasoning_steps": False,
                    "show_tool_calls": False,
                },
                "metadata": {
                    "context_window": 128000,
                    "supports_tools": True,
                },
            },
            "coding": {
                "name": "coding",
                "description": "Test coding specialist",
                "llm_config": {
                    "provider": "openai",
                    "model": "gpt-4",
                    "api_config": {
                        "base_url": "https://api.openai.com/v1",
                        "api_key_env": "OPENAI_API_KEY",
                    },
                    "model_params": {
                        "temperature": 0.5,
                        "max_tokens": 4000,
                        "streaming": False,
                    },
                },
                "agent_config": {
                    "tools": [],
                    "middleware": [],
                    "checkpointer": False,
                },
                "runtime_limits": {
                    "max_execution_time": 90,
                    "recursion_limit": 50,
                },
                "display_config": {
                    "streaming_enabled": False,
                    "show_reasoning_steps": False,
                    "show_tool_calls": False,
                },
                "metadata": {
                    "context_window": 8000,
                    "supports_tools": True,
                },
            },
        }

        # Create temporary config file
        self.temp_file = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        )
        json.dump(self.test_config, self.temp_file)
        self.temp_file.close()

        # Create mock prompt registry
        self.mock_prompt_registry = Mock()
        self.mock_prompt_registry.get_subagent_prompt.return_value = (
            "Test system prompt"
        )

        # Create registry with test config
        self.registry = SubAgentsProviderRegistry(
            config_path=self.temp_file.name,
            prompt_registry=self.mock_prompt_registry,
        )

    def tearDown(self):
        """Clean up test fixtures."""
        if os.path.exists(self.temp_file.name):
            os.unlink(self.temp_file.name)

    def test_load_config_success(self):
        """Test successful configuration loading."""
        self.assertEqual(len(self.registry._configs), 2)
        self.assertIn("research", self.registry._configs)
        self.assertIn("coding", self.registry._configs)

    def test_get_available_subagents(self):
        """Test getting list of available subagents."""
        available = self.registry.get_available_subagents()
        self.assertEqual(len(available), 2)
        self.assertIn("research", available)
        self.assertIn("coding", available)

    def test_get_subagent_config_success(self):
        """Test getting complete subagent configuration."""
        config = self.registry.get_subagent_config("research")

        # Check main structure
        self.assertIn("name", config)
        self.assertIn("description", config)
        self.assertIn("system_prompt", config)
        self.assertIn("llm_config", config)
        self.assertIn("agent_config", config)
        self.assertIn("runtime_limits", config)
        self.assertIn("display_config", config)
        self.assertIn("metadata", config)

        # Check LLM config structure
        llm_config = config["llm_config"]
        self.assertEqual(llm_config["provider"], "zhipu")
        self.assertEqual(llm_config["model"], "glm-4.6")
        self.assertIn("api_config", llm_config)
        self.assertIn("model_params", llm_config)

        # Check model params
        model_params = llm_config["model_params"]
        self.assertEqual(model_params["temperature"], 0.7)
        self.assertEqual(model_params["max_tokens"], 2000)
        self.assertEqual(model_params["streaming"], False)

        # Check runtime limits
        runtime_limits = config["runtime_limits"]
        self.assertEqual(runtime_limits["max_execution_time"], 60)
        self.assertEqual(runtime_limits["recursion_limit"], 30)

        # Check system prompt was loaded from prompt registry
        self.assertEqual(config["system_prompt"], "Test system prompt")
        self.mock_prompt_registry.get_subagent_prompt.assert_called_with("research")

    def test_get_subagent_config_not_found(self):
        """Test getting config for non-existent subagent."""
        with self.assertRaises(ValueError) as context:
            self.registry.get_subagent_config("nonexistent")

        self.assertIn("Unknown subagent type", str(context.exception))

    def test_get_llm_params_only(self):
        """Test extracting only valid LLM parameters."""
        with patch.dict(os.environ, {"TEST_API_KEY": "test-key-123"}):
            params = self.registry.get_llm_params_only("research")

            # Should only contain valid LLM parameters
            self.assertIn("temperature", params)
            self.assertIn("max_tokens", params)
            self.assertIn("streaming", params)
            self.assertIn("base_url", params)
            self.assertIn("api_key", params)

            # Check values
            self.assertEqual(params["temperature"], 0.7)
            self.assertEqual(params["max_tokens"], 2000)
            self.assertEqual(params["streaming"], False)
            self.assertEqual(params["base_url"], "https://test.api.com")
            self.assertEqual(params["api_key"], "test-key-123")

            # Should NOT contain agent or display config
            self.assertNotIn("recursion_limit", params)
            self.assertNotIn("max_execution_time", params)
            self.assertNotIn("context_window", params)
            self.assertNotIn("show_tool_calls", params)

    def test_get_llm_params_without_api_key(self):
        """Test LLM params extraction when API key is not in environment."""
        with patch.dict(os.environ, {}, clear=True):
            params = self.registry.get_llm_params_only("research")

            # Should still have other params
            self.assertIn("temperature", params)
            self.assertIn("max_tokens", params)

            # But no api_key
            self.assertNotIn("api_key", params)

    def test_parameter_overrides(self):
        """Test applying parameter overrides."""
        config = self.registry.get_subagent_config(
            "research", temperature=0.9, max_tokens=5000, recursion_limit=100
        )

        # Check overrides applied
        self.assertEqual(config["llm_config"]["model_params"]["temperature"], 0.9)
        self.assertEqual(config["llm_config"]["model_params"]["max_tokens"], 5000)
        self.assertEqual(config["runtime_limits"]["recursion_limit"], 100)

    def test_validate_subagent_type(self):
        """Test subagent type validation."""
        self.assertTrue(self.registry.validate_subagent_type("research"))
        self.assertTrue(self.registry.validate_subagent_type("coding"))
        self.assertFalse(self.registry.validate_subagent_type("nonexistent"))

    def test_reload_config(self):
        """Test configuration reloading."""
        # Modify config file
        new_config = self.test_config.copy()
        new_config["analysis"] = {
            "name": "analysis",
            "description": "Analysis specialist",
            "llm_config": {
                "provider": "anthropic",
                "model": "claude-3",
                "api_config": {"api_key_env": "ANTHROPIC_KEY"},
                "model_params": {"temperature": 0.6, "max_tokens": 3000, "streaming": False},
            },
            "agent_config": {"tools": [], "middleware": [], "checkpointer": False},
            "runtime_limits": {"max_execution_time": 120, "recursion_limit": 40},
            "display_config": {
                "streaming_enabled": False,
                "show_reasoning_steps": False,
                "show_tool_calls": False,
            },
            "metadata": {"context_window": 200000, "supports_tools": True},
        }

        with open(self.temp_file.name, "w") as f:
            json.dump(new_config, f)

        # Reload
        result = self.registry.reload_config()

        self.assertTrue(result)
        self.assertEqual(len(self.registry.get_available_subagents()), 3)
        self.assertIn("analysis", self.registry.get_available_subagents())

    def test_config_file_not_found(self):
        """Test handling of missing config file."""
        registry = SubAgentsProviderRegistry(
            config_path="/nonexistent/path.json",
            prompt_registry=self.mock_prompt_registry,
        )

        self.assertEqual(len(registry._configs), 0)
        self.assertEqual(registry.get_available_subagents(), [])

    def test_invalid_json(self):
        """Test handling of invalid JSON."""
        # Create file with invalid JSON
        invalid_file = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        )
        invalid_file.write("{invalid json content")
        invalid_file.close()

        try:
            registry = SubAgentsProviderRegistry(
                config_path=invalid_file.name,
                prompt_registry=self.mock_prompt_registry,
            )

            self.assertEqual(len(registry._configs), 0)
        finally:
            os.unlink(invalid_file.name)

    def test_extract_methods(self):
        """Test individual extraction methods."""
        config = self.test_config["research"]

        llm_config = self.registry._extract_llm_config(config)
        self.assertEqual(llm_config["provider"], "zhipu")
        self.assertEqual(llm_config["model"], "glm-4.6")

        agent_config = self.registry._extract_agent_config(config)
        self.assertEqual(agent_config["tools"], [])
        self.assertEqual(agent_config["checkpointer"], False)

        runtime_limits = self.registry._extract_runtime_limits(config)
        self.assertEqual(runtime_limits["max_execution_time"], 60)

        display_config = self.registry._extract_display_config(config)
        self.assertEqual(display_config["streaming_enabled"], False)

        metadata = self.registry._extract_metadata(config)
        self.assertEqual(metadata["context_window"], 128000)

    def test_repr(self):
        """Test string representation."""
        repr_str = repr(self.registry)
        self.assertIn("SubAgentsProviderRegistry", repr_str)
        self.assertIn("research", repr_str)
        self.assertIn("coding", repr_str)


if __name__ == "__main__":
    unittest.main()
