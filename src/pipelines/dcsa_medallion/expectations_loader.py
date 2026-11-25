"""Load LinkML-derived Spark SQL expectations for Lakeflow Declarative Pipelines."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def find_expectations_path(explicit_path: Path | None = None) -> Path:
    """Locate generated/ldp_expectations.json across local, test, and DABs workspace layouts."""
    if explicit_path is not None:
        if explicit_path.is_file():
            return explicit_path
        raise FileNotFoundError(f"Explicit expectations path not found: {explicit_path}")

    env_val = os.environ.get("TCL_EXPECTATIONS_PATH", "").strip()
    candidates: list[Path] = []
    if env_val:
        candidates.append(Path(env_val))

    here = Path(__file__).resolve() if "__file__" in globals() else Path.cwd().resolve()
    for candidate_root in (here, *here.parents, Path.cwd().resolve()):
        candidates.append(candidate_root / "generated" / "ldp_expectations.json")

    for candidate in candidates:
        if candidate.is_file():
            return candidate

    searched = ", ".join(str(p) for p in candidates)
    raise FileNotFoundError(
        f"Could not locate generated/ldp_expectations.json; searched: {searched}"
    )


def load_all_expectations(path: Path | None = None) -> dict[str, Any]:
    """Load the full LinkML-compiled expectations registry."""
    target = find_expectations_path(path)
    return json.loads(target.read_text(encoding="utf-8"))


def load_table_expectations(table_fqn: str, path: Path | None = None) -> dict[str, str]:
    """Return mapping of {rule_name: spark_sql_expression} for a governed DCSA table."""
    registry = load_all_expectations(path)
    if table_fqn not in registry:
        raise KeyError(f"No compiled LinkML expectations registered for table: {table_fqn}")
    return {rule["name"]: rule["sql"] for rule in registry[table_fqn]["rules"]}


def build_quarantine_filter(rules: dict[str, str]) -> str:
    """Return a Spark SQL predicate selecting rows failing at least one expectation."""
    if not rules:
        return "FALSE"
    combined = " AND ".join(f"COALESCE(({sql}), FALSE)" for sql in rules.values())
    return f"NOT ({combined})"


def build_violation_reason_expr(rules: dict[str, str]) -> str:
    """Return a Spark SQL expression concatenating all violated expectation names."""
    if not rules:
        return "''"
    parts = [
        f"CASE WHEN NOT ({sql}) OR ({sql}) IS NULL THEN '{name}' ELSE NULL END"
        for name, sql in rules.items()
    ]
    return f"concat_ws('; ', {', '.join(parts)})"
