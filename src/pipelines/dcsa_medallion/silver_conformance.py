"""Silver conformance, quarantine tables, and AUTO CDC SCD1/SCD2 using LinkML expectations."""

from __future__ import annotations

from pyspark import pipelines as dp
from pyspark.sql import DataFrame
from pyspark.sql import functions as F

try:
    from pipelines.dcsa_medallion.expectations_loader import (
        build_quarantine_filter,
        build_violation_reason_expr,
        load_table_expectations,
    )
except ImportError:
    from expectations_loader import (  # type: ignore[no-redef]
        build_quarantine_filter,
        build_violation_reason_expr,
        load_table_expectations,
    )


def _catalog() -> str:
    return spark.conf.get("tcl.catalog", "workspace")  # noqa: F821


_EQUIP_RULES = load_table_expectations("silver_dcsa.silver_portgate_equipment_events")
_TRANSPORT_RULES = load_table_expectations("silver_dcsa.silver_portgate_transport_events")
_REEFER_RULES = load_table_expectations("silver_dcsa.silver_reeferpulse_iot_telemetry")
_EBL_RULES = load_table_expectations("silver_dcsa.silver_dcsa_ebl_current")
_BOOKING_RULES = load_table_expectations("silver_dcsa.silver_voyagecore_bookings")
_SCHEDULE_RULES = load_table_expectations("silver_dcsa.silver_voyagecore_carrier_schedules")
_JIT_RULES = load_table_expectations("silver_dcsa.silver_harboursync_jit_port_calls")


# ---------------------------------------------------------------------------
# PortGate Equipment & Transport Events (Clean Silver + Quarantine)
# ---------------------------------------------------------------------------


@dp.table(
    name="silver_dcsa.silver_portgate_equipment_events",
    comment="Validated DCSA EquipmentEvent records enforced against LinkML expectations.",
)
@dp.expect_all_or_drop(_EQUIP_RULES)
def silver_portgate_equipment_events() -> DataFrame:
    return (
        spark.readStream.table(f"{_catalog()}.bronze_dcsa.portgate_equipment_events")  # noqa: F821
        .withColumn("event_created_date_time", F.to_timestamp("event_created_date_time"))
        .withColumn("event_date_time", F.to_timestamp("event_date_time"))
        .drop("_rescued_data", "_ingested_at")
    )


@dp.table(
    name="silver_dcsa.quarantine_portgate_equipment_events",
    comment="Quarantined PortGate equipment events violating ISO 6346, UN/LOCODE, or enum rules.",
)
def quarantine_portgate_equipment_events() -> DataFrame:
    return (
        spark.readStream.table(f"{_catalog()}.bronze_dcsa.portgate_equipment_events")  # noqa: F821
        .filter(F.expr(build_quarantine_filter(_EQUIP_RULES)))
        .withColumn("quarantine_reason", F.expr(build_violation_reason_expr(_EQUIP_RULES)))
        .withColumn("quarantined_at", F.current_timestamp())
    )


@dp.table(
    name="silver_dcsa.silver_portgate_transport_events",
    comment="Validated DCSA TransportEvent vessel arrival/departure milestones.",
)
@dp.expect_all_or_drop(_TRANSPORT_RULES)
def silver_portgate_transport_events() -> DataFrame:
    return (
        spark.readStream.table(f"{_catalog()}.bronze_dcsa.portgate_transport_events")  # noqa: F821
        .withColumn("event_created_date_time", F.to_timestamp("event_created_date_time"))
        .withColumn("event_date_time", F.to_timestamp("event_date_time"))
        .drop("_rescued_data", "_ingested_at")
    )


@dp.table(
    name="silver_dcsa.quarantine_portgate_transport_events",
    comment="Quarantined PortGate vessel transport events failing LinkML contracts.",
)
def quarantine_portgate_transport_events() -> DataFrame:
    return (
        spark.readStream.table(f"{_catalog()}.bronze_dcsa.portgate_transport_events")  # noqa: F821
        .filter(F.expr(build_quarantine_filter(_TRANSPORT_RULES)))
        .withColumn("quarantine_reason", F.expr(build_violation_reason_expr(_TRANSPORT_RULES)))
        .withColumn("quarantined_at", F.current_timestamp())
    )


# ---------------------------------------------------------------------------
# ReeferPulse IoT Telemetry (Drops & Quarantines sensor faults such as -99.0C)
# ---------------------------------------------------------------------------


@dp.table(
    name="silver_dcsa.silver_reeferpulse_iot_telemetry",
    comment="Validated reefer telemetry passing LinkML thermal (-45..+60C) and GPS bounds.",
)
@dp.expect_all_or_drop(_REEFER_RULES)
def silver_reeferpulse_iot_telemetry() -> DataFrame:
    return (
        spark.readStream.table(f"{_catalog()}.bronze_dcsa.reeferpulse_iot_telemetry")  # noqa: F821
        .withColumn("recorded_at", F.to_timestamp("recorded_at"))
        .drop("topic", "kafka_partition", "kafka_offset", "_ingested_at")
    )


@dp.table(
    name="silver_dcsa.quarantine_reeferpulse_iot_telemetry",
    comment="Quarantined reefer telemetry capturing out-of-range sensor faults such as -99.0C.",
)
def quarantine_reeferpulse_iot_telemetry() -> DataFrame:
    return (
        spark.readStream.table(f"{_catalog()}.bronze_dcsa.reeferpulse_iot_telemetry")  # noqa: F821
        .filter(F.expr(build_quarantine_filter(_REEFER_RULES)))
        .withColumn("quarantine_reason", F.expr(build_violation_reason_expr(_REEFER_RULES)))
        .withColumn("quarantined_at", F.current_timestamp())
    )


