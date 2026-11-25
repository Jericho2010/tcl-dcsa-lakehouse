"""Unit tests for Databricks Native App TCL Port Control workbench (demo mode)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parent.parent
APP_PATH = PROJECT_ROOT / "apps" / "port-control" / "app.py"


def _load_app_module():
    spec = importlib.util.spec_from_file_location("tcl_port_control_app", APP_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["tcl_port_control_app"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_port_control_workbench_routes_in_demo_mode(monkeypatch) -> None:
    """All workbench API routes and UI respond cleanly in offline demo mode."""
    monkeypatch.setenv("TCL_DEMO_MODE", "1")
    monkeypatch.setenv("TCL_CATALOG", "workspace")
    app_mod = _load_app_module()
    client = TestClient(app_mod.app)

    home = client.get("/")
    assert home.status_code == 200
    assert "Port Call & Reefer Exception Workbench" in home.text

    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.json() == {"status": "ok", "mode": "demo", "catalog": "workspace"}

    kpis = client.get("/api/kpis")
    assert kpis.status_code == 200
    body = kpis.json()
    assert body["port_call_kpis"]["total_port_calls"] == 15
    assert body["container_journey_kpis"]["reefer_excursion_count"] == 2
    assert len(body["ports"]) == 6

    exc = client.get("/api/exceptions")
    assert exc.status_code == 200
    exc_json = exc.json()
    assert len(exc_json["reefer_excursions"]) == 2
    assert any(q["record_id"] == "rf-sensor-fault-minus99" for q in exc_json["quarantine_records"])

    triage_post = client.post(
        "/api/triage",
        json={
            "exception_id": "rf-sensor-fault-minus99",
            "entity_type": "quarantine_record",
            "equipment_or_call_id": "TCLU1000001",
            "severity": "MEDIUM",
            "disposition": "DISMISS_SENSOR_NOISE",
            "operator_note": "Probe calibrated at Tauranga depot.",
            "triaged_by": "qa.engineer",
        },
    )
    assert triage_post.status_code == 201
    triage_id = triage_post.json()["record"]["triage_id"]

    triage_list = client.get("/api/triage")
    assert triage_list.status_code == 200
    assert any(item["triage_id"] == triage_id for item in triage_list.json()["items"])

    genie_reefer = client.post(
        "/api/genie/ask",
        json={"question": "Why did reefer cold-chain excursions spike?"},
    )
    assert genie_reefer.status_code == 200
    assert "-11.2C" in genie_reefer.json()["answer"]
    assert "MEASURE(" in genie_reefer.json()["generated_sql"]

    genie_ports = client.post(
        "/api/genie/ask",
        json={"question": "Which ports lead schedule reliability?"},
    )
    assert genie_ports.status_code == 200
    assert "73.3%" in genie_ports.json()["answer"]
