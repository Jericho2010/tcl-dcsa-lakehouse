from __future__ import annotations

import re
import sys
from datetime import (
    date,
    datetime,
    time
)
from decimal import Decimal
from enum import Enum
from typing import (
    Any,
    ClassVar,
    Literal,
    Optional,
    Union
)

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    RootModel,
    SerializationInfo,
    SerializerFunctionWrapHandler,
    field_validator,
    model_serializer
)


metamodel_version = "1.12.0"
version = "1.0.0"


class ConfiguredBaseModel(BaseModel):
    model_config = ConfigDict(
        serialize_by_alias = True,
        validate_by_name = True,
        validate_assignment = True,
        validate_default = True,
        extra = "forbid",
        arbitrary_types_allowed = True,
        use_enum_values = True,
        strict = False,
    )





class LinkMLMeta(RootModel):
    root: dict[str, Any] = {}
    model_config = ConfigDict(frozen=True)

    def __getattr__(self, key:str):
        return getattr(self.root, key)

    def __getitem__(self, key:str):
        return self.root[key]

    def __setitem__(self, key:str, value):
        self.root[key] = value

    def __contains__(self, key:str) -> bool:
        return key in self.root


linkml_meta = LinkMLMeta({'default_prefix': 'dcsa_ent',
     'default_range': 'string',
     'description': 'Unified LinkML umbrella schema importing DCSA Common, T&T v3, '
                    'eBL/OVS v3, and JIT v1 domain models alongside curated Gold '
                    'KPI schemas.',
     'id': 'https://tasmancontainerline.example/linkml/dcsa/enterprise',
     'imports': ['linkml:types',
                 'dcsa_common',
                 'dcsa_tnt_v3',
                 'dcsa_ebl_v3',
                 'dcsa_jit_v1'],
     'name': 'dcsa_enterprise',
     'prefixes': {'dcsa_common': {'prefix_prefix': 'dcsa_common',
                                  'prefix_reference': 'https://tasmancontainerline.example/linkml/dcsa/common/'},
                  'dcsa_ebl': {'prefix_prefix': 'dcsa_ebl',
                               'prefix_reference': 'https://tasmancontainerline.example/linkml/dcsa/ebl/v3/'},
                  'dcsa_ent': {'prefix_prefix': 'dcsa_ent',
                               'prefix_reference': 'https://tasmancontainerline.example/linkml/dcsa/enterprise/'},
                  'dcsa_jit': {'prefix_prefix': 'dcsa_jit',
                               'prefix_reference': 'https://tasmancontainerline.example/linkml/dcsa/jit/v1/'},
                  'dcsa_tnt': {'prefix_prefix': 'dcsa_tnt',
                               'prefix_reference': 'https://tasmancontainerline.example/linkml/dcsa/tnt/v3/'},
                  'linkml': {'prefix_prefix': 'linkml',
                             'prefix_reference': 'https://w3id.org/linkml/'}},
     'source_file': 'models/linkml/dcsa/dcsa_enterprise.yaml',
     'title': 'Tasman Container Line (TCL) Enterprise DCSA Umbrella Schema'} )

class EventClassifierCode(str, Enum):
    """
    DCSA classifier indicating whether an event timestamp is planned, actual, or estimated.
    """
    PLN = "PLN"
    """
    Planned schedule timestamp.
    """
    ACT = "ACT"
    """
    Actual observed timestamp.
    """
    EST = "EST"
    """
    Estimated forecast timestamp.
    """


class EquipmentEventTypeCode(str, Enum):
    """
    DCSA Track & Trace v3 equipment milestone event codes.
    """
    LOAD = "LOAD"
    """
    Container loaded onto vessel.
    """
    DISC = "DISC"
    """
    Container discharged from vessel.
    """
    GTIN = "GTIN"
    """
    Container gated into terminal.
    """
    GTOT = "GTOT"
    """
    Container gated out of terminal.
    """
    STUF = "STUF"
    """
    Container stuffed at origin.
    """
    STRP = "STRP"
    """
    Container stripped at destination.
    """
    PICK = "PICK"
    """
    Empty container picked up.
    """
    DROP = "DROP"
    """
    Empty container returned/dropped off.
    """
    INSP = "INSP"
    """
    Container inspected.
    """
    RSEA = "RSEA"
    """
    Container resealed.
    """
    RMVD = "RMVD"
    """
    Seal removed from container.
    """


class TransportEventTypeCode(str, Enum):
    """
    DCSA Track & Trace v3 vessel transport milestone codes.
    """
    ARRI = "ARRI"
    """
    Vessel arrived at transport call location.
    """
    DEPA = "DEPA"
    """
    Vessel departed from transport call location.
    """


class ShipmentEventTypeCode(str, Enum):
    """
    DCSA eBL / Booking shipment lifecycle document status codes.
    """
    RECE = "RECE"
    """
    Received by carrier.
    """
    DRFT = "DRFT"
    """
    Draft created.
    """
    PENA = "PENA"
    """
    Pending approval.
    """
    PENU = "PENU"
    """
    Pending update.
    """
    REJE = "REJE"
    """
    Rejected.
    """
    APPR = "APPR"
    """
    Approved.
    """
    ISSU = "ISSU"
    """
    Issued.
    """
    SURR = "SURR"
    """
    Surrendered.
    """
    SUBM = "SUBM"
    """
    Submitted.
    """
    VOID = "VOID"
    """
    Voided.
    """
    CONF = "CONF"
    """
    Confirmed.
    """
    REQS = "REQS"
    """
    Requested.
    """
    CMPL = "CMPL"
    """
    Completed.
    """
    HOLD = "HOLD"
    """
    Placed on hold.
    """
    RELS = "RELS"
    """
    Released.
    """


