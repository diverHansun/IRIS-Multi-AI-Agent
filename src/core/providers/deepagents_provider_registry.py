"""
Provider registry dedicated to DeepAgents.

Manages main agent configurations with clear parameter categorization,
following the same pattern as SubAgentsProviderRegistry for consistency.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.core.config.loader import ConfigLoader, get_config_loader

logger = logging.getLogger(__name__)


class DeepAgentsProviderRegistry:
    """
    Expose DeepAgents provider, model, and middleware configuration.

    Responsibilities:
    - Load and manage main agent configurations from JSON
    - Categorize parameters (LLM, runtime, middleware, display, safety, metadata)
    - Provide clean, validated configuration for agent creation

    Following SOLID principles:
    - SRP: Only manages main agent configurations
    - OCP: Extendable without modifying existing code
    - DIP: Depends on configuration files, not concrete implementations
    """

    def __init__(
        self,
        base_path: Optional[str | Path] = "config/agents/deep",
        config_loader: Optional[ConfigLoader] = None,
    ) -> None:
        self.base_path = Path(base_path) if base_path else None
        self._config_loader: ConfigLoader = config_loader or get_config_loader()
        self._cache: Dict[Path, Dict[str, Any]] = {}
        self._providers: Dict[str, Any] = {}
        self._middleware_cache: Optional[Dict[str, Any]] = None
        self._models_cache: Optional[Dict[str, Any]] = None
        self.reload()

    def reload(self) -> None:
        """Reload configuration from disk."""
        self._cache.clear()
        providers = self._load_main_providers_config()
        self._providers = {key.lower(): value for key, value in providers.items()}
        self._middleware_cache = None
        self._models_cache = None
        logger.info(f"Loaded {len(self._providers)} provider configurations")

    def get_available_providers(self) -> List[str]:
        """Return list of configured provider identifiers."""
        return list(self._providers.keys())

    def list_providers(self) -> Dict[str, Any]:
        """Return raw provider configuration."""
        return self._providers

    def get_api_config(self, provider: str) -> Dict[str, Any]:
        """
        Get API configuration for a provider.

        Args:
            provider: Provider name (case-insensitive)

        Returns:
            Dictionary with base_url and api_key_env

        Raises:
            ValueError: If provider not found
        """
        provider_key = provider.lower()
        provider_cfg = self._providers.get(provider_key)
        if not provider_cfg:
            raise ValueError(
                f"Provider {provider} not found in deep agents configuration"
            )

        return provider_cfg.get("api_config", {})

    def get_llm_params(self, provider: str, model: str) -> Dict[str, Any]:
        """
        Get only LLM parameters for init_chat_model.

        Args:
            provider: Provider name
            model: Model name

        Returns:
            Dictionary with temperature, max_tokens, streaming, etc.

        Raises:
            ValueError: If provider or model not found
        """
        model_cfg = self._get_model_config(provider, model)
        llm_params = model_cfg.get("llm_params", {}).copy()

        # Add API config
        api_config = self.get_api_config(provider)
        if "base_url" in api_config:
            llm_params["base_url"] = api_config["base_url"]

        # Get API key from environment if configured
        if "api_key_env" in api_config:
            import os

            api_key = os.getenv(api_config["api_key_env"])
            if api_key:
                llm_params["api_key"] = api_key

        return llm_params

    def get_runtime_config(self, provider: str, model: str) -> Dict[str, Any]:
        """
        Get runtime configuration.

        Args:
            provider: Provider name
            model: Model name

        Returns:
            Dictionary with recursion_limit, step_timeout, stream_mode

        Raises:
            ValueError: If provider or model not found
        """
        model_cfg = self._get_model_config(provider, model)
        return model_cfg.get("runtime_config", {})

    def get_middleware_config_for_model(
        self, provider: str, model: str
    ) -> Dict[str, Any]:
        """
        Get middleware configuration for specific model.

        Args:
            provider: Provider name
            model: Model name

        Returns:
            Dictionary with middleware settings

        Raises:
            ValueError: If provider or model not found
        """
        model_cfg = self._get_model_config(provider, model)
        return model_cfg.get("middleware_config", {})

    def get_display_config(self, provider: str, model: str) -> Dict[str, Any]:
        """
        Get display configuration for streaming and logging.

        Args:
            provider: Provider name
            model: Model name

        Returns:
            Dictionary with display preferences

        Raises:
            ValueError: If provider or model not found
        """
        model_cfg = self._get_model_config(provider, model)
        return model_cfg.get("display_config", {})

    def get_safety_config(self, provider: str, model: str) -> Dict[str, Any]:
        """
        Get safety configuration including HITL settings.

        Args:
            provider: Provider name
            model: Model name

        Returns:
            Dictionary with safety settings and hitl_config

        Raises:
            ValueError: If provider or model not found
        """
        model_cfg = self._get_model_config(provider, model)
        return model_cfg.get("safety_config", {})

    def get_metadata(self, provider: str, model: str) -> Dict[str, Any]:
        """
        Get metadata (informational only).

        Args:
            provider: Provider name
            model: Model name

        Returns:
            Dictionary with context_window and other metadata

        Raises:
            ValueError: If provider or model not found
        """
        model_cfg = self._get_model_config(provider, model)
        return model_cfg.get("metadata", {})

    def get_complete_config(self, provider: str, model: str) -> Dict[str, Any]:
        """
        Get complete categorized configuration for a provider/model.

        This method returns all configuration in a structured format.

        Args:
            provider: Provider name
            model: Model name

        Returns:
            Dictionary with all categorized configuration

        Raises:
            ValueError: If provider or model not found
        """
        provider_key = provider.lower()
        provider_cfg = self._providers.get(provider_key)
        if not provider_cfg:
            raise ValueError(
                f"Provider {provider} not found in deep agents configuration"
            )

        model_cfg = self._get_model_config(provider, model)

        return {
            "provider": provider_key,
            "model": model,
            "description": provider_cfg.get("description", ""),
            "api_config": provider_cfg.get("api_config", {}),
            "llm_params": model_cfg.get("llm_params", {}),
            "runtime_config": model_cfg.get("runtime_config", {}),
            "middleware_config": model_cfg.get("middleware_config", {}),
            "display_config": model_cfg.get("display_config", {}),
            "safety_config": model_cfg.get("safety_config", {}),
            "metadata": model_cfg.get("metadata", {}),
        }

    def get_models_config(self) -> Dict[str, Any]:
        """
        Return configuration for subagent models.

        This is for backward compatibility.
        """
        if self._models_cache is None:
            self._models_cache = self._load_subagent_models_config()
        return self._models_cache

    def get_middleware_config(self) -> Dict[str, Any]:
        """
        Return global middleware configuration.

        This loads from separate middleware config files.
        """
        if self._middleware_cache is None:
            self._middleware_cache = self._load_middleware_config()
        return self._middleware_cache

    def _get_model_config(self, provider: str, model: str) -> Dict[str, Any]:
        """
        Get model configuration from provider.

        Args:
            provider: Provider name
            model: Model name

        Returns:
            Model configuration dictionary

        Raises:
            ValueError: If provider or model not found
        """
        provider_key = provider.lower()
        provider_cfg = self._providers.get(provider_key)
        if not provider_cfg:
            raise ValueError(
                f"Provider {provider} not found in deep agents configuration"
            )

        models_cfg = provider_cfg.get("models", {})
        model_cfg = models_cfg.get(model)
        if not model_cfg:
            raise ValueError(f"Model {model} not found for provider {provider}")

        return model_cfg

    def _load_main_providers_config(
        self, *, use_cache: bool = True
    ) -> Dict[str, Any]:
        """Load main providers configuration with fallback support."""
        # 先尝试 .iris（项目/用户）与内置 config
        config = self._config_loader.load_shared_json("agents/deep/mainagents.json")
        if config:
            return config

        # 回退到显式 base_path
        if self.base_path:
            return self._load_deep_json_from_base_path(
                canonical_name="mainagents.json",
                example_name="mainagents.example.json",
                use_cache=use_cache,
            )

        return {}

    def _load_subagent_models_config(
        self, *, use_cache: bool = True
    ) -> Dict[str, Any]:
        """Load subagent models configuration."""
        config = self._config_loader.load_shared_json("agents/deep/subagents.json")
        if config:
            return config

        if self.base_path:
            return self._load_deep_json_from_base_path(
                canonical_name="subagents.json",
                example_name="subagents.example.json",
                use_cache=use_cache,
            )
        return {}

    def _load_deep_json_from_base_path(
        self,
        *,
        canonical_name: str,
        example_name: str,
        use_cache: bool,
    ) -> Dict[str, Any]:
        """Load deep-agent config from canonical base path with legacy fallback."""
        assert self.base_path is not None

        candidates = [
            self.base_path / canonical_name,
            self.base_path / example_name,
            self.base_path / "models" / canonical_name,
            self.base_path / "models" / example_name,
        ]
        for candidate in candidates:
            if candidate.exists():
                return self._load_json(candidate, use_cache=use_cache)
        return {}

    def _load_middleware_config(self, *, use_cache: bool = True) -> Dict[str, Any]:
        """Load middleware configuration for filesystem, shell, and skills settings."""
        virtual_cfg: Dict[str, Any] = (
            self._config_loader.load_shared_json(
                "agents/deep/middleware/filesystem/virtual_filesystem.json"
            )
            or {}
        )
        real_cfg: Dict[str, Any] = (
            self._config_loader.load_shared_json(
                "agents/deep/middleware/filesystem/real_filesystem.json"
            )
            or {}
        )
        shell_cfg: Dict[str, Any] = (
            self._config_loader.load_shared_json("agents/deep/middleware/shell.json")
            or {}
        )
        skills_cfg: Dict[str, Any] = (
            self._config_loader.load_shared_json("agents/deep/middleware/skills/skills.json")
            or {}
        )

        if self.base_path:
            middleware_dir = self.base_path / "middleware"
            filesystem_dir = middleware_dir / "filesystem"

            virtual_path = filesystem_dir / "virtual_filesystem.json"
            real_path = filesystem_dir / "real_filesystem.json"
            legacy_path = middleware_dir / "filesystem.json"
            shell_path = middleware_dir / "shell.json"
            skills_path = middleware_dir / "skills" / "skills.json"

            if not virtual_cfg:
                if virtual_path.exists():
                    virtual_cfg = self._load_json(virtual_path, use_cache=use_cache)
                elif legacy_path.exists():
                    virtual_cfg = self._load_json(legacy_path, use_cache=use_cache)

            if not real_cfg and real_path.exists():
                real_cfg = self._load_json(real_path, use_cache=use_cache)

            if not shell_cfg and shell_path.exists():
                shell_cfg = self._load_json(shell_path, use_cache=use_cache)

            if not skills_cfg and skills_path.exists():
                skills_cfg = self._load_json(skills_path, use_cache=use_cache)

        return {
            "filesystem": {
                "virtual": virtual_cfg,
                "real": real_cfg,
            },
            "shell": shell_cfg,
            "skills": skills_cfg,
        }

    def _load_json(self, path: Path, *, use_cache: bool) -> Dict[str, Any]:
        """Load JSON file with optional caching."""
        if use_cache and path in self._cache:
            return self._cache[path]

        if not path.exists():
            logger.warning(f"Configuration file not found: {path}")
            return {}

        try:
            with path.open("r", encoding="utf-8") as stream:
                data = json.load(stream)
                if use_cache:
                    self._cache[path] = data
                return data
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from {path}: {e}")
            return {}
        except Exception as e:
            logger.error(f"Failed to load configuration from {path}: {e}")
            return {}
