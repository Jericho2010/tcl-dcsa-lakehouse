"""Unit tests for LinkML DCSA compilation into Pydantic, JSON Schema, UC, LDP, and ODCS."""

from __future__ import annotations

import importlib.util
import json
from datetime import date, datetime
from pathlib import Path

import pytest
from linkml_runtime.utils.schemaview import SchemaView
from pydantic import ValidationError

from tcl_compiler.compile_dcsa import (
    CONTRACT_SPECS,
    ENTERPRISE_SCHEMA_PATH,
    PROJECT_ROOT,
    compile_all,
)


def _load_generated_pydantic(module_path: Path):
    spec = importlib.util.spec_from_file_location("generated_dcsa_models", module_path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_compile_all_generates_expected_artifacts_without_dev_prefix() -> None:
    """Compiler emits Pydantic, JSON Schema, UC comments, LDP rules, and 5 ODCS contracts."""
    outputs = compile_all()
    assert len(CONTRACT_SPECS) == 5

    expected_paths = [
        PROJECT_ROOT / "generated" / "pydantic" / "dcsa_models.py",
        PROJECT_ROOT / "generated" / "jsonschema" / "dcsa_schema.json",
        PROJECT_ROOT / "generated" / "uc_comments.json",
        PROJECT_ROOT / "generated" / "ldp_expectations.json",
        PROJECT_ROOT / "contracts" / "odcs" / "portgate_tos_events.odcs.yaml",
        PROJECT_ROOT / "contracts" / "odcs" / "reeferpulse_iot_telemetry.odcs.yaml",
        PROJECT_ROOT / "contracts" / "odcs" / "voyagecore_ebl_bookings.odcs.yaml",
        PROJECT_ROOT / "contracts" / "odcs" / "harboursync_jit_port_calls.odcs.yaml",
        PROJECT_ROOT / "contracts" / "odcs" / "gold_dcsa_port_call_kpis.odcs.yaml",
    ]
    for path in expected_paths:
        assert path.is_file(), f"Missing generated file: {path}"
        assert path in outputs.values()

    uc_comments = json.loads(
        (PROJECT_ROOT / "generated" / "uc_comments.json").read_text(encoding="utf-8")
    )
    assert "silver_dcsa.silver_reeferpulse_iot_telemetry" in uc_comments
    assert "gold_dcsa.gold_port_call_performance" in uc_comments
    assert all("dev_" not in tbl for tbl in uc_comments)


def test_generated_pydantic_models_enforce_dcsa_patterns_and_physical_bounds() -> None:
    """Generated Pydantic models validate valid records and reject UN/LOCODE & -99C faults."""
    compile_all()
    dcsa = _load_generated_pydantic(PROJECT_ROOT / "generated" / "pydantic" / "dcsa_models.py")

    valid_equip = dcsa.EquipmentEvent(
        event_id="evt-001",
        event_created_date_time=datetime(2026, 11, 20, 10, 0, 0),
        event_date_time=datetime(2026, 11, 20, 9, 55, 0),
        event_classifier_code="ACT",
        source_system="portgate_tos",
        equipment_event_type_code="LOAD",
        equipment_reference="TCLU1234567",
        iso_equipment_code="45R1",
        empty_indicator_code="LADEN",
        un_location_code="NZAKL",
    )
    assert valid_equip.un_location_code == "NZAKL"

    with pytest.raises(ValidationError):
        dcsa.EquipmentEvent(
            event_id="evt-002",
            event_created_date_time=datetime(2026, 11, 20, 10, 0, 0),
            event_date_time=datetime(2026, 11, 20, 9, 55, 0),
            event_classifier_code="ACT",
            source_system="portgate_tos",
            equipment_event_type_code="LOAD",
            equipment_reference="BAD123",
            iso_equipment_code="45R1",
            empty_indicator_code="LADEN",
            un_location_code="12345",
        )

    valid_reefer = dcsa.ReeferTelemetryReading(
        reading_id="rf-001",
        equipment_reference="TCLU7654321",
        recorded_at=datetime(2026, 11, 20, 10, 5, 0),
        setpoint_temp_c=-18.5,
        supply_air_temp_c=-18.2,
        return_air_temp_c=-17.9,
        relative_humidity_pct=65.0,
        power_status="ON",
        latitude=-36.8485,
        longitude=174.7633,
        excursion_flag=False,
    )
    assert valid_reefer.setpoint_temp_c == -18.5

    # Sensor fault -99.0 C must fail LinkML-compiled Pydantic bounds
    with pytest.raises(ValidationError):
        dcsa.ReeferTelemetryReading(
            reading_id="rf-fault",
            equipment_reference="TCLU7654321",
            recorded_at=datetime(2026, 11, 20, 10, 10, 0),
            setpoint_temp_c=-18.5,
            supply_air_temp_c=-99.0,
            return_air_temp_c=-17.9,
            relative_humidity_pct=65.0,
            power_status="ALARM",
            latitude=-36.8485,
            longitude=174.7633,
            excursion_flag=True,
        )

    valid_ebl = dcsa.TransportDocument(
        transport_document_reference="TCLBL20260001",
        carrier_booking_reference="BKG20260001",
        document_status="ISSU",
        issue_date=date(2026, 11, 20),
        shipper_name="Tasman Kiwifruit Exporters Ltd",
        shipper_contact_email="logistics@tasman-exports.example",
        consignee_name="Pacific Cold Storage Pty Ltd",
        port_of_loading="NZAKL",
        port_of_discharge="AUSYD",
        vessel_imo_number="9876543",
    )
    assert valid_ebl.port_of_loading == "NZAKL"


def test_uc_comments_pii_and_ldp_expectations_match_schemaview() -> None:
    """PII governance annotations and Spark SQL expectations stay in sync with LinkML SchemaView."""
    compile_all()
    sv = SchemaView(str(ENTERPRISE_SCHEMA_PATH))
    uc_comments = json.loads(
        (PROJECT_ROOT / "generated" / "uc_comments.json").read_text(encoding="utf-8")
    )
    ldp = json.loads(
        (PROJECT_ROOT / "generated" / "ldp_expectations.json").read_text(encoding="utf-8")
    )

    td_uc = uc_comments["silver_dcsa.silver_dcsa_ebl_current"]
    assert set(td_uc["pii_columns"]) == {"shipper_contact_email", "consignee_name"}
    assert td_uc["columns"]["shipper_contact_email"]["classification"] == "confidential"
    assert "pii" in td_uc["columns"]["consignee_name"]["tags"]

    ebl_rules = {
        r["name"]: r["sql"] for r in ldp["silver_dcsa.silver_dcsa_ebl_current"]["rules"]
    }
    assert "\\\\s" in ebl_rules["shipper_contact_email_pattern"]
    assert "\\\\." in ebl_rules["shipper_contact_email_pattern"]

    reefer_rules = {
        r["name"]: r["sql"]
        for r in ldp["silver_dcsa.silver_reeferpulse_iot_telemetry"]["rules"]
    }
    assert "supply_air_temp_c >= -45.0" in reefer_rules["supply_air_temp_c_min_bound"]
    assert (
        "equipment_reference RLIKE '^[A-Z]{4}[0-9]{7}$'"
        in reefer_rules["equipment_reference_pattern"]
    )
    assert "'ON'" in reefer_rules["power_status_enum_values"]

    # Every class mapped into contracts retains the exact slot count from SchemaView
    for tbl_meta in uc_comments.values():
        cls_slots = {s.name for s in sv.class_induced_slots(tbl_meta["class_name"])}
        assert set(tbl_meta["columns"].keys()) == cls_slots