class PowerStatus(str, Enum):
    """
    Refrigerated container power supply telemetry state.
    """
    ON = "ON"
    """
    Reefer unit powered on and regulating.
    """
    OFF = "OFF"
    """
    Reefer unit powered off.
    """
    ALARM = "ALARM"
    """
    Reefer unit reporting active alarm condition.
    """
    DEFROST = "DEFROST"
    """
    Reefer unit running defrost cycle.
    """
    UNKNOWN = "UNKNOWN"
    """
    Power status unavailable from IoT gateway.
    """


class JitPhaseCode(str, Enum):
    """
    DCSA Just-In-Time (JIT) v1.x port call timestamp milestone phases.
    """
    ETA_PBP = "ETA_PBP"
    """
    Estimated time of arrival at Pilot Boarding Place.
    """
    ATA_PBP = "ATA_PBP"
    """
    Actual time of arrival at Pilot Boarding Place.
    """
    ETB_BERTH = "ETB_BERTH"
    """
    Estimated time alongside berth.
    """
    ATB_BERTH = "ATB_BERTH"
    """
    Actual time alongside berth (all fast).
    """
    ATD_BERTH = "ATD_BERTH"
    """
    Actual time of departure from berth.
    """



class Location(ConfiguredBaseModel):
    """
    Normalized UN/LOCODE maritime terminal or port geographic reference.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://tasmancontainerline.example/linkml/dcsa/common'})

    un_location_code: str = Field(default=..., description="""5-character UN/LOCODE port identifier.""", json_schema_extra = { "linkml_meta": {'domain_of': ['Location',
                       'EquipmentEvent',
                       'TransportEvent',
                       'CarrierSchedule',
                       'PortCallTimestamp',
                       'PortCallPerformanceKpi']} })
    location_name: Optional[str] = Field(default=None, description="""Human-readable port or terminal name.""", json_schema_extra = { "linkml_meta": {'domain_of': ['Location']} })
    facility_code: Optional[str] = Field(default=None, description="""SMDG or BIC terminal facility code within the UN/LOCODE.""", json_schema_extra = { "linkml_meta": {'domain_of': ['Location', 'EquipmentEvent']} })
    latitude: Optional[float] = Field(default=None, description="""WGS84 latitude in decimal degrees.""", ge=-90.0, le=90.0, json_schema_extra = { "linkml_meta": {'domain_of': ['Location', 'ReeferTelemetryReading']} })
    longitude: Optional[float] = Field(default=None, description="""WGS84 longitude in decimal degrees.""", ge=-180.0, le=180.0, json_schema_extra = { "linkml_meta": {'domain_of': ['Location', 'ReeferTelemetryReading']} })

    @field_validator('un_location_code')
    def pattern_un_location_code(cls, v):
        pattern=re.compile(r"^[A-Z]{2}[A-Z2-9]{3}$")
        if isinstance(v, list):
            for element in v:
                if isinstance(element, str) and not pattern.search(element):
                    err_msg = f"Invalid un_location_code format: {element}"
                    raise ValueError(err_msg)
        elif isinstance(v, str) and not pattern.search(v):
            err_msg = f"Invalid un_location_code format: {v}"
            raise ValueError(err_msg)
        return v


class AuditableEvent(ConfiguredBaseModel):
    """
    Common audit and event timing attributes inherited across DCSA event classes.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://tasmancontainerline.example/linkml/dcsa/common',
         'mixin': True})

    event_id: str = Field(default=..., description="""Globally unique deterministic identifier for the DCSA event record.""", json_schema_extra = { "linkml_meta": {'domain_of': ['AuditableEvent']} })
    event_created_date_time: datetime  = Field(default=..., description="""UTC timestamp when the source system created the event payload.""", json_schema_extra = { "linkml_meta": {'domain_of': ['AuditableEvent']} })
    event_date_time: datetime  = Field(default=..., description="""UTC timestamp when the operational event occurred, is estimated, or is planned.""", json_schema_extra = { "linkml_meta": {'domain_of': ['AuditableEvent']} })
    event_classifier_code: EventClassifierCode = Field(default=..., description="""Classification of event_date_time (PLN, ACT, or EST).""", json_schema_extra = { "linkml_meta": {'domain_of': ['AuditableEvent']} })
    source_system: str = Field(default=..., description="""Originating operational system identifier (e.g., portgate_tos, voyagecore_ebl).""", json_schema_extra = { "linkml_meta": {'domain_of': ['AuditableEvent']} })


