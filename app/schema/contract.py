"""
CareLens Canonical Output Contract and Pydantic Validation Models.
Enforces the exact CareLens JSON contract specified by clinical safety requirements.
"""

from enum import Enum
from typing import List
from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict


class InspectionType(str, Enum):
    EQUIPMENT_SETUP = "Equipment_Setup"
    PATIENT_MONITOR = "Patient_Monitor"
    UNKNOWN = "Unknown"


class OverallStatus(str, Enum):
    PASS = "PASS"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class OverlayStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"


class VitalsExtracted(BaseModel):
    """
    Extracted vital signs from patient monitors.
    Always includes all 4 keys as strings. Missing/unreadable values must be "N/A".
    """
    model_config = ConfigDict(extra="forbid")

    heart_rate_bpm: str = Field(
        default="N/A",
        description="Heart rate in beats per minute, or 'N/A' if missing/unreadable."
    )
    spo2_percent: str = Field(
        default="N/A",
        description="Oxygen saturation in percent, or 'N/A' if missing/unreadable."
    )
    blood_pressure_mmHg: str = Field(
        default="N/A",
        description="Blood pressure formatted as 'SYS/DIA' (e.g. '120/80') or 'N/A'."
    )
    respiration_rate: str = Field(
        default="N/A",
        description="Respiration rate in breaths per minute, or 'N/A' if missing/unreadable."
    )


class VisualOverlay(BaseModel):
    """
    Normalized 2D bounding box and assessment for a detected clinical component.
    box_2d format: [ymin, xmin, ymax, xmax] with coordinates in 0..1000.
    """
    model_config = ConfigDict(extra="forbid")

    label: str = Field(..., description="Short descriptive label of the visible component.")
    box_2d: List[int] = Field(
        ...,
        description="Four normalized integers [ymin, xmin, ymax, xmax] between 0 and 1000."
    )
    status: OverlayStatus = Field(
        ...,
        description="Status of this specific component: PASS or FAIL against validated rules."
    )
    detail: str = Field(
        ...,
        description="Grounded visual observation details; verify against clinical protocol."
    )

    @field_validator("box_2d")
    @classmethod
    def validate_box_2d(cls, box: List[int]) -> List[int]:
        if len(box) != 4:
            raise ValueError(f"box_2d must contain exactly 4 integers [ymin, xmin, ymax, xmax], got {len(box)}")
        ymin, xmin, ymax, xmax = box
        for val, name in zip(box, ["ymin", "xmin", "ymax", "xmax"]):
            if not isinstance(val, int):
                raise ValueError(f"{name} must be an integer, got {type(val)}")
            if val < 0 or val > 1000:
                raise ValueError(f"{name} must be between 0 and 1000, got {val}")
        if ymin > ymax:
            raise ValueError(f"ymin ({ymin}) must be <= ymax ({ymax})")
        if xmin > xmax:
            raise ValueError(f"xmin ({xmin}) must be <= xmax ({xmax})")
        return box


class CareLensResponse(BaseModel):
    """
    Canonical response contract for CareLens.
    Strictly forbids any extra keys to ensure reliable downstream consumption.
    """
    model_config = ConfigDict(extra="forbid")

    inspection_type: InspectionType = Field(
        ...,
        description="Classification: Equipment_Setup, Patient_Monitor, or Unknown."
    )
    overall_status: OverallStatus = Field(
        ...,
        description="Risk assessment: PASS, WARNING, or CRITICAL according to validated rules."
    )
    vitals_extracted: VitalsExtracted = Field(
        ...,
        description="Extracted monitor readings or N/A values."
    )
    visual_overlays: List[VisualOverlay] = Field(
        default_factory=list,
        description="Detected visual components with normalized bounding boxes."
    )
    findings: List[str] = Field(
        default_factory=list,
        description="Concise evidence-based observations without ungrounded speculation."
    )
    audio_alert_text: str = Field(
        ...,
        description="One imperative sentence of fewer than 15 words for voice alerts."
    )

    @field_validator("audio_alert_text")
    @classmethod
    def validate_audio_alert(cls, text: str) -> str:
        words = text.strip().split()
        if len(words) >= 15:
            raise ValueError(
                f"audio_alert_text must be fewer than 15 words (got {len(words)} words: '{text}')"
            )
        if not text.strip():
            raise ValueError("audio_alert_text cannot be empty")
        return text.strip()
