"""Compile Apache Ossie semantic model via real ossie-databricks and ossie-microsoft CLIs."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
OSSIE_MODEL_PATH = PROJECT_ROOT / "semantic" / "ossie" / "dcsa_ops.ossie.yaml"
DATABRICKS_OUT_DIR = PROJECT_ROOT / "generated" / "databricks"
POWERBI_OUT_DIR = PROJECT_ROOT / "generated" / "powerbi"
BIM_OUTPUT_PATH = POWERBI_OUT_DIR / "dcsa_ops.model.bim"
METRIC_VIEW_SQL_PATH = DATABRICKS_OUT_DIR / "deploy_metric_views.sql"


def _cli_executable(name: str) -> str:
    """Resolve CLI executable from the active Python environment's bin directory."""
    candidate = Path(sys.executable).parent / name
    return str(candidate) if candidate.exists() else name


def _run_cli(args: list[str]) -> subprocess.CompletedProcess[str]:
    """Execute a real converter CLI and raise RuntimeError with diagnostics on failure."""
    proc = subprocess.run(args, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(
            f"Command {' '.join(args)} failed (exit {proc.returncode}):\n"
            f"STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
        )
    return proc


def _strip_comment_header(yaml_text: str) -> str:
    """Drop leading '# Metric view: ...' header emitted by ossie-databricks deploy."""
    lines = yaml_text.splitlines()
    if lines and lines[0].lstrip().startswith("# Metric view:"):
        lines = lines[1:]
    return "\n".join(lines).strip()


def compile_semantic_spine(
    ossie_path: Path = OSSIE_MODEL_PATH,
    databricks_dir: Path = DATABRICKS_OUT_DIR,
    powerbi_dir: Path = POWERBI_OUT_DIR,
    catalog: str = "tcl_lakehouse",
    schema: str = "gold_dcsa",
) -> dict[str, Any]:
    """Compile Ossie YAML to Databricks Metric Views + SQL DDL and Power BI TMSL (.model.bim)."""
    databricks_dir.mkdir(parents=True, exist_ok=True)
    powerbi_dir.mkdir(parents=True, exist_ok=True)

    # 1. Invoke real ossie-databricks deploy
    dbx_proc = _run_cli(
        [
            _cli_executable("ossie-databricks"),
            "deploy",
            str(ossie_path),
            "-o",
            str(databricks_dir),
            "--catalog",
            catalog,
            "--schema",
            schema,
            "--overwrite",
        ]
    )

    metric_views_dir = databricks_dir / "metric_views"
    sql_statements = [
        "-- =============================================================================",
        "-- Auto-generated from semantic/ossie/dcsa_ops.ossie.yaml via ossie-databricks deploy",
        "-- Parameterized Databricks Unity Catalog Metric Views DDL (pure gold_dcsa schema)",
        "-- =============================================================================",
        "",
    ]
    metric_view_files = sorted(metric_views_dir.glob("*.yaml"))
    for mv_file in metric_view_files:
        dataset_name = mv_file.stem
        body = _strip_comment_header(mv_file.read_text(encoding="utf-8"))
        # Parameterize hardcoded default catalog token if present while keeping pure gold_dcsa
        parameterized_body = body.replace(f"source: {catalog}.", "source: ${catalog}.")
        sql_statements.extend(
            [
                f"CREATE OR REPLACE VIEW ${{catalog}}.{schema}.{dataset_name}",
                "WITH METRICS",
                "LANGUAGE YAML",
                "AS $$",
                parameterized_body,
                "$$;",
                "",
            ]
        )

    sql_path = databricks_dir / "deploy_metric_views.sql"
    sql_path.write_text("\n".join(sql_statements), encoding="utf-8")

    # 2. Invoke real ossie-microsoft export -> model.bim
    bim_path = powerbi_dir / "dcsa_ops.model.bim"
    ms_proc = _run_cli(
        [
            _cli_executable("ossie-microsoft"),
            "export",
            "-i",
            str(ossie_path),
            "-o",
            str(bim_path),
        ]
    )

    # 3. Probe real ossie-microsoft --pbip (requires optional .NET TOM assemblies)
    pbip_probe = subprocess.run(
        [
            _cli_executable("ossie-microsoft"),
            "export",
            "-i",
            str(ossie_path),
            "--pbip",
            str(powerbi_dir),
            "--force",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    bim_obj = json.loads(bim_path.read_text(encoding="utf-8"))
    measures = [
        {
            "table": table["name"],
            "name": measure["name"],
            "expression": measure["expression"],
        }
        for table in bim_obj.get("model", {}).get("tables", [])
        for measure in table.get("measures", [])
    ]

    return {
        "databricks_warnings": dbx_proc.stderr.strip(),
        "metric_views": [str(p.relative_to(PROJECT_ROOT)) for p in metric_view_files],
        "deploy_sql": str(sql_path.relative_to(PROJECT_ROOT)),
        "powerbi_warnings": ms_proc.stderr.strip(),
        "bim_path": str(bim_path.relative_to(PROJECT_ROOT)),
        "measures": measures,
        "pbip_probe_exit_code": pbip_probe.returncode,
        "pbip_probe_stderr": pbip_probe.stderr.strip(),
    }


def main() -> int:
    """CLI entrypoint compiling Apache Ossie semantic models for Databricks and Power BI."""
    summary = compile_semantic_spine()
    print(f"[compile_semantic] Databricks Metric Views: {summary['metric_views']}")
    print(f"[compile_semantic] Databricks SQL DDL     : {summary['deploy_sql']}")
    if summary["databricks_warnings"]:
        print(f"[compile_semantic] Databricks warnings    :\n{summary['databricks_warnings']}")
    print(f"[compile_semantic] Power BI model.bim     : {summary['bim_path']}")
    print(f"[compile_semantic] Translated DAX count   : {len(summary['measures'])}")
    if summary["powerbi_warnings"]:
        print(f"[compile_semantic] Power BI warnings      :\n{summary['powerbi_warnings']}")
    probe_detail = (
        summary["pbip_probe_stderr"].splitlines()[-1] if summary["pbip_probe_stderr"] else "OK"
    )
    print(
        f"[compile_semantic] Power BI --pbip probe  : exit={summary['pbip_probe_exit_code']} "
        f"({probe_detail})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
