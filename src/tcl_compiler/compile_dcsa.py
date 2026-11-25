"""Compile LinkML DCSA models into Pydantic, JSON Schema, UC comments, LDP rules, and ODCS."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from linkml.generators.jsonschemagen import JsonSchemaGenerator
from linkml.generators.pydanticgen import PydanticGenerator
from linkml_runtime.linkml_model.meta import SlotDefinition
from linkml_runtime.utils.schemaview import SchemaView

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
ENTERPRISE_SCHEMA_PATH = PROJECT_ROOT / "models" / "linkml" / "dcsa" / "dcsa_enterprise.yaml"
GENERATED_DIR = PROJECT_ROOT / "generated"
CONTRACTS_ODCS_DIR = PROJECT_ROOT / "contracts" / "odcs"


@dataclass(frozen=True)
class ContractSpec:
    """Declarative mapping from LinkML domain classes to an ODCS v3 contract."""

    filename: str
    contract_id: str
    name: str
    schema_name: str
    purpose: str
    sla_freshness: str
    class_tables: tuple[tuple[str, str], ...]


CONTRACT_SPECS: tuple[ContractSpec, ...] = (
    ContractSpec(
        filename="portgate_tos_events.odcs.yaml",
        contract_id="tcl-portgate-tos-events",
        name="TCL PortGate TOS Equipment and Transport Events",
        schema_name="silver_dcsa",
        purpose=(
            "Governed DCSA Track & Trace v3 equipment handling and vessel transport events "
            "curated in Silver from PortGate TOS."
        ),
        sla_freshness="15",
        class_tables=(
            ("EquipmentEvent", "silver_portgate_equipment_events"),
            ("TransportEvent", "silver_portgate_transport_events"),
        ),
    ),
    ContractSpec(
        filename="reeferpulse_iot_telemetry.odcs.yaml",
        contract_id="tcl-reeferpulse-iot-telemetry",
        name="TCL ReeferPulse IoT Container Telemetry",
        schema_name="silver_dcsa",
        purpose=(
            "Governed DCSA T&T v3.0.0 refrigerated container telemetry stream curated in Silver "
            "enforcing physical thermal and GPS bounds."
        ),
        sla_freshness="5",
        class_tables=(("ReeferTelemetryReading", "silver_reeferpulse_iot_telemetry"),),
    ),
    ContractSpec(
        filename="voyagecore_ebl_bookings.odcs.yaml",
        contract_id="tcl-voyagecore-ebl-bookings",
        name="TCL VoyageCore eBL, Bookings and Carrier Schedules",
        purpose=(
            "Governed DCSA eBL v3 transport documents (SCD Type 1 current view with PII "
            "governance), bookings, and OVS carrier schedules curated in Silver."
        ),
        schema_name="silver_dcsa",
        sla_freshness="30",
        class_tables=(
            ("TransportDocument", "silver_dcsa_ebl_current"),
            ("BookingRecord", "silver_voyagecore_bookings"),
            ("CarrierSchedule", "silver_voyagecore_carrier_schedules"),
        ),
    ),
    ContractSpec(
        filename="harboursync_jit_port_calls.odcs.yaml",
        contract_id="tcl-harboursync-jit-port-calls",
        name="TCL HarbourSync JIT Port Call Timestamps",
        schema_name="silver_dcsa",
        purpose=(
            "Governed DCSA Just-In-Time (JIT) v1.x five-phase vessel port call arrival "
            "and berth timestamps curated in Silver."
        ),
        sla_freshness="15",
        class_tables=(("PortCallTimestamp", "silver_harboursync_jit_port_calls"),),
    ),
    ContractSpec(
        filename="gold_dcsa_port_call_kpis.odcs.yaml",
        contract_id="tcl-gold-dcsa-port-call-kpis",
        name="TCL Gold DCSA Port Call Performance KPIs",
        schema_name="gold_dcsa",
        purpose=(
            "Curated Gold port call turnaround, berth wait time, and schedule reliability "
            "contract consumed by analytics and AI agents."
        ),
        sla_freshness="60",
        class_tables=(("PortCallPerformanceKpi", "gold_port_call_performance"),),
    ),
)

_LOGICAL_TO_DELTA: dict[str, tuple[str, str]] = {
    "string": ("string", "STRING"),
    "integer": ("integer", "BIGINT"),
    "float": ("number", "DOUBLE"),
    "double": ("number", "DOUBLE"),
    "boolean": ("boolean", "BOOLEAN"),
    "datetime": ("timestamp", "TIMESTAMP"),
    "date": ("date", "DATE"),
}


def _resolve_types_and_constraints(
    sv: SchemaView, slot: SlotDefinition
) -> dict[str, Any]:
    """Extract base range, Delta physical type, pattern, bounds, enum values, and PII tags."""
    range_name = slot.range or "string"
    enum_def = sv.get_enum(range_name)
    type_def = sv.get_type(range_name)

    if range_name in _LOGICAL_TO_DELTA:
        base_range = range_name
        enum_values = []
    elif enum_def is not None:
        base_range = "string"
        enum_values = list((enum_def.permissible_values or {}).keys())
    elif type_def is not None:
        candidate = str(type_def.typeof or type_def.name or "string")
        base_range = candidate if candidate in _LOGICAL_TO_DELTA else "string"
        enum_values = []
    else:
        base_range = "string"
        enum_values = []

    logical_type, physical_type = _LOGICAL_TO_DELTA[base_range]
    pattern = slot.pattern or (type_def.pattern if type_def is not None else None)

    ann_items = slot.annotations._items() if slot.annotations else []
    annotations = {str(k): str(getattr(v, "value", v)) for k, v in ann_items}
    is_pii = annotations.get("pii", "").lower() == "true"

    return {
        "base_range": base_range,
        "logical_type": logical_type,
        "physical_type": physical_type,
        "pattern": pattern,
        "enum_values": enum_values,
        "min_val": slot.minimum_value,
        "max_val": slot.maximum_value,
        "is_pii": is_pii,
        "pii_category": annotations.get("pii_category"),
        "classification": annotations.get(
            "classification", "confidential" if is_pii else "internal"
        ),
    }


def _build_slot_expectations(
    table_fqn: str,
    slot: SlotDefinition,
    meta: dict[str, Any],
) -> list[dict[str, Any]]:
    """Derive Spark SQL boolean expectations directly from LinkML slot constraints."""
    col = slot.name
    rules: list[dict[str, Any]] = []
    required = bool(slot.required)

    def _guard(expr: str) -> str:
        return expr if required else f"({col} IS NULL OR {expr})"

    if required:
        rules.append(
            {
                "name": f"{col}_not_null",
                "column": col,
                "sql": f"{col} IS NOT NULL",
                "action": "fail" if slot.identifier else "drop",
                "source_rule": "required",
                "description": f"{col} must not be NULL on {table_fqn}.",
            }
        )

    if meta["pattern"]:
        escaped = str(meta["pattern"]).replace("\\", "\\\\").replace("'", "\\'")
        rules.append(
            {
                "name": f"{col}_pattern",
                "column": col,
                "sql": _guard(f"{col} RLIKE '{escaped}'"),
                "action": "drop",
                "source_rule": f"pattern:{meta['pattern']}",
                "description": f"{col} must match regex {meta['pattern']}.",
            }
        )

    if meta["min_val"] is not None:
        rules.append(
            {
                "name": f"{col}_min_bound",
                "column": col,
                "sql": _guard(f"{col} >= {meta['min_val']}"),
                "action": "drop",
                "source_rule": f"minimum_value:{meta['min_val']}",
                "description": f"{col} must be >= {meta['min_val']}.",
            }
        )

    if meta["max_val"] is not None:
        rules.append(
            {
                "name": f"{col}_max_bound",
                "column": col,
                "sql": _guard(f"{col} <= {meta['max_val']}"),
                "action": "drop",
                "source_rule": f"maximum_value:{meta['max_val']}",
                "description": f"{col} must be <= {meta['max_val']}.",
            }
        )

    if meta["enum_values"]:
        quoted = ", ".join(f"'{v}'" for v in meta["enum_values"])
        rules.append(
            {
                "name": f"{col}_enum_values",
                "column": col,
                "sql": _guard(f"{col} IN ({quoted})"),
                "action": "drop",
                "source_rule": f"enum:{slot.range}",
                "description": f"{col} must belong to DCSA enum {slot.range}.",
            }
        )

    return rules


def _build_odcs_contract(sv: SchemaView, spec: ContractSpec) -> dict[str, Any]:
    """Build an ODCS v3.1.0 compliant data contract dictionary from LinkML classes."""
    schema_objects: list[dict[str, Any]] = []

    for cls_name, table_name in spec.class_tables:
        cls_def = sv.get_class(cls_name)
        table_fqn = f"{spec.schema_name}.{table_name}"
        properties: list[dict[str, Any]] = []
        quality_rules: list[dict[str, Any]] = []

        for slot in sv.class_induced_slots(cls_name):
            meta = _resolve_types_and_constraints(sv, slot)
            prop: dict[str, Any] = {
                "name": slot.name,
                "logicalType": meta["logical_type"],
                "physicalType": meta["physical_type"],
                "description": slot.description or f"{slot.name} attribute compiled from LinkML.",
                "required": bool(slot.required),
                "classification": meta["classification"],
            }
            if slot.identifier:
                prop["primaryKey"] = True
                prop["primaryKeyPosition"] = 1
                prop["unique"] = True

            if meta["is_pii"]:
                tags = ["pii"]
                if meta["pii_category"]:
                    tags.append(f"pii_category:{meta['pii_category']}")
                prop["tags"] = tags

            logical_opts: dict[str, Any] = {}
            if meta["pattern"]:
                logical_opts["pattern"] = meta["pattern"]
            elif meta["enum_values"]:
                logical_opts["pattern"] = "^(" + "|".join(meta["enum_values"]) + ")$"
            if meta["min_val"] is not None:
                logical_opts["minimum"] = meta["min_val"]
            if meta["max_val"] is not None:
                logical_opts["maximum"] = meta["max_val"]
            if logical_opts:
                prop["logicalTypeOptions"] = logical_opts

            properties.append(prop)

            for rule in _build_slot_expectations(table_fqn, slot, meta):
                quality_rules.append(
                    {
                        "name": f"{table_name}_{rule['name']}",
                        "type": "sql",
                        "description": rule["description"],
                        "query": f"SELECT COUNT(*) FROM {table_name} WHERE NOT ({rule['sql']})",
                        "mustBe": 0,
                        "severity": "error",
                    }
                )

        schema_objects.append(
            {
                "name": table_name,
                "physicalName": table_name,
                "physicalType": "table",
                "description": (cls_def.description if cls_def else "") or table_name,
                "properties": properties,
                "quality": quality_rules,
            }
        )

    return {
        "apiVersion": "v3.1.0",
        "kind": "DataContract",
        "id": spec.contract_id,
        "name": spec.name,
        "version": "1.0.0",
        "status": "active",
        "domain": "maritime-dcsa-logistics",
        "dataProduct": spec.contract_id,
        "description": {
            "purpose": spec.purpose,
            "usage": (
                "Auto-compiled from models/linkml/dcsa/dcsa_enterprise.yaml via "
                "tcl_compiler.compile_dcsa; do not edit generated schema blocks by hand."
            ),
        },
        "servers": [
            {
                "server": "databricks_lakehouse",
                "type": "databricks",
                "catalog": "tcl_lakehouse",
                "schema": spec.schema_name,
            }
        ],
        "team": {
            "name": "TCL DCSA Data Architecture",
            "members": [
                {
                    "username": "tcl-data-platform",
                    "name": "TCL Data Platform Engineering",
                    "role": "owner",
                }
            ],
        },
        "slaProperties": [
            {
                "property": "latency",
                "value": spec.sla_freshness,
                "unit": "minutes",
                "description": "Maximum allowed end-to-end ingestion freshness SLA.",
            }
        ],
        "schema": schema_objects,
    }


def _normalize_generated_paths(text: str, project_root: Path = PROJECT_ROOT) -> str:
    """Replace machine-specific repo root prefixes with portable relative paths."""
    resolved = project_root.resolve()
    for prefix in {f"{resolved}/", f"{resolved.as_posix()}/"}:
        text = text.replace(prefix, "")
    return text


def compile_all(
    schema_path: Path = ENTERPRISE_SCHEMA_PATH,
    generated_dir: Path = GENERATED_DIR,
    contracts_dir: Path = CONTRACTS_ODCS_DIR,
) -> dict[str, Path]:
    """Compile LinkML DCSA schema into Pydantic, JSON Schema, UC comments, LDP rules, and ODCS."""
    sv = SchemaView(str(schema_path))
    resolved_root = str(PROJECT_ROOT.resolve())

    pydantic_path = generated_dir / "pydantic" / "dcsa_models.py"
    pydantic_path.parent.mkdir(parents=True, exist_ok=True)
    pydantic_code = _normalize_generated_paths(PydanticGenerator(str(schema_path)).serialize())
    assert resolved_root not in pydantic_code, "Absolute repo path leaked into generated Pydantic"
    pydantic_path.write_text(pydantic_code, encoding="utf-8")

    jsonschema_path = generated_dir / "jsonschema" / "dcsa_schema.json"
    jsonschema_path.parent.mkdir(parents=True, exist_ok=True)
    jsonschema_str = _normalize_generated_paths(JsonSchemaGenerator(str(schema_path)).serialize())
    assert resolved_root not in jsonschema_str, "Absolute repo path leaked into JSON Schema"
    jsonschema_path.write_text(jsonschema_str, encoding="utf-8")

    uc_comments: dict[str, Any] = {}
    ldp_expectations: dict[str, Any] = {}
    contracts_dir.mkdir(parents=True, exist_ok=True)
    outputs: dict[str, Path] = {
        "pydantic": pydantic_path,
        "jsonschema": jsonschema_path,
    }

    for spec in CONTRACT_SPECS:
        for cls_name, table_name in spec.class_tables:
            cls_def = sv.get_class(cls_name)
            table_fqn = f"{spec.schema_name}.{table_name}"
            col_comments: dict[str, Any] = {}
            pii_cols: list[str] = []
            rules_for_table: list[dict[str, Any]] = []

            for slot in sv.class_induced_slots(cls_name):
                meta = _resolve_types_and_constraints(sv, slot)
                tags = ["pii"] if meta["is_pii"] else []
                if meta["pii_category"]:
                    tags.append(meta["pii_category"])
                if meta["is_pii"]:
                    pii_cols.append(slot.name)

                col_comments[slot.name] = {
                    "comment": slot.description or slot.name,
                    "physical_type": meta["physical_type"],
                    "pii": meta["is_pii"],
                    "pii_category": meta["pii_category"],
                    "classification": meta["classification"],
                    "tags": tags,
                }
                rules_for_table.extend(_build_slot_expectations(table_fqn, slot, meta))

            uc_comments[table_fqn] = {
                "schema": spec.schema_name,
                "table": table_name,
                "class_name": cls_name,
                "table_comment": (cls_def.description if cls_def else "") or table_name,
                "pii_columns": pii_cols,
                "columns": col_comments,
            }
            ldp_expectations[table_fqn] = {
                "schema": spec.schema_name,
                "table": table_name,
                "class_name": cls_name,
                "rules": rules_for_table,
            }

        contract_doc = _build_odcs_contract(sv, spec)
        contract_path = contracts_dir / spec.filename
        contract_path.write_text(
            yaml.safe_dump(contract_doc, sort_keys=False, allow_unicode=False),
            encoding="utf-8",
        )
        outputs[spec.contract_id] = contract_path

    uc_comments_path = generated_dir / "uc_comments.json"
    uc_comments_path.write_text(json.dumps(uc_comments, indent=2) + "\n", encoding="utf-8")
    outputs["uc_comments"] = uc_comments_path

    ldp_expectations_path = generated_dir / "ldp_expectations.json"
    ldp_expectations_path.write_text(
        json.dumps(ldp_expectations, indent=2) + "\n", encoding="utf-8"
    )
    outputs["ldp_expectations"] = ldp_expectations_path

    return outputs


def main() -> int:
    """CLI entrypoint compiling DCSA LinkML models into downstream contracts and code."""
    outputs = compile_all()
    for name, path in outputs.items():
        print(f"[compile_dcsa] {name}: {path.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