# ---------------------------------------------------------------------------
# HarbourSync JIT Port Calls & VoyageCore Schedules/Bookings
# ---------------------------------------------------------------------------


@dp.table(
    name="silver_dcsa.silver_harboursync_jit_port_calls",
    comment="Validated 5-phase DCSA JIT port call timestamps.",
)
@dp.expect_all_or_drop(_JIT_RULES)
def silver_harboursync_jit_port_calls() -> DataFrame:
    return (
        spark.readStream.table(f"{_catalog()}.bronze_dcsa.harboursync_jit_port_calls")  # noqa: F821
        .withColumn("event_created_date_time", F.to_timestamp("event_created_date_time"))
        .withColumn("event_date_time", F.to_timestamp("event_date_time"))
        .drop("_rescued_data", "_ingested_at")
    )


@dp.table(
    name="silver_dcsa.quarantine_harboursync_jit_port_calls",
    comment="Quarantined JIT port call timestamps failing LinkML rules.",
)
def quarantine_harboursync_jit_port_calls() -> DataFrame:
    return (
        spark.readStream.table(f"{_catalog()}.bronze_dcsa.harboursync_jit_port_calls")  # noqa: F821
        .filter(F.expr(build_quarantine_filter(_JIT_RULES)))
        .withColumn("quarantine_reason", F.expr(build_violation_reason_expr(_JIT_RULES)))
        .withColumn("quarantined_at", F.current_timestamp())
    )


@dp.table(
    name="silver_dcsa.silver_voyagecore_bookings",
    comment="Validated DCSA freight booking records.",
)
@dp.expect_all_or_drop(_BOOKING_RULES)
def silver_voyagecore_bookings() -> DataFrame:
    return (
        spark.readStream.table(f"{_catalog()}.bronze_dcsa.voyagecore_bookings")  # noqa: F821
        .withColumn("booking_created_at", F.to_timestamp("booking_created_at"))
        .drop("cdc_operation", "sequence_ts", "_rescued_data", "_ingested_at")
    )


@dp.table(
    name="silver_dcsa.silver_voyagecore_carrier_schedules",
    comment="Validated DCSA OVS proforma and planned port call schedules.",
)
@dp.expect_all_or_drop(_SCHEDULE_RULES)
def silver_voyagecore_carrier_schedules() -> DataFrame:
    return (
        spark.readStream.table(f"{_catalog()}.bronze_dcsa.voyagecore_carrier_schedules")  # noqa: F821
        .withColumn("planned_arrival_utc", F.to_timestamp("planned_arrival_utc"))
        .withColumn("planned_departure_utc", F.to_timestamp("planned_departure_utc"))
        .drop("cdc_operation", "sequence_ts", "_rescued_data", "_ingested_at")
    )


# ---------------------------------------------------------------------------
# VoyageCore TransportDocument CDC -> AUTO CDC SCD Type 1 & SCD Type 2
# ---------------------------------------------------------------------------


@dp.table(
    name="silver_dcsa.stg_voyagecore_transport_documents",
    comment="Contract-checked VoyageCore eBL CDC staging stream feeding AUTO CDC.",
)
@dp.expect_all_or_drop(_EBL_RULES)
def stg_voyagecore_transport_documents() -> DataFrame:
    return (
        spark.readStream.table(f"{_catalog()}.bronze_dcsa.voyagecore_transport_documents")  # noqa: F821
        .withColumn("sequence_ts", F.to_timestamp("sequence_ts"))
        .withColumn("issue_date", F.to_date("issue_date"))
        .drop("_rescued_data", "_ingested_at")
    )


@dp.table(
    name="silver_dcsa.quarantine_voyagecore_transport_documents",
    comment="Quarantined VoyageCore eBL CDC events failing email/port/IMO validation.",
)
def quarantine_voyagecore_transport_documents() -> DataFrame:
    return (
        spark.readStream.table(  # noqa: F821
            f"{_catalog()}.bronze_dcsa.voyagecore_transport_documents"
        )
        .filter(F.expr(build_quarantine_filter(_EBL_RULES)))
        .withColumn("quarantine_reason", F.expr(build_violation_reason_expr(_EBL_RULES)))
        .withColumn("quarantined_at", F.current_timestamp())
    )


dp.create_streaming_table(
    name="silver_dcsa.silver_dcsa_ebl_current",
    comment="SCD Type 1 current view of DCSA eBL transport documents ordered by sequence_ts.",
)

dp.create_auto_cdc_flow(
    target="silver_dcsa.silver_dcsa_ebl_current",
    source="silver_dcsa.stg_voyagecore_transport_documents",
    keys=["transport_document_reference"],
    sequence_by=F.col("sequence_ts"),
    apply_as_deletes=F.expr("cdc_operation = 'DELETE'"),
    except_column_list=["cdc_operation", "sequence_ts"],
    stored_as_scd_type=1,
)

dp.create_streaming_table(
    name="silver_dcsa.silver_dcsa_ebl_history",
    comment="SCD Type 2 full audit history of DCSA eBL transport document transitions.",
)

dp.create_auto_cdc_flow(
    target="silver_dcsa.silver_dcsa_ebl_history",
    source="silver_dcsa.stg_voyagecore_transport_documents",
    keys=["transport_document_reference"],
    sequence_by=F.col("sequence_ts"),
    apply_as_deletes=F.expr("cdc_operation = 'DELETE'"),
    except_column_list=["cdc_operation", "sequence_ts"],
    stored_as_scd_type=2,
)