class EquipmentEvent(AuditableEvent):
    """
    DCSA Track & Trace v3 container equipment handling event captured at terminal gates, quaysides, or depots.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://tasmancontainerline.example/linkml/dcsa/tnt/v3',
         'mixins': ['AuditableEvent']})

    equipment_event_type_code: EquipmentEventTypeCode = Field(default=..., description="""DCSA equipment milestone code (e.g., LOAD, DISC, GTIN, GTOT).""", json_schema_extra = { "linkml_meta": {'domain_of': ['EquipmentEvent']} })
    equipment_reference: str = Field(default=..., description="""ISO 6346 container identifier (e.g., TCLU1234567).""", json_schema_extra = { "linkml_meta": {'domain_of': ['EquipmentEvent', 'ReeferTelemetryReading']} })
    iso_equipment_code: str = Field(default=..., description="""4-character ISO 6346 container size and type code (e.g., 45R1, 42G1).""", json_schema_extra = { "linkml_meta": {'domain_of': ['EquipmentEvent']} })
    empty_indicator_code: str = Field(default=..., description="""Container load state indicator (EMPTY or LADEN).""", json_schema_extra = { "linkml_meta": {'domain_of': ['EquipmentEvent']} })
    un_location_code: str = Field(default=..., description="""UN/LOCODE port where the equipment event occurred.""", json_schema_extra = { "linkml_meta": {'domain_of': ['Location',
                       'EquipmentEvent',
                       'TransportEvent',
                       'CarrierSchedule',
                       'PortCallTimestamp',
                       'PortCallPerformanceKpi']} })
    facility_code: Optional[str] = Field(default=None, description="""SMDG terminal facility code.""", json_schema_extra = { "linkml_meta": {'domain_of': ['Location', 'EquipmentEvent']} })
    transport_call_id: Optional[str] = Field(default=None, description="""Foreign reference linking vessel-side events to the port call.""", json_schema_extra = { "linkml_meta": {'domain_of': ['EquipmentEvent', 'TransportEvent']} })
    carrier_voyage_number: Optional[str] = Field(default=None, description="""Operational carrier voyage identifier.""", json_schema_extra = { "linkml_meta": {'domain_of': ['EquipmentEvent',
                       'TransportEvent',
                       'CarrierSchedule',
                       'PortCallTimestamp',
                       'PortCallPerformanceKpi']} })
    event_id: str = Field(default=..., description="""Globally unique deterministic identifier for the DCSA event record.""", json_schema_extra = { "linkml_meta": {'domain_of': ['AuditableEvent']} })
    event_created_date_time: datetime  = Field(default=..., description="""UTC timestamp when the source system created the event payload.""", json_schema_extra = { "linkml_meta": {'domain_of': ['AuditableEvent']} })
    event_date_time: datetime  = Field(default=..., description="""UTC timestamp when the operational event occurred, is estimated, or is planned.""", json_schema_extra = { "linkml_meta": {'domain_of': ['AuditableEvent']} })
    event_classifier_code: EventClassifierCode = Field(default=..., description="""Classification of event_date_time (PLN, ACT, or EST).""", json_schema_extra = { "linkml_meta": {'domain_of': ['AuditableEvent']} })
    source_system: str = Field(default=..., description="""Originating operational system identifier (e.g., portgate_tos, voyagecore_ebl).""", json_schema_extra = { "linkml_meta": {'domain_of': ['AuditableEvent']} })

    @field_validator('equipment_reference')
    def pattern_equipment_reference(cls, v):
        pattern=re.compile(r"^[A-Z]{4}[0-9]{7}$")
        if isinstance(v, list):
            for element in v:
                if isinstance(element, str) and not pattern.search(element):
                    err_msg = f"Invalid equipment_reference format: {element}"
                    raise ValueError(err_msg)
        elif isinstance(v, str) and not pattern.search(v):
            err_msg = f"Invalid equipment_reference format: {v}"
            raise ValueError(err_msg)
        return v

    @field_validator('iso_equipment_code')
    def pattern_iso_equipment_code(cls, v):
        pattern=re.compile(r"^[0-9A-Z]{4}$")
        if isinstance(v, list):
            for element in v:
                if isinstance(element, str) and not pattern.search(element):
                    err_msg = f"Invalid iso_equipment_code format: {element}"
                    raise ValueError(err_msg)
        elif isinstance(v, str) and not pattern.search(v):
            err_msg = f"Invalid iso_equipment_code format: {v}"
            raise ValueError(err_msg)
        return v

    @field_validator('empty_indicator_code')
    def pattern_empty_indicator_code(cls, v):
        pattern=re.compile(r"^(EMPTY|LADEN)$")
        if isinstance(v, list):
            for element in v:
                if isinstance(element, str) and not pattern.search(element):
                    err_msg = f"Invalid empty_indicator_code format: {element}"
                    raise ValueError(err_msg)
        elif isinstance(v, str) and not pattern.search(v):
            err_msg = f"Invalid empty_indicator_code format: {v}"
            raise ValueError(err_msg)
        return v

    @field_validator('un_location_code')
    def pattern_un_location_code(cls, v):
        pattern=re.compile(r"^[A-Z]{2}[A-Z2-9]{3}$")
        if isinstance(v, list):
            for element in v:
                if isinstance(element, str) and not pattern.search(element):
                    err_msg = f"Invalid un_location_code format: {element}"
                    raise ValueError(err_msg)
        elif isinstance(v, str) and not pattern.search(v):
            err_msg = f"Invalid un_location_code format: {v}"
            raise ValueError(err_msg)
        return v


class TransportEvent(AuditableEvent):
    """
    DCSA Track & Trace v3 vessel arrival and departure milestone event for a transport call.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://tasmancontainerline.example/linkml/dcsa/tnt/v3',
         'mixins': ['AuditableEvent']})

    transport_event_type_code: TransportEventTypeCode = Field(default=..., description="""Vessel movement event type (ARRI or DEPA).""", json_schema_extra = { "linkml_meta": {'domain_of': ['TransportEvent']} })
    transport_call_id: str = Field(default=..., description="""Unique identifier of the transport call at the terminal.""", json_schema_extra = { "linkml_meta": {'domain_of': ['EquipmentEvent', 'TransportEvent']} })
    vessel_imo_number: str = Field(default=..., description="""7-digit IMO ship identification number.""", json_schema_extra = { "linkml_meta": {'domain_of': ['TransportEvent',
                       'TransportDocument',
                       'CarrierSchedule',
                       'PortCallTimestamp',
                       'PortCallPerformanceKpi']} })
    carrier_voyage_number: str = Field(default=..., description="""Operational carrier voyage identifier.""", json_schema_extra = { "linkml_meta": {'domain_of': ['EquipmentEvent',
                       'TransportEvent',
                       'CarrierSchedule',
                       'PortCallTimestamp',
                       'PortCallPerformanceKpi']} })
    un_location_code: str = Field(default=..., description="""UN/LOCODE port where the vessel event applies.""", json_schema_extra = { "linkml_meta": {'domain_of': ['Location',
                       'EquipmentEvent',
                       'TransportEvent',
                       'CarrierSchedule',
                       'PortCallTimestamp',
                       'PortCallPerformanceKpi']} })
    delay_reason_code: Optional[str] = Field(default=None, description="""Standardized SMDG delay reason code when behind schedule.""", json_schema_extra = { "linkml_meta": {'domain_of': ['TransportEvent', 'PortCallTimestamp']} })
    change_remark: Optional[str] = Field(default=None, description="""Operational commentary explaining schedule updates.""", json_schema_extra = { "linkml_meta": {'domain_of': ['TransportEvent']} })
    event_id: str = Field(default=..., description="""Globally unique deterministic identifier for the DCSA event record.""", json_schema_extra = { "linkml_meta": {'domain_of': ['AuditableEvent']} })
    event_created_date_time: datetime  = Field(default=..., description="""UTC timestamp when the source system created the event payload.""", json_schema_extra = { "linkml_meta": {'domain_of': ['AuditableEvent']} })
    event_date_time: datetime  = Field(default=..., description="""UTC timestamp when the operational event occurred, is estimated, or is planned.""", json_schema_extra = { "linkml_meta": {'domain_of': ['AuditableEvent']} })
    event_classifier_code: EventClassifierCode = Field(default=..., description="""Classification of event_date_time (PLN, ACT, or EST).""", json_schema_extra = { "linkml_meta": {'domain_of': ['AuditableEvent']} })
    source_system: str = Field(default=..., description="""Originating operational system identifier (e.g., portgate_tos, voyagecore_ebl).""", json_schema_extra = { "linkml_meta": {'domain_of': ['AuditableEvent']} })

    @field_validator('vessel_imo_number')
    def pattern_vessel_imo_number(cls, v):
        pattern=re.compile(r"^[0-9]{7}$")
        if isinstance(v, list):
            for element in v:
                if isinstance(element, str) and not pattern.search(element):
                    err_msg = f"Invalid vessel_imo_number format: {element}"
                    raise ValueError(err_msg)
        elif isinstance(v, str) and not pattern.search(v):
            err_msg = f"Invalid vessel_imo_number format: {v}"
            raise ValueError(err_msg)
        return v

    @field_validator('un_location_code')
    def pattern_un_location_code(cls, v):
        pattern=re.compile(r"^[A-Z]{2}[A-Z2-9]{3}$")
        if isinstance(v, list):
            for element in v:
                if isinstance(element, str) and not pattern.search(element):
                    err_msg = f"Invalid un_location_code format: {element}"
                    raise ValueError(err_msg)
        elif isinstance(v, str) and not pattern.search(v):
            err_msg = f"Invalid un_location_code format: {v}"
            raise ValueError(err_msg)
        return v


