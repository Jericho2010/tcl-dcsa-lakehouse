"""Serverless ODCS contract verification job executing datacontract-cli against UC tables."""

from __future__ import annotations

import argparse
import json
import re
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml


def _resolve_project_root() -> Path:
    start = Path(__file__).resolve().parent if "__file__" in globals() else Path.cwd().resolve()
    for candidate in (start, *start.parents):
        if (candidate / "contracts").is_dir() and (candidate / "src").is_dir():
            return candidate
    return Path.cwd().resolve()


PROJECT_ROOT = _resolve_project_root()
DEFAULT_CONTRACTS_DIR = PROJECT_ROOT / "contracts" / "odcs"

_SPARK_TO_DUCKDB_TYPES: dict[str, str] = {
    "string": "VARCHAR",
    "bigint": "BIGINT",
    "long": "BIGINT",
    "int": "INTEGER",
    "integer": "INTEGER",
    "smallint": "SMALLINT",
    "short": "SMALLINT",
    "tinyint": "TINYINT",
    "byte": "TINYINT",
    "double": "DOUBLE",
    "float": "FLOAT",
    "boolean": "BOOLEAN",
    "date": "DATE",
    "timestamp": "TIMESTAMP",
    "timestamp_ntz": "TIMESTAMP",
}

_RLIKE_RE = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)\s+RLIKE\s+'((?:[^'\\]|\\.)*)'")


def rewrite_contract_catalog(contract_path: Path, target_catalog: str) -> str:
    """Return ODCS YAML with servers[*].catalog pointed at target_catalog."""
    doc = yaml.safe_load(contract_path.read_text(encoding="utf-8"))
    for server in doc.get("servers") or []:
        if isinstance(server, dict):
            server["catalog"] = target_catalog
    return yaml.safe_dump(doc, sort_keys=False, allow_unicode=False)


def _spark_rlike_to_duckdb_query(query: str) -> str:
    """Convert Spark SQL RLIKE predicates to DuckDB regexp_matches with unescaped backslashes."""

    def _replace(match: re.Match[str]) -> str:
        col = match.group(1)
        pattern = match.group(2).replace("\\\\", "\\").replace("\\'", "''")
        return f"regexp_matches({col}, '{pattern}')"

    return _RLIKE_RE.sub(_replace, query)


def rewrite_contract_for_duckdb(contract_path: Path, db_path: Path) -> tuple[str, str, list[str]]:
    """Rewrite ODCS YAML to target a local DuckDB database and return (yaml, schema, tables)."""
    doc = yaml.safe_load(contract_path.read_text(encoding="utf-8"))
    servers = doc.get("servers") or []
    schema_name = str(servers[0].get("schema", "silver_dcsa")) if servers else "silver_dcsa"
    doc["servers"] = [
        {
            "server": "duckdb_local_validation",
            "type": "duckdb",
            "database": str(db_path),
            "schema": schema_name,
        }
    ]
    tables: list[str] = []
    for obj in doc.get("schema") or []:
        if isinstance(obj, dict):
            if obj.get("name"):
                tables.append(str(obj["name"]))
            for q in obj.get("quality") or []:
                if isinstance(q, dict) and isinstance(q.get("query"), str):
                    q["query"] = _spark_rlike_to_duckdb_query(q["query"])
    return (
        yaml.safe_dump(doc, sort_keys=False, allow_unicode=False),
        schema_name,
        tables,
    )


