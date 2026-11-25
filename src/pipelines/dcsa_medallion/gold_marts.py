"""Gold dimensional marts matching semantic/ossie/dcsa_ops.ossie.yaml schemas exactly."""

from __future__ import annotations

from pyspark import pipelines as dp
from pyspark.sql import DataFrame
from pyspark.sql import functions as F


def _catalog() -> str:
    return spark.conf.get("tcl.catalog", "workspace")  # noqa: F821


@dp.materialized_view(
    name="gold_dcsa.gold_port_call_performance",
    comment="Gold port call turnaround, berth wait, and schedule reliability mart (DCSA JIT+OVS).",
)
def gold_port_call_performance() -> DataFrame:
    catalog = _catalog()
    jit = spark.read.table(f"{catalog}.silver_dcsa.silver_harboursync_jit_port_calls")  # noqa: F821
    schedules = spark.read.table(  # noqa: F821
        f"{catalog}.silver_dcsa.silver_voyagecore_carrier_schedules"
    )

    port_phases = jit.groupBy(
        "port_call_id",
        "vessel_imo_number",
        "carrier_voyage_number",
        "un_location_code",
    ).agg(
        F.max(
            F.when(F.col("jit_phase_code") == "ATA_PBP", F.to_timestamp("event_date_time"))
        ).alias("ata_pbp_ts"),
        F.max(
            F.when(F.col("jit_phase_code") == "ATB_BERTH", F.to_timestamp("event_date_time"))
        ).alias("atb_berth_ts"),
        F.max(
            F.when(F.col("jit_phase_code") == "ATD_BERTH", F.to_timestamp("event_date_time"))
        ).alias("atd_berth_ts"),
    )

    port_lookup = (
        F.when(F.col("un_location_code") == "NZAKL", F.lit("Auckland"))
        .when(F.col("un_location_code") == "NZTRG", F.lit("Tauranga"))
        .when(F.col("un_location_code") == "NZLYT", F.lit("Lyttelton"))
        .when(F.col("un_location_code") == "AUBNE", F.lit("Brisbane"))
        .when(F.col("un_location_code") == "AUSYD", F.lit("Sydney"))
        .when(F.col("un_location_code") == "FJSVA", F.lit("Suva"))
        .otherwise(F.col("un_location_code"))
    )

    joined = port_phases.join(
        schedules.select(
            "vessel_imo_number",
            "carrier_voyage_number",
            "un_location_code",
            "vessel_name",
            F.to_timestamp("planned_arrival_utc").alias("planned_arrival_ts"),
        ),
        on=["vessel_imo_number", "carrier_voyage_number", "un_location_code"],
        how="left",
    )

    return joined.select(
        F.col("port_call_id"),
        F.col("vessel_imo_number"),
        F.coalesce(F.col("vessel_name"), F.lit("UNKNOWN")).alias("vessel_name"),
        F.col("carrier_voyage_number"),
        F.col("un_location_code"),
        port_lookup.alias("port_name"),
        F.to_date(F.col("ata_pbp_ts")).alias("call_date"),
        F.when(
            (F.unix_timestamp("ata_pbp_ts") - F.unix_timestamp("planned_arrival_ts")) <= 7200,
            F.lit(1),
        )
        .otherwise(F.lit(0))
        .cast("bigint")
        .alias("on_time_flag"),
        F.round(
            (F.unix_timestamp("atd_berth_ts") - F.unix_timestamp("ata_pbp_ts")) / 3600.0,
            2,
        )
        .cast("double")
        .alias("port_turnaround_hours"),
        F.round(
            (F.unix_timestamp("atb_berth_ts") - F.unix_timestamp("ata_pbp_ts")) / 3600.0,
            2,
        )
        .cast("double")
        .alias("berth_wait_hours"),
    )


@dp.materialized_view(
    name="gold_dcsa.gold_container_journey_reefer",
    comment="Gold container journey dwell, cold-chain excursion, and active eBL analytics mart.",
)
def gold_container_journey_reefer() -> DataFrame:
    catalog = _catalog()
    equip = spark.read.table(  # noqa: F821
        f"{catalog}.silver_dcsa.silver_portgate_equipment_events"
    )
    reefer = spark.read.table(  # noqa: F821
        f"{catalog}.silver_dcsa.silver_reeferpulse_iot_telemetry"
    )
    ebl = spark.read.table(f"{catalog}.silver_dcsa.silver_dcsa_ebl_current")  # noqa: F821

    container_moves = equip.groupBy(
        "equipment_reference",
        "transport_call_id",
        "un_location_code",
    ).agg(
        F.min(F.to_timestamp("event_date_time")).alias("first_move_ts"),
        F.max(F.to_timestamp("event_date_time")).alias("last_move_ts"),
    )

    excursions = reefer.groupBy("equipment_reference").agg(
        F.max(F.when(F.col("excursion_flag"), F.lit(1)).otherwise(F.lit(0)))
        .cast("int")
        .alias("excursion_flag_int")
    )

    ebl_by_pol = ebl.groupBy(F.col("port_of_loading").alias("un_location_code")).agg(
        F.min("transport_document_reference").alias("transport_document_reference")
    )

    joined = container_moves.join(excursions, on="equipment_reference", how="left").join(
        ebl_by_pol, on="un_location_code", how="left"
    )

    return joined.select(
        F.concat_ws("-", F.col("transport_call_id"), F.col("equipment_reference")).alias(
            "journey_id"
        ),
        F.col("transport_call_id").alias("port_call_id"),
        F.col("equipment_reference"),
        F.col("un_location_code"),
        F.col("transport_document_reference"),
        F.to_date(F.col("first_move_ts")).alias("journey_date"),
        F.coalesce(F.col("excursion_flag_int"), F.lit(0)).cast("int").alias("excursion_flag_int"),
        F.round(
            (F.unix_timestamp("last_move_ts") - F.unix_timestamp("first_move_ts")) / 3600.0,
            2,
        )
        .cast("double")
        .alias("dwell_hours"),
    )