class ReeferTelemetryReading(ConfiguredBaseModel):
    """
    DCSA Track & Trace v3.0.0 refrigerated container IoT telemetry packet with physical safety bounds.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://tasmancontainerline.example/linkml/dcsa/tnt/v3'})

    reading_id: str = Field(default=..., description="""Unique telemetry packet identifier emitted by the reefer modem.""", json_schema_extra = { "linkml_meta": {'domain_of': ['ReeferTelemetryReading']} })
    equipment_reference: str = Field(default=..., description="""ISO 6346 identifier of the monitored reefer container.""", json_schema_extra = { "linkml_meta": {'domain_of': ['EquipmentEvent', 'ReeferTelemetryReading']} })
    recorded_at: datetime  = Field(default=..., description="""UTC timestamp recorded by the reefer sensor controller.""", json_schema_extra = { "linkml_meta": {'domain_of': ['ReeferTelemetryReading']} })
    setpoint_temp_c: float = Field(default=..., description="""Target cargo setpoint temperature in degrees Celsius (-40C to +30C).""", ge=-40.0, le=30.0, json_schema_extra = { "linkml_meta": {'domain_of': ['ReeferTelemetryReading']} })
    supply_air_temp_c: float = Field(default=..., description="""Supply air probe temperature in degrees Celsius (-45C to +60C); rejects sensor faults such as -99C.""", ge=-45.0, le=60.0, json_schema_extra = { "linkml_meta": {'domain_of': ['ReeferTelemetryReading']} })
    return_air_temp_c: float = Field(default=..., description="""Return air probe temperature in degrees Celsius (-45C to +60C); rejects sensor faults such as -99C.""", ge=-45.0, le=60.0, json_schema_extra = { "linkml_meta": {'domain_of': ['ReeferTelemetryReading']} })
    relative_humidity_pct: Optional[float] = Field(default=None, description="""Cargo chamber relative humidity percentage (0 to 100).""", ge=0.0, le=100.0, json_schema_extra = { "linkml_meta": {'domain_of': ['ReeferTelemetryReading']} })
    power_status: PowerStatus = Field(default=..., description="""Reefer compressor/power supply state (ON, OFF, ALARM, DEFROST, UNKNOWN).""", json_schema_extra = { "linkml_meta": {'domain_of': ['ReeferTelemetryReading']} })
    latitude: float = Field(default=..., description="""GPS latitude reported with the telemetry reading (-90 to +90).""", ge=-90.0, le=90.0, json_schema_extra = { "linkml_meta": {'domain_of': ['Location', 'ReeferTelemetryReading']} })
    longitude: float = Field(default=..., description="""GPS longitude reported with the telemetry reading (-180 to +180).""", ge=-180.0, le=180.0, json_schema_extra = { "linkml_meta": {'domain_of': ['Location', 'ReeferTelemetryReading']} })
    excursion_flag: bool = Field(default=..., description="""True when supply or return temperature breached cold-chain tolerance bands.""", json_schema_extra = { "linkml_meta": {'domain_of': ['ReeferTelemetryReading']} })

    @field_validator('equipment_reference')
    def pattern_equipment_reference(cls, v):
        pattern=re.compile(r"^[A-Z]{4}[0-9]{7}$")
        if isinstance(v, list):
            for element in v:
                if isinstance(element, str) and not pattern.search(element):
                    err_msg = f"Invalid equipment_reference format: {element}"
                    raise ValueError(err_msg)
        elif isinstance(v, str) and not pattern.search(v):
            err_msg = f"Invalid equipment_reference format: {v}"
            raise ValueError(err_msg)
        return v


class TransportDocument(ConfiguredBaseModel):
    """
    DCSA Electronic Bill of Lading (eBL v3) transport document master record.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://tasmancontainerline.example/linkml/dcsa/ebl/v3'})

    transport_document_reference: str = Field(default=..., description="""Unique transport document / Bill of Lading reference number.""", json_schema_extra = { "linkml_meta": {'domain_of': ['TransportDocument']} })
    carrier_booking_reference: str = Field(default=..., description="""Associated DCSA carrier booking reference.""", json_schema_extra = { "linkml_meta": {'domain_of': ['TransportDocument', 'BookingRecord']} })
    document_status: ShipmentEventTypeCode = Field(default=..., description="""Current DCSA eBL workflow state (e.g., DRFT, APPR, ISSU, SURR).""", json_schema_extra = { "linkml_meta": {'domain_of': ['TransportDocument']} })
    issue_date: date = Field(default=..., description="""Date the transport document was issued or drafted.""", json_schema_extra = { "linkml_meta": {'domain_of': ['TransportDocument']} })
    shipper_name: str = Field(default=..., description="""Legal commercial shipper organization name.""", json_schema_extra = { "linkml_meta": {'domain_of': ['TransportDocument']} })
    shipper_contact_email: str = Field(default=..., description="""Shipper primary contact email address (governed PII attribute).""", json_schema_extra = { "linkml_meta": {'annotations': {'classification': {'tag': 'classification',
                                            'value': 'confidential'},
                         'pii': {'tag': 'pii', 'value': 'true'},
                         'pii_category': {'tag': 'pii_category',
                                          'value': 'direct_identifier'}},
         'domain_of': ['TransportDocument']} })
    consignee_name: str = Field(default=..., description="""Designated consignee party name (governed PII attribute).""", json_schema_extra = { "linkml_meta": {'annotations': {'classification': {'tag': 'classification',
                                            'value': 'confidential'},
                         'pii': {'tag': 'pii', 'value': 'true'},
                         'pii_category': {'tag': 'pii_category',
                                          'value': 'party_name'}},
         'domain_of': ['TransportDocument']} })
    port_of_loading: str = Field(default=..., description="""UN/LOCODE port of loading.""", json_schema_extra = { "linkml_meta": {'domain_of': ['TransportDocument']} })
    port_of_discharge: str = Field(default=..., description="""UN/LOCODE port of discharge.""", json_schema_extra = { "linkml_meta": {'domain_of': ['TransportDocument']} })
    vessel_imo_number: Optional[str] = Field(default=None, description="""7-digit IMO number of the primary ocean vessel.""", json_schema_extra = { "linkml_meta": {'domain_of': ['TransportEvent',
                       'TransportDocument',
                       'CarrierSchedule',
                       'PortCallTimestamp',
                       'PortCallPerformanceKpi']} })

    @field_validator('shipper_contact_email')
    def pattern_shipper_contact_email(cls, v):
        pattern=re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
        if isinstance(v, list):
            for element in v:
                if isinstance(element, str) and not pattern.search(element):
                    err_msg = f"Invalid shipper_contact_email format: {element}"
                    raise ValueError(err_msg)
        elif isinstance(v, str) and not pattern.search(v):
            err_msg = f"Invalid shipper_contact_email format: {v}"
            raise ValueError(err_msg)
        return v

    @field_validator('port_of_loading')
    def pattern_port_of_loading(cls, v):
        pattern=re.compile(r"^[A-Z]{2}[A-Z2-9]{3}$")
        if isinstance(v, list):
            for element in v:
                if isinstance(element, str) and not pattern.search(element):
                    err_msg = f"Invalid port_of_loading format: {element}"
                    raise ValueError(err_msg)
        elif isinstance(v, str) and not pattern.search(v):
            err_msg = f"Invalid port_of_loading format: {v}"
            raise ValueError(err_msg)
        return v

    @field_validator('port_of_discharge')
    def pattern_port_of_discharge(cls, v):
        pattern=re.compile(r"^[A-Z]{2}[A-Z2-9]{3}$")
        if isinstance(v, list):
            for element in v:
                if isinstance(element, str) and not pattern.search(element):
                    err_msg = f"Invalid port_of_discharge format: {element}"
                    raise ValueError(err_msg)
        elif isinstance(v, str) and not pattern.search(v):
            err_msg = f"Invalid port_of_discharge format: {v}"
            raise ValueError(err_msg)
        return v

    @field_validator('vessel_imo_number')
    def pattern_vessel_imo_number(cls, v):
        pattern=re.compile(r"^[0-9]{7}$")
        if isinstance(v, list):
            for element in v:
                if isinstance(element, str) and not pattern.search(element):
                    err_msg = f"Invalid vessel_imo_number format: {element}"
                    raise ValueError(err_msg)
        elif isinstance(v, str) and not pattern.search(v):
            err_msg = f"Invalid vessel_imo_number format: {v}"
            raise ValueError(err_msg)
        return v


