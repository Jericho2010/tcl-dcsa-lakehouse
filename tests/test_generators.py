"""Unit tests for deterministic 4-source DCSA synthetic payload generator."""

from __future__ import annotations

import importlib.util
import json
from datetime import datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from generators.dcsa_synthetic_generator import generate_all

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _load_dcsa_models():
    models_path = PROJECT_ROOT / "generated" / "pydantic" / "dcsa_models.py"
    spec = importlib.util.spec_from_file_location("dcsa_models_gen_test", models_path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _read_jsonl(path: Path) -> list[dict]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def test_generate_all_produces_all_four_dcsa_sources_and_quarantine_cases(tmp_path: Path) -> None:
    """Generator emits valid DCSA payloads plus deliberate bad rows and out-of-order CDC."""
    dcsa = _load_dcsa_models()
    written = generate_all(output_root=tmp_path, seed=42)

    assert len(written) == 8
    for path in written.values():
        assert path.is_file()

    # 1. PortGate TOS: valid events pass Pydantic; 2 bad rows fail Pydantic
    eq_rows = _read_jsonl(written["portgate_equipment_events"])
    tr_rows = _read_jsonl(written["portgate_transport_events"])
    assert len(tr_rows) >= 10
    for row in tr_rows:
        dcsa.TransportEvent(**row)

    bad_ids = {"ee-quarantine-bad-equip", "ee-quarantine-bad-locode"}
    good_eq = [r for r in eq_rows if r["event_id"] not in bad_ids]
    bad_eq = [r for r in eq_rows if r["event_id"] in bad_ids]
    assert len(bad_eq) == 2
    for row in good_eq:
        dcsa.EquipmentEvent(**row)
    for bad in bad_eq:
        with pytest.raises(ValidationError):
            dcsa.EquipmentEvent(**bad)

    # 2. ReeferPulse IoT: Kafka envelopes + normal + excursion + -99.0C sensor fault
    rf_envelopes = _read_jsonl(written["reeferpulse_iot_telemetry"])
    assert all(
        {"topic", "partition", "offset", "timestamp", "key", "value"}.issubset(env.keys())
        for env in rf_envelopes
    )
    rf_good = [
        e["value"]
        for e in rf_envelopes
        if e["value"]["reading_id"] != "rf-sensor-fault-minus99"
    ]
    rf_fault = [
        e["value"]
        for e in rf_envelopes
        if e["value"]["reading_id"] == "rf-sensor-fault-minus99"
    ]
    assert len(rf_fault) == 1
    assert rf_fault[0]["supply_air_temp_c"] == -99.0
    assert any(r["excursion_flag"] is True for r in rf_good)
    for row in rf_good:
        dcsa.ReeferTelemetryReading(**row)
    with pytest.raises(ValidationError):
        dcsa.ReeferTelemetryReading(**rf_fault[0])

    # 3. VoyageCore ERP CDC: INSERT/UPDATE/DELETE + out-of-order sequence_ts
    td_rows = _read_jsonl(written["voyagecore_transport_documents"])
    ops = {r["cdc_operation"] for r in td_rows}
    assert ops == {"INSERT", "UPDATE", "DELETE"}
    for row in td_rows:
        clean = {k: v for k, v in row.items() if k not in {"cdc_operation", "sequence_ts"}}
        dcsa.TransportDocument(**clean)

    # Verify out-of-order update for TCLBL20260001
    doc1_events = [r for r in td_rows if r["transport_document_reference"] == "TCLBL20260001"]
    doc1_ts = [datetime.fromisoformat(r["sequence_ts"].replace("Z", "+00:00")) for r in doc1_events]
    assert doc1_ts[-1] < doc1_ts[-2]

    # 4. HarbourSync JIT: all 5 JIT phases present
    jit_rows = _read_jsonl(written["harboursync_jit_port_calls"])
    jit_phases = {r["jit_phase_code"] for r in jit_rows}
    assert jit_phases == {"ETA_PBP", "ATA_PBP", "ETB_BERTH", "ATB_BERTH", "ATD_BERTH"}
    for row in jit_rows:
        dcsa.PortCallTimestamp(**row)
