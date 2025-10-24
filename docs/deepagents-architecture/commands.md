# DeepAgents Commands

## Overview

DeepAgents introduces new command-line interfaces to manage deep agent functionality, including mode switching, filesystem management, and configuration control.

## Command Structure

### Mode Commands

#### `/mode deep`
Switches to deep agent mode, enabling multi-agent capabilities with middleware support.

**Usage:**
```bash
/mode deep
```

**Response:**
```
Switched to deep agent mode. DeepAgents initialized with middleware support.
```

### Deep Agent Commands

#### `/deep status`
Displays current deep agent configuration and status.

**Usage:**
```bash
/deep status
```

**Response:**
```
Deep Agent Status:
- Mode: deep
- Middleware: filesystem, subagents
- Filesystem Mode: read-only
- Active Subagents: research, coding
```

#### `/deep filesystem <permission_mode>`
Controls filesystem middleware permission behavior.

**Permission Modes:**
- `read-only`: Only allows file reading operations (read_file, list_files, search_files)
- `ask-before-edit`: Prompts user before file modifications (includes write_file, edit_file, delete_file)
- `auto-edit`: Allows automatic file editing (high risk, all operations without confirmation)

**Usage:**
```bash
/deep filesystem read-only
/deep filesystem ask-before-edit
/deep filesystem auto-edit
```

**Response:**
```
Filesystem permission mode switched to: read-only
Available tools: read_file, list_files, search_files
Allowed paths: /workspace/, /data/, /tmp/
Security: Path validation enabled, max file size: 10MB
```

#### `/deep subagents <action>`
Manages subagent information and status.

**Actions:**
- `list`: List available subagent types
- `status`: Display current subagent status

**Usage:**
```bash
/deep subagents list
/deep subagents status
```

**Response:**
```
Available Subagents:
- research: Claude 4.5 Sonnet, GLM-4.6
- coding: Qwen3 Coder
- analysis: Claude 4.5 Sonnet

Active Subagents: 0/3
Max Concurrent: 3
```

#### `/deep middleware <action>`
Manages middleware status and configuration.

**Actions:**
- `status`: Display middleware status

**Usage:**
```bash
/deep middleware status
```

**Response:**
```
Middleware Status:
- filesystem: enabled (read-only mode)
- subagents: enabled (3 types available)
- patch_tool_calls: enabled
```

#### `/deep config <action>`
Manages deep agent configuration.

**Actions:**
- `show`: Display current configuration
- `reload`: Reload configuration from files

**Usage:**
```bash
/deep config show
/deep config reload
```

**Response:**
```
Configuration loaded from:
- config/agents/deep/models/providers.json
- config/agents/deep/middleware/filesystem.json
- config/agents/deep/middleware/subagents.json
```

## Implementation

### Command Registration

```python
# src/application/commands/deep/__init__.py
from .filesystem_commands import FilesystemModeCommand
from .config_commands import ConfigCommand

__all__ = [
    "FilesystemModeCommand",
    "ConfigCommand"
]
```

### Filesystem Mode Command

```python
# src/application/commands/deep/filesystem_commands.py
class FilesystemModeCommand(BaseCommand):
    def execute(self, mode: str):
        valid_modes = ["read-only", "ask-before-edit", "auto-edit"]
        if mode not in valid_modes:
            return CommandResult.error(f"Invalid mode: {mode}")
        
        # Update filesystem middleware configuration
        self._update_filesystem_mode(mode)
        return CommandResult.success(f"Filesystem mode: {mode}")
```

### Configuration Command

```python
# src/application/commands/deep/config_commands.py
class ConfigCommand(BaseCommand):
    def execute(self, action: str):
        if action == "show":
            return self._show_config()
        elif action == "reload":
            return self._reload_config()
        else:
            return CommandResult.error(f"Unknown action: {action}")
```

## Security Considerations

### Filesystem Access Control

- **Path Validation**: All file operations are restricted to configured allowed paths
- **Mode Enforcement**: Filesystem mode determines available operations
- **Size Limits**: File size restrictions prevent resource abuse

### Configuration Security

- **Validation**: All configuration changes are validated before application
- **Backup**: Configuration changes create backup before modification
- **Audit**: All configuration changes are logged for security auditing

## Error Handling

### Common Error Responses

```bash
# Invalid mode
/deep filesystem invalid-mode
Error: Invalid filesystem mode. Valid modes: read-only, ask-before-edit, auto-edit

# Configuration error
/deep config reload
Error: Failed to reload configuration. Check config files.

# Permission error
/deep filesystem auto-edit
Error: Auto-edit mode requires administrator privileges.
```

### Error Recovery

- **Fallback**: Invalid configurations fall back to safe defaults
- **Rollback**: Failed configuration changes are automatically rolled back
- **Logging**: All errors are logged for debugging and security analysis
