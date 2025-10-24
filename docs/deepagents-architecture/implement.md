## DeepAgents Implementation Plan

### 1. Repository Structure & Scaffolding
- Mirror the documented layout under `src/agents/deepagents/` (managers, factories, adapters, instances, middleware helpers).
- Add configuration loaders under `src/core/providers/` and related JSON resources in `config/agents/deep/`.
- Introduce prompt registry and templates in `src/components/deepagents/prompts/`.

### 2. Configuration & Provider Integration
- Extend the provider registry with built-in JSON loading to expose deep agent models and middleware configs.
- Provide manual reload commands aligned with existing `/mcp` configuration handling.
- Validate JSON payloads and enforce defaults (filesystem permissions, subagent limits).

### 3. Factories, Adapters, and Instances
- Create base classes plus concrete research, coding, and analysis variants.
- Ensure adapters pull prompts, assemble middleware settings, and expose capability metadata.
- Implement base deep agent instance with shared behaviors (info reporting, middleware hooks).

### 4. Manager & Subagent Orchestration
- Build `DeepAgentManager` to compose provider configs, adapters, middleware, and factories.
- Add `SubAgentManager` for subagent lifecycle, using basic agent manager for spawning.
- Integrate middleware initialization (filesystem, subagents, patch tool calls) during agent creation.

### 5. Service Layer & Commands
- Add deep agent service package (engine initialization, lifecycle, conversation handlers, middleware services).
- Register deep service in application router.
- Implement CLI commands for mode switching, filesystem permissions, middleware status, and config reload.

### 6. Testing Strategy
- Author import smoke tests for new packages.
- Write pytest suites covering configuration loading, manager creation, middleware permission logic, and command handlers.

### 7. Documentation & Follow-up
- Update docs to reference new configuration files, command usage, and workflow.
- Review filesystem defaults and subagent limits after initial integration to confirm safety and usability.
