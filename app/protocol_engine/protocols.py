"""
Versioned Clinical Protocol Definitions for CareLens.
Separates validated safety rules from model reasoning.
"""

from typing import Dict, Any, Optional
from pydantic import BaseModel, Field


class VitalsThresholds(BaseModel):
    hr_min: int
    hr_max: int
    hr_critical_low: int
    hr_critical_high: int

    spo2_min_nominal: int
    spo2_warning_threshold: int
    spo2_critical_threshold: int
    spo2_hyperoxia_warning: Optional[int] = None

    bp_systolic_min: int
    bp_systolic_max: int
    bp_systolic_critical_low: int
    bp_systolic_critical_high: int

    rr_min: int
    rr_max: int
    rr_critical_low: int
    rr_critical_high: int


class EquipmentRules(BaseModel):
    max_nasal_cannula_o2_lpm: float
    max_pediatric_o2_lpm: float
    require_open_roller_clamp: bool = True
    forbid_air_in_line: bool = True


class ClinicalProtocol(BaseModel):
    protocol_id: str
    version: str
    name: str
    population: str
    description: str
    vitals: VitalsThresholds
    equipment: EquipmentRules


CLINICAL_PROTOCOLS: Dict[str, ClinicalProtocol] = {
    "adult_icu_v1.0": ClinicalProtocol(
        protocol_id="adult_icu_v1.0",
        version="1.0.0",
        name="Adult Intensive Care Standard Protocol",
        population="Adult (>= 18 yrs)",
        description="Standard reference ranges and equipment rules for adult ICU beds.",
        vitals=VitalsThresholds(
            hr_min=60,
            hr_max=100,
            hr_critical_low=45,
            hr_critical_high=130,
            spo2_min_nominal=94,
            spo2_warning_threshold=93,
            spo2_critical_threshold=88,
            bp_systolic_min=90,
            bp_systolic_max=140,
            bp_systolic_critical_low=80,
            bp_systolic_critical_high=180,
            rr_min=12,
            rr_max=20,
            rr_critical_low=8,
            rr_critical_high=30,
        ),
        equipment=EquipmentRules(
            max_nasal_cannula_o2_lpm=6.0,
            max_pediatric_o2_lpm=2.0,
            require_open_roller_clamp=True,
            forbid_air_in_line=True,
        ),
    ),
    "pediatric_icu_v1.0": ClinicalProtocol(
        protocol_id="pediatric_icu_v1.0",
        version="1.0.0",
        name="Pediatric Intensive Care Safety Protocol",
        population="Pediatric (1 mo - 12 yrs)",
        description="Strict oxygen titration limits and pediatric vital reference ranges.",
        vitals=VitalsThresholds(
            hr_min=80,
            hr_max=130,
            hr_critical_low=60,
            hr_critical_high=160,
            spo2_min_nominal=95,
            spo2_warning_threshold=94,
            spo2_critical_threshold=90,
            bp_systolic_min=80,
            bp_systolic_max=115,
            bp_systolic_critical_low=70,
            bp_systolic_critical_high=140,
            rr_min=20,
            rr_max=30,
            rr_critical_low=14,
            rr_critical_high=45,
        ),
        equipment=EquipmentRules(
            max_nasal_cannula_o2_lpm=2.0,
            max_pediatric_o2_lpm=2.0,
            require_open_roller_clamp=True,
            forbid_air_in_line=True,
        ),
    ),
    "neonatal_icu_v1.0": ClinicalProtocol(
        protocol_id="neonatal_icu_v1.0",
        version="1.0.0",
        name="Neonatal Intensive Care Precision Protocol",
        population="Neonatal (< 28 days)",
        description="Neonatal vital ranges and strict hyperoxia/hypoxia protection.",
        vitals=VitalsThresholds(
            hr_min=100,
            hr_max=160,
            hr_critical_low=80,
            hr_critical_high=190,
            spo2_min_nominal=90,
            spo2_warning_threshold=89,
            spo2_critical_threshold=85,
            spo2_hyperoxia_warning=98,
            bp_systolic_min=60,
            bp_systolic_max=90,
            bp_systolic_critical_low=50,
            bp_systolic_critical_high=110,
            rr_min=30,
            rr_max=60,
            rr_critical_low=20,
            rr_critical_high=75,
        ),
        equipment=EquipmentRules(
            max_nasal_cannula_o2_lpm=1.0,
            max_pediatric_o2_lpm=1.0,
            require_open_roller_clamp=True,
            forbid_air_in_line=True,
        ),
    ),
}

DEFAULT_PROTOCOL_ID = "adult_icu_v1.0"


def get_protocol(protocol_id: Optional[str] = None) -> ClinicalProtocol:
    if not protocol_id or protocol_id not in CLINICAL_PROTOCOLS:
        return CLINICAL_PROTOCOLS[DEFAULT_PROTOCOL_ID]
    return CLINICAL_PROTOCOLS[protocol_id]
