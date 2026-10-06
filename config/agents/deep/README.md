# DeepAgents Config Layout

Canonical bundled deep-agent config paths now live directly under this folder:

- `mainagents.example.json`
- `subagents.example.json`
- `middleware/...`

Runtime and `.iris` override paths are also canonicalized to:

- `.iris/agents/deep/mainagents.json`
- `.iris/agents/deep/subagents.json`

The `models/` subdirectory is kept only as a legacy compatibility mirror during
the transition period. New code and docs should prefer the root-level paths in
this directory.

## Windows / macOS compatibility

Use `"shell_type": "auto"` in `middleware/shell.json` for portable defaults:

- Windows: `cmd.exe /Q`.
- macOS/Linux: `/bin/bash --norc --noprofile`.

The launching terminal (PowerShell on Windows or zsh on macOS) is independent of this persistent agent Shell. Prefer `workspace_root: "auto"` so it follows the current project. Custom absolute paths and `startup_commands` must match the host OS; copying configuration does not translate Windows commands into bash commands.

Rebuild `.venv` after moving to another OS. Existing user `.iris` files are preserved during initialization, so review old Shell settings when migrating. Installation steps and platform validation limits are documented in [IRIS_SETUP.md](../../../IRIS_SETUP.md#platform-reference).
