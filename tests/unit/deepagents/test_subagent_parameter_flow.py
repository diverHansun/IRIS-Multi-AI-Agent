"""
Unit tests for SubAgent parameter flow.

Tests verify that configuration parameters flow correctly through:
1. SubAgent dataclass structure
2. Factory parameter passing
3. Middleware parameter usage
"""

import unittest
from dataclasses import asdict
from unittest.mock import Mock, patch, MagicMock

from src.components.deepagents.runtime_middlewares.subagents import SubAgent


class TestSubAgentDataclass(unittest.TestCase):
    """Test SubAgent dataclass structure and field storage."""

    def test_subagent_has_required_fields(self):
        """Test SubAgent dataclass has all required fields."""
        subagent = SubAgent(
            name="test",
            description="Test subagent",
            system_prompt="Test prompt",
            tools=["tool1", "tool2"],
            model="test-model",
            metadata={"key": "value"},
            recursion_limit=50,
            step_timeout=60.0,
            middleware=["middleware1"],
            checkpointer=True,
            display_config={"streaming_enabled": True},
        )

        # Verify all fields are stored
        self.assertEqual(subagent.name, "test")
        self.assertEqual(subagent.description, "Test subagent")
        self.assertEqual(subagent.system_prompt, "Test prompt")
        self.assertEqual(subagent.tools, ["tool1", "tool2"])
        self.assertEqual(subagent.model, "test-model")
        self.assertEqual(subagent.metadata, {"key": "value"})
        self.assertEqual(subagent.recursion_limit, 50)
        self.assertEqual(subagent.step_timeout, 60.0)
        self.assertEqual(subagent.middleware, ["middleware1"])
        self.assertEqual(subagent.checkpointer, True)
        self.assertEqual(subagent.display_config, {"streaming_enabled": True})

    def test_subagent_default_values(self):
        """Test SubAgent dataclass default values."""
        subagent = SubAgent(
            name="test", description="Test subagent", system_prompt="Test prompt"
        )

        # Verify default values
        self.assertEqual(subagent.tools, [])
        self.assertIsNone(subagent.model)
        self.assertEqual(subagent.metadata, {})
        self.assertIsNone(subagent.recursion_limit)
        self.assertIsNone(subagent.step_timeout)
        self.assertEqual(subagent.middleware, [])
        self.assertIsNone(subagent.checkpointer)
        self.assertEqual(subagent.display_config, {})

    def test_subagent_with_agent_config_parameters(self):
        """Test SubAgent can store agent_config parameters."""
        subagent = SubAgent(
            name="test",
            description="Test subagent",
            system_prompt="Test prompt",
            tools=["search", "calculator"],
            middleware=["retry_middleware", "logging_middleware"],
            checkpointer=False,
        )

        # Verify agent_config parameters are stored
        self.assertEqual(len(subagent.tools), 2)
        self.assertIn("search", subagent.tools)
        self.assertIn("calculator", subagent.tools)
        self.assertEqual(len(subagent.middleware), 2)
        self.assertEqual(subagent.checkpointer, False)

    def test_subagent_with_display_config(self):
        """Test SubAgent can store display_config parameters."""
        display_cfg = {
            "streaming_enabled": True,
            "show_reasoning_steps": True,
            "show_tool_calls": False,
        }

        subagent = SubAgent(
            name="test",
            description="Test subagent",
            system_prompt="Test prompt",
            display_config=display_cfg,
        )

        # Verify display_config is stored
        self.assertEqual(subagent.display_config, display_cfg)
        self.assertTrue(subagent.display_config["streaming_enabled"])
        self.assertTrue(subagent.display_config["show_reasoning_steps"])
        self.assertFalse(subagent.display_config["show_tool_calls"])


class TestFactoryParameterPassing(unittest.TestCase):
    """Test Factory layer passes parameters correctly to SubAgent."""

    @patch("langchain.chat_models.init_chat_model")
    def test_factory_passes_agent_config_to_subagent(self, mock_init_chat_model):
        """Test Factory passes agent_config parameters to SubAgent spec."""
        from src.agents.deepagents.factories.base import BaseDeepAgentFactory

        # Mock subagent manager
        mock_manager = Mock()
        mock_manager.get_available_subagents.return_value = {"test": {}}

        # Mock config with agent_config parameters
        test_config = {
            "name": "test",
            "description": "Test subagent",
            "system_prompt": "Test prompt",
            "llm_config": {
                "provider": "openai",
                "model": "gpt-4",
                "api_config": {},
                "model_params": {},
            },
            "agent_config": {
                "tools": ["tool1", "tool2"],
                "middleware": ["middleware1"],
                "checkpointer": True,
            },
            "runtime_limits": {"recursion_limit": 50, "max_execution_time": 60},
            "display_config": {
                "streaming_enabled": True,
                "show_reasoning_steps": False,
            },
            "metadata": {"context_window": 8000, "supports_tools": True},
        }

        mock_manager.get_subagent_config.return_value = test_config
        mock_manager.subagents_registry.get_llm_params_only.return_value = {}

        # Mock LLM
        mock_llm = Mock()
        mock_init_chat_model.return_value = mock_llm

        # Mock adapter
        mock_adapter = Mock()
        mock_adapter.get_model_identifier_for.return_value = "openai:gpt-4"

        factory = BaseDeepAgentFactory()

        # Build subagent specs
        specs, metadata = factory._build_subagent_specs(
            adapter=mock_adapter,
            subagent_manager=mock_manager,
            middleware_config={"subagents": {"subagents": {}}},
        )

        # Verify SubAgent spec received all parameters
        self.assertEqual(len(specs), 1)
        spec = specs[0]

        self.assertEqual(spec.name, "test")
        self.assertEqual(spec.tools, ["tool1", "tool2"])
        self.assertEqual(spec.middleware, ["middleware1"])
        self.assertEqual(spec.checkpointer, True)
        self.assertEqual(spec.recursion_limit, 50)
        self.assertEqual(spec.step_timeout, 60)
        self.assertEqual(spec.display_config["streaming_enabled"], True)
        self.assertEqual(spec.metadata["context_window"], 8000)


