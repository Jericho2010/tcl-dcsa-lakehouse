"""TCL Port Call & Reefer Exception Workbench (Databricks Native FastAPI App)."""

from __future__ import annotations

import os
import re
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

APP_DIR = Path(__file__).resolve().parent
STATIC_DIR = APP_DIR / "static"


class TriageRequest(BaseModel):
    """Operator exception triage write-back payload persisted to governance_dcsa."""

    exception_id: str = Field(min_length=1, max_length=128)
    entity_type: Literal["reefer_excursion", "quarantine_record", "port_delay"]
    equipment_or_call_id: str = Field(min_length=1, max_length=64)
    severity: Literal["HIGH", "MEDIUM", "LOW"]
    disposition: Literal[
        "ESCALATE_TERMINAL",
        "REROUTE_INSPECTION",
        "DISMISS_SENSOR_NOISE",
        "MONITOR",
    ]
    operator_note: str = Field(default="", max_length=500)
    triaged_by: str = Field(min_length=1, max_length=120)


class GenieAskRequest(BaseModel):
    """Natural-language operational question routed to Databricks Genie Space."""

    question: str = Field(min_length=2, max_length=500)


class AppRuntimeState:
    """Thread-local demo/live runtime configuration and in-memory triage buffer."""

    def __init__(self) -> None:
        self.triage_log: list[dict[str, Any]] = [
            {
                "triage_id": "tr-demo-0001",
                "triaged_at": "2026-11-20T04:15:00Z",
                "entity_type": "reefer_excursion",
                "equipment_or_call_id": "TCLU1000003",
                "severity": "HIGH",
                "disposition": "ESCALATE_TERMINAL",
                "operator_note": "Alerted Auckland reefer technician for compressor inspection.",
                "triaged_by": "ops.duty.controller",
            }
        ]

    @property
    def catalog(self) -> str:
        raw = os.environ.get("TCL_CATALOG", "workspace").strip() or "workspace"
        if not re.fullmatch(r"[A-Za-z0-9_]+", raw):
            raise ValueError(f"Unsafe catalog identifier: {raw!r}")
        return raw

    @property
    def warehouse_id(self) -> str:
        return os.environ.get("DATABRICKS_WAREHOUSE_ID", "").strip()

    @property
    def genie_space_id(self) -> str:
        return os.environ.get("GENIE_SPACE_ID", "").strip()

    @property
    def demo_mode(self) -> bool:
        forced = os.environ.get("TCL_DEMO_MODE", "").strip().lower()
        if forced in {"1", "true", "yes"}:
            return True
        if forced in {"0", "false", "no"}:
            return False
        return not (
            bool(self.warehouse_id)
            and bool(os.environ.get("DATABRICKS_HOST", "").strip())
        )


STATE = AppRuntimeState()

app = FastAPI(
    title="TCL Port Call & Reefer Exception Workbench",
    version="1.0.0",
    description="DCSA operational KPI cockpit, Silver quarantine inspector, and Genie workbench.",
)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


def _esc(val: str) -> str:
    return val.replace("'", "''")


def _execute_sql(statement: str) -> list[dict[str, Any]]:
    """Run SQL against Databricks SQL Warehouse via databricks-sdk Statement Execution API."""
    from databricks.sdk import WorkspaceClient

    client = WorkspaceClient()
    resp = client.statement_execution.execute_statement(
        warehouse_id=STATE.warehouse_id,
        statement=statement,
        wait_timeout="30s",
    )
    cols = (
        [c.name for c in (resp.manifest.schema.columns or [])]
        if resp.manifest and resp.manifest.schema
        else []
    )
    rows = (resp.result.data_array or []) if resp.result else []
    return [dict(zip(cols, row, strict=False)) for row in rows]


