"""Unit tests for expectations_loader, LDP pipeline AST structure, and job SQL builders."""

from __future__ import annotations

import ast
from pathlib import Path

import yaml

from jobs.bootstrap_uc_objects import build_bootstrap_statements
from jobs.deploy_serving_governance import (
    build_bronze_mask_cleanup_statements,
    build_metric_view_statements,
    build_pii_masking_statements,
    build_uc_comment_statements,
)
from jobs.ingest_harboursync_jit import run_ingestion
from jobs.run_contract_tests import (
    _enum_value,
    _is_backend_failure,
    rewrite_contract_catalog,
    rewrite_contract_for_duckdb,
)
from pipelines.dcsa_medallion.expectations_loader import (
    build_quarantine_filter,
    build_violation_reason_expr,
    load_table_expectations,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PIPE_DIR = PROJECT_ROOT / "src" / "pipelines" / "dcsa_medallion"


def test_expectations_loader_builds_filter_and_violation_reason() -> None:
    """expectations_loader loads LinkML rules and builds Spark SQL quarantine expressions."""
    rules = load_table_expectations("silver_dcsa.silver_reeferpulse_iot_telemetry")
    assert "supply_air_temp_c_min_bound" in rules
    assert "equipment_reference_pattern" in rules

    q_filter = build_quarantine_filter(rules)
    assert q_filter.startswith("NOT (")
    assert "supply_air_temp_c >= -45.0" in q_filter

    reason_expr = build_violation_reason_expr(rules)
    assert reason_expr.startswith("concat_ws('; ',")
    assert "'supply_air_temp_c_min_bound'" in reason_expr


def test_ldp_pipeline_modules_use_modern_pyspark_pipelines_and_match_ossie() -> None:
    """Pipeline modules use pyspark.pipelines, AUTO CDC SCD1/2, both ingest modes, zero dev_."""
    for filename in ("bronze_ingestion.py", "silver_conformance.py", "gold_marts.py"):
        src = (PIPE_DIR / filename).read_text(encoding="utf-8")
        tree = ast.parse(src)
        assert tree is not None
        assert "from pyspark import pipelines as dp" in src
        assert "dev_" not in src

    bronze_src = (PIPE_DIR / "bronze_ingestion.py").read_text(encoding="utf-8")
    assert 'format("cloudFiles")' in bronze_src
    assert 'format("kafka")' in bronze_src
    assert "azure_enterprise" in bronze_src
    assert "lakeflow_voyagecore_" in bronze_src

    silver_src = (PIPE_DIR / "silver_conformance.py").read_text(encoding="utf-8")
    assert "@dp.expect_all_or_drop" in silver_src
    assert "dp.create_auto_cdc_flow" in silver_src
    assert "stored_as_scd_type=1" in silver_src
    assert "stored_as_scd_type=2" in silver_src
    assert "quarantine_reeferpulse_iot_telemetry" in silver_src

    gold_src = (PIPE_DIR / "gold_marts.py").read_text(encoding="utf-8")
    assert "@dp.materialized_view" in gold_src
    ossie = yaml.safe_load(
        (PROJECT_ROOT / "semantic" / "ossie" / "dcsa_ops.ossie.yaml").read_text(encoding="utf-8")
    )
    for ds in ossie["datasets"]:
        for field in ds["fields"]:
            assert field["name"] in gold_src, (
                f"Gold pipeline missing column {field['name']} required by Ossie {ds['name']}"
            )


def test_serverless_job_sql_builders_and_ingestion_modes(tmp_path: Path) -> None:
    """Job DDL builders enforce pure schemas, PII masking, catalog substitution & ingestion."""
    boot = "\n".join(build_bootstrap_statements("workspace"))
    for schema in ("bronze_dcsa", "silver_dcsa", "gold_dcsa", "governance_dcsa"):
        assert f"CREATE SCHEMA IF NOT EXISTS workspace.{schema}" in boot
    assert "CREATE VOLUME IF NOT EXISTS workspace.bronze_dcsa.landing_harboursync_jit" in boot
    assert "dev_" not in boot

    mv_stmts = build_metric_view_statements("workspace")
    assert len(mv_stmts) == 2
    assert all("workspace.gold_dcsa." in s for s in mv_stmts)

    comment_stmts = build_uc_comment_statements("workspace")
    expected_comment = "COMMENT ON VIEW workspace.gold_dcsa.gold_port_call_performance"
    assert any(expected_comment in s for s in comment_stmts)
    assert any(
        "ALTER MATERIALIZED VIEW workspace.gold_dcsa.gold_port_call_performance ALTER COLUMN" in s
        for s in comment_stmts
    )

    mask_stmts = build_pii_masking_statements("workspace")
    assert any("workspace.governance_dcsa.mask_pii_email" in s for s in mask_stmts)
    assert any("silver_dcsa.silver_dcsa_ebl_current" in s for s in mask_stmts)
    assert any("silver_dcsa.silver_dcsa_ebl_history" in s for s in mask_stmts)
    assert all("bronze_dcsa.voyagecore_transport_documents" not in s for s in mask_stmts)

    cleanup_stmts = build_bronze_mask_cleanup_statements("workspace")
    assert any(
        "bronze_dcsa.voyagecore_transport_documents ALTER COLUMN shipper_contact_email DROP MASK"
        in s
        for s in cleanup_stmts
    )

    rewritten = rewrite_contract_catalog(
        PROJECT_ROOT / "contracts" / "odcs" / "reeferpulse_iot_telemetry.odcs.yaml",
        "workspace",
    )
    parsed = yaml.safe_load(rewritten)
    assert parsed["servers"][0]["catalog"] == "workspace"

    duck_yaml, duck_schema, duck_tables = rewrite_contract_for_duckdb(
        PROJECT_ROOT / "contracts" / "odcs" / "voyagecore_ebl_bookings.odcs.yaml",
        tmp_path / "validation.duckdb",
    )
    duck_doc = yaml.safe_load(duck_yaml)
    assert duck_doc["servers"][0]["type"] == "duckdb"
    assert duck_doc["servers"][0]["database"] == str(tmp_path / "validation.duckdb")
    assert duck_schema == "silver_dcsa"
    assert "silver_dcsa_ebl_current" in duck_tables
    email_queries = [
        q["query"]
        for obj in duck_doc["schema"]
        if obj["name"] == "silver_dcsa_ebl_current"
        for q in obj["quality"]
        if q["name"].endswith("shipper_contact_email_pattern")
    ]
    assert len(email_queries) == 1
    expected_re = "regexp_matches(shipper_contact_email, '^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$')"
    assert expected_re in email_queries[0]

    from datacontract.model.run import Check, ResultEnum

    assert _enum_value(ResultEnum.passed) == "passed"
    spark_err_check = Check(
        type="field_unique",
        name="unique_check",
        result=ResultEnum.failed,
        reason="Error evaluating check: No such option",
    )
    assert _is_backend_failure([spark_err_check]) is not None

    ent_written = run_ingestion(
        catalog="tcl_staging",
        ingestion_mode="azure_enterprise",
        output_dir=tmp_path,
    )
    assert "harboursync_jit_port_calls" in ent_written
    assert "reeferpulse_iot_telemetry" not in ent_written
