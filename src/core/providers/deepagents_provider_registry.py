"""Provider registry dedicated to DeepAgents."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional


class DeepAgentsProviderRegistry:
    """Expose DeepAgents provider, model, and middleware configuration."""

    def __init__(self, base_path: str | Path = "config/agents/deep") -> None:
        self.base_path = Path(base_path)
        self._cache: Dict[Path, Dict[str, Any]] = {}
        self._providers: Dict[str, Any] = {}
        self._middleware_cache: Optional[Dict[str, Any]] = None
        self._models_cache: Optional[Dict[str, Any]] = None
        self.reload()

    def reload(self) -> None:
        """Reload configuration from disk."""
        self._cache.clear()
        providers = self._load_main_providers_config()
        self._providers = {key.upper(): value for key, value in providers.items()}
        self._middleware_cache = None
        self._models_cache = None

    def get_available_providers(self) -> List[str]:
        """Return list of configured provider identifiers."""
        return list(self._providers.keys())

    def list_providers(self) -> Dict[str, Any]:
        """Return raw provider configuration."""
        return self._providers

    def get_deep_agent_config(self, provider: str, model: str) -> Dict[str, Any]:
        """Return merged configuration for a provider/model combination."""
        provider_key = provider.upper()
        provider_cfg = self._providers.get(provider_key)
        if not provider_cfg:
            raise ValueError(f"Provider {provider} not found in deep agents configuration")

        models_cfg = provider_cfg.get("models", {})
        model_cfg = models_cfg.get(model)
        if not model_cfg:
            raise ValueError(f"Model {model} not found for provider {provider}")

        base_fields = {
            key: value
            for key, value in provider_cfg.items()
            if key != "models"
        }
        merged = {**base_fields, **model_cfg}
        return merged

    def get_models_config(self) -> Dict[str, Any]:
        """Return configuration for subagent models."""
        if self._models_cache is None:
            self._models_cache = self._load_subagent_models_config()
        return self._models_cache

    def get_middleware_config(self) -> Dict[str, Any]:
        """Return middleware configuration."""
        if self._middleware_cache is None:
            self._middleware_cache = self._load_middleware_config()
        return self._middleware_cache

    def _load_main_providers_config(self, *, use_cache: bool = True) -> Dict[str, Any]:
        """Load main providers configuration with fallback support."""
        primary_path = self.base_path / "models" / "providers.json"
        fallback_path = self.base_path / "models" / "main_agent.json"
        if primary_path.exists():
            return self._load_json(primary_path, use_cache=use_cache)
        return self._load_json(fallback_path, use_cache=use_cache)

    def _load_subagent_models_config(self, *, use_cache: bool = True) -> Dict[str, Any]:
        """Load subagent models configuration."""
        return self._load_json(self.base_path / "models" / "subagents.json", use_cache=use_cache)

    def _load_middleware_config(self, *, use_cache: bool = True) -> Dict[str, Any]:
        """Load middleware configuration including filesystem and subagents settings."""
        filesystem_cfg = self._load_json(self.base_path / "middleware" / "filesystem.json", use_cache=use_cache)
        subagents_cfg = self._load_json(self.base_path / "middleware" / "subagents.json", use_cache=use_cache)
        return {
            "filesystem": filesystem_cfg,
            "subagents": subagents_cfg,
        }

    def _load_json(self, path: Path, *, use_cache: bool) -> Dict[str, Any]:
        """Load JSON file with optional caching."""
        if use_cache and path in self._cache:
            return self._cache[path]

        if not path.exists():
            return {}

        with path.open("r", encoding="utf-8") as stream:
            data = json.load(stream)
            if use_cache:
                self._cache[path] = data
            return data
