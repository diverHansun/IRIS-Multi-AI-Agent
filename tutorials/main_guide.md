**Refactor Guide: CLI/GUI/Registry Modularization**

- Scope: Split an oversized `main.py` into focused components under `src/components`, consolidate command handling, default to English commands, and remove the `async_demo()` path.
- Objectives:
  - Reduce coupling and improve maintainability and testability.
  - Separate concerns: entrypoint vs. CLI routing vs. rendering vs. domain operations.
  - Keep behavior identical for existing commands while defaulting command syntax to English.

**Target Layout**
- `main.py`: Minimal entrypoint (environment prep + delegate to CLI run).
- `src/components/`
  - `cli.py`: Event loop + command router + AppState lifecycle.
  - `control.py`: General commands (mode switching, LLM switching, streaming toggle, info, llms).
  - `session_control.py`: Session commands (clear/new/sessions/restore/delete/cleanup).
  - `mcp_control.py`: MCP commands (`mcp status/tools/reload`).
  - `registry.py`: Provider/model catalog + validation (incl. dynamic Ollama discovery).
  - `gui.py`: Rich rendering (welcome/help/LLM list/info panels/sessions/MCP status).

**Module Responsibilities**
- `main.py`
  - Prepares environment (stdout encoding, `sys.path` for `src`, dotenv if needed).
  - Parses minimal CLI args (e.g., default run mode), then calls `src.components.cli.run()`.
  - Does not: manage event loop logic, command parsing, business logic, or rendering.

- `src/components/cli.py`
  - Owns the application loop: read input, parse command, call control handlers, send results to GUI.
  - Initializes `AppState` with: `console`, `agent`, `global_memory`, `session_manager`, `session_id`, `llm_mode` (default True), `streaming_enabled` (default True), optional `mcp_manager`.
  - Integrates streaming for LLM mode via existing `src/llm/streaming_llm.py`.
  - Centralizes error handling and graceful shutdown.
  - Router lives here (no extra file): maps commands to handlers from `control.py`, `session_control.py`, `mcp_control.py`.

- `src/components/control.py` (General Control)
  - General, non-session, non-MCP commands:
    - `help`: returns help payload (GUI renders); no printing inside control.
    - `info`: aggregates agent, mode, streaming state, model features.
    - `llms`: uses `registry.get_catalog()` to build provider/model list.
    - `switch <provider> [model]`: creates a new agent via `agent_factory.create_agent`, preserves memory continuity.
    - `mode llm|agent`: toggles `AppState.llm_mode`.
    - `stream on|off`: toggles `AppState.streaming_enabled` (only effective in LLM mode).
  - Returns structured results (see CommandResult) for GUI to render.

- `src/components/session_control.py`
  - Session commands (delegates to `SessionManager`/`GlobalMemoryManager`):
    - `clear`: clear current session memory content (keep files/index).
    - `new`: create new session and switch current `session_id`.
    - `sessions`: list historical sessions (with paging limit for display).
    - `restore <session_id>`: switch `AppState.session_id` and rehydrate context.
    - `delete_session <session_id>`: delete session files and index; update current session if needed.
    - `cleanup`: remove orphaned files and index entries.

- `src/components/mcp_control.py`
  - MCP integration commands (against `src/MCP/manager.py` GlobalMCPManager):
    - `mcp status [-v]`: status and optional verbose tool schema summary.
    - `mcp tools [--json]`: list MCP tools (prefixed names) or raw JSON.
    - `mcp reload`: reload `config/mcp.toml` and return summary.
  - Robust when MCP disabled or deps missing: return clear error in payload.

- `src/components/registry.py`
  - Catalog of providers/models with details and recommendations.
  - Pulls base data from `agent_factory.get_available_configurations()`.
  - Enhances Ollama provider with dynamic model discovery via `list_ollama_models()`.
  - Exposes helpers:
    - `get_catalog()`: full merged catalog for GUI consumption.
    - `validate(provider, model)`: validate requested switch; Ollama is permissive but cross-checks local availability if possible.
    - `resolve_default(provider)`: choose a default model if omitted (dynamic for Ollama if local models present).

