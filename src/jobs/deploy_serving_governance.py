"""Deploy Unity Catalog Metric Views, LinkML UC comments, and PII dynamic data masking."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


def _resolve_project_root() -> Path:
    start = Path(__file__).resolve().parent if "__file__" in globals() else Path.cwd().resolve()
    for candidate in (start, *start.parents):
        if (candidate / "generated").is_dir() and (candidate / "src").is_dir():
            return candidate
    return Path.cwd().resolve()


PROJECT_ROOT = _resolve_project_root()
DEFAULT_METRIC_SQL = PROJECT_ROOT / "generated" / "databricks" / "deploy_metric_views.sql"
DEFAULT_UC_COMMENTS = PROJECT_ROOT / "generated" / "uc_comments.json"

_PII_MASKED_TABLES: tuple[str, ...] = (
    "silver_dcsa.silver_dcsa_ebl_current",
    "silver_dcsa.silver_dcsa_ebl_history",
)


def build_bronze_mask_cleanup_statements(catalog: str) -> list[str]:
    """Return DDL to drop any legacy PII mask from Bronze transport documents."""
    return [
        f"ALTER TABLE {catalog}.bronze_dcsa.voyagecore_transport_documents "
        "ALTER COLUMN shipper_contact_email DROP MASK"
    ]


def _escape_sql_string(value: str) -> str:
    return value.replace("'", "''")


def build_metric_view_statements(catalog: str, sql_path: Path | None = None) -> list[str]:
    """Read generated deploy_metric_views.sql and parameterize target catalog DDL."""
    target_path = sql_path or DEFAULT_METRIC_SQL
    raw_sql = target_path.read_text(encoding="utf-8").replace("${catalog}", catalog)
    blocks = re.findall(
        r"CREATE\s+OR\s+REPLACE\s+VIEW\s+[\s\S]*?\$\$;",
        raw_sql,
        flags=re.IGNORECASE,
    )
    return [blk.rstrip(";").strip() for blk in blocks if blk.strip()]


def build_uc_comment_statements(catalog: str, uc_comments_path: Path | None = None) -> list[str]:
    """Build Unity Catalog COMMENT ON TABLE/VIEW and ALTER COLUMN COMMENT statements."""
    target_path = uc_comments_path or DEFAULT_UC_COMMENTS
    registry = json.loads(target_path.read_text(encoding="utf-8"))
    stmts: list[str] = []
    for table_fqn, table_meta in registry.items():
        full_table = f"{catalog}.{table_fqn}"
        schema_name = str(table_meta.get("schema", ""))
        is_mv = schema_name == "gold_dcsa"
        table_comment = _escape_sql_string(str(table_meta.get("table_comment", "")))
        if is_mv:
            stmts.append(f"COMMENT ON VIEW {full_table} IS '{table_comment}'")
        else:
            stmts.append(f"COMMENT ON TABLE {full_table} IS '{table_comment}'")
        for col_name, col_meta in table_meta.get("columns", {}).items():
            col_comment = _escape_sql_string(str(col_meta.get("comment", "")))
            alter_kw = "ALTER MATERIALIZED VIEW" if is_mv else "ALTER TABLE"
            stmts.append(
                f"{alter_kw} {full_table} ALTER COLUMN {col_name} COMMENT '{col_comment}'"
            )
    return stmts


def build_pii_masking_statements(catalog: str) -> list[str]:
    """Build 80/20 Dynamic Data Masking UDF and column mask attachment DDL."""
    mask_fn = f"{catalog}.governance_dcsa.mask_pii_email"
    stmts = [
        f"""CREATE OR REPLACE FUNCTION {mask_fn}(email STRING)
RETURNS STRING
RETURN CASE
    WHEN is_account_group_member('dcsa_pii_readers') THEN email
    WHEN email IS NULL THEN NULL
    ELSE regexp_replace(email, '^([^@]{{1,2}})[^@]*(@.*)$', '$1***$2')
END""",
    ]
    for tbl in _PII_MASKED_TABLES:
        stmts.append(
            f"ALTER TABLE {catalog}.{tbl} "
            f"ALTER COLUMN shipper_contact_email SET MASK {mask_fn}"
        )
    return stmts


def main(argv: list[str] | None = None) -> int:
    """Databricks serverless job entrypoint deploying Metric Views, comments, and PII masks."""
    parser = argparse.ArgumentParser(description="Deploy UC Metric Views and governance controls.")
    parser.add_argument("--catalog", default="workspace", help="Target UC catalog name.")
    args = parser.parse_args(argv)

    from pyspark.sql import SparkSession

    spark = SparkSession.getActiveSession() or SparkSession.builder.getOrCreate()
    for stmt in build_bronze_mask_cleanup_statements(args.catalog):
        try:
            spark.sql(stmt)
        except Exception as exc:
            print(f"[deploy_serving_governance] Skipping Bronze mask cleanup: {exc}")

    for stmt in (
        build_metric_view_statements(args.catalog)
        + build_uc_comment_statements(args.catalog)
        + build_pii_masking_statements(args.catalog)
    ):
        spark.sql(stmt)
    print(
        f"[deploy_serving_governance] Deployed Metric Views, comments, and mask on {args.catalog}"
    )
    return 0


if __name__ == "__main__":
    exit_code = main()
    if exit_code != 0:
        raise SystemExit(exit_code)
