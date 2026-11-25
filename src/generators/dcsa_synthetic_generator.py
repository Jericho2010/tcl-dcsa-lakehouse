"""Deterministic synthetic DCSA payload generator across all 4 maritime operational sources."""

from __future__ import annotations

import argparse
import json
import random
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any


def _resolve_project_root() -> Path:
    start = Path(__file__).resolve().parent if "__file__" in globals() else Path.cwd().resolve()
    for candidate in (start, *start.parents):
        if (candidate / "src").is_dir() and (candidate / "contracts").is_dir():
            return candidate
    return Path.cwd().resolve()


PROJECT_ROOT = _resolve_project_root()
DEFAULT_LOCAL_LANDING = PROJECT_ROOT / "data" / "sample_landing"

PORTS: tuple[dict[str, Any], ...] = (
    {"un_location_code": "NZAKL", "port_name": "Auckland", "lat": -36.8485, "lon": 174.7633},
    {"un_location_code": "NZTRG", "port_name": "Tauranga", "lat": -37.6531, "lon": 176.1836},
    {"un_location_code": "NZLYT", "port_name": "Lyttelton", "lat": -43.6050, "lon": 172.7194},
    {"un_location_code": "AUBNE", "port_name": "Brisbane", "lat": -27.3842, "lon": 153.1731},
    {"un_location_code": "AUSYD", "port_name": "Sydney", "lat": -33.9718, "lon": 151.2131},
    {"un_location_code": "FJSVA", "port_name": "Suva", "lat": -18.1333, "lon": 178.4250},
)

VESSELS: tuple[dict[str, str], ...] = (
    {"vessel_imo_number": "9810001", "vessel_name": "MV TASMAN HORIZON"},
    {"vessel_imo_number": "9810002", "vessel_name": "MV AOTEAROA STAR"},
    {"vessel_imo_number": "9810003", "vessel_name": "MV CORAL TRADER"},
)

EQUIPMENT_POOL: tuple[dict[str, Any], ...] = tuple(
    {
        "equipment_reference": f"TCLU10000{idx:02d}",
        "iso_equipment_code": "45R1" if idx <= 12 else "42G1",
        "is_reefer": idx <= 12,
    }
    for idx in range(1, 19)
)