class ShipmentEvent(AuditableEvent):
    """
    DCSA ShipmentEvent tracking booking and eBL document approval, issuance, and surrender transitions.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://tasmancontainerline.example/linkml/dcsa/ebl/v3',
         'mixins': ['AuditableEvent']})

    shipment_event_type_code: ShipmentEventTypeCode = Field(default=..., description="""DCSA shipment status transition code.""", json_schema_extra = { "linkml_meta": {'domain_of': ['ShipmentEvent']} })
    document_type_code: str = Field(default=..., description="""DCSA document type code (e.g., TRD for Transport Document, CBR for Carrier Booking).""", json_schema_extra = { "linkml_meta": {'domain_of': ['ShipmentEvent']} })
    document_id: str = Field(default=..., description="""Identifier of the referenced TransportDocument or BookingRecord.""", json_schema_extra = { "linkml_meta": {'domain_of': ['ShipmentEvent']} })
    reason: Optional[str] = Field(default=None, description="""Optional status change note or rejection reason.""", json_schema_extra = { "linkml_meta": {'domain_of': ['ShipmentEvent']} })
    event_id: str = Field(default=..., description="""Globally unique deterministic identifier for the DCSA event record.""", json_schema_extra = { "linkml_meta": {'domain_of': ['AuditableEvent']} })
    event_created_date_time: datetime  = Field(default=..., description="""UTC timestamp when the source system created the event payload.""", json_schema_extra = { "linkml_meta": {'domain_of': ['AuditableEvent']} })
    event_date_time: datetime  = Field(default=..., description="""UTC timestamp when the operational event occurred, is estimated, or is planned.""", json_schema_extra = { "linkml_meta": {'domain_of': ['AuditableEvent']} })
    event_classifier_code: EventClassifierCode = Field(default=..., description="""Classification of event_date_time (PLN, ACT, or EST).""", json_schema_extra = { "linkml_meta": {'domain_of': ['AuditableEvent']} })
    source_system: str = Field(default=..., description="""Originating operational system identifier (e.g., portgate_tos, voyagecore_ebl).""", json_schema_extra = { "linkml_meta": {'domain_of': ['AuditableEvent']} })

    @field_validator('document_type_code')
    def pattern_document_type_code(cls, v):
        pattern=re.compile(r"^(CBR|BKG|SHI|SRM|TRD|ARN|VGM|CAS|CUS|DGD|OOG)$")
        if isinstance(v, list):
            for element in v:
                if isinstance(element, str) and not pattern.search(element):
                    err_msg = f"Invalid document_type_code format: {element}"
                    raise ValueError(err_msg)
        elif isinstance(v, str) and not pattern.search(v):
            err_msg = f"Invalid document_type_code format: {v}"
            raise ValueError(err_msg)
        return v


class BookingRecord(ConfiguredBaseModel):
    """
    DCSA Booking v2 freight booking request and confirmation record.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://tasmancontainerline.example/linkml/dcsa/ebl/v3'})

    carrier_booking_reference: str = Field(default=..., description="""Unique carrier booking reference identifier.""", json_schema_extra = { "linkml_meta": {'domain_of': ['TransportDocument', 'BookingRecord']} })
    booking_status: ShipmentEventTypeCode = Field(default=..., description="""Current DCSA booking lifecycle status.""", json_schema_extra = { "linkml_meta": {'domain_of': ['BookingRecord']} })
    booking_created_at: datetime  = Field(default=..., description="""UTC timestamp when booking was created.""", json_schema_extra = { "linkml_meta": {'domain_of': ['BookingRecord']} })
    place_of_receipt: str = Field(default=..., description="""UN/LOCODE origin place of receipt.""", json_schema_extra = { "linkml_meta": {'domain_of': ['BookingRecord']} })
    place_of_delivery: str = Field(default=..., description="""UN/LOCODE destination place of delivery.""", json_schema_extra = { "linkml_meta": {'domain_of': ['BookingRecord']} })
    teu_count: int = Field(default=..., description="""Booked capacity in Twenty-foot Equivalent Units (1 to 25000).""", ge=1, le=25000, json_schema_extra = { "linkml_meta": {'domain_of': ['BookingRecord']} })
    reefer_required: bool = Field(default=..., description="""True when refrigerated containers are required for the booking.""", json_schema_extra = { "linkml_meta": {'domain_of': ['BookingRecord']} })

    @field_validator('place_of_receipt')
    def pattern_place_of_receipt(cls, v):
        pattern=re.compile(r"^[A-Z]{2}[A-Z2-9]{3}$")
        if isinstance(v, list):
            for element in v:
                if isinstance(element, str) and not pattern.search(element):
                    err_msg = f"Invalid place_of_receipt format: {element}"
                    raise ValueError(err_msg)
        elif isinstance(v, str) and not pattern.search(v):
            err_msg = f"Invalid place_of_receipt format: {v}"
            raise ValueError(err_msg)
        return v

    @field_validator('place_of_delivery')
    def pattern_place_of_delivery(cls, v):
        pattern=re.compile(r"^[A-Z]{2}[A-Z2-9]{3}$")
        if isinstance(v, list):
            for element in v:
                if isinstance(element, str) and not pattern.search(element):
                    err_msg = f"Invalid place_of_delivery format: {element}"
                    raise ValueError(err_msg)
        elif isinstance(v, str) and not pattern.search(v):
            err_msg = f"Invalid place_of_delivery format: {v}"
            raise ValueError(err_msg)
        return v


