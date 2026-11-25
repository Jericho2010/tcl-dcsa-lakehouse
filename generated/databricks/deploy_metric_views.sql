-- =============================================================================
-- Auto-generated from semantic/ossie/dcsa_ops.ossie.yaml via ossie-databricks deploy
-- Parameterized Databricks Unity Catalog Metric Views DDL (pure gold_dcsa schema)
-- =============================================================================

CREATE OR REPLACE VIEW ${catalog}.gold_dcsa.mv_container_journey_kpis
WITH METRICS
LANGUAGE YAML
AS $$
version: '1.1'
source: ${catalog}.gold_dcsa.gold_container_journey_reefer
comment: Curated Gold container journey and reefer IoT thermal excursion dataset.
dimensions:
- name: journey_id
  expr: journey_id
  comment: Unique container journey grain identifier.
- name: port_call_id
  expr: port_call_id
  comment: Foreign key linking container moves to mv_port_call_kpis.
  synonyms:
  - port call fk
  - transport call key
- name: equipment_reference
  expr: equipment_reference
  comment: ISO 6346 container identifier (4 letters + 7 digits).
  synonyms:
  - container number
  - reefer unit id
- name: un_location_code
  expr: un_location_code
  comment: UN/LOCODE port where the container movement occurred.
  synonyms:
  - movement port code
- name: transport_document_reference
  expr: transport_document_reference
  comment: DCSA eBL transport document reference covering the shipment.
  synonyms:
  - ebl number
  - bill of lading
- name: journey_date
  expr: journey_date
  comment: Calendar date of the container journey milestone.
  synonyms:
  - container move date
- name: excursion_flag_int
  expr: excursion_flag_int
  comment: Binary thermal excursion flag (1 = reefer excursion observed, 0 = within bounds).
- name: dwell_hours
  expr: dwell_hours
  comment: Terminal dwell duration in hours from discharge/gate-in to gate-out/load.
measures:
- name: cold_chain_excursion_rate_pct
  expr: SUM(excursion_flag_int) / NULLIF(COUNT(*), 0)
  comment: Ratio of container moves experiencing a reefer cold-chain thermal excursion.
  synonyms:
  - excursion rate
  - cold chain failure rate
  - reefer breach pct
- name: total_container_moves
  expr: COUNT(*)
  comment: Total number of tracked container journey records.
  synonyms:
  - container moves
  - total boxes moved
- name: reefer_excursion_count
  expr: SUM(excursion_flag_int)
  comment: Count of container journeys recording a reefer temperature excursion.
  synonyms:
  - excursion count
  - cold chain alarms
- name: avg_dwell_hours
  expr: AVG(dwell_hours)
  comment: Average container terminal dwell time in hours.
  synonyms:
  - mean container dwell
  - average yard stay
- name: active_ebl_count
  expr: COUNT(DISTINCT transport_document_reference)
  comment: Count of distinct active eBL transport documents in container journeys.
  synonyms:
  - distinct ebl count
  - active bills of lading
$$;

CREATE OR REPLACE VIEW ${catalog}.gold_dcsa.mv_port_call_kpis
WITH METRICS
LANGUAGE YAML
AS $$
version: '1.1'
source: ${catalog}.gold_dcsa.gold_port_call_performance
comment: Curated Gold port call performance metrics per JIT and OVS port call.
dimensions:
- name: port_call_id
  expr: port_call_id
  comment: Canonical port call primary key joining schedule and JIT phases.
  synonyms:
  - call id
  - transport call key
- name: vessel_imo_number
  expr: vessel_imo_number
  comment: 7-digit IMO ship identification number.
  synonyms:
  - imo number
  - ship id
- name: vessel_name
  expr: vessel_name
  comment: Registered ocean vessel name.
  synonyms:
  - ship name
  - vessel
- name: carrier_voyage_number
  expr: carrier_voyage_number
  comment: Operational carrier voyage identifier.
  synonyms:
  - voyage number
  - voyage code
- name: un_location_code
  expr: un_location_code
  comment: 5-character UN/LOCODE port identifier (e.g. NZAKL, AUSYD).
  synonyms:
  - port code
  - locode
- name: port_name
  expr: port_name
  comment: Human-readable port terminal name.
  synonyms:
  - port
  - harbor name
- name: call_date
  expr: call_date
  comment: Calendar date of the vessel arrival at Pilot Boarding Place.
  synonyms:
  - arrival date
  - port call date
- name: on_time_flag
  expr: on_time_flag
  comment: Binary indicator (1 = arrived within OVS SLA window, 0 = delayed).
- name: port_turnaround_hours
  expr: port_turnaround_hours
  comment: Elapsed hours from Pilot Boarding Place arrival to berth departure.
- name: berth_wait_hours
  expr: berth_wait_hours
  comment: Elapsed wait hours from Pilot Boarding Place arrival to berth all-fast.
measures:
- name: schedule_reliability_pct
  expr: SUM(on_time_flag) / NULLIF(COUNT(*), 0)
  comment: Share of vessel port calls arriving on time against OVS schedule SLA.
  synonyms:
  - on time performance
  - otp
  - schedule reliability
- name: avg_port_turnaround_hours
  expr: AVG(port_turnaround_hours)
  comment: Average vessel turnaround duration in hours from PBP arrival to departure.
  synonyms:
  - average turnaround time
  - mean port stay
- name: avg_berth_wait_hours
  expr: AVG(berth_wait_hours)
  comment: Average anchorage waiting hours before vessel berthing.
  synonyms:
  - berth congestion wait
  - average anchorage wait
- name: total_port_calls
  expr: COUNT(*)
  comment: Total number of completed vessel port calls.
  synonyms:
  - port call count
  - vessel arrivals
- name: on_time_calls
  expr: SUM(on_time_flag)
  comment: Count of vessel port calls meeting OVS arrival reliability SLA.
  synonyms:
  - reliable calls
  - punctual port calls
$$;
