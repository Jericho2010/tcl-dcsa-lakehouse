"""Unit tests for Apache Ossie semantic spec and dual Databricks + Power BI compilation."""

from __future__ import annotations

import json

import yaml

from tcl_compiler.compile_semantic import (
    BIM_OUTPUT_PATH,
    DATABRICKS_OUT_DIR,
    METRIC_VIEW_SQL_PATH,
    OSSIE_MODEL_PATH,
    PROJECT_ROOT,
    compile_semantic_spine,
)


def test_ossie_spec_uses_0_3_0_dev0_and_structured_extensions() -> None:
    """semantic/ossie/dcsa_ops.ossie.yaml follows Ossie 0.3.0.dev0 without custom_extensions."""
    raw_text = OSSIE_MODEL_PATH.read_text(encoding="utf-8")
    assert "custom_extensions" not in raw_text
    assert "dev_" not in raw_text

    doc = yaml.safe_load(raw_text)
    assert doc["version"] == "0.3.0.dev0"
    assert doc["name"] == "dcsa_ops"
    assert isinstance(doc["ai_context"], dict)
    assert len(doc["datasets"]) == 2
    assert len(doc["relationships"]) == 1
    assert len(doc["metrics"]) == 10
    assert isinstance(doc["nonportable_extensions"][0]["data"], dict)


def test_compile_semantic_produces_databricks_and_powerbi_outputs() -> None:
    """Real ossie-databricks and ossie-microsoft CLIs compile Metric Views, SQL, and model.bim."""
    summary = compile_semantic_spine()

    mv_port_calls = DATABRICKS_OUT_DIR / "metric_views" / "mv_port_call_kpis.yaml"
    mv_journeys = DATABRICKS_OUT_DIR / "metric_views" / "mv_container_journey_kpis.yaml"
    rewritten_ossie = DATABRICKS_OUT_DIR / "dcsa_ops.ossie.yaml"

    assert mv_port_calls.is_file()
    assert mv_journeys.is_file()
    assert rewritten_ossie.is_file()
    assert METRIC_VIEW_SQL_PATH.is_file()
    assert BIM_OUTPUT_PATH.is_file()

    port_call_mv = yaml.safe_load(mv_port_calls.read_text(encoding="utf-8"))
    journey_mv = yaml.safe_load(mv_journeys.read_text(encoding="utf-8"))
    assert len(port_call_mv["measures"]) == 5
    assert len(journey_mv["measures"]) == 5
    assert "schedule_reliability_pct" in {m["name"] for m in port_call_mv["measures"]}
    assert "cold_chain_excursion_rate_pct" in {m["name"] for m in journey_mv["measures"]}

    sql_text = METRIC_VIEW_SQL_PATH.read_text(encoding="utf-8")
    assert "CREATE OR REPLACE VIEW ${catalog}.gold_dcsa.mv_port_call_kpis" in sql_text
    assert "CREATE OR REPLACE VIEW ${catalog}.gold_dcsa.mv_container_journey_kpis" in sql_text
    assert "WITH METRICS" in sql_text
    assert "LANGUAGE YAML" in sql_text
    assert "dev_" not in sql_text

    bim = json.loads(BIM_OUTPUT_PATH.read_text(encoding="utf-8"))
    tables = {t["name"]: t for t in bim["model"]["tables"]}
    assert set(tables.keys()) == {"mv_port_call_kpis", "mv_container_journey_kpis"}
    assert len(bim["model"]["relationships"]) == 1

    all_measures = [m for t in tables.values() for m in t.get("measures", [])]
    assert len(all_measures) == 10
    for measure in all_measures:
        assert "BLANK()" not in measure["expression"], (
            f"Measure {measure['name']} fell back to BLANK"
        )

    assert len(summary["measures"]) == 10

    override_tmdl = PROJECT_ROOT / "semantic" / "powerbi_overrides" / "dax_specialist_measures.tmdl"
    override_readme = PROJECT_ROOT / "semantic" / "powerbi_overrides" / "README.md"
    assert override_tmdl.is_file() and override_tmdl.stat().st_size > 100
    assert override_readme.is_file() and override_readme.stat().st_size > 100
