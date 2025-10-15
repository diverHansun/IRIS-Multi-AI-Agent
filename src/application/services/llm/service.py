from __future__ import annotations

from typing import Any, Dict

from src.llm.managers import create_llm, get_llm_info, reload_llm_config

from src.application.services.base import BaseEngineService
from src.application.services.catalog import get_catalog_service
from src.application.services.llm.conversation import handle_llm_query
from src.application.services.llm.streaming import register_llm


class LLMService(BaseEngineService):
    @staticmethod
    def _config(ctx) -> Dict[str, Any]:
        return ctx.get_engine_config("llm")

    def _ensure_llm(self, ctx) -> Any:
        config = self._config(ctx)
        llm = config.get("llm_instance")
        provider = config.get("provider")
        model = config.get("model")
        if llm is None:
            llm = create_llm(provider, model, mode="llm")
            config["llm_instance"] = llm
            register_llm(provider, llm)
        return llm

    def _get_model_info(self, provider: str, model: str | None) -> Dict[str, Any]:
        info = get_llm_info(provider, model)
        return {
            "provider": info.get("provider", provider),
            "model": info.get("model", model),
            "name": info.get("model_name", info.get("name", info.get("model", model))),
            "description": info.get("description", ""),
        }

    async def initialize(self, ctx) -> Dict[str, Any]:
        config = self._config(ctx)
        config.setdefault("streaming", True)
        try:
            llm = self._ensure_llm(ctx)
        except Exception as exc:
            return {
                "type": "error",
                "message": f"Failed to initialize LLM engine: {exc}",
                "payload": {},
            }

        provider = config.get("provider")
        model = config.get("model")
        info = self._get_model_info(provider, model)

        return {
            "type": "success",
            "message": "LLM engine initialized.",
            "payload": {
                "agent": {
                    "provider": info.get("provider"),
                    "model": info.get("model"),
                    "name": info.get("name"),
                    "description": info.get("description"),
                },
                "mode": {
                    "mode": "llm",
                    "streaming": bool(config.get("streaming", True)),
                    "session_id": ctx.session_id,
                },
            },
        }

    async def handle_query(self, ctx, query: str) -> str:
        config = self._config(ctx)
        llm = self._ensure_llm(ctx)
        provider = config.get("provider", "unknown")
        streaming = bool(config.get("streaming", True))
        return await handle_llm_query(ctx, llm, provider, query, streaming=streaming)

    async def switch_model(self, ctx, provider: str, model: str | None = None) -> Dict[str, Any]:
        config = self._config(ctx)
        config["provider"] = provider
        if model is not None:
            config["model"] = model
        config["llm_instance"] = None
        try:
            llm = self._ensure_llm(ctx)
            info = self._get_model_info(provider, config.get("model"))
        except Exception as exc:
            return {
                "type": "error",
                "message": f"Failed to switch LLM: {exc}",
                "payload": {},
            }

        return {
            "type": "success",
            "message": f"Switched to {info.get('provider')} / {info.get('model')}",
            "payload": {
                "agent": {
                    "provider": info.get("provider"),
                    "model": info.get("model"),
                    "name": info.get("name"),
                    "description": info.get("description"),
                },
                "mode": {
                    "mode": "llm",
                    "streaming": bool(config.get("streaming", True)),
                    "session_id": ctx.session_id,
                },
            },
        }

    def get_info(self, ctx) -> Dict[str, Any]:
        config = self._config(ctx)
        provider = config.get("provider")
        model = config.get("model")
        info = {}
        try:
            info = self._get_model_info(provider, model)
        except Exception:
            info = {"provider": provider, "model": model}
        return {
            "agent": {
                "provider": info.get("provider", provider),
                "model": info.get("model", model),
                "name": info.get("name", info.get("model", model)),
                "description": info.get("description", ""),
            },
            "mode": {
                "mode": "llm",
                "streaming": bool(config.get("streaming", True)),
                "session_id": ctx.session_id,
            },
        }

    def reload_config(self) -> Dict[str, Any]:
        success = reload_llm_config()
        if success:
            return {"type": "success", "message": "LLM configuration reloaded.", "payload": {}}
        return {"type": "error", "message": "Failed to reload LLM configuration.", "payload": {}}

    async def list_catalog(self) -> Dict[str, Any]:
        catalog_service = get_catalog_service("llm")
        catalog = await catalog_service.get_catalog()
        if isinstance(catalog, dict) and "error" in catalog:
            return {
                "type": "error",
                "message": catalog.get("error", "Failed to load LLM catalog."),
                "payload": catalog,
            }
        return {
            "type": "success",
            "message": "",
            "payload": {"kind": "llm_catalog", "catalog": catalog},
        }

