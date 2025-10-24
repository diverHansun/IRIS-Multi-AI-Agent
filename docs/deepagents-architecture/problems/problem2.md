# Problem Report: Additional Deep Agent Bugs Found in Testing

## Issue Summary

Three additional critical bugs were discovered during user testing:

1. `/info` command displays basic mode configuration after switching to deep mode
2. 404 error due to duplicate `/chat/completions` path in API requests
3. SubAgents not showing in `/deep subagents` commands

## Problem Details

### Problem 1: /info Shows Basic Mode Configuration

**Symptom**:
```
After executing /mode deep and /info:
Provider: zhipu
Model: glm-4.5-flash  <- This is basic mode's model!
Tool Count: 0
Agent Type: deep
```

**Expected**:
```
Provider: ZHIPU
Model: glm-4.6  <- Should be deep mode's model
```

**Root Cause**:

In `src/application/commands/agent/mode_commands.py:41-42`, the code used `setdefault()` to set provider and model:

```python
config.setdefault("provider", "ZHIPU")
config.setdefault("model", "glm-4.6")
```

The problem: `setdefault()` only sets the value if the key doesn't exist. When switching from basic mode to deep mode, the config dictionary already has `provider` and `model` keys from basic mode (e.g., `zhipu` and `glm-4.5-flash`). Therefore, `setdefault()` does nothing and the old basic mode values remain.

**Solution**:

Change from `setdefault()` to direct assignment:

```python
config["provider"] = "ZHIPU"
config["model"] = "glm-4.6"
```

This ensures the deep mode defaults always override previous values.

**Files Modified**:
- `src/application/commands/agent/mode_commands.py:41-56`

---

### Problem 2: 404 Error - Duplicate Path in API URL

**Symptom**:
```
Deep Agent Error: Deep agent execution failed: Error code: 404 -
{'timestamp': '2025-10-24T13:53:18.367+00:00', 'status': 404,
'error': 'Not Found', 'path': '/v4/chat/completions/chat/completions'}
```

**Root Cause**:

The `base_url` in configuration files included the full endpoint path:

```json
{
  "ZHIPU": {
    "base_url": "https://open.bigmodel.cn/api/paas/v4/chat/completions"
  }
}
```

However, LangChain's `init_chat_model()` automatically appends `/chat/completions` to the base_url, resulting in:
```
https://open.bigmodel.cn/api/paas/v4/chat/completions/chat/completions
                                        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                                        Duplicated!
```

**Correct Pattern**:

The `base_url` should only include the API version, NOT the endpoint path:

```json
{
  "ZHIPU": {
    "base_url": "https://open.bigmodel.cn/api/paas/v4"
  }
}
```

LangChain will automatically append `/chat/completions` to create the full URL:
```
https://open.bigmodel.cn/api/paas/v4/chat/completions
```

**Solution**:

Remove `/chat/completions` suffix from all `base_url` configurations:

1. `config/agents/deep/models/providers.json`:
   - ZHIPU: `https://open.bigmodel.cn/api/paas/v4` (was: `.../v4/chat/completions`)
   - TONGYI: `https://dashscope.aliyuncs.com/compatible-mode/v1` (was: `.../v1/chat/completions`)

2. `config/agents/deep/models/subagents.json`:
   - Same changes for ZHIPU and TONGYI subagent configurations

**Files Modified**:
- `config/agents/deep/models/providers.json`
- `config/agents/deep/models/subagents.json`

---

## Impact Assessment

| Problem | Severity | Impact |
|---------|----------|--------|
| /info Shows Basic Config | High | Confusing UX - users cannot verify correct mode switch |
| 404 Duplicate Path Error | Critical | All deep agent queries fail with 404 |

## Root Cause Analysis

### Problem 1: setdefault() Misuse

The issue stems from misunderstanding `setdefault()` behavior:
- `setdefault(key, value)`: Only sets if key doesn't exist
- Direct assignment `config[key] = value`: Always sets, overriding existing values

When switching modes, we need to **override** previous config, not preserve it.

### Problem 2: base_url Confusion

The confusion arises from different API client patterns:
- **Raw HTTP clients**: Require full URL including endpoint path
- **LangChain clients**: Expect base URL only, append endpoint automatically

Our config followed the "raw HTTP" pattern, but LangChain's `init_chat_model()` expects the "base URL only" pattern.

**OpenAI-compatible API Standard**:
```
Base URL: https://api.example.com/v1
Endpoint: /chat/completions
Full URL: https://api.example.com/v1/chat/completions
```

---

### Problem 3: SubAgents Not Showing in Commands

**Symptom**:
```
agent:DEEP[S] > /deep subagents list
No subagents configured.

agent:DEEP[S] > /deep subagents status
Subagents Status:
- Active: none
```

**Expected**:
```
agent:DEEP[S] > /deep subagents list
Available Subagents:
- research
- coding
- analysis
```

**Root Cause**:

In `src/agents/deepagents/managers/subagent_manager.py:61,69`, the code incorrectly assumed `models_config` has a nested "subagents" key:

```python
# WRONG (Line 61)
def get_available_subagents(self):
    return self.models_config.get("subagents", {})  # Returns empty dict!

# WRONG (Line 69)
def _resolve_subagent_config(self, subagent_type: str):
    subagents = self.models_config.get("subagents", {})  # Returns empty dict!
    config = subagents.get(subagent_type)
```

However, `get_models_config()` directly returns the content of `subagents.json`:
```json
{
  "research": {...},
  "coding": {...},
  "analysis": {...}
}
```

There is NO "subagents" wrapper key, so `.get("subagents", {})` always returns `{}`.

**Solution**:

Remove the incorrect `.get("subagents", {})` call:

```python
# Line 59-63 (CORRECT)
def get_available_subagents(self):
    # models_config is already the subagents dict from subagents.json
    return self.models_config if self.models_config else {}

# Line 69-72 (CORRECT)
def _resolve_subagent_config(self, subagent_type: str):
    # models_config is already the subagents dict
    config = self.models_config.get(subagent_type)
    if not config:
        raise ValueError(f"Unknown subagent type: {subagent_type}")
```

**Files Modified**:
- `src/agents/deepagents/managers/subagent_manager.py`

**Impact**:
- `/deep subagents list` now correctly shows research, coding, analysis
- SubAgent LLM instances are created during agent initialization
- Main agent can delegate tasks to subagents via task tool

---

## Testing Checklist

After fixes:

- [ ] Switch from basic to deep mode: `/mode basic` → `/mode deep`
- [ ] Run `/info` and verify: `Model: glm-4.6` (not glm-4.5-flash)
- [ ] Send a query to deep agent
- [ ] Verify no 404 errors in response
- [ ] Check logs show correct URL: `.../v4/chat/completions` (not duplicated)
- [ ] Run `/deep subagents list` and verify shows: research, coding, analysis
- [ ] Run `/deep subagents status` and verify shows correct config

---

## Lessons Learned

1. **Always use direct assignment when overriding config between modes**
   - `setdefault()` is for initialization only
   - Mode switching requires explicit override

2. **Understand the API client's URL construction pattern**
   - LangChain clients auto-append endpoints
   - base_url should be version-level, not endpoint-level

3. **Test mode switching in both directions**
   - basic → deep
   - deep → basic
   - Ensure config is properly reset each time

---

**Document Version**: 1.1
**Date**: 2025-01-24
**Last Updated**: 2025-01-24
**Discovered By**: User Testing
**Status**: Fixed

**Related Documents**:
- `problem1.md` - Original four issues
- `problem1-fixes.md` - Implementation of original fixes