- `src/components/gui.py`
  - Pure Rich-based rendering; no business logic or state mutation.
  - Renders:
    - `print_welcome()`, `print_help()` (default English commands).
    - `render_llms(catalog)`, `render_info(info, mode, streaming)`.
    - `render_sessions(list, total, note)`, `render_mcp_status(status)`, `render_mcp_tools(tools, json_flag)`.
  - Central place for text resources, future i18n hooks.

**Command Set (Default English)**
- General: `help`, `info`, `llms`, `switch <provider> [model]`, `mode llm|agent`, `stream on|off`.
- Sessions: `clear`, `new`, `sessions`, `restore <session_id>`, `delete_session <session_id>`, `cleanup`.
- MCP: `mcp status [-v]`, `mcp tools [--json]`, `mcp reload`.
- Notes:
  - Chinese aliases currently present in `main.py` will not be advertised; we may preserve them as hidden aliases for backward compatibility, but default docs and prompts use English.

**Key Data Structures**
- AppState (owned by CLI):
  - `console`: a Rich Console instance (single shared instance).
  - `agent`: current agent instance from `agent_factory`.
  - `global_memory`: `GlobalMemoryManager`.
  - `session_manager`: `SessionManager`.
  - `session_id`: current session id.
  - `llm_mode`: bool (True = LLM streaming chat, False = Agent with tools).
  - `streaming_enabled`: bool (effective only when `llm_mode` is True).
  - `mcp_manager`: optional, instance facade for GlobalMCPManager or None.

- CommandResult (returned by control modules):
  - `type`: one of `success`, `error`, `info`, `list`, `status`.
  - `message`: optional human-readable summary.
  - `payload`: structured data for GUI (dict/list of dicts) to render.
  - `meta`: optional extra (e.g., paging info, counts).

**What Moves Where (from main.py)**
- To `gui.py`:
  - `print_welcome()` -> `print_welcome()` (content updated to English by default).
  - `print_help()` -> `print_help()` (English; MCP help remains but revised).

- Split into `registry.py` + `gui.py`:
  - `print_available_llms()` -> `registry.get_catalog()` (data) + `gui.render_llms(catalog)` (render).

- To `control.py` (general):
  - `switch_llm(provider, model, global_memory)` -> `switch_llm(ctx, provider, model)` returning `CommandResult` with agent info and continuing session.
  - Mode/stream toggles -> `set_mode(ctx, 'llm'|'agent')`, `set_stream(ctx, 'on'|'off')`.
  - `info` -> `get_info(ctx)` aggregates agent info + mode/stream + features.

- To `session_control.py`:
  - `clear/new/sessions/restore/delete_session/cleanup` logic (wrapping `SessionManager` and `GlobalMemoryManager`).

- To `mcp_control.py`:
  - MCP: `status/tools/reload` (wrapping `GlobalMCPManager`).

- To `cli.py`:
  - The `cli_async()` loop: input reading, routing, and handing results to `gui.py`.
  - Router: tokenizes command lines, dispatches to appropriate control module.

- Removed:
  - `async_demo()` – delete function and any CLI switching branch for it.

- `main.py` after refactor:
  - Keep environment setup (stdout encoding, `sys.path` injection for `src`).
  - Replace branching with a single `asyncio.run(components.cli.run())` (single loop).

**Migration Steps**
1) Create `src/components/` and empty modules: `cli.py`, `control.py`, `session_control.py`, `mcp_control.py`, `registry.py`, `gui.py`.
2) Move welcome/help text to `gui.py`; convert command docs to English; keep content parity with current features.
3) Extract `print_available_llms()`:
   - Data logic -> `registry.get_catalog()` (merges `agent_factory.get_available_configurations()` with local Ollama discovery via `list_ollama_models()`).
   - Display logic -> `gui.render_llms(catalog)`.
