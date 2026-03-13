# IRIS CLI – Quick Setup (Global Use)

This guide shows how to package and use the `iris` command globally, while keeping secrets safe and configuration simple.

## 1) Prerequisites
- Windows + PowerShell.
- Python 3.10+.
- `uv` installed (`pip install uv` or download from uv site).
- Project virtualenv ready at `.venv` (run `uv sync` in the project if not yet created).

## 2) Build & install the global tool
Run in the project root:
```powershell
.venv\Scripts\activate
uv tool uninstall iris-muti-ai-agent 2>$null
uv tool install --python .venv\Scripts\python.exe --editable --force --reinstall --refresh --no-cache .
```
Branding and package naming:
- Brand label: `IRIS:muti-ai-agent`
- Python package id: `iris-muti-ai-agent` (used by `uv tool`)

This packages the project (including bundled `config/`) and installs `iris` to your user tool path (e.g. `C:\Users\<you>\.local\bin\iris.exe`).

## 3) Initialize global config
First-run (or to reset):
```powershell
Remove-Item -Recurse -Force $env:USERPROFILE\.iris
iris
```
The first launch creates `C:\Users\<you>\.iris`, copies default configs, and prints a short guide.

## 4) Set API keys
```powershell
cd $env:USERPROFILE\.iris
Copy-Item .env.example .env -Force
notepad .env   # fill ZHIPU_API_KEY / OPENAI_API_KEY / ANTHROPIC_API_KEY, etc.
```
Keys placed here work for all directories. A project-specific `.env` (or `<project>/.iris/`) will override the global values when you run `iris` inside that project.

## 5) Update after code changes
Rebuild and reinstall the tool anytime you modify the project:
```powershell
uv tool install --python .venv\Scripts\python.exe --editable --force --reinstall --refresh --no-cache .
```

## 6) Verify
```powershell
where iris                     # should show ...\.local\bin\iris.exe
dir $env:USERPROFILE\.iris     # should contain config.toml, .env, llm/, agents/, tools/, sessions/
```

## 7) Config precedence (highest wins)
1. Current directory `.env`
2. Current project `.iris/` (if present)
3. Global `C:\Users\<you>\.iris`
4. Bundled defaults inside the packaged wheel

If `iris` reports missing configs or keys, ensure the relevant file exists in one of the higher-priority locations above.
