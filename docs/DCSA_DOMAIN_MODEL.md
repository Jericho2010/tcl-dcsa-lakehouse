# DCSA Domain Model &amp; Semantic KPI Reference

Tasman Container Line (TCL) standardizes its Lakehouse entities on four **Digital Container Shipping Association (DCSA)** operational standards modeled declaratively in **LinkML** and **Apache Ossie**.

---

## 1. Modular LinkML Schema Hierarchy (`models/linkml/dcsa/`)

| Schema File | DCSA Standard | Key Classes, Mixins &amp; Types |
| :--- | :--- | :--- |
| [`dcsa_common.yaml`](../models/linkml/dcsa/dcsa_common.yaml) | Shared DCSA Core Primitives | Types: `UNLocationCode` (`^[A-Z]{2}[A-Z2-9]{3}$`), `EquipmentReference` ISO 6346 (`^[A-Z]{4}[0-9]{7}$`), `VesselIMONumber` (`^[0-9]{7}$`) · Enums: `EventClassifierCode` (`PLN`/`ACT`/`EST`), `EquipmentEventTypeCode`, `TransportEventTypeCode`, `ShipmentEventTypeCode`, `PowerStatus`, `JitPhaseCode` · Classes: `Location`, `AuditableEvent` mixin |
| [`dcsa_tnt_v3.yaml`](../models/linkml/dcsa/dcsa_tnt_v3.yaml) | Track &amp; Trace v3.0.0 (IoT &amp; Reefer) | `EquipmentEvent`, `TransportEvent`, `ReeferTelemetryReading` (thermal physical bounds: `setpoint_temp_c` `-40..+30°C`, `supply_air_temp_c` / `return_air_temp_c` `-45..+60°C`, `relative_humidity_pct` `0..100`, GPS `latitude` `-90..+90`, `longitude` `-180..+180`) |
| [`dcsa_ebl_v3.yaml`](../models/linkml/dcsa/dcsa_ebl_v3.yaml) | eBL v3, Booking &amp; OVS | `TransportDocument` (with PII annotations on `shipper_contact_email` and `consignee_name`), `ShipmentEvent`, `BookingRecord`, `CarrierSchedule` (OVS proforma &amp; planned arrivals) |
| [`dcsa_jit_v1.yaml`](../models/linkml/dcsa/dcsa_jit_v1.yaml) | Just-in-Time (JIT) Port Call v1.x | `PortCallTimestamp` capturing all 5 port-call phases (`ETA_PBP`, `ATA_PBP`, `ETB_BERTH`, `ATB_BERTH`, `ATD_BERTH`) |
| [`dcsa_enterprise.yaml`](../models/linkml/dcsa/dcsa_enterprise.yaml) | Umbrella Enterprise Model | Imports all 4 domain profiles + Gold `PortCallPerformance` analytical class; single input to [`compile_dcsa.py`](../src/tcl_compiler/compile_dcsa.py) |

---

## 2. Operational Trade Lanes &amp; Synthetic Test Scenarios

[`src/generators/dcsa_synthetic_generator.py`](../src/generators/dcsa_synthetic_generator.py) generates realistic Tasman &amp; Pacific carrier operations:

- **Ports (`UN/LOCODE`):** `NZAKL` (Auckland), `NZTRG` (Tauranga), `NZLYT` (Lyttelton), `AUBNE` (Brisbane), `AUSYD` (Sydney), `FJSVA` (Suva).
- **Fleet Vessels:** `MV TASMAN HORIZON`, `MV AOTEAROA STAR`, `MV CORAL TRADER`.
- **Deliberate Governance Proof Cases Baked into Every Run:**
  1. **PortGate Quarantine Cases (2 rows):** Invalid ISO 6346 container reference (`BAD-CONT-99`) and invalid UN/LOCODE (`12345`) → caught by `silver_dcsa.quarantine_portgate_equipment_events`.
  2. **ReeferPulse Sensor Fault (1 row):** Physically impossible supply air reading (`-99.0°C`) → caught by `silver_dcsa.quarantine_reeferpulse_iot_telemetry` (while genuine cold-chain excursions at `-11.2°C` remain valid data and surface in Gold KPIs and the Port Control Workbench!).
  3. **VoyageCore Out-of-Order CDC &amp; `DELETE`:** Multiple state transitions (`DRFT` → `APPR` → `ISSU` → `SURR`) with late-arriving timestamps and a logical delete → reconciled via `dp.create_auto_cdc_flow` into `14` current SCD1 rows and `31` SCD2 audit history rows.

