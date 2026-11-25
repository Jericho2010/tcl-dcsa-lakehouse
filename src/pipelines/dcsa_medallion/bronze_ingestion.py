"""Bronze ingestion layer for all 4 DCSA operational sources (Free Edition & Azure Enterprise)."""

from __future__ import annotations

from pyspark import pipelines as dp
from pyspark.sql import DataFrame
from pyspark.sql import functions as F
from pyspark.sql.types import (
    BooleanType,
    DoubleType,
    IntegerType,
    StringType,
    StructField,
    StructType,
)


def _catalog() -> str:
    return spark.conf.get("tcl.catalog", "workspace")  # noqa: F821


def _ingestion_mode() -> str:
    return spark.conf.get("tcl.ingestion_mode", "free_edition")  # noqa: F821


def _read_cloudfiles_json(volume_subpath: str, schema_ddl: str | None = None) -> DataFrame:
    catalog = _catalog()
    path = f"/Volumes/{catalog}/bronze_dcsa/{volume_subpath}"
    reader = (
        spark.readStream.format("cloudFiles")  # noqa: F821
        .option("cloudFiles.format", "json")
        .option("cloudFiles.inferColumnTypes", "true")
    )
    if schema_ddl:
        reader = reader.schema(schema_ddl)
    return reader.load(path).withColumn("_ingested_at", F.current_timestamp())


_REEFER_PAYLOAD_SCHEMA = StructType(
    [
        StructField("reading_id", StringType(), False),
        StructField("equipment_reference", StringType(), False),
        StructField("recorded_at", StringType(), False),
        StructField("setpoint_temp_c", DoubleType(), False),
        StructField("supply_air_temp_c", DoubleType(), False),
        StructField("return_air_temp_c", DoubleType(), False),
        StructField("relative_humidity_pct", DoubleType(), True),
        StructField("power_status", StringType(), False),
        StructField("latitude", DoubleType(), False),
        StructField("longitude", DoubleType(), False),
        StructField("excursion_flag", BooleanType(), False),
    ]
)

_REEFER_ENVELOPE_SCHEMA = StructType(
    [
        StructField("topic", StringType(), True),
        StructField("partition", IntegerType(), True),
        StructField("offset", IntegerType(), True),
        StructField("timestamp", StringType(), True),
        StructField("key", StringType(), True),
        StructField("value", _REEFER_PAYLOAD_SCHEMA, True),
    ]
)


# ---------------------------------------------------------------------------
# 1. PortGate TOS (EquipmentEvent & TransportEvent)
# ---------------------------------------------------------------------------


@dp.table(
    name="bronze_dcsa.portgate_equipment_events",
    comment="Raw DCSA T&T v3 equipment events ingested from PortGate TOS.",
)
def bronze_portgate_equipment_events() -> DataFrame:
    return _read_cloudfiles_json("landing_portgate_tos/equipment_events")


@dp.table(
    name="bronze_dcsa.portgate_transport_events",
    comment="Raw DCSA T&T v3 vessel transport events ingested from PortGate TOS.",
)
def bronze_portgate_transport_events() -> DataFrame:
    return _read_cloudfiles_json("landing_portgate_tos/transport_events")


# ---------------------------------------------------------------------------
# 2. ReeferPulse IoT Mesh (Free Edition Volume JSONL or Azure Event Hubs Kafka)
# ---------------------------------------------------------------------------