4) Extract `switch_llm()` to `control.switch_llm(ctx, provider, model)`:
   - Calls `agent_factory.create_agent(...)` with `global_memory_manager=ctx.global_memory`.
   - Returns `CommandResult` including provider/model, tool_count, memory status.
5) Implement mode and stream toggles in `control.py` (`set_mode`, `set_stream`) that only mutate `AppState` and return `CommandResult`.
6) Implement `info` in `control.py`: aggregate `agent.get_info()` plus mode/streaming flags and any model special features.
7) Implement `session_control.py`: wrap `SessionManager` APIs for the six session commands; ensure results are structured for GUI to render.
8) Implement `mcp_control.py`: call `GlobalMCPManager.get_status/get_tools/reload_config` with defensive handling when MCP is disabled/missing dependencies.
9) Build `cli.py` main loop:
   - Initialize `AppState` (console/agent/memory/session/mode/stream flags; optionally lazy-init MCP if enabled).
   - On start: call `gui.print_welcome()` and show current mode summary.
   - Read input with `asyncio.to_thread(console.input, prompt)`.
   - Parse command tokens and dispatch to controls.
   - Route `CommandResult` to GUI rendering functions.
   - For LLM mode user queries: use `stream_llm_response()` from `src/llm/streaming_llm.py` with memory context and save back to memory.
10) Simplify `main.py` to delegate to `cli.run()`; remove `async_demo()` and any args branch that triggers it.
11) Sanity pass: update help text, ensure English examples, and remove explicit Chinese aliases from docs (optionally retain parsing support).

**Testing & Validation**
- Smoke test (manual):
  - Launch and verify welcome/help rendering.
  - `llms` shows providers and dynamic Ollama models with recommendations.
  - `switch openai gpt-4o-mini` (or `switch zhipu glm-4-plus`) switches agent and preserves memory.
  - `mode agent` then ask a tool-using query; `mode llm` and try streaming; `stream off` works only in LLM mode.
  - Session commands: `new`, `sessions`, `restore <id>`, `delete_session <id>`, `cleanup`.
  - MCP: `mcp status [-v]`, `mcp tools [--json]`, `mcp reload` behave sensibly whether enabled or not.

- Unit-level checks (lightweight):
  - `registry.get_catalog()` returns consistent structure given `agent_factory.get_available_configurations()`.
  - `control.validate` flows don’t print; return `CommandResult` with errors.
  - `cli` routing maps commands to correct handlers (can be tested by feeding tokens to a pure function).

- Non-functional:
  - Console encoding and Unicode safety (Windows) respected; streaming panel continues working.
  - No circular imports between components and `agents/llm/MCP`.

**Rollback Plan**
- All moves are localized; in case of issues, revert to previous `main.py` and remove `src/components/` additions.

**Risks & Mitigations**
- Risk: Circular imports.
  - Mitigation: `components/*` only depend on lower layers (`agents`, `llm`, `memory`, `MCP`); lower layers never import `components`.
- Risk: Streaming path double-renders.
  - Mitigation: Continue using current `stream_llm_response` for progress UI; GUI handles only summaries and non-stream panels.
- Risk: Ollama discovery latency/errors.
  - Mitigation: Catch exceptions and degrade gracefully with hints.

**Conventions**
- Commands default to English; keep code identifiers in English.
- Filenames: `registry.py` (not `register.py`) for catalog semantics and consistency with existing `registry` naming in `src/prompts`.
- Avoid printing in control/registry; only GUI prints.

**Acceptance Criteria**
- `main.py` ≤ ~50 lines and contains no command logic.
- All commands behave as before (minus Chinese docs), with English help and examples.
- New components are covered by a smoke test run and basic unit checks where feasible.

**Next Steps**
- Confirm this plan. If approved, implement in the order of “GUI/help → registry/llms → control/switch/mode/stream/info → session_control → mcp_control → CLI loop → main cleanup → tests and polish”.