def _load_tables_into_duckdb(
    spark: Any,
    catalog: str,
    schema_name: str,
    table_names: list[str],
    db_path: Path,
) -> None:
    """Materialize Spark UC tables into a DuckDB file preserving column types."""
    import duckdb

    con = duckdb.connect(str(db_path))
    try:
        escaped_schema = schema_name.replace('"', '""')
        con.execute(f'CREATE SCHEMA IF NOT EXISTS "{escaped_schema}"')
        for table_name in table_names:
            sdf = spark.table(f"{catalog}.{schema_name}.{table_name}")
            col_defs = [
                (
                    field.name,
                    _SPARK_TO_DUCKDB_TYPES.get(field.dataType.simpleString().lower(), "VARCHAR"),
                )
                for field in sdf.schema.fields
            ]
            escaped_table = table_name.replace('"', '""')
            ddl_cols = ", ".join(
                f'"{col.replace(chr(34), chr(34) * 2)}" {dtype}' for col, dtype in col_defs
            )
            con.execute(f'DROP TABLE IF EXISTS "{escaped_schema}"."{escaped_table}"')
            con.execute(f'CREATE TABLE "{escaped_schema}"."{escaped_table}" ({ddl_cols})')

            pdf = sdf.toPandas()
            if not pdf.empty:
                select_exprs = ", ".join(
                    f'CAST("{col.replace(chr(34), chr(34) * 2)}" AS {dtype})'
                    for col, dtype in col_defs
                )
                con.register("_tmp_pdf", pdf)
                con.execute(
                    f'INSERT INTO "{escaped_schema}"."{escaped_table}" '
                    f"SELECT {select_exprs} FROM _tmp_pdf"
                )
                con.unregister("_tmp_pdf")
    finally:
        con.close()


_BACKEND_ERROR_MARKERS: tuple[str, ...] = (
    "no such option",
    "cannot_convert_column_into_bool",
    "_jsparksession",
    "could not connect",
    "not installed",
    "sparkconnect",
)


def _enum_value(val: Any) -> str:
    """Extract normalized string value from an Enum or string object."""
    return str(getattr(val, "value", val)).lower()


def _is_backend_failure(checks: list[Any]) -> str | None:
    """Detect backend/connection or Spark Connect incompatibility failures in checks."""
    if not checks:
        return "No checks executed by backend"
    for check in checks:
        check_type = _enum_value(getattr(check, "type", ""))
        result = _enum_value(getattr(check, "result", ""))
        reason = str(getattr(check, "reason", "") or "")
        if check_type in {"general", "connection"} and result in {"failed", "error"}:
            return reason or str(getattr(check, "name", "backend failure"))
        if result == "error":
            return reason or str(getattr(check, "name", "backend error"))
        lower_reason = reason.lower()
        if any(marker in lower_reason for marker in _BACKEND_ERROR_MARKERS):
            return reason
    return None


def _execute_contract(
    DataContract: Any,
    spark: Any,
    catalog: str,
    contract_path: Path,
    contract_id: str,
    tmpdir: Path,
    skip_spark_reason: str | None = None,
) -> tuple[Any, str, str | None]:
    """Run DataContract via Spark/Ibis first, falling back to DuckDB on Serverless Connect error."""
    rewritten_yaml = rewrite_contract_catalog(contract_path, catalog)
    tmp_contract = tmpdir / contract_path.name
    tmp_contract.write_text(rewritten_yaml, encoding="utf-8")

    fallback_reason: str | None = skip_spark_reason
    if fallback_reason is None:
        try:
            dc = DataContract(data_contract_file=str(tmp_contract), spark=spark)
            run = dc.test()
            checks = list(getattr(run, "checks", []) or [])
            backend_err = _is_backend_failure(checks)
            if backend_err is None:
                return run, "spark_ibis", None
            fallback_reason = backend_err
        except Exception as exc:
            fallback_reason = str(exc)

    db_path = tmpdir / f"{contract_id}.duckdb"
    duckdb_yaml, schema_name, table_names = rewrite_contract_for_duckdb(contract_path, db_path)
    _load_tables_into_duckdb(spark, catalog, schema_name, table_names, db_path)

    tmp_duckdb_contract = tmpdir / f"{contract_path.stem}.duckdb.odcs.yaml"
    tmp_duckdb_contract.write_text(duckdb_yaml, encoding="utf-8")
    dc_duck = DataContract(data_contract_file=str(tmp_duckdb_contract))
    return dc_duck.test(), "duckdb_fallback", fallback_reason