class TestMiddlewareParameterUsage(unittest.TestCase):
    """Test Middleware layer uses configuration parameters correctly."""

    @patch("langchain.agents.create_agent")
    def test_middleware_uses_configured_tools(self, mock_create_agent):
        """Test Middleware uses configured tools instead of hardcoded defaults."""
        from src.components.deepagents.runtime_middlewares.subagents import (
            SubAgent,
            SubAgentMiddleware,
        )

        # Create SubAgent with custom tools
        custom_tools = ["custom_tool1", "custom_tool2"]
        subagent = SubAgent(
            name="test",
            description="Test subagent",
            system_prompt="Test prompt",
            tools=custom_tools,
            model="test-model",
        )

        # Create middleware with default tools
        default_tools = ["default_tool1", "default_tool2"]
        mock_create_agent.return_value = Mock()

        middleware = SubAgentMiddleware(
            default_model="default-model",
            default_tools=default_tools,
            subagents=[subagent],
            default_middleware=[],
        )

        # Verify create_agent was called with merged tools (custom before defaults)
        call_args = mock_create_agent.call_args
        tools_passed = call_args[1]["tools"]

        # Custom tools should be first
        self.assertEqual(tools_passed[:2], custom_tools)
        # Followed by default tools
        self.assertEqual(tools_passed[2:], default_tools)

    @patch("langchain.agents.create_agent")
    def test_middleware_uses_configured_middleware(self, mock_create_agent):
        """Test Middleware uses configured middleware instead of hardcoded defaults."""
        from src.components.deepagents.runtime_middlewares.subagents import (
            SubAgent,
            SubAgentMiddleware,
        )

        # Create SubAgent with custom middleware
        custom_mw = [Mock(name="custom_mw1")]
        subagent = SubAgent(
            name="test",
            description="Test subagent",
            system_prompt="Test prompt",
            middleware=custom_mw,
            model="test-model",
        )

        # Create middleware with default middleware
        default_mw = [Mock(name="default_mw1")]
        mock_create_agent.return_value = Mock()

        middleware = SubAgentMiddleware(
            default_model="default-model",
            default_tools=[],
            subagents=[subagent],
            default_middleware=default_mw,
        )

        # Verify create_agent was called with merged middleware (defaults before custom)
        call_args = mock_create_agent.call_args
        middleware_passed = call_args[1]["middleware"]

        # Default middleware should be first
        self.assertEqual(middleware_passed[0], default_mw[0])
        # Followed by custom middleware
        self.assertEqual(middleware_passed[1], custom_mw[0])

    @patch("langchain.agents.create_agent")
    def test_middleware_uses_configured_checkpointer(self, mock_create_agent):
        """Test Middleware uses configured checkpointer instead of hardcoded False."""
        from src.components.deepagents.runtime_middlewares.subagents import (
            SubAgent,
            SubAgentMiddleware,
        )

        # Create SubAgent with checkpointer enabled
        subagent = SubAgent(
            name="test",
            description="Test subagent",
            system_prompt="Test prompt",
            checkpointer=True,
            model="test-model",
        )

        mock_create_agent.return_value = Mock()

        middleware = SubAgentMiddleware(
            default_model="default-model",
            default_tools=[],
            subagents=[subagent],
            default_middleware=[],
        )

        # Verify create_agent was called with checkpointer=True
        call_args = mock_create_agent.call_args
        checkpointer_passed = call_args[1]["checkpointer"]
        self.assertTrue(checkpointer_passed)

    @patch("langchain.agents.create_agent")
    def test_middleware_respects_checkpointer_false(self, mock_create_agent):
        """Test Middleware respects checkpointer=False configuration."""
        from src.components.deepagents.runtime_middlewares.subagents import (
            SubAgent,
            SubAgentMiddleware,
        )

        # Create SubAgent with checkpointer explicitly disabled
        subagent = SubAgent(
            name="test",
            description="Test subagent",
            system_prompt="Test prompt",
            checkpointer=False,
            model="test-model",
        )

        mock_create_agent.return_value = Mock()

        middleware = SubAgentMiddleware(
            default_model="default-model",
            default_tools=[],
            subagents=[subagent],
            default_middleware=[],
        )

        # Verify create_agent was called with checkpointer=False
        call_args = mock_create_agent.call_args
        checkpointer_passed = call_args[1]["checkpointer"]
        self.assertFalse(checkpointer_passed)

    @patch("langchain.agents.create_agent")
    def test_middleware_uses_default_tools_when_no_custom(self, mock_create_agent):
        """Test Middleware uses default tools when no custom tools configured."""
        from src.components.deepagents.runtime_middlewares.subagents import (
            SubAgent,
            SubAgentMiddleware,
        )

        # Create SubAgent without custom tools
        subagent = SubAgent(
            name="test",
            description="Test subagent",
            system_prompt="Test prompt",
            tools=[],  # Empty tools
            model="test-model",
        )

        # Create middleware with default tools
        default_tools = ["default_tool1", "default_tool2"]
        mock_create_agent.return_value = Mock()

        middleware = SubAgentMiddleware(
            default_model="default-model",
            default_tools=default_tools,
            subagents=[subagent],
            default_middleware=[],
        )

        # Verify create_agent was called with merged list (empty custom + defaults)
        call_args = mock_create_agent.call_args
        tools_passed = call_args[1]["tools"]
        # After fix: always merges, so empty list + default_tools = default_tools
        self.assertEqual(tools_passed, default_tools)

    @patch("langchain.agents.create_agent")
    def test_tools_merging_consistency(self, mock_create_agent):
        """Test tools merging is consistent regardless of custom tools presence."""
        from src.components.deepagents.runtime_middlewares.subagents import (
            SubAgent,
            SubAgentMiddleware,
        )

        default_tools = ["default1", "default2"]
        mock_create_agent.return_value = Mock()

        # Case 1: Empty custom tools
        subagent_empty = SubAgent(
            name="test1",
            description="Test subagent",
            system_prompt="Test prompt",
            tools=[],
            model="test-model",
        )

        middleware1 = SubAgentMiddleware(
            default_model="default-model",
            default_tools=default_tools,
            subagents=[subagent_empty],
            default_middleware=[],
        )

        call1 = mock_create_agent.call_args
        tools1 = call1[1]["tools"]

        # Case 2: With custom tools
        mock_create_agent.reset_mock()
        custom_tools = ["custom1"]
        subagent_custom = SubAgent(
            name="test2",
            description="Test subagent",
            system_prompt="Test prompt",
            tools=custom_tools,
            model="test-model",
        )

        middleware2 = SubAgentMiddleware(
            default_model="default-model",
            default_tools=default_tools,
            subagents=[subagent_custom],
            default_middleware=[],
        )

        call2 = mock_create_agent.call_args
        tools2 = call2[1]["tools"]

        # Both should be merged lists, not one copy and one merge
        # Case 1: [] + default_tools = default_tools
        self.assertEqual(tools1, default_tools)
        # Case 2: custom_tools + default_tools
        self.assertEqual(tools2, [*custom_tools, *default_tools])


