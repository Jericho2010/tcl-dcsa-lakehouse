"""Idempotent Unity Catalog schema, volume, and governance table bootstrap job."""

from __future__ import annotations

import argparse

SCHEMAS: tuple[str, ...] = (
    "bronze_dcsa",
    "silver_dcsa",
    "gold_dcsa",
    "governance_dcsa",
)

LANDING_VOLUMES: tuple[str, ...] = (
    "landing_portgate_tos",
    "landing_reeferpulse_iot",
    "landing_voyagecore_cdc",
    "landing_harboursync_jit",
)


def build_bootstrap_statements(catalog: str) -> list[str]:
    """Generate idempotent Unity Catalog DDL statements for schemas, volumes, and governance."""
    if not catalog or not catalog.replace("_", "").isalnum():
        raise ValueError(f"Invalid Unity Catalog name: {catalog!r}")

    stmts: list[str] = []
    for schema in SCHEMAS:
        stmts.append(f"CREATE SCHEMA IF NOT EXISTS {catalog}.{schema}")

    for volume in LANDING_VOLUMES:
        stmts.append(f"CREATE VOLUME IF NOT EXISTS {catalog}.bronze_dcsa.{volume}")

    stmts.append(
        f"""CREATE TABLE IF NOT EXISTS {catalog}.governance_dcsa.contract_test_results (
    run_id STRING NOT NULL,
    executed_at TIMESTAMP NOT NULL,
    catalog_name STRING NOT NULL,
    contract_id STRING NOT NULL,
    contract_file STRING NOT NULL,
    passed BOOLEAN NOT NULL,
    checks_total INT NOT NULL,
    checks_failed INT NOT NULL,
    summary STRING
) USING DELTA"""
    )

    stmts.append(
        f"""CREATE TABLE IF NOT EXISTS {catalog}.governance_dcsa.exception_triage_log (
    triage_id STRING NOT NULL,
    triaged_at TIMESTAMP NOT NULL,
    entity_type STRING NOT NULL,
    equipment_or_call_id STRING NOT NULL,
    severity STRING NOT NULL,
    disposition STRING NOT NULL,
    operator_note STRING,
    triaged_by STRING NOT NULL
) USING DELTA"""
    )

    return stmts


def main(argv: list[str] | None = None) -> int:
    """Databricks serverless job entrypoint executing UC bootstrap DDL."""
    parser = argparse.ArgumentParser(description="Bootstrap TCL DCSA Unity Catalog objects.")
    parser.add_argument("--catalog", default="workspace", help="Target UC catalog name.")
    args = parser.parse_args(argv)

    from pyspark.sql import SparkSession

    spark = SparkSession.getActiveSession() or SparkSession.builder.getOrCreate()
    for stmt in build_bootstrap_statements(args.catalog):
        spark.sql(stmt)
    print(f"[bootstrap_uc_objects] Provisioned schemas, volumes, and governance in {args.catalog}")
    return 0


if __name__ == "__main__":
    exit_code = main()
    if exit_code != 0:
        raise SystemExit(exit_code)
