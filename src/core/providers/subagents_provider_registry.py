"""
Subagent Provider Registry for DeepAgents module.

Manages subagent configurations with clear parameter categorization following
the same pattern as BasicAgentsProviderRegistry for consistency.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.components.deepagents.prompts.registry import DeepAgentPromptRegistry

logger = logging.getLogger(__name__)


class SubAgentsProviderRegistry:
    """
    Provider registry for DeepAgent subagents.

    Responsibilities:
    - Load and manage subagent configurations from JSON
    - Categorize parameters (LLM, agent, runtime, display, metadata)
    - Integrate with prompt registry for system prompts
    - Provide clean, validated configuration for subagent creation

    Following SOLID principles:
    - SRP: Only manages subagent configurations
    - OCP: Extendable without modifying existing code
    - DIP: Depends on configuration files, not concrete implementations
    """

    def __init__(
        self,
        config_path: Optional[str] = None,
        prompt_registry: Optional[DeepAgentPromptRegistry] = None,
    ):
        """
        Initialize SubAgents provider registry.

        Args:
            config_path: Path to subagents configuration file.
                If None, uses default path.
            prompt_registry: Optional custom prompt registry instance.
                If None, creates default instance.
        """
        self._config_path = Path(
            config_path or "config/agents/deep/models/subagents.json"
        )
        self._prompt_registry = prompt_registry or DeepAgentPromptRegistry()
        self._configs: Dict[str, Dict[str, Any]] = {}
        self._load_from_config()

    def _load_from_config(self) -> None:
        """Load subagent configurations from JSON file."""
        try:
            with open(self._config_path, "r", encoding="utf-8") as f:
                config_data = json.load(f)

            self._configs = config_data
            logger.info(
                f"Loaded {len(self._configs)} subagent configurations from {self._config_path}"
            )

        except FileNotFoundError:
            logger.error(f"Configuration file not found: {self._config_path}")
            self._configs = {}
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse configuration file: {e}")
            self._configs = {}
        except Exception as e:
            logger.error(f"Failed to load subagent configurations: {e}")
            self._configs = {}

    def reload_config(self) -> bool:
        """
        Reload configuration from file.

        Returns:
            True if reload successful, False otherwise
        """
        logger.info("Reloading subagent configurations...")
        try:
            self._load_from_config()
            return True
        except Exception as e:
            logger.error(f"Failed to reload configurations: {e}")
            return False

    def get_available_subagents(self) -> List[str]:
        """
        Get list of available subagent types.

        Returns:
            List of subagent type names
        """
        return list(self._configs.keys())

    def get_subagent_config(
        self, subagent_type: str, **overrides: Any
    ) -> Dict[str, Any]:
        """
        Get complete subagent configuration with categorized parameters.

        Args:
            subagent_type: Type of subagent (research, coding, analysis)
            **overrides: Optional parameter overrides

        Returns:
            Dictionary with categorized configuration:
            {
                "name": str,
                "description": str,
                "system_prompt": str,
                "llm_config": {...},
                "agent_config": {...},
                "runtime_limits": {...},
                "display_config": {...},
                "metadata": {...}
            }

        Raises:
            ValueError: If subagent type is not found
        """
        if subagent_type not in self._configs:
            available = ", ".join(self._configs.keys())
            raise ValueError(
                f"Unknown subagent type: {subagent_type}. "
                f"Available types: {available}"
            )

        config = self._configs[subagent_type]

        # Load system prompt from prompt registry
        system_prompt = self._prompt_registry.get_subagent_prompt(subagent_type)

        # Build complete configuration
        result = {
            "name": config.get("name", subagent_type),
            "description": config.get("description", ""),
            "system_prompt": system_prompt,
            "llm_config": self._extract_llm_config(config),
            "agent_config": self._extract_agent_config(config),
            "runtime_limits": self._extract_runtime_limits(config),
            "display_config": self._extract_display_config(config),
            "metadata": self._extract_metadata(config),
        }

        # Apply overrides if provided
        if overrides:
            self._apply_overrides(result, overrides)

        logger.debug(
            f"Resolved subagent config for '{subagent_type}': "
            f"provider={result['llm_config']['provider']}, "
            f"model={result['llm_config']['model']}"
        )

        return result

    def _extract_llm_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract LLM configuration from subagent config.

        Returns:
            Dictionary with provider, model, api_config, and model_params
        """
        llm_cfg = config.get("llm_config", {})
        return {
            "provider": llm_cfg.get("provider", ""),
            "model": llm_cfg.get("model", ""),
            "api_config": llm_cfg.get("api_config", {}),
            "model_params": llm_cfg.get("model_params", {}),
        }

    def _extract_agent_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract agent configuration.

        Returns:
            Dictionary with tools, middleware, and checkpointer settings
        """
        agent_cfg = config.get("agent_config", {})
        return {
            "tools": agent_cfg.get("tools", []),
            "middleware": agent_cfg.get("middleware", []),
            "checkpointer": agent_cfg.get("checkpointer", False),
        }

    def _extract_runtime_limits(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract runtime limit configuration.

        Returns:
            Dictionary with max_execution_time and recursion_limit
        """
        limits = config.get("runtime_limits", {})
        return {
            "max_execution_time": limits.get("max_execution_time"),
            "recursion_limit": limits.get("recursion_limit"),
        }

    def _extract_display_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract display configuration for streaming and logging.

        Returns:
            Dictionary with streaming and display preferences
        """
        display = config.get("display_config", {})
        return {
            "streaming_enabled": display.get("streaming_enabled", False),
            "show_reasoning_steps": display.get("show_reasoning_steps", False),
            "show_tool_calls": display.get("show_tool_calls", False),
        }

    def _extract_metadata(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract metadata (informational only, not passed to API).

        Returns:
            Dictionary with context_window and other metadata
        """
        metadata = config.get("metadata", {})
        return {
            "context_window": metadata.get("context_window"),
            "supports_tools": metadata.get("supports_tools", True),
        }

    def _apply_overrides(self, result: Dict[str, Any], overrides: Dict[str, Any]) -> None:
        """
        Apply user-provided overrides to configuration.

        Args:
            result: Configuration dictionary to modify
            overrides: Override values
        """
        # Allow overriding model parameters
        if "temperature" in overrides:
            result["llm_config"]["model_params"]["temperature"] = overrides["temperature"]
        if "max_tokens" in overrides:
            result["llm_config"]["model_params"]["max_tokens"] = overrides["max_tokens"]

        # Allow overriding runtime limits
        if "max_execution_time" in overrides:
            result["runtime_limits"]["max_execution_time"] = overrides["max_execution_time"]
        if "recursion_limit" in overrides:
            result["runtime_limits"]["recursion_limit"] = overrides["recursion_limit"]

    def get_llm_params_only(self, subagent_type: str) -> Dict[str, Any]:
        """
        Get only LLM parameters suitable for init_chat_model.

        This method returns a clean parameter dict that can be safely
        passed to LangChain's init_chat_model function without causing
        400 errors from invalid parameters.

        Args:
            subagent_type: Type of subagent

        Returns:
            Dictionary with only valid LLM API parameters:
            {
                "temperature": float,
                "max_tokens": int,
                "streaming": bool,
                "base_url": str,
                "api_key": str (if available from env)
            }
        """
        config = self.get_subagent_config(subagent_type)
        llm_config = config["llm_config"]
        api_config = llm_config["api_config"]
        model_params = llm_config["model_params"]

        # Build clean parameters dict with only valid LLM params
        params = {}

        # Add model parameters (whitelist approach)
        if "temperature" in model_params:
            params["temperature"] = model_params["temperature"]
        if "max_tokens" in model_params:
            params["max_tokens"] = model_params["max_tokens"]
        if "streaming" in model_params:
            params["streaming"] = model_params["streaming"]
        if "top_p" in model_params:
            params["top_p"] = model_params["top_p"]
        if "timeout" in model_params:
            params["timeout"] = model_params["timeout"]

        # Add API connection parameters
        if "base_url" in api_config:
            params["base_url"] = api_config["base_url"]

        # Get API key from environment if configured
        if "api_key_env" in api_config:
            import os
            api_key = os.getenv(api_config["api_key_env"])
            if api_key:
                params["api_key"] = api_key

        return params

    def validate_subagent_type(self, subagent_type: str) -> bool:
        """
        Validate if subagent type exists.

        Args:
            subagent_type: Type of subagent

        Returns:
            True if subagent type exists, False otherwise
        """
        return subagent_type in self._configs

    def __repr__(self) -> str:
        return f"SubAgentsProviderRegistry(subagents={list(self._configs.keys())})"


# Global subagents registry instance
subagents_registry = SubAgentsProviderRegistry()