class CarrierSchedule(ConfiguredBaseModel):
    """
    DCSA Operational Vessel Schedules (OVS) proforma and planned port call schedule.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://tasmancontainerline.example/linkml/dcsa/ebl/v3'})

    schedule_id: str = Field(default=..., description="""Unique vessel schedule port call slot identifier.""", json_schema_extra = { "linkml_meta": {'domain_of': ['CarrierSchedule']} })
    vessel_imo_number: str = Field(default=..., description="""7-digit IMO vessel identifier.""", json_schema_extra = { "linkml_meta": {'domain_of': ['TransportEvent',
                       'TransportDocument',
                       'CarrierSchedule',
                       'PortCallTimestamp',
                       'PortCallPerformanceKpi']} })
    vessel_name: str = Field(default=..., description="""Registered commercial vessel name.""", json_schema_extra = { "linkml_meta": {'domain_of': ['CarrierSchedule', 'PortCallPerformanceKpi']} })
    carrier_service_code: str = Field(default=..., description="""Tasman trade lane service loop code (e.g., TASMAN-EXPRESS).""", json_schema_extra = { "linkml_meta": {'domain_of': ['CarrierSchedule']} })
    carrier_voyage_number: str = Field(default=..., description="""Planned operational voyage code.""", json_schema_extra = { "linkml_meta": {'domain_of': ['EquipmentEvent',
                       'TransportEvent',
                       'CarrierSchedule',
                       'PortCallTimestamp',
                       'PortCallPerformanceKpi']} })
    un_location_code: str = Field(default=..., description="""Scheduled UN/LOCODE port of call.""", json_schema_extra = { "linkml_meta": {'domain_of': ['Location',
                       'EquipmentEvent',
                       'TransportEvent',
                       'CarrierSchedule',
                       'PortCallTimestamp',
                       'PortCallPerformanceKpi']} })
    planned_arrival_utc: datetime  = Field(default=..., description="""Scheduled baseline arrival timestamp in UTC.""", json_schema_extra = { "linkml_meta": {'domain_of': ['CarrierSchedule']} })
    planned_departure_utc: datetime  = Field(default=..., description="""Scheduled baseline departure timestamp in UTC.""", json_schema_extra = { "linkml_meta": {'domain_of': ['CarrierSchedule']} })

    @field_validator('vessel_imo_number')
    def pattern_vessel_imo_number(cls, v):
        pattern=re.compile(r"^[0-9]{7}$")
        if isinstance(v, list):
            for element in v:
                if isinstance(element, str) and not pattern.search(element):
                    err_msg = f"Invalid vessel_imo_number format: {element}"
                    raise ValueError(err_msg)
        elif isinstance(v, str) and not pattern.search(v):
            err_msg = f"Invalid vessel_imo_number format: {v}"
            raise ValueError(err_msg)
        return v

    @field_validator('un_location_code')
    def pattern_un_location_code(cls, v):
        pattern=re.compile(r"^[A-Z]{2}[A-Z2-9]{3}$")
        if isinstance(v, list):
            for element in v:
                if isinstance(element, str) and not pattern.search(element):
                    err_msg = f"Invalid un_location_code format: {element}"
                    raise ValueError(err_msg)
        elif isinstance(v, str) and not pattern.search(v):
            err_msg = f"Invalid un_location_code format: {v}"
            raise ValueError(err_msg)
        return v


class PortCallTimestamp(AuditableEvent):
    """
    DCSA Just-In-Time port call milestone timestamp spanning ETA_PBP, ATA_PBP, ETB_BERTH, ATB_BERTH, and ATD_BERTH.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://tasmancontainerline.example/linkml/dcsa/jit/v1',
         'mixins': ['AuditableEvent']})

    port_call_id: str = Field(default=..., description="""Canonical port call identifier joining carrier schedule, terminal berth, and vessel events.""", json_schema_extra = { "linkml_meta": {'domain_of': ['PortCallTimestamp', 'PortCallPerformanceKpi']} })
    vessel_imo_number: str = Field(default=..., description="""7-digit IMO vessel identifier.""", json_schema_extra = { "linkml_meta": {'domain_of': ['TransportEvent',
                       'TransportDocument',
                       'CarrierSchedule',
                       'PortCallTimestamp',
                       'PortCallPerformanceKpi']} })
    carrier_voyage_number: str = Field(default=..., description="""Carrier voyage code for the port call.""", json_schema_extra = { "linkml_meta": {'domain_of': ['EquipmentEvent',
                       'TransportEvent',
                       'CarrierSchedule',
                       'PortCallTimestamp',
                       'PortCallPerformanceKpi']} })
    un_location_code: str = Field(default=..., description="""UN/LOCODE port identifier where the JIT milestone was recorded.""", json_schema_extra = { "linkml_meta": {'domain_of': ['Location',
                       'EquipmentEvent',
                       'TransportEvent',
                       'CarrierSchedule',
                       'PortCallTimestamp',
                       'PortCallPerformanceKpi']} })
    jit_phase_code: JitPhaseCode = Field(default=..., description="""One of the 5 JIT phases (ETA_PBP, ATA_PBP, ETB_BERTH, ATB_BERTH, ATD_BERTH).""", json_schema_extra = { "linkml_meta": {'domain_of': ['PortCallTimestamp']} })
    terminal_code: Optional[str] = Field(default=None, description="""SMDG container terminal facility code.""", json_schema_extra = { "linkml_meta": {'domain_of': ['PortCallTimestamp']} })
    berth_code: Optional[str] = Field(default=None, description="""Assigned terminal berth identifier.""", json_schema_extra = { "linkml_meta": {'domain_of': ['PortCallTimestamp']} })
    delay_reason_code: Optional[str] = Field(default=None, description="""SMDG delay reason code when vessel misses target window.""", json_schema_extra = { "linkml_meta": {'domain_of': ['TransportEvent', 'PortCallTimestamp']} })
    event_id: str = Field(default=..., description="""Globally unique deterministic identifier for the DCSA event record.""", json_schema_extra = { "linkml_meta": {'domain_of': ['AuditableEvent']} })
    event_created_date_time: datetime  = Field(default=..., description="""UTC timestamp when the source system created the event payload.""", json_schema_extra = { "linkml_meta": {'domain_of': ['AuditableEvent']} })
    event_date_time: datetime  = Field(default=..., description="""UTC timestamp when the operational event occurred, is estimated, or is planned.""", json_schema_extra = { "linkml_meta": {'domain_of': ['AuditableEvent']} })
    event_classifier_code: EventClassifierCode = Field(default=..., description="""Classification of event_date_time (PLN, ACT, or EST).""", json_schema_extra = { "linkml_meta": {'domain_of': ['AuditableEvent']} })
    source_system: str = Field(default=..., description="""Originating operational system identifier (e.g., portgate_tos, voyagecore_ebl).""", json_schema_extra = { "linkml_meta": {'domain_of': ['AuditableEvent']} })

    @field_validator('vessel_imo_number')
    def pattern_vessel_imo_number(cls, v):
        pattern=re.compile(r"^[0-9]{7}$")
        if isinstance(v, list):
            for element in v:
                if isinstance(element, str) and not pattern.search(element):
                    err_msg = f"Invalid vessel_imo_number format: {element}"
                    raise ValueError(err_msg)
        elif isinstance(v, str) and not pattern.search(v):
            err_msg = f"Invalid vessel_imo_number format: {v}"
            raise ValueError(err_msg)
        return v

    @field_validator('un_location_code')
    def pattern_un_location_code(cls, v):
        pattern=re.compile(r"^[A-Z]{2}[A-Z2-9]{3}$")
        if isinstance(v, list):
            for element in v:
                if isinstance(element, str) and not pattern.search(element):
                    err_msg = f"Invalid un_location_code format: {element}"
                    raise ValueError(err_msg)
        elif isinstance(v, str) and not pattern.search(v):
            err_msg = f"Invalid un_location_code format: {v}"
            raise ValueError(err_msg)
        return v