def _demo_kpis() -> dict[str, Any]:
    return {
        "mode": "demo",
        "catalog": STATE.catalog,
        "port_call_kpis": {
            "schedule_reliability_pct": 0.7333,
            "avg_port_turnaround_hours": 20.84,
            "avg_berth_wait_hours": 2.15,
            "total_port_calls": 15,
            "on_time_calls": 11,
        },
        "container_journey_kpis": {
            "cold_chain_excursion_rate_pct": 0.0667,
            "total_container_moves": 30,
            "reefer_excursion_count": 2,
            "avg_dwell_hours": 27.4,
            "active_ebl_count": 14,
        },
        "ports": [
            {
                "un_location_code": "NZAKL",
                "port_name": "Auckland",
                "total_port_calls": 3,
                "on_time_calls": 3,
                "schedule_reliability_pct": 1.0,
                "avg_port_turnaround_hours": 18.2,
                "avg_berth_wait_hours": 1.35,
            },
            {
                "un_location_code": "NZTRG",
                "port_name": "Tauranga",
                "total_port_calls": 3,
                "on_time_calls": 2,
                "schedule_reliability_pct": 0.6667,
                "avg_port_turnaround_hours": 21.6,
                "avg_berth_wait_hours": 2.40,
            },
            {
                "un_location_code": "NZLYT",
                "port_name": "Lyttelton",
                "total_port_calls": 2,
                "on_time_calls": 2,
                "schedule_reliability_pct": 1.0,
                "avg_port_turnaround_hours": 17.9,
                "avg_berth_wait_hours": 1.15,
            },
            {
                "un_location_code": "AUBNE",
                "port_name": "Brisbane",
                "total_port_calls": 2,
                "on_time_calls": 1,
                "schedule_reliability_pct": 0.50,
                "avg_port_turnaround_hours": 24.4,
                "avg_berth_wait_hours": 3.55,
            },
            {
                "un_location_code": "AUSYD",
                "port_name": "Sydney",
                "total_port_calls": 3,
                "on_time_calls": 2,
                "schedule_reliability_pct": 0.6667,
                "avg_port_turnaround_hours": 22.8,
                "avg_berth_wait_hours": 2.75,
            },
            {
                "un_location_code": "FJSVA",
                "port_name": "Suva",
                "total_port_calls": 2,
                "on_time_calls": 1,
                "schedule_reliability_pct": 0.50,
                "avg_port_turnaround_hours": 19.7,
                "avg_berth_wait_hours": 1.90,
            },
        ],
    }


def _demo_exceptions() -> dict[str, Any]:
    return {
        "mode": "demo",
        "catalog": STATE.catalog,
        "reefer_excursions": [
            {
                "reading_id": "rf-TCLU1000003-0007",
                "equipment_reference": "TCLU1000003",
                "recorded_at": "2026-11-03T16:00:00Z",
                "setpoint_temp_c": -18.0,
                "supply_air_temp_c": -11.2,
                "return_air_temp_c": -10.5,
                "power_status": "ALARM",
                "excursion_flag": True,
            },
            {
                "reading_id": "rf-TCLU1000008-0022",
                "equipment_reference": "TCLU1000008",
                "recorded_at": "2026-11-06T08:00:00Z",
                "setpoint_temp_c": -18.0,
                "supply_air_temp_c": -11.2,
                "return_air_temp_c": -10.5,
                "power_status": "ALARM",
                "excursion_flag": True,
            },
        ],
        "quarantine_records": [
            {
                "source_table": "quarantine_reeferpulse_iot_telemetry",
                "record_id": "rf-sensor-fault-minus99",
                "key_reference": "TCLU1000001",
                "observed_value": "supply_air_temp_c=-99.0, return_air_temp_c=-99.0",
                "quarantine_reason": "supply_air_temp_c_min_bound; return_air_temp_c_min_bound",
            },
            {
                "source_table": "quarantine_portgate_equipment_events",
                "record_id": "ee-quarantine-bad-equip",
                "key_reference": "BAD-CONT-99",
                "observed_value": "equipment_reference=BAD-CONT-99",
                "quarantine_reason": "equipment_reference_pattern",
            },
            {
                "source_table": "quarantine_portgate_equipment_events",
                "record_id": "ee-quarantine-bad-locode",
                "key_reference": "12345",
                "observed_value": "un_location_code=12345",
                "quarantine_reason": "un_location_code_pattern",
            },
        ],
    }


@app.get("/", include_in_schema=False)
def serve_index() -> FileResponse:
    """Serve the single-page TCL Port Control Workbench UI."""
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
def health() -> dict[str, Any]:
    """Return runtime status, demo vs live mode, and active UC catalog."""
    return {
        "status": "ok",
        "mode": "demo" if STATE.demo_mode else "live",
        "catalog": STATE.catalog,
    }