@dp.table(
    name="bronze_dcsa.reeferpulse_iot_telemetry",
    comment="Raw DCSA T&T v3.0.0 reefer telemetry parsed from Kafka/Event Hubs envelopes.",
)
def bronze_reeferpulse_iot_telemetry() -> DataFrame:
    catalog = _catalog()
    if _ingestion_mode() == "azure_enterprise":
        kafka_stream = (
            spark.readStream.format("kafka")  # noqa: F821
            .option(
                "kafka.bootstrap.servers",
                spark.conf.get("tcl.kafka.bootstrap_servers"),  # noqa: F821
            )
            .option("subscribe", spark.conf.get("tcl.kafka.topic"))  # noqa: F821
            .option("kafka.security.protocol", "SASL_SSL")
            .option("kafka.sasl.mechanism", "PLAIN")
            .option(
                "kafka.sasl.jaas.config",
                spark.conf.get("tcl.kafka.sasl_jaas_config"),  # noqa: F821
            )
            .load()
        )
        parsed = kafka_stream.select(
            F.col("topic"),
            F.col("partition").cast("int").alias("kafka_partition"),
            F.col("offset").cast("long").alias("kafka_offset"),
            F.from_json(F.col("value").cast("string"), _REEFER_PAYLOAD_SCHEMA).alias("p"),
        )
        return parsed.select(
            "p.*",
            "topic",
            "kafka_partition",
            "kafka_offset",
            F.current_timestamp().alias("_ingested_at"),
        )

    raw = (
        spark.readStream.format("cloudFiles")  # noqa: F821
        .option("cloudFiles.format", "json")
        .schema(_REEFER_ENVELOPE_SCHEMA)
        .load(f"/Volumes/{catalog}/bronze_dcsa/landing_reeferpulse_iot")
    )
    return raw.select(
        F.col("value.*"),
        F.col("topic"),
        F.col("partition").alias("kafka_partition"),
        F.col("offset").cast("long").alias("kafka_offset"),
        F.current_timestamp().alias("_ingested_at"),
    )


# ---------------------------------------------------------------------------
# 3. VoyageCore ERP CDC (Free Edition Volume CDC JSONL or Lakeflow Connect)
# ---------------------------------------------------------------------------


def _read_voyagecore_cdc(table_subpath: str, managed_source_table: str) -> DataFrame:
    catalog = _catalog()
    if _ingestion_mode() == "azure_enterprise":
        return spark.readStream.table(  # noqa: F821
            f"{catalog}.bronze_dcsa.{managed_source_table}"
        ).withColumn("_ingested_at", F.current_timestamp())
    return _read_cloudfiles_json(f"landing_voyagecore_cdc/{table_subpath}")


@dp.table(
    name="bronze_dcsa.voyagecore_transport_documents",
    comment="Raw DCSA eBL v3 transport documents CDC stream from VoyageCore ERP.",
)
def bronze_voyagecore_transport_documents() -> DataFrame:
    return _read_voyagecore_cdc("transport_documents", "lakeflow_voyagecore_transport_documents")


@dp.table(
    name="bronze_dcsa.voyagecore_shipment_events",
    comment="Raw DCSA shipment lifecycle events CDC stream from VoyageCore ERP.",
)
def bronze_voyagecore_shipment_events() -> DataFrame:
    return _read_voyagecore_cdc("shipment_events", "lakeflow_voyagecore_shipment_events")


@dp.table(
    name="bronze_dcsa.voyagecore_bookings",
    comment="Raw DCSA freight bookings CDC stream from VoyageCore ERP.",
)
def bronze_voyagecore_bookings() -> DataFrame:
    return _read_voyagecore_cdc("bookings", "lakeflow_voyagecore_bookings")


@dp.table(
    name="bronze_dcsa.voyagecore_carrier_schedules",
    comment="Raw DCSA OVS carrier schedules CDC stream from VoyageCore ERP.",
)
def bronze_voyagecore_carrier_schedules() -> DataFrame:
    return _read_voyagecore_cdc("carrier_schedules", "lakeflow_voyagecore_carrier_schedules")


# ---------------------------------------------------------------------------
# 4. HarbourSync Port API (JIT Port Call Timestamps)
# ---------------------------------------------------------------------------


@dp.table(
    name="bronze_dcsa.harboursync_jit_port_calls",
    comment="Raw 5-phase DCSA JIT v1 port call timestamps landed by HarbourSync Port API.",
)
def bronze_harboursync_jit_port_calls() -> DataFrame:
    return _read_cloudfiles_json("landing_harboursync_jit")
