"""
LLM Utilities

Provides general LLM-related utility functions and tools.

Note: Provider-specific utilities are now in src.llm.langchain.providers
"""

# Streaming output for LLM direct chat
# IMPORTANT: These are for LLM chat ONLY, NOT for Agent tool calling
# Agents should use non-streaming methods (agent.ainvoke) to get complete responses
from .streaming import (
    StreamingLLM,
    StreamingCallbackHandler,
    StreamingManager,
    stream_llm_response,  # LLM chat only - decorated with @for_llm_only
)

__all__ = [
    # Streaming output (LLM direct chat only)
    "StreamingLLM",
    "StreamingCallbackHandler",
    "StreamingManager",
    "stream_llm_response",
]