@app.get("/api/kpis")
def get_kpis() -> dict[str, Any]:
    """Fetch UC Metric View KPIs using MEASURE(...) SQL or return demo dataset KPIs."""
    if STATE.demo_mode:
        return _demo_kpis()

    c = STATE.catalog
    pc_summary = _execute_sql(
        f"""
        SELECT
            MEASURE(schedule_reliability_pct) AS schedule_reliability_pct,
            MEASURE(avg_port_turnaround_hours) AS avg_port_turnaround_hours,
            MEASURE(avg_berth_wait_hours) AS avg_berth_wait_hours,
            MEASURE(total_port_calls) AS total_port_calls,
            MEASURE(on_time_calls) AS on_time_calls
        FROM {c}.gold_dcsa.mv_port_call_kpis
        """
    )
    cj_summary = _execute_sql(
        f"""
        SELECT
            MEASURE(cold_chain_excursion_rate_pct) AS cold_chain_excursion_rate_pct,
            MEASURE(total_container_moves) AS total_container_moves,
            MEASURE(reefer_excursion_count) AS reefer_excursion_count,
            MEASURE(avg_dwell_hours) AS avg_dwell_hours,
            MEASURE(active_ebl_count) AS active_ebl_count
        FROM {c}.gold_dcsa.mv_container_journey_kpis
        """
    )
    ports = _execute_sql(
        f"""
        SELECT
            un_location_code,
            port_name,
            MEASURE(total_port_calls) AS total_port_calls,
            MEASURE(on_time_calls) AS on_time_calls,
            MEASURE(schedule_reliability_pct) AS schedule_reliability_pct,
            MEASURE(avg_port_turnaround_hours) AS avg_port_turnaround_hours,
            MEASURE(avg_berth_wait_hours) AS avg_berth_wait_hours
        FROM {c}.gold_dcsa.mv_port_call_kpis
        GROUP BY un_location_code, port_name
        ORDER BY total_port_calls DESC
        """
    )
    return {
        "mode": "live",
        "catalog": c,
        "port_call_kpis": pc_summary[0] if pc_summary else {},
        "container_journey_kpis": cj_summary[0] if cj_summary else {},
        "ports": ports,
    }


@app.get("/api/exceptions")
def get_exceptions() -> dict[str, Any]:
    """Fetch active reefer cold-chain excursions and Silver quarantine contract breaches."""
    if STATE.demo_mode:
        return _demo_exceptions()

    c = STATE.catalog
    reefer = _execute_sql(
        f"""
        SELECT reading_id, equipment_reference, recorded_at, setpoint_temp_c,
               supply_air_temp_c, return_air_temp_c, power_status, excursion_flag
        FROM {c}.silver_dcsa.silver_reeferpulse_iot_telemetry
        WHERE excursion_flag = TRUE
        ORDER BY recorded_at DESC
        LIMIT 25
        """
    )
    q_reefer = _execute_sql(
        f"""
        SELECT 'quarantine_reeferpulse_iot_telemetry' AS source_table,
               reading_id AS record_id,
               equipment_reference AS key_reference,
               CONCAT(
                   'supply=', supply_air_temp_c, ', return=', return_air_temp_c
               ) AS observed_value,
               quarantine_reason
        FROM {c}.silver_dcsa.quarantine_reeferpulse_iot_telemetry
        ORDER BY quarantined_at DESC
        LIMIT 25
        """
    )
    q_equip = _execute_sql(
        f"""
        SELECT 'quarantine_portgate_equipment_events' AS source_table,
               event_id AS record_id,
               equipment_reference AS key_reference,
               CONCAT('un_location_code=', un_location_code) AS observed_value,
               quarantine_reason
        FROM {c}.silver_dcsa.quarantine_portgate_equipment_events
        ORDER BY quarantined_at DESC
        LIMIT 25
        """
    )
    return {
        "mode": "live",
        "catalog": c,
        "reefer_excursions": reefer,
        "quarantine_records": q_reefer + q_equip,
    }


@app.get("/api/triage")
def list_triage() -> dict[str, Any]:
    """Return recent operator triage records from governance_dcsa or demo buffer."""
    if STATE.demo_mode:
        return {"mode": "demo", "catalog": STATE.catalog, "items": list(reversed(STATE.triage_log))}

    c = STATE.catalog
    rows = _execute_sql(
        f"""
        SELECT triage_id, triaged_at, entity_type, equipment_or_call_id,
               severity, disposition, operator_note, triaged_by
        FROM {c}.governance_dcsa.exception_triage_log
        ORDER BY triaged_at DESC
        LIMIT 50
        """
    )
    return {"mode": "live", "catalog": c, "items": rows}


