#!/usr/bin/env bash
# macOS-only helper; Windows uses: uv sync --python 3.11 --locked
# Install this checkout in its own virtual environment and initialize user config.
set -euo pipefail

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "This script is for macOS. On other platforms, run uv sync --python 3.11 --locked." >&2
  exit 1
fi
if ! command -v uv >/dev/null 2>&1; then
  echo "uv is required. Install it with Homebrew: brew install uv" >&2
  exit 1
fi

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_dir"
uv sync --python 3.11 --locked

.venv/bin/python - <<'PY'
import os

from dotenv import dotenv_values
from src.core.config.initializer import ConfigInitializer

initializer = ConfigInitializer()
initializer.initialize(quiet=True)
if not initializer.is_initialized():
    raise SystemExit('IRIS configuration initialization failed')
env_path = initializer.share_dir / '.env'
if not env_path.exists():
    # A template is not a configured credential. Leave placeholder keys empty.
    values = dotenv_values(initializer.share_dir / '.env.example')
    with open(env_path, 'x', encoding='utf-8', opener=lambda path, flags: os.open(path, flags, 0o600)) as handle:
        for key, value in values.items():
            if value is None or value.startswith('your_'):
                value = ''
            handle.write(f'{key}={value}\n')
print(f'Configuration: {initializer.share_dir}')
print('Add your API key in .env or use the first-launch setup wizard.')
PY

printf '\nReady. Start from the project directory:\n  uv run --locked iris\n\nOr activate the virtual environment:\n  source .venv/bin/activate\n  iris\n'
