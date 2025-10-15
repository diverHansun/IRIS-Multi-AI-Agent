from __future__ import annotations

from typing import Any, Dict

from ..base import BaseEngineService


class AgentFlowService(BaseEngineService):
    async def initialize(self, ctx) -> Dict[str, Any]:
        return {"type": "info", "message": "AgentFlow initialization is not implemented.", "payload": {}}

    async def handle_query(self, ctx, query: str) -> str:
        raise NotImplementedError("AgentFlow query handling is not available yet.")

    async def switch_model(self, ctx, provider: str, model: str | None = None) -> Dict[str, Any]:
        return {"type": "error", "message": "AgentFlow model switching is not available yet.", "payload": {}}

    def get_info(self, ctx) -> Dict[str, Any]:
        return {"engine": "agentflow", "status": "pending"}
