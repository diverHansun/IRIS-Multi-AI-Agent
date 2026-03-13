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
