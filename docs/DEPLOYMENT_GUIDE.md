# Deployment &amp; Operations Guide

This guide covers running **Tasman Container Line (TCL)** across four modes: **Local Offline**, **Databricks Free Edition**, **GitHub Actions CI/CD**, and **Enterprise Azure Databricks + Azure DevOps**.

---

## 1. Prerequisites

| Tool | Minimum Version | Purpose |
| :--- | :--- | :--- |
| **Python** | `3.11+` (tested on `3.12`) | LinkML &amp; Apache Ossie compilers, FastAPI workbench, pytest |
| **[`uv`](https://docs.astral.sh/uv/)** | `0.9+` | Deterministic dependency &amp; virtual environment management |
| **Databricks CLI** | `1.3.0+` (tested on `1.20.0`) | `engine: direct` DABs validation, deployment, and orchestration (live mode only) |
| **GitHub CLI (`gh`)** | Optional | Inspecting Actions CI runs or managing secrets |

---

## 2. Mode A — Local Offline Verification &amp; Demo Workbench (2 Minutes)

No Databricks account or cloud credentials are required:

```bash
# Bootstrap locked virtual environment (includes real LinkML, datacontract-cli, and apache/ossie-converters)
./setup.sh

# Run full offline compiler + contract lint + ruff + pytest gate
./run.sh

# Optional: inspect deterministic 4-source DCSA synthetic data locally
uv run python -m generators.dcsa_synthetic_generator --output-dir data/sample_landing

# Launch the TCL Port Control FastAPI Workbench in deterministic demo mode
./run.sh --serve-app
# Visit http://127.0.0.1:8000
```

---

## 3. Mode B — Live Databricks Free Edition Deployment (`dev` Target)

### Step 1: Authenticate Databricks CLI (OAuth Recommended)

```bash
databricks auth login --host https://<YOUR-WORKSPACE>.cloud.databricks.com
databricks auth profiles
```

Find your Serverless SQL Warehouse ID:

```bash
databricks warehouses list --output json
```

### Step 2: Validate &amp; Deploy the DABs Bundle

Pass your Serverless SQL Warehouse ID strictly via runtime `--var` (never hardcode it in `databricks.yml`):

```bash
export WAREHOUSE_ID="<YOUR_SERVERLESS_WAREHOUSE_ID>"

databricks bundle validate -t dev --var="warehouse_id=${WAREHOUSE_ID}"
databricks bundle deploy -t dev --var="warehouse_id=${WAREHOUSE_ID}"
```

This provisions:
- 1 Serverless Lakeflow Declarative Pipeline (`dcsa_medallion_pipeline`)
- 2 Serverless Jobs (`tcl_dcsa_e2e_orchestrator` and `tcl_contract_quality_gate`)
- 1 AI/BI Genie Space (`tcl_ops_genie`, via `bundle.engine: direct`)
- 1 Databricks Native App shell (`tcl-port-control`)

### Step 3: Run the 5-Task End-to-End Orchestrator Job

```bash
databricks bundle run -t dev --var="warehouse_id=${WAREHOUSE_ID}" tcl_dcsa_e2e_orchestrator
```

The orchestrator executes sequentially:
1. `bootstrap_uc_objects` → creates `bronze_dcsa`, `silver_dcsa`, `gold_dcsa`, `governance_dcsa`, 4 UC Volumes, and audit Delta tables in `workspace`.
2. `ingest_harboursync_jit` → lands all 4 DCSA operational datasets into `/Volumes/workspace/bronze_dcsa/landing_*`.
3. `run_dcsa_medallion_pipeline` → runs Bronze, Silver + Quarantine, `AUTO CDC` SCD1/SCD2, and Gold Materialized Views.
4. `deploy_serving_governance` → deploys `mv_port_call_kpis` &amp; `mv_container_journey_kpis`, applies UC comments, and attaches `mask_pii_email` on Silver eBL tables.
5. `run_contract_tests` → executes all 5 ODCS v3.1.0 contracts live via native `spark_ibis` (`420/420` checks).

*(Note: After changing expectation regexes or schema rules in development, trigger a one-time `--full-refresh` on `dcsa_medallion_pipeline` before re-running the orchestrator so Auto Loader checkpoints reprocess cleanly.)*

### Step 4: Start &amp; Deploy the Live Databricks App (`tcl-port-control`)

```bash
databricks apps start tcl-port-control
databricks apps deploy tcl-port-control \
  --source-code-path "/Workspace/Users/<YOUR_DATABRICKS_USER>/.bundle/tcl-dcsa-lakehouse/dev/files/apps/port-control"
databricks apps get tcl-port-control --output json
```

### Step 5: Verify Live Unity Catalog Proofs in SQL Editor

```sql
-- 1. Port Call Schedule Reliability & Turnaround KPIs (UC Metric View)
SELECT un_location_code, port_name,
       MEASURE(schedule_reliability_pct)    AS reliability_pct,
       MEASURE(avg_port_turnaround_hours)   AS turnaround_hours,
       MEASURE(avg_berth_wait_hours)        AS berth_wait_hours,
       MEASURE(total_port_calls)            AS total_calls,
       MEASURE(on_time_calls)               AS on_time_calls
FROM workspace.gold_dcsa.mv_port_call_kpis
GROUP BY 1, 2
ORDER BY 1;

-- 2. Container Journey & Cold-Chain Reefer Excursions (UC Metric View)
SELECT un_location_code,
       MEASURE(cold_chain_excursion_rate_pct) AS excursion_rate_pct,
       MEASURE(total_container_moves)         AS moves,
       MEASURE(reefer_excursion_count)        AS excursions,
       MEASURE(avg_dwell_hours)               AS avg_dwell_hours,
       MEASURE(active_ebl_count)              AS active_ebls
FROM workspace.gold_dcsa.mv_container_journey_kpis
GROUP BY 1
ORDER BY 1;

-- 3. Quarantine & AUTO CDC SCD1/SCD2 Verification
SELECT 'quarantine_portgate_equipment' AS tbl, COUNT(*) AS rows FROM workspace.silver_dcsa.quarantine_portgate_equipment_events
UNION ALL SELECT 'quarantine_reeferpulse_iot', COUNT(*) FROM workspace.silver_dcsa.quarantine_reeferpulse_iot_telemetry
UNION ALL SELECT 'silver_ebl_current_scd1',    COUNT(*) FROM workspace.silver_dcsa.silver_dcsa_ebl_current
UNION ALL SELECT 'silver_ebl_history_scd2',    COUNT(*) FROM workspace.silver_dcsa.silver_dcsa_ebl_history;

-- 4. Native spark_ibis ODCS Audit Results
SELECT contract_id, passed, checks_total, checks_failed
FROM workspace.governance_dcsa.contract_test_results
ORDER BY executed_at DESC, contract_id
LIMIT 5;

-- 5. Dynamic PII Masking Proof on Silver eBL
SELECT transport_document_reference, shipper_contact_email
FROM workspace.silver_dcsa.silver_dcsa_ebl_current
ORDER BY 1
LIMIT 5;
```

---

## 4. Mode C — GitHub Actions CI/CD (Live in This Repo)

[`.github/workflows/ci-cd.yml`](../.github/workflows/ci-cd.yml) runs automatically on every push and PR to `main`:

- **`ci` Job (Always Runs — Zero Secrets Needed):** `uv sync`, `ruff check .`, LinkML compile + `git diff --exit-code generated contracts`, `datacontract lint` across all 5 contracts, `datacontract breaking` drift check, Apache Ossie dual compile + `git diff --exit-code generated`, and `pytest -v`.
- **`cd-databricks` Job (Runs on `main` when Secrets Configured):** Add repository secrets `DATABRICKS_HOST` and `DATABRICKS_TOKEN` (and optional `WAREHOUSE_ID`) under **Settings → Secrets and variables → Actions** to enable automated `databricks bundle validate` and `deploy`. When secrets are absent, the job skips cleanly.

---

## 5. Mode D — Enterprise Azure Databricks &amp; Azure DevOps Migration

[`azure-pipelines.yml`](../azure-pipelines.yml) provides a production 4-stage pipeline (`Compile_And_Gate` → `Deploy_Dev` → `Deploy_Staging` → `Deploy_Prod` with Environment approval gates). To promote from `free_edition` to `azure_enterprise`:

1. Provision environment-isolated Unity Catalogs (`tcl_staging`, `tcl_prod`) — schemas remain pure (`bronze_dcsa`, `silver_dcsa`, `gold_dcsa`, `governance_dcsa`).
2. Configure pipeline secrets/conf for Event Hubs Kafka-compatible SASL_SSL (`tcl.kafka.bootstrap_servers`, `tcl.kafka.topic`, `tcl.kafka.sasl_jaas_config` via Databricks Secret Scopes) and Lakeflow Connect managed Bronze tables for VoyageCore ERP.
3. Bind Azure DevOps Variable Groups (`DATABRICKS_DEV_*`, `DATABRICKS_STAGING_*`, `DATABRICKS_PROD_*`, or Entra ID OIDC Service Principals) and deploy via `databricks bundle deploy -t staging` / `-t prod`.