@app.post("/api/triage", status_code=201)
def create_triage(payload: TriageRequest) -> dict[str, Any]:
    """Persist an exception triage decision to governance_dcsa.exception_triage_log."""
    triage_id = f"tr-{uuid.uuid4().hex[:10]}"
    triaged_at = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    record = {
        "triage_id": triage_id,
        "triaged_at": triaged_at,
        "exception_id": payload.exception_id,
        "entity_type": payload.entity_type,
        "equipment_or_call_id": payload.equipment_or_call_id,
        "severity": payload.severity,
        "disposition": payload.disposition,
        "operator_note": payload.operator_note,
        "triaged_by": payload.triaged_by,
    }

    if STATE.demo_mode:
        STATE.triage_log.append(record)
        return {"status": "persisted", "mode": "demo", "record": record}

    c = STATE.catalog
    _execute_sql(
        f"""
        INSERT INTO {c}.governance_dcsa.exception_triage_log
            (triage_id, triaged_at, entity_type, equipment_or_call_id,
             severity, disposition, operator_note, triaged_by)
        VALUES (
            '{_esc(triage_id)}',
            TIMESTAMP '{_esc(triaged_at)}',
            '{_esc(payload.entity_type)}',
            '{_esc(payload.equipment_or_call_id)}',
            '{_esc(payload.severity)}',
            '{_esc(payload.disposition)}',
            '{_esc(payload.operator_note)}',
            '{_esc(payload.triaged_by)}'
        )
        """
    )
    return {"status": "persisted", "mode": "live", "record": record}


@app.post("/api/genie/ask")
def ask_genie(payload: GenieAskRequest) -> dict[str, Any]:
    """Route natural-language questions to Databricks Genie Space or demo responder."""
    if not STATE.demo_mode and STATE.genie_space_id:
        from databricks.sdk import WorkspaceClient

        client = WorkspaceClient()
        msg = client.genie.start_conversation_and_wait(
            space_id=STATE.genie_space_id,
            content=payload.question,
        )
        answer_texts = [
            att.text.content
            for att in (msg.attachments or [])
            if getattr(att, "text", None) and getattr(att.text, "content", None)
        ]
        sql_texts = [
            att.query.query
            for att in (msg.attachments or [])
            if getattr(att, "query", None) and getattr(att.query, "query", None)
        ]
        return {
            "mode": "live",
            "question": payload.question,
            "answer": "\n".join(answer_texts) or "Genie completed query execution.",
            "generated_sql": sql_texts[0] if sql_texts else None,
        }

    q = payload.question.lower()
    c = STATE.catalog
    if any(k in q for k in ("reefer", "excursion", "cold", "temp", "-99")):
        return {
            "mode": "demo",
            "question": payload.question,
            "answer": (
                "Reefer cold-chain excursion rate is 6.7% (2 excursion moves of 30 total: "
                "TCLU1000003 and TCLU1000008 spiked to -11.2C against a -18.0C setpoint). "
                "The -99.0C sensor fault (rf-sensor-fault-minus99) was dropped by Silver LinkML "
                "expectations and isolated into silver_dcsa.quarantine_reeferpulse_iot_telemetry."
            ),
            "generated_sql": (
                f"SELECT un_location_code, MEASURE(cold_chain_excursion_rate_pct), "
                f"MEASURE(reefer_excursion_count) FROM {c}.gold_dcsa.mv_container_journey_kpis "
                f"GROUP BY un_location_code;"
            ),
        }
    return {
        "mode": "demo",
        "question": payload.question,
        "answer": (
            "Fleet-wide DCSA schedule reliability is 73.3% (11 of 15 port calls on time) with an "
            "average port turnaround of 20.84 hours and 2.15 hours average berth wait. Auckland "
            "(NZAKL) and Lyttelton (NZLYT) lead at 100.0% reliability."
        ),
        "generated_sql": (
            f"SELECT un_location_code, port_name, MEASURE(schedule_reliability_pct), "
            f"MEASURE(avg_port_turnaround_hours) FROM {c}.gold_dcsa.mv_port_call_kpis "
            f"GROUP BY un_location_code, port_name ORDER BY MEASURE(schedule_reliability_pct) DESC;"
        ),
    }
