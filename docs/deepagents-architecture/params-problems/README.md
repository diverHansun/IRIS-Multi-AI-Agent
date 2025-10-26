# SubAgent Configuration Problems Documentation

This directory contains detailed analysis and solutions for configuration parameter flow issues in the DeepAgent SubAgent system.

## Documents

### [subagent-config-issues.md](./subagent-config-issues.md)
Comprehensive analysis of three critical issues preventing SubAgent configuration parameters from flowing correctly through the system:

1. **Incomplete Data Structure Design** - Missing fields in SubAgent dataclass
2. **Factory Layer Parameter Passing Interruption** - Configuration not passed from Factory to SubAgent spec
3. **Middleware Layer Hardcoded Logic** - Runtime ignores configuration and uses hardcoded defaults

## Quick Reference

### Problem Summary
- **Affected Configuration**: `config/agents/deep/models/subagents.json`
- **Configuration Sections with Issues**: `agent_config`, `display_config`, partial `metadata`
- **Working Sections**: `llm_config`, `runtime_limits`
- **Broken Parameters**: tools, middleware, checkpointer, display preferences
- **Impact**: 40% of SubAgent configuration parameters have no runtime effect

### Fix Locations
1. `src/components/deepagents/runtime_middlewares/__init__.py` - SubAgent dataclass
2. `src/agents/deepagents/factories/base.py` - _build_subagent_specs() method
3. `src/components/deepagents/runtime_middlewares/__init__.py` - _create_subagent_runnables() method

### Priority
- **P0 (Critical)**: Data structure and parameter passing fixes
- **P1 (High)**: Validation and logging
- **P2 (Medium)**: Documentation and testing

## Related Documentation

- [DeepAgents Architecture](../deepagents.md)
- [Configuration Guide](../../astream-building/configuration-guide.md)
- [Middleware Documentation](../middleware.md)

## Status

- **Analysis**: Complete
- **Fixes**: Pending implementation
- **Testing**: Not started
- **Documentation**: Complete