class PortCallPerformanceKpi(ConfiguredBaseModel):
    """
    Curated Gold analytical dataset summarizing port call turnaround, berth wait time, and schedule reliability per port call.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://tasmancontainerline.example/linkml/dcsa/enterprise'})

    port_call_id: str = Field(default=..., description="""Canonical port call primary key matching silver_port_call_turnaround.""", json_schema_extra = { "linkml_meta": {'domain_of': ['PortCallTimestamp', 'PortCallPerformanceKpi']} })
    vessel_imo_number: str = Field(default=..., description="""7-digit IMO ship identification number.""", json_schema_extra = { "linkml_meta": {'domain_of': ['TransportEvent',
                       'TransportDocument',
                       'CarrierSchedule',
                       'PortCallTimestamp',
                       'PortCallPerformanceKpi']} })
    vessel_name: str = Field(default=..., description="""Vessel name for operational reporting.""", json_schema_extra = { "linkml_meta": {'domain_of': ['CarrierSchedule', 'PortCallPerformanceKpi']} })
    carrier_voyage_number: str = Field(default=..., description="""Operational carrier voyage identifier.""", json_schema_extra = { "linkml_meta": {'domain_of': ['EquipmentEvent',
                       'TransportEvent',
                       'CarrierSchedule',
                       'PortCallTimestamp',
                       'PortCallPerformanceKpi']} })
    un_location_code: str = Field(default=..., description="""UN/LOCODE port identifier.""", json_schema_extra = { "linkml_meta": {'domain_of': ['Location',
                       'EquipmentEvent',
                       'TransportEvent',
                       'CarrierSchedule',
                       'PortCallTimestamp',
                       'PortCallPerformanceKpi']} })
    port_name: str = Field(default=..., description="""Normalized port name.""", json_schema_extra = { "linkml_meta": {'domain_of': ['PortCallPerformanceKpi']} })
    call_date: date = Field(default=..., description="""Port call arrival calendar date.""", json_schema_extra = { "linkml_meta": {'domain_of': ['PortCallPerformanceKpi']} })
    on_time_flag: int = Field(default=..., description="""Binary schedule reliability indicator (1 = arrived within OVS SLA window, 0 = delayed).""", ge=0, le=1, json_schema_extra = { "linkml_meta": {'domain_of': ['PortCallPerformanceKpi']} })
    port_turnaround_hours: float = Field(default=..., description="""Total elapsed hours between Pilot Boarding Place arrival and berth departure.""", ge=0.0, le=720.0, json_schema_extra = { "linkml_meta": {'domain_of': ['PortCallPerformanceKpi']} })
    berth_wait_hours: float = Field(default=..., description="""Elapsed anchorage/wait hours between Pilot Boarding Place arrival and berth all-fast.""", ge=0.0, le=720.0, json_schema_extra = { "linkml_meta": {'domain_of': ['PortCallPerformanceKpi']} })

    @field_validator('vessel_imo_number')
    def pattern_vessel_imo_number(cls, v):
        pattern=re.compile(r"^[0-9]{7}$")
        if isinstance(v, list):
            for element in v:
                if isinstance(element, str) and not pattern.search(element):
                    err_msg = f"Invalid vessel_imo_number format: {element}"
                    raise ValueError(err_msg)
        elif isinstance(v, str) and not pattern.search(v):
            err_msg = f"Invalid vessel_imo_number format: {v}"
            raise ValueError(err_msg)
        return v

    @field_validator('un_location_code')
    def pattern_un_location_code(cls, v):
        pattern=re.compile(r"^[A-Z]{2}[A-Z2-9]{3}$")
        if isinstance(v, list):
            for element in v:
                if isinstance(element, str) and not pattern.search(element):
                    err_msg = f"Invalid un_location_code format: {element}"
                    raise ValueError(err_msg)
        elif isinstance(v, str) and not pattern.search(v):
            err_msg = f"Invalid un_location_code format: {v}"
            raise ValueError(err_msg)
        return v


# Model rebuild
# see https://pydantic-docs.helpmanual.io/usage/models/#rebuilding-a-model
Location.model_rebuild()
AuditableEvent.model_rebuild()
EquipmentEvent.model_rebuild()
TransportEvent.model_rebuild()
ReeferTelemetryReading.model_rebuild()
TransportDocument.model_rebuild()
ShipmentEvent.model_rebuild()
BookingRecord.model_rebuild()
CarrierSchedule.model_rebuild()
PortCallTimestamp.model_rebuild()
PortCallPerformanceKpi.model_rebuild()
