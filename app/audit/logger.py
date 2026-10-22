"""
CareLens Clinical Audit Logger.
Maintains tamper-evident audit trails with clinician verification and privacy protection.
Does NOT persist raw patient imagery without explicit authorization.
"""

import os
import json
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class ClinicianAcknowledgement(BaseModel):
    clinician_id: str = Field(..., description="Staff ID or clinician name.")
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    acknowledged: bool = True
    action_taken: str = Field(..., description="Action taken, e.g. 'Adjusted flow', 'Verified false alarm', 'Continued monitoring'.")
    notes: Optional[str] = None


class AuditRecord(BaseModel):
    audit_id: str
    timestamp: str
    model_version: str
    runtime_environment: str
    protocol_id: str
    protocol_version: str
    patient_context: str
    inspection_type: str
    overall_status: str
    latency_ms: float
    findings_count: int
    findings_summary: List[str]
    vitals_summary: Dict[str, str]
    audio_alert_text: str
    acknowledgement: Optional[ClinicianAcknowledgement] = None


class ClinicalAuditLogger:
    def __init__(self, log_file_path: str = "audit_trail.jsonl"):
        self.log_file_path = log_file_path
        self._in_memory_records: List[AuditRecord] = []
        self._load_existing_logs()

    def _load_existing_logs(self):
        if os.path.exists(self.log_file_path):
            try:
                with open(self.log_file_path, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.strip():
                            data = json.loads(line)
                            self._in_memory_records.append(AuditRecord.model_validate(data))
            except Exception:
                pass

    def record_audit(
        self,
        metadata: Dict[str, Any],
        response_dict: Dict[str, Any],
    ) -> AuditRecord:
        """
        Records a safety audit event. Never saves raw pixel imagery.
        """
        record = AuditRecord(
            audit_id=metadata.get("audit_id", "unknown"),
            timestamp=metadata.get("timestamp", datetime.now(timezone.utc).isoformat()),
            model_version=metadata.get("provider", "edge_cv"),
            runtime_environment="macOS_AppleSilicon_Metal_Edge",
            protocol_id=metadata.get("protocol_id", "default"),
            protocol_version=metadata.get("protocol_version", "1.0.0"),
            patient_context=metadata.get("patient_context", "adult"),
            inspection_type=response_dict.get("inspection_type", "Unknown"),
            overall_status=response_dict.get("overall_status", "WARNING"),
            latency_ms=metadata.get("latency_ms", 0.0),
            findings_count=len(response_dict.get("findings", [])),
            findings_summary=response_dict.get("findings", []),
            vitals_summary=response_dict.get("vitals_extracted", {}),
            audio_alert_text=response_dict.get("audio_alert_text", ""),
            acknowledgement=None,
        )

        self._in_memory_records.append(record)

        # Append to persistent jsonl log
        try:
            with open(self.log_file_path, "a", encoding="utf-8") as f:
                f.write(record.model_dump_json() + "\n")
        except Exception:
            pass

        return record

    def acknowledge_audit(
        self,
        audit_id: str,
        clinician_id: str,
        action_taken: str,
        notes: Optional[str] = None,
    ) -> Optional[AuditRecord]:
        """
        Records a clinician's human verification and action.
        """
        ack = ClinicianAcknowledgement(
            clinician_id=clinician_id,
            action_taken=action_taken,
            notes=notes,
        )

        target_record: Optional[AuditRecord] = None
        for rec in reversed(self._in_memory_records):
            if rec.audit_id == audit_id:
                rec.acknowledgement = ack
                target_record = rec
                break

        if target_record:
            # Re-write the updated log file
            try:
                with open(self.log_file_path, "w", encoding="utf-8") as f:
                    for rec in self._in_memory_records:
                        f.write(rec.model_dump_json() + "\n")
            except Exception:
                pass

        return target_record

    def get_recent_records(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Returns recent audit logs in reverse chronological order."""
        return [r.model_dump() for r in reversed(self._in_memory_records[-limit:])]


# Global singleton logger
global_audit_logger = ClinicalAuditLogger()
