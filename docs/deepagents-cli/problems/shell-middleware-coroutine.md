# Shell Middleware Coroutine Error

## 1. Current Problem
- The custom ShellToolMiddleware returns the handler result directly in wrap_tool_call and reuses it from wrap_tool_call without awaiting, so async tool handlers bubble up as raw coroutines.
- When LangGraph resumes after HITL, those coroutine objects get written into state["messages"], and LangChain later raises ValueError: Unsupported message type: <class 'coroutine'> during streaming or checkpointing.

## 2. Optimization Ideas
- Refactor wrap_tool_call to be truly async: accept an awaitable handler, await non-shell tools, and run shell commands inside the async method before constructing a ToolMessage.
- Alternatively, drop the bespoke middleware and reuse the upstream wrapper so future LangChain fixes (timeouts, redaction, truncation flags) arrive automatically.
- Add a regression test that simulates a non-shell tool going through the middleware in async mode and asserts the return type is a ToolMessage, not a coroutine object.

## 3. Official Reference
- LangChain’s built-in ShellToolMiddleware (see .venv/Lib/site-packages/langchain/agents/middleware/shell_tool.py) awaits the handler in wrap_tool_call and manages session resources via _SessionResources.
- The official DeepAgents CLI wires ResumableShellToolMiddleware from deepagents.libs.deepagents.middleware.resumable_shell, which inherits the upstream behavior and recreates shell sessions safely after HITL pauses.
