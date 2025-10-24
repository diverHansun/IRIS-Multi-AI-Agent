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

#### `/deep filesystem <mode>`
Controls filesystem middleware behavior.

**Modes:**
- `read-only`: Only allows file reading operations
- `ask-before-edit`: Prompts user before file modifications
- `auto-edit`: Allows automatic file editing (high risk)

**Usage:**
```bash
/deep filesystem read-only
/deep filesystem ask-before-edit
/deep filesystem auto-edit
```

**Response:**
```
Filesystem mode switched to: read-only
Allowed paths: /workspace/, /data/, /tmp/
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
- config/agents/deep/middleware/filesystem.json
- config/agents/deep/middleware/subagents.json
- config/agents/deep/models/subagents.json
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