def _iso_utc(dt: datetime) -> str:
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _write_jsonl(path: Path, records: list[dict[str, Any]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(rec, separators=(",", ":")) for rec in records]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return path


def _build_port_calls(rng: random.Random) -> list[dict[str, Any]]:
    """Build synchronized OVS schedule + 5-phase JIT port calls across NZ/AU/Pacific."""
    base_time = datetime(2026, 11, 1, 6, 0, tzinfo=UTC)
    calls: list[dict[str, Any]] = []
    idx = 1
    for day_offset in range(0, 10, 2):
        for v_idx, vessel in enumerate(VESSELS):
            port = PORTS[(day_offset + v_idx) % len(PORTS)]
            planned_arr = base_time + timedelta(days=day_offset, hours=v_idx * 8)
            planned_dep = planned_arr + timedelta(hours=22)
            # Mix on-time calls (<2h delay) and delayed calls (4-8h delay)
            is_delayed = (idx % 4) == 0
            arrival_delay_h = rng.uniform(4.5, 8.5) if is_delayed else rng.uniform(-0.5, 1.4)
            ata_pbp = planned_arr + timedelta(hours=arrival_delay_h)
            berth_wait_h = round(rng.uniform(2.5, 6.0) if is_delayed else rng.uniform(0.8, 2.0), 2)
            etb_berth = ata_pbp + timedelta(hours=1.2)
            atb_berth = ata_pbp + timedelta(hours=berth_wait_h)
            ops_hours = round(rng.uniform(14.0, 24.0), 2)
            atd_berth = atb_berth + timedelta(hours=ops_hours)

            calls.append(
                {
                    "port_call_id": f"PC-2026-{idx:04d}",
                    "schedule_id": f"SCH-2026-{idx:04d}",
                    "carrier_service_code": "TASMAN-EXP",
                    "carrier_voyage_number": f"2611{v_idx + 1}{'N' if idx % 2 else 'S'}",
                    "vessel_imo_number": vessel["vessel_imo_number"],
                    "vessel_name": vessel["vessel_name"],
                    "un_location_code": port["un_location_code"],
                    "port_name": port["port_name"],
                    "lat": port["lat"],
                    "lon": port["lon"],
                    "planned_arr": planned_arr,
                    "planned_dep": planned_dep,
                    "phases": {
                        "ETA_PBP": planned_arr - timedelta(minutes=15),
                        "ATA_PBP": ata_pbp,
                        "ETB_BERTH": etb_berth,
                        "ATB_BERTH": atb_berth,
                        "ATD_BERTH": atd_berth,
                    },
                    "delay_reason_code": "WEA" if is_delayed else None,
                }
            )
            idx += 1
    return calls


def _generate_portgate(
    calls: list[dict[str, Any]], rng: random.Random
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Generate PortGate TOS EquipmentEvent and TransportEvent rows plus bad quarantine cases."""
    equipment_events: list[dict[str, Any]] = []
    transport_events: list[dict[str, Any]] = []

    for c_idx, call in enumerate(calls):
        for phase_type, phase_key in (("ARRI", "ATB_BERTH"), ("DEPA", "ATD_BERTH")):
            ts = call["phases"][phase_key]
            transport_events.append(
                {
                    "event_id": f"te-{call['port_call_id']}-{phase_type}",
                    "event_created_date_time": _iso_utc(ts + timedelta(minutes=2)),
                    "event_date_time": _iso_utc(ts),
                    "event_classifier_code": "ACT",
                    "source_system": "portgate_tos",
                    "transport_event_type_code": phase_type,
                    "transport_call_id": call["port_call_id"],
                    "vessel_imo_number": call["vessel_imo_number"],
                    "carrier_voyage_number": call["carrier_voyage_number"],
                    "un_location_code": call["un_location_code"],
                    "delay_reason_code": call["delay_reason_code"],
                    "change_remark": "Berth operations completed" if phase_type == "DEPA" else None,
                }
            )

        # Pair 2 containers per port call with GTIN/LOAD or DISC/GTOT pairs for dwell metrics
        for offset in range(2):
            equip = EQUIPMENT_POOL[(c_idx * 2 + offset) % len(EQUIPMENT_POOL)]
            in_ts = call["phases"]["ATB_BERTH"] + timedelta(hours=offset + 1)
            out_ts = in_ts + timedelta(hours=round(rng.uniform(12.0, 46.0), 2))
            for seq, (ev_type, ev_ts) in enumerate((("DISC", in_ts), ("GTOT", out_ts)), start=1):
                event_ref = equip["equipment_reference"]
                equipment_events.append(
                    {
                        "event_id": f"ee-{call['port_call_id']}-{event_ref}-{seq}",
                        "event_created_date_time": _iso_utc(ev_ts + timedelta(minutes=1)),
                        "event_date_time": _iso_utc(ev_ts),
                        "event_classifier_code": "ACT",
                        "source_system": "portgate_tos",
                        "equipment_event_type_code": ev_type,
                        "equipment_reference": equip["equipment_reference"],
                        "iso_equipment_code": equip["iso_equipment_code"],
                        "empty_indicator_code": "LADEN",
                        "un_location_code": call["un_location_code"],
                        "facility_code": f"{call['un_location_code']}TM1",
                        "transport_call_id": call["port_call_id"],
                        "carrier_voyage_number": call["carrier_voyage_number"],
                    }
                )

    # Deliberate contract-violating rows to prove Silver quarantine filtering
    bad_ts = datetime(2026, 11, 5, 12, 0, tzinfo=UTC)
    equipment_events.append(
        {
            "event_id": "ee-quarantine-bad-equip",
            "event_created_date_time": _iso_utc(bad_ts),
            "event_date_time": _iso_utc(bad_ts),
            "event_classifier_code": "ACT",
            "source_system": "portgate_tos",
            "equipment_event_type_code": "LOAD",
            "equipment_reference": "BAD-CONT-99",
            "iso_equipment_code": "45R1",
            "empty_indicator_code": "LADEN",
            "un_location_code": "NZAKL",
            "facility_code": "NZAKLTM1",
            "transport_call_id": calls[0]["port_call_id"],
            "carrier_voyage_number": calls[0]["carrier_voyage_number"],
        }
    )
    equipment_events.append(
        {
            "event_id": "ee-quarantine-bad-locode",
            "event_created_date_time": _iso_utc(bad_ts),
            "event_date_time": _iso_utc(bad_ts),
            "event_classifier_code": "ACT",
            "source_system": "portgate_tos",
            "equipment_event_type_code": "DISC",
            "equipment_reference": "TCLU1000001",
            "iso_equipment_code": "45R1",
            "empty_indicator_code": "LADEN",
            "un_location_code": "12345",
            "facility_code": "NZAKLTM1",
            "transport_call_id": calls[0]["port_call_id"],
            "carrier_voyage_number": calls[0]["carrier_voyage_number"],
        }
    )
    return equipment_events, transport_events


def _generate_reeferpulse(
    calls: list[dict[str, Any]], rng: random.Random
) -> list[dict[str, Any]]:
    """Generate Kafka-wrapped ReeferPulse IoT telemetry (normal, excursions, and -99C fault)."""
    envelopes: list[dict[str, Any]] = []
    reefers = [e for e in EQUIPMENT_POOL if e["is_reefer"]]
    offset = 0

    for idx, equip in enumerate(reefers):
        call = calls[idx % len(calls)]
        base_ts = call["phases"]["ATB_BERTH"]
        for sample_idx in range(3):
            ts = base_ts + timedelta(hours=sample_idx * 4)
            is_excursion = equip["equipment_reference"] in {"TCLU1000003", "TCLU1000008"} and (
                sample_idx == 1
            )
            setpoint = -18.0
            supply = -11.2 if is_excursion else round(setpoint + rng.uniform(-0.4, 0.6), 2)
            ret_air = -10.5 if is_excursion else round(supply + rng.uniform(0.3, 0.8), 2)
            power = "ALARM" if is_excursion else "ON"

            payload = {
                "reading_id": f"rf-{equip['equipment_reference']}-{offset:04d}",
                "equipment_reference": equip["equipment_reference"],
                "recorded_at": _iso_utc(ts),
                "setpoint_temp_c": setpoint,
                "supply_air_temp_c": supply,
                "return_air_temp_c": ret_air,
                "relative_humidity_pct": round(rng.uniform(60.0, 75.0), 1),
                "power_status": power,
                "latitude": call["lat"],
                "longitude": call["lon"],
                "excursion_flag": is_excursion,
            }
            envelopes.append(
                {
                    "topic": "tcl.reeferpulse.telemetry.v3",
                    "partition": idx % 3,
                    "offset": offset,
                    "timestamp": _iso_utc(ts + timedelta(seconds=3)),
                    "key": equip["equipment_reference"],
                    "value": payload,
                }
            )
            offset += 1

    # Deliberate -99.0 C sensor fault to prove Silver quarantine rejects out-of-range telemetry
    fault_ts = calls[0]["phases"]["ATB_BERTH"] + timedelta(hours=6)
    envelopes.append(
        {
            "topic": "tcl.reeferpulse.telemetry.v3",
            "partition": 0,
            "offset": offset,
            "timestamp": _iso_utc(fault_ts + timedelta(seconds=2)),
            "key": "TCLU1000001",
            "value": {
                "reading_id": "rf-sensor-fault-minus99",
                "equipment_reference": "TCLU1000001",
                "recorded_at": _iso_utc(fault_ts),
                "setpoint_temp_c": -18.0,
                "supply_air_temp_c": -99.0,
                "return_air_temp_c": -99.0,
                "relative_humidity_pct": 65.0,
                "power_status": "ALARM",
                "latitude": calls[0]["lat"],
                "longitude": calls[0]["lon"],
                "excursion_flag": True,
            },
        }
    )
    return envelopes


def _generate_voyagecore_cdc(calls: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Generate VoyageCore CDC feeds with INSERT/UPDATE/DELETE and out-of-order updates."""
    transport_docs: list[dict[str, Any]] = []
    shipment_events: list[dict[str, Any]] = []
    bookings: list[dict[str, Any]] = []
    carrier_schedules: list[dict[str, Any]] = []

    for idx, call in enumerate(calls, start=1):
        ref = f"TCLBL2026{idx:04d}"
        bkg_ref = f"BKG2026{idx:04d}"
        pol = call["un_location_code"]
        pod = PORTS[(idx + 2) % len(PORTS)]["un_location_code"]
        t0 = call["planned_arr"] - timedelta(days=3)

        bookings.append(
            {
                "cdc_operation": "INSERT",
                "sequence_ts": _iso_utc(t0),
                "carrier_booking_reference": bkg_ref,
                "booking_status": "CONF",
                "booking_created_at": _iso_utc(t0),
                "place_of_receipt": pol,
                "place_of_delivery": pod,
                "teu_count": 2 + (idx % 4),
                "reefer_required": True,
            }
        )
        carrier_schedules.append(
            {
                "cdc_operation": "INSERT",
                "sequence_ts": _iso_utc(t0),
                "schedule_id": call["schedule_id"],
                "vessel_imo_number": call["vessel_imo_number"],
                "vessel_name": call["vessel_name"],
                "carrier_service_code": call["carrier_service_code"],
                "carrier_voyage_number": call["carrier_voyage_number"],
                "un_location_code": pol,
                "planned_arrival_utc": _iso_utc(call["planned_arr"]),
                "planned_departure_utc": _iso_utc(call["planned_dep"]),
            }
        )

        # Standard lifecycle INSERT -> UPDATE (DRFT -> ISSU)
        base_doc = {
            "transport_document_reference": ref,
            "carrier_booking_reference": bkg_ref,
            "issue_date": t0.strftime("%Y-%m-%d"),
            "shipper_name": f"Aotearoa Produce Exporter {idx} Ltd",
            "shipper_contact_email": f"export.desk{idx}@tasman-shipper.example",
            "consignee_name": f"Pacific Cold Logistics {idx} Pty Ltd",
            "port_of_loading": pol,
            "port_of_discharge": pod,
            "vessel_imo_number": call["vessel_imo_number"],
        }
        transport_docs.append(
            {
                **base_doc,
                "cdc_operation": "INSERT",
                "sequence_ts": _iso_utc(t0),
                "document_status": "DRFT",
            }
        )
        transport_docs.append(
            {
                **base_doc,
                "cdc_operation": "UPDATE",
                "sequence_ts": _iso_utc(t0 + timedelta(hours=6)),
                "document_status": "ISSU",
            }
        )
        shipment_events.append(
            {
                "cdc_operation": "INSERT",
                "sequence_ts": _iso_utc(t0 + timedelta(hours=6)),
                "event_id": f"se-{ref}-issu",
                "event_created_date_time": _iso_utc(t0 + timedelta(hours=6)),
                "event_date_time": _iso_utc(t0 + timedelta(hours=6)),
                "event_classifier_code": "ACT",
                "source_system": "voyagecore_ebl",
                "shipment_event_type_code": "ISSU",
                "document_type_code": "TRD",
                "document_id": ref,
                "reason": "eBL issued upon carrier cargo verification",
            }
        )

    # Deliberate late-arriving update for TCLBL20260001 with older sequence_ts (SCD1/2 test)
    first_call = calls[0]
    late_base_ts = first_call["planned_arr"] - timedelta(days=3)
    transport_docs.append(
        {
            "cdc_operation": "UPDATE",
            "sequence_ts": _iso_utc(late_base_ts + timedelta(hours=2)),
            "transport_document_reference": "TCLBL20260001",
            "carrier_booking_reference": "BKG20260001",
            "document_status": "APPR",
            "issue_date": late_base_ts.strftime("%Y-%m-%d"),
            "shipper_name": "Aotearoa Produce Exporter 1 Ltd",
            "shipper_contact_email": "export.desk1@tasman-shipper.example",
            "consignee_name": "Pacific Cold Logistics 1 Pty Ltd",
            "port_of_loading": first_call["un_location_code"],
            "port_of_discharge": PORTS[3]["un_location_code"],
            "vessel_imo_number": first_call["vessel_imo_number"],
        }
    )

    # Explicit DELETE CDC record for last cancelled draft eBL
    cancelled_ts = calls[-1]["planned_arr"] - timedelta(days=2)
    transport_docs.append(
        {
            "cdc_operation": "DELETE",
            "sequence_ts": _iso_utc(cancelled_ts + timedelta(hours=12)),
            "transport_document_reference": f"TCLBL2026{len(calls):04d}",
            "carrier_booking_reference": f"BKG2026{len(calls):04d}",
            "document_status": "VOID",
            "issue_date": cancelled_ts.strftime("%Y-%m-%d"),
            "shipper_name": f"Aotearoa Produce Exporter {len(calls)} Ltd",
            "shipper_contact_email": f"export.desk{len(calls)}@tasman-shipper.example",
            "consignee_name": f"Pacific Cold Logistics {len(calls)} Pty Ltd",
            "port_of_loading": calls[-1]["un_location_code"],
            "port_of_discharge": PORTS[0]["un_location_code"],
            "vessel_imo_number": calls[-1]["vessel_imo_number"],
        }
    )

    return {
        "transport_documents": transport_docs,
        "shipment_events": shipment_events,
        "bookings": bookings,
        "carrier_schedules": carrier_schedules,
    }


def _generate_harboursync_jit(calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Generate 5-phase DCSA JIT v1 port call timestamp events per vessel call."""
    jit_events: list[dict[str, Any]] = []
    for call in calls:
        for phase_code in ("ETA_PBP", "ATA_PBP", "ETB_BERTH", "ATB_BERTH", "ATD_BERTH"):
            ts = call["phases"][phase_code]
            classifier = "EST" if phase_code.startswith("ET") else "ACT"
            jit_events.append(
                {
                    "event_id": f"jit-{call['port_call_id']}-{phase_code}",
                    "event_created_date_time": _iso_utc(ts + timedelta(minutes=1)),
                    "event_date_time": _iso_utc(ts),
                    "event_classifier_code": classifier,
                    "source_system": "harboursync_port_api",
                    "port_call_id": call["port_call_id"],
                    "vessel_imo_number": call["vessel_imo_number"],
                    "carrier_voyage_number": call["carrier_voyage_number"],
                    "un_location_code": call["un_location_code"],
                    "jit_phase_code": phase_code,
                    "terminal_code": f"{call['un_location_code']}TM1",
                    "berth_code": "B04",
                    "delay_reason_code": call["delay_reason_code"],
                }
            )
    return jit_events


def generate_all(
    output_root: Path | None = None,
    catalog: str | None = None,
    seed: int = 42,
    sources: set[str] | None = None,
) -> dict[str, Path]:
    """Generate deterministic DCSA datasets for all 4 sources into local dir or UC Volumes."""
    if catalog:
        root = Path(f"/Volumes/{catalog}/bronze_dcsa")
    else:
        root = output_root or DEFAULT_LOCAL_LANDING

    active = sources or {"portgate_tos", "reeferpulse_iot", "voyagecore_cdc", "harboursync_jit"}
    rng = random.Random(seed)
    calls = _build_port_calls(rng)
    written: dict[str, Path] = {}

    if "portgate_tos" in active:
        eq_events, tr_events = _generate_portgate(calls, rng)
        written["portgate_equipment_events"] = _write_jsonl(
            root / "landing_portgate_tos" / "equipment_events" / "events.jsonl", eq_events
        )
        written["portgate_transport_events"] = _write_jsonl(
            root / "landing_portgate_tos" / "transport_events" / "events.jsonl", tr_events
        )

    if "reeferpulse_iot" in active:
        reefer_envelopes = _generate_reeferpulse(calls, rng)
        written["reeferpulse_iot_telemetry"] = _write_jsonl(
            root / "landing_reeferpulse_iot" / "telemetry.jsonl", reefer_envelopes
        )

    if "voyagecore_cdc" in active:
        cdc_tables = _generate_voyagecore_cdc(calls)
        for tbl_name, rows in cdc_tables.items():
            written[f"voyagecore_{tbl_name}"] = _write_jsonl(
                root / "landing_voyagecore_cdc" / tbl_name / "cdc.jsonl", rows
            )

    if "harboursync_jit" in active:
        jit_events = _generate_harboursync_jit(calls)
        written["harboursync_jit_port_calls"] = _write_jsonl(
            root / "landing_harboursync_jit" / "port_call_timestamps.jsonl", jit_events
        )

    return written


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for local or Databricks UC Volume synthetic DCSA generation."""
    parser = argparse.ArgumentParser(
        description="Generate synthetic TCL DCSA operational payloads."
    )
    parser.add_argument(
        "--output-dir", type=Path, default=None, help="Local output root directory."
    )
    parser.add_argument("--catalog", type=str, default=None, help="Target UC catalog for /Volumes.")
    parser.add_argument("--seed", type=int, default=42, help="Deterministic RNG seed.")
    args = parser.parse_args(argv)

    written = generate_all(output_root=args.output_dir, catalog=args.catalog, seed=args.seed)
    for key, path in written.items():
        print(f"[dcsa_synthetic_generator] {key}: {path}")
    return 0


if __name__ == "__main__":
    exit_code = main()
    if exit_code != 0:
        raise SystemExit(exit_code)