class TestParameterFlowIntegration(unittest.TestCase):
    """Integration tests for complete parameter flow."""

    def test_complete_parameter_flow_from_config_to_runtime(self):
        """Test parameters flow correctly from config through all layers."""
        # This is an integration test that would require full setup
        # For now, we verify the structure is correct
        from src.components.deepagents.runtime_middlewares.subagents import SubAgent

        # Simulate config data
        config_data = {
            "name": "research",
            "description": "Research specialist",
            "agent_config": {
                "tools": ["search", "scrape"],
                "middleware": ["retry"],
                "checkpointer": False,
            },
            "display_config": {"streaming_enabled": False},
            "metadata": {"context_window": 128000},
        }

        # Create SubAgent as Factory would
        subagent = SubAgent(
            name=config_data["name"],
            description=config_data["description"],
            system_prompt="Test prompt",
            tools=config_data["agent_config"]["tools"],
            middleware=config_data["agent_config"]["middleware"],
            checkpointer=config_data["agent_config"]["checkpointer"],
            display_config=config_data["display_config"],
            metadata=config_data["metadata"],
        )

        # Verify all parameters preserved
        self.assertEqual(subagent.name, "research")
        self.assertEqual(subagent.tools, ["search", "scrape"])
        self.assertEqual(subagent.middleware, ["retry"])
        self.assertEqual(subagent.checkpointer, False)
        self.assertEqual(subagent.display_config["streaming_enabled"], False)
        self.assertEqual(subagent.metadata["context_window"], 128000)


if __name__ == "__main__":
    unittest.main()
