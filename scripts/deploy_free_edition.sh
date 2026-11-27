#!/usr/bin/env bash
set -euo pipefail

# One-command Databricks Free Edition deployer for Tasman Container Line (TCL).
# Works for any user with an authenticated Databricks CLI (v1.3.0+) and a Serverless SQL Warehouse.
#
# Usage:
#   ./scripts/deploy_free_edition.sh [--profile <name>] [--warehouse-id <id>] [--catalog <name>] [--deploy-app]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "$REPO_ROOT"

PROFILE=""
WAREHOUSE_ID=""
CATALOG="workspace"
DEPLOY_APP="false"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --profile)
            PROFILE="${2:?--profile requires a value}"
            shift 2
            ;;
        --warehouse-id)
            WAREHOUSE_ID="${2:?--warehouse-id requires a value}"
            shift 2
            ;;
        --catalog)
            CATALOG="${2:?--catalog requires a value}"
            shift 2
            ;;
        --deploy-app)
            DEPLOY_APP="true"
            shift
            ;;
        -h|--help)
            sed -n '3,8p' "$0"
            exit 0
            ;;
        *)
            echo "[deploy] Unknown argument: $1" >&2
            exit 2
            ;;
    esac
done

if ! command -v databricks >/dev/null 2>&1; then
    echo "[deploy] ERROR: Databricks CLI (>= 1.3.0) not found." >&2
    echo "[deploy] Install: curl -fsSL https://raw.githubusercontent.com/databricks/setup-cli/main/install.sh | sh" >&2
    exit 1
fi

PROFILE_ARGS=()
if [[ -n "$PROFILE" ]]; then
    PROFILE_ARGS=(--profile "$PROFILE")
fi

echo "[deploy] 1/5 Verifying Databricks CLI authentication..."
USER_JSON="$(databricks "${PROFILE_ARGS[@]}" current-user me --output json)"
DBX_USER="$(python3 -c 'import json,sys; print(json.load(sys.stdin).get("userName",""))' <<< "$USER_JSON")"
if [[ -z "$DBX_USER" ]]; then
    echo "[deploy] ERROR: Could not resolve current Databricks user. Run: databricks auth login --host https://<your-workspace>" >&2
    exit 1
fi
echo "[deploy] Authenticated cleanly."

if [[ -z "$WAREHOUSE_ID" ]]; then
    echo "[deploy] Auto-detecting Serverless SQL Warehouse..."
    WH_JSON="$(databricks "${PROFILE_ARGS[@]}" warehouses list --output json)"
    WAREHOUSE_ID="$(python3 -c '
import json, sys
whs = json.load(sys.stdin)
serverless = [w for w in whs if w.get("enable_serverless_compute")]
chosen = serverless[0] if serverless else (whs[0] if whs else None)
print(chosen["id"] if chosen else "")
' <<< "$WH_JSON")"
    if [[ -z "$WAREHOUSE_ID" ]]; then
        echo "[deploy] ERROR: No SQL Warehouse found. Pass --warehouse-id <id> explicitly." >&2
        exit 1
    fi
fi
echo "[deploy] Target catalog: ${CATALOG} | SQL Warehouse detected."

echo "[deploy] 2/5 Validating Databricks Declarative Automation Bundle (dev)..."
databricks "${PROFILE_ARGS[@]}" bundle validate -t dev \
    --var="catalog=${CATALOG}" \
    --var="warehouse_id=${WAREHOUSE_ID}"

echo "[deploy] 3/5 Deploying bundle to Databricks Free Edition..."
# Note: On a brand-new workspace where gold_dcsa Metric Views do not exist yet,
# Genie Space creation can fail until the first orchestrator run populates gold_dcsa.
if ! databricks "${PROFILE_ARGS[@]}" bundle deploy -t dev \
    --var="catalog=${CATALOG}" \
    --var="warehouse_id=${WAREHOUSE_ID}"; then
    echo "[deploy] First-time workspace bootstrap detected (gold_dcsa Metric Views not yet materialized)."
    echo "[deploy] Temporarily deferring Genie Space resource until after the initial orchestrator run..."
    TMP_GENIE="$(mktemp)"
    mv resources/genie_spaces.yml "$TMP_GENIE"
    trap 'mv -f "$TMP_GENIE" resources/genie_spaces.yml 2>/dev/null || true' EXIT
    databricks "${PROFILE_ARGS[@]}" bundle deploy -t dev \
        --var="catalog=${CATALOG}" \
        --var="warehouse_id=${WAREHOUSE_ID}"
    databricks "${PROFILE_ARGS[@]}" bundle run -t dev \
        --var="catalog=${CATALOG}" \
        --var="warehouse_id=${WAREHOUSE_ID}" \
        tcl_dcsa_e2e_orchestrator
    mv -f "$TMP_GENIE" resources/genie_spaces.yml
    trap - EXIT
    echo "[deploy] Re-deploying full bundle including Genie Space now that gold_dcsa exists..."
    databricks "${PROFILE_ARGS[@]}" bundle deploy -t dev \
        --var="catalog=${CATALOG}" \
        --var="warehouse_id=${WAREHOUSE_ID}"
else
    echo "[deploy] 4/5 Running 5-task tcl_dcsa_e2e_orchestrator job..."
    databricks "${PROFILE_ARGS[@]}" bundle run -t dev \
        --var="catalog=${CATALOG}" \
        --var="warehouse_id=${WAREHOUSE_ID}" \
        tcl_dcsa_e2e_orchestrator
fi

if [[ "$DEPLOY_APP" == "true" ]]; then
    echo "[deploy] 5/5 Starting and deploying tcl-port-control Databricks App..."
    databricks "${PROFILE_ARGS[@]}" apps start tcl-port-control >/dev/null 2>&1 || true
    APP_SRC="/Workspace/Users/${DBX_USER}/.bundle/tcl-dcsa-lakehouse/dev/files/apps/port-control"
    databricks "${PROFILE_ARGS[@]}" apps deploy tcl-port-control --source-code-path "$APP_SRC"
    echo "[deploy] App deployed cleanly. Check status with: databricks apps get tcl-port-control"
else
    echo "[deploy] 5/5 Skipping Databricks App deploy (re-run with --deploy-app to start tcl-port-control)."
fi

echo "[deploy] Done! Run the SQL checks in docs/DEPLOYMENT_GUIDE.md to inspect live UC Metric Views & contract audit results."
