# SubAgents Debug Implementation Summary

## Overview
Implemented comprehensive debugging logging across 7 critical points in the SubAgents execution flow to enable rapid diagnosis of issues when using the task tool in Deep Agent mode.

## Implementation Date
2025-10-27

## Files Modified

### 1. Main Loop Error Handling
**File**: `src/application/cli/main.py`

**Changes**: Lines 132-144
- Added full exception type display
- Added detailed error logging with `exc_info=True`
- Added conditional debug mode traceback display
- Now shows: exception type, message, and full stack trace in debug mode

**What it reveals**:
- Complete exception information instead of just the message
- Full stack trace for debugging
- Exception type to quickly identify error category

---

### 2. Subagent Creation Stage
**File**: `src/components/deepagents/runtime_middlewares/__init__.py`

**Changes**: Lines 162-252
- Added logging at the start of subagent creation process
- Added per-subagent creation logging
- Added detailed configuration logging (model, tools, middleware)
- Added success/failure logging for each subagent
- Added comprehensive exception handling with `exc_info=True`

**Log Markers**:
- `[SubAgent Init] Starting subagent creation process`
- `[SubAgent Init] Creating subagent: {name}`
- `[SubAgent Init] {name} - Model: {model}`
- `[SubAgent Init] {name} - Created successfully`
- `[SubAgent Init] Failed to create subagent`

**What it reveals**:
- Whether subagents are created at all
- Which subagent fails during creation
- Configuration details (tools, middleware, timeouts)
- Exact point of failure in creation pipeline

---

### 3. Task Tool Creation
**File**: `src/components/deepagents/runtime.py`

**Changes**:
- Added logging import (line 5, 10)
- Lines 108-119: Enhanced task tool creation logging

**Log Markers**:
- `[Runtime] Task tool created successfully with {count} subagents`
- `[Runtime] Available subagent types: {types}`
- `[Runtime] Task tool added to tools list. Total tools: {count}`
- `[Runtime] No task tool created - no subagents available`

**What it reveals**:
- Whether task tool was created
- How many subagents are available
- Which subagent types can be called
- Total number of tools available to main agent

---

### 4. Subagent Invocation Entry (Part of Point 5)
**File**: `src/components/deepagents/runtime_middlewares/__init__.py`

**Changes**: Lines 264-267
- Added detailed invocation entry logging
- Added validation logging
- Added available subagents list logging

**Log Markers**:
- `[SubAgent Call] Received task delegation - Type: {type}`
- `[SubAgent Call] Task description: {description}`
- `[SubAgent Call] Available subagents: {list}`
- `[SubAgent Call] Unknown subagent type`

**What it reveals**:
- Which subagent type main agent is trying to call
- Whether the subagent type exists
- Task description being passed
- Validation failures

---

### 5. Subagent Execution Stage
**File**: `src/components/deepagents/runtime_middlewares/__init__.py`

**Changes**: Lines 254-314
- Added execution start/end timing
- Added input format logging
- Added result structure logging
- Added response preview logging
- Separated TimeoutError from general exceptions
- Added detailed exception logging with timing

**Log Markers**:
- `[SubAgent Exec] Starting '{type}' execution`
- `[SubAgent Exec] Input message type: {type}`
- `[SubAgent Exec] '{type}' completed in {elapsed}s`
- `[SubAgent Exec] Result type: {type}`
- `[SubAgent Exec] Response length: {length} characters`
- `[SubAgent Exec] Response preview: {preview}`
- `[SubAgent Exec] {type}' timed out after {elapsed}s`
- `[SubAgent Exec] '{type}' failed after {elapsed}s`

**What it reveals**:
- Exact execution timing
- Input/output data structures
- Whether subagent completed or failed
- Type of failure (timeout vs error)
- Response content preview
- Full exception details with stack trace

---

### 6. Event Handler Task Tracking
**File**: `src/application/services/agent/deep/event_handler.py`

**Changes**:
- Added logging import (line 5, 15)
- Lines 154-161: Enhanced task tool call detection

**Log Markers**:
- `[EventHandler] Detected task tool call - ID: {id}`
- `[EventHandler] Task tool args - subagent_type: {type}`

**What it reveals**:
- When main agent calls task tool
- Tool call ID for correlation
- Which subagent type is being requested
- Correlation between tool call and execution

---

### 7. Timeout Detection
**File**: `src/application/services/agent/deep/conversation.py`

**Changes**:
- Added logging import (line 5, 18)
- Lines 107-115: Enhanced timeout detection logging
- Lines 116-119: Added recursion error logging
- Lines 132-138: Enhanced timeout message logging

**Log Markers**:
- `[Conversation] Execution timed out after {elapsed}s (limit: {max}s)`
- `[Conversation] Last event at timeout: {keys}`
- `[Conversation] Recursion limit exceeded`
- `[Conversation] Deep agent execution timed out`

**What it reveals**:
- Exact timeout timing
- What was happening when timeout occurred
- Whether timeout was due to time limit or recursion limit
- Last event being processed

---

## Logging Hierarchy

All logs use hierarchical prefixes for easy filtering:

```
[SubAgent Init]  - Subagent creation phase
[Runtime]        - Runtime setup and tool registration
[SubAgent Call]  - Subagent invocation entry point
[SubAgent Exec]  - Subagent execution details
[EventHandler]   - Event stream processing
[Conversation]   - Conversation-level control flow
```

## Log Filtering Commands

### View all SubAgent logs
```bash
grep "\[SubAgent" logs/app.log
```

### View only errors
```bash
grep "ERROR" logs/app.log | grep -i "subagent"
```

### View execution timing
```bash
grep "completed in" logs/app.log
```

### View specific subagent
```bash
grep "research" logs/app.log | grep "\[SubAgent"
```

### View full flow for a session
```bash
grep -E "\[(SubAgent|Runtime|EventHandler|Conversation)\]" logs/app.log
```

## Expected Log Flow (Successful Case)

```
1. [SubAgent Init] Starting subagent creation process
2. [SubAgent Init] Creating subagent: research
3. [SubAgent Init] research - Created successfully
4. [Runtime] Task tool created successfully with 3 subagents
5. [Runtime] Available subagent types: ['research', 'coding', 'analysis']
6. [EventHandler] Detected task tool call - ID: call_xxx
7. [SubAgent Call] Received task delegation - Type: research
8. [SubAgent Exec] Starting 'research' execution
9. [SubAgent Exec] 'research' completed in 5.23s
10. [SubAgent Exec] Response length: 1234 characters
```

## Expected Log Flow (Error Case)

### Case 1: Subagent Creation Failure
```
1. [SubAgent Init] Starting subagent creation process
2. [SubAgent Init] Creating subagent: research
3. ERROR - [SubAgent Init] Failed to create subagent 'research': ModelNotFoundError
   (Full stack trace follows)
```

### Case 2: API Call Failure
```
1. [SubAgent Call] Received task delegation - Type: research
2. [SubAgent Exec] Starting 'research' execution
3. ERROR - [SubAgent Exec] 'research' failed after 0.15s: APIConnectionError
   (Full stack trace follows)
```

### Case 3: Timeout
```
1. [SubAgent Exec] Starting 'research' execution
2. ERROR - [Conversation] Execution timed out after 300.00s (limit: 300s)
3. [Conversation] Deep agent execution timed out
```

## Debugging Workflow

### Step 1: Check if subagents were created
```bash
grep "\[SubAgent Init\]" logs/app.log | tail -20
```

Expected: See "Created successfully" for all subagents

### Step 2: Check if task tool was created
```bash
grep "\[Runtime\] Task tool" logs/app.log | tail -5
```

Expected: "Task tool created successfully with N subagents"

### Step 3: Check if task tool was called
```bash
grep "\[EventHandler\] Detected task tool" logs/app.log | tail -10
```

Expected: See task tool call with ID

### Step 4: Check subagent execution
```bash
grep "\[SubAgent Exec\]" logs/app.log | tail -20
```

Expected: See "Starting", then "completed in Xs" or error message

### Step 5: Check for errors
```bash
grep "ERROR" logs/app.log | grep -E "\[SubAgent|\[Runtime|\[Conversation\]" | tail -20
```

## Common Issues and Their Log Signatures

### Issue: "Conversation error" without details
**Old behavior**: Only shows "Conversation error: {message}"
**New behavior**: Shows "Conversation error ({ExceptionType}): {message}" + full stack trace in logs

### Issue: Subagent never responds
**Look for**:
- `[SubAgent Exec] Starting` but no `completed`
- May show timeout or exception in logs

### Issue: Wrong subagent type
**Look for**:
- `[SubAgent Call] Unknown subagent type`
- Check available types in `[Runtime] Available subagent types`

### Issue: API authentication failure
**Look for**:
- `[SubAgent Exec] failed after` with API-related exception
- Check model configuration in `[SubAgent Init]` logs

### Issue: Timeout
**Look for**:
- `[Conversation] Execution timed out after`
- Check what was happening: `[Conversation] Last event at timeout`

## Testing the Debug Implementation

### Test 1: Trigger a known error
```python
# In your query, request a non-existent subagent type
"Use the 'nonexistent' subagent to analyze this"
```

Expected logs:
```
[SubAgent Call] Unknown subagent type 'nonexistent'
```

### Test 2: Check normal flow
```python
# Request a valid subagent
"Use the research subagent to find information about AI"
```

Expected logs: Full flow from Init to Exec completed

### Test 3: Check error details
Temporarily misconfigure API key and observe:
```
ERROR - [SubAgent Exec] 'research' failed after X.XXs: AuthenticationError
```

## Notes

- All logging uses standard Python `logging` module
- Log level: INFO for major events, DEBUG for details, ERROR for failures
- All exceptions log with `exc_info=True` for full stack traces
- Timing information included in all execution logs
- No emojis used in log messages (professional format)
- All log messages use English

## Maintenance

When modifying the subagents system:
1. Add logging at entry/exit points of new functions
2. Use the established prefixes for consistency
3. Include timing information for async operations
4. Log both success and failure cases
5. Use appropriate log levels (INFO/DEBUG/ERROR)
