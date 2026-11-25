#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [[ "${1:-}" == "--serve-app" ]]; then
    echo "[run] Starting TCL Port Control Workbench locally at http://127.0.0.1:8000 ..."
    exec uv run uvicorn app:app --app-dir apps/port-control --host 127.0.0.1 --port 8000
fi

echo "[run] 1/5 Compiling LinkML DCSA domain models..."
uv run python -m tcl_compiler.compile_dcsa

echo "[run] 2/5 Linting all ODCS v3.1.0 contracts..."
for contract in contracts/odcs/*.odcs.yaml; do
    uv run datacontract lint "$contract"
done

echo "[run] 3/5 Compiling Apache Ossie semantic spine..."
uv run python -m tcl_compiler.compile_semantic

echo "[run] 4/5 Running ruff static checks..."
uv run ruff check .

echo "[run] 5/5 Running pytest verification suite..."
uv run pytest -v
