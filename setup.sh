#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "[setup] Syncing Python >=3.11 environment via uv..."
uv sync

echo "[setup] Verifying installed real tools..."
uv run datacontract --version
uv run ossie-databricks --help >/dev/null
echo "[setup] ossie-databricks CLI OK"
uv run ossie-microsoft --help >/dev/null
echo "[setup] ossie-microsoft CLI OK"
uv run python -c "from importlib.metadata import version; import linkml, linkml_runtime; print('[setup] linkml:', version('linkml'), 'linkml-runtime:', version('linkml-runtime'))"
echo "[setup] Setup complete."