def run_all_contract_checks(
    spark: Any,
    catalog: str = "workspace",
    contracts_dir: Path = DEFAULT_CONTRACTS_DIR,
) -> list[dict[str, Any]]:
    """Run DataContract(...).test() for all ODCS files and persist results to governance_dcsa."""
    from datacontract.data_contract import DataContract

    run_id = str(uuid.uuid4())
    executed_at = datetime.now(UTC)
    results: list[dict[str, Any]] = []
    contract_files = sorted(contracts_dir.glob("*.odcs.yaml"))
    spark_fallback_reason: str | None = None

    with tempfile.TemporaryDirectory() as tmpdir_str:
        tmpdir = Path(tmpdir_str)
        for contract_path in contract_files:
            raw_doc = yaml.safe_load(contract_path.read_text(encoding="utf-8"))
            contract_id = str(raw_doc.get("id", contract_path.stem))

            run, engine, fallback_reason = _execute_contract(
                DataContract=DataContract,
                spark=spark,
                catalog=catalog,
                contract_path=contract_path,
                contract_id=contract_id,
                tmpdir=tmpdir,
                skip_spark_reason=spark_fallback_reason,
            )
            if engine == "duckdb_fallback" and spark_fallback_reason is None:
                spark_fallback_reason = fallback_reason
            checks = list(getattr(run, "checks", []) or [])
            failed_checks = [
                c for c in checks if _enum_value(getattr(c, "result", "")) != "passed"
            ]
            has_passed_fn = getattr(run, "has_passed", None)
            passed = bool(has_passed_fn()) if callable(has_passed_fn) else len(failed_checks) == 0

            summary_payload: dict[str, Any] = {
                "result": _enum_value(getattr(run, "result", "unknown")),
                "engine": engine,
                "checks": len(checks),
            }
            if fallback_reason:
                summary_payload["fallback_reason"] = fallback_reason[:240]
            if failed_checks:
                summary_payload["sample_failures"] = [
                    {
                        "name": str(getattr(c, "name", "")),
                        "model": str(getattr(c, "model", "")),
                        "field": str(getattr(c, "field", "")),
                        "reason": str(getattr(c, "reason", ""))[:200],
                    }
                    for c in failed_checks[:5]
                ]

            print(
                f"[run_contract_tests] {contract_id}: passed={passed} engine={engine} "
                f"checks={len(checks)} failed={len(failed_checks)}"
            )
            results.append(
                {
                    "run_id": run_id,
                    "executed_at": executed_at,
                    "catalog_name": catalog,
                    "contract_id": contract_id,
                    "contract_file": contract_path.name,
                    "passed": passed,
                    "checks_total": len(checks),
                    "checks_failed": len(failed_checks),
                    "summary": json.dumps(summary_payload),
                }
            )

    if results:
        df = spark.createDataFrame(results)
        df.write.mode("append").saveAsTable(f"{catalog}.governance_dcsa.contract_test_results")

    failures = [r for r in results if not r["passed"]]
    if failures:
        details = "; ".join(f"{r['contract_id']}={r['summary']}" for r in failures)
        raise RuntimeError(f"ODCS contract test failures detected: {details}")

    return results


def main(argv: list[str] | None = None) -> int:
    """Databricks serverless job entrypoint validating live tables against ODCS contracts."""
    parser = argparse.ArgumentParser(description="Execute ODCS contract tests in Spark.")
    parser.add_argument("--catalog", default="workspace", help="Target UC catalog name.")
    parser.add_argument("--contracts-dir", type=Path, default=DEFAULT_CONTRACTS_DIR)
    args = parser.parse_args(argv)

    from pyspark.sql import SparkSession

    spark = SparkSession.getActiveSession() or SparkSession.builder.getOrCreate()
    results = run_all_contract_checks(
        spark=spark, catalog=args.catalog, contracts_dir=args.contracts_dir
    )
    print(f"[run_contract_tests] Passed {len(results)} ODCS contract suites on {args.catalog}")
    return 0


if __name__ == "__main__":
    exit_code = main()
    if exit_code != 0:
        raise SystemExit(exit_code)