---

## 3. Contract-to-Table Mapping (ODCS v3.1.0)

| ODCS Contract File | Target Unity Catalog Schema | Governed Tables Validated Live | Live `spark_ibis` Checks |
| :--- | :--- | :--- | :---: |
| [`portgate_tos_events.odcs.yaml`](../contracts/odcs/portgate_tos_events.odcs.yaml) | `silver_dcsa` | `silver_portgate_equipment_events`, `silver_portgate_transport_events` | **112 / 112** |
| [`reeferpulse_iot_telemetry.odcs.yaml`](../contracts/odcs/reeferpulse_iot_telemetry.odcs.yaml) | `silver_dcsa` | `silver_reeferpulse_iot_telemetry` | **71 / 71** |
| [`voyagecore_ebl_bookings.odcs.yaml`](../contracts/odcs/voyagecore_ebl_bookings.odcs.yaml) | `silver_dcsa` | `silver_dcsa_ebl_current`, `silver_voyagecore_bookings`, `silver_voyagecore_carrier_schedules` | **125 / 125** |
| [`harboursync_jit_port_calls.odcs.yaml`](../contracts/odcs/harboursync_jit_port_calls.odcs.yaml) | `silver_dcsa` | `silver_harboursync_jit_port_calls` | **55 / 55** |
| [`gold_dcsa_port_call_kpis.odcs.yaml`](../contracts/odcs/gold_dcsa_port_call_kpis.odcs.yaml) | `gold_dcsa` | `gold_port_call_performance` | **57 / 57** |
| **Total** | | **8 curated Unity Catalog tables** | **420 / 420** |

---

## 4. Governed Apache Ossie KPI Glossary (`semantic/ossie/dcsa_ops.ossie.yaml`)

All 10 metrics compile simultaneously to **Databricks UC Metric Views** (`MEASURE(...)`) and **Power BI TMSL DAX** (`generated/powerbi/dcsa_ops.model.bim`):

### Dataset 1: `mv_port_call_kpis` (`gold_dcsa.gold_port_call_performance`)

| Measure Name | Portable Ossie Expression | Business Meaning | Genie / AI Synonyms |
| :--- | :--- | :--- | :--- |
| `schedule_reliability_pct` | `SUM(on_time_flag) / NULLIF(COUNT(*), 0)` | Share of vessel port calls arriving within OVS SLA window (`<= 2h`) | `on time performance`, `otp`, `schedule reliability` |
| `avg_port_turnaround_hours` | `AVG(port_turnaround_hours)` | Mean elapsed hours from PBP arrival (`ATA_PBP`) to berth departure (`ATD_BERTH`) | `average turnaround time`, `mean port stay` |
| `avg_berth_wait_hours` | `AVG(berth_wait_hours)` | Mean anchorage wait hours from `ATA_PBP` to berth all-fast (`ATB_BERTH`) | `berth congestion wait`, `average anchorage wait` |
| `total_port_calls` | `COUNT(*)` | Total completed vessel port calls | `port call count`, `vessel arrivals` |
| `on_time_calls` | `SUM(on_time_flag)` | Count of punctual vessel port calls meeting OVS SLA | `reliable calls`, `punctual port calls` |

### Dataset 2: `mv_container_journey_kpis` (`gold_dcsa.gold_container_journey_reefer`)

| Measure Name | Portable Ossie Expression | Business Meaning | Genie / AI Synonyms |
| :--- | :--- | :--- | :--- |
| `cold_chain_excursion_rate_pct` | `SUM(excursion_flag_int) / NULLIF(COUNT(*), 0)` | Share of container moves recording a cold-chain thermal breach | `excursion rate`, `cold chain failure rate`, `reefer breach pct` |
| `total_container_moves` | `COUNT(*)` | Total tracked container journey records | `container moves`, `total boxes moved` |
| `reefer_excursion_count` | `SUM(excursion_flag_int)` | Count of container journeys experiencing a reefer thermal excursion | `excursion count`, `cold chain alarms` |
| `avg_dwell_hours` | `AVG(dwell_hours)` | Average container terminal dwell time in hours | `mean container dwell`, `average yard stay` |
| `active_ebl_count` | `COUNT(DISTINCT transport_document_reference)` | Distinct active eBL transport documents linked to journeys | `distinct ebl count`, `active bills of lading` |

*(Star-schema relationship declared in Ossie: `mv_container_journey_kpis.port_call_id` → `mv_port_call_kpis.port_call_id`.)*
