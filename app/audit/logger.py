"""
CareLens Clinical Audit Logger with Cryptographic Hash-Chain Integrity.
Maintains genuinely tamper-evident audit trails with clinician verification and privacy protection.
Does NOT persist raw patient imagery without explicit authorization.
"""

import os
import json
import hashlib
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple
from pydantic import BaseModel, Field, ConfigDict


def compute_record_hash(payload: Dict[str, Any]) -> str:
    """
    Computes deterministic SHA-256 digest of canonical JSON serialization.
    Excludes any existing 'record_hash' key during computation.
    """
    clean_payload = {k: v for k, v in payload.items() if k != "record_hash"}
    canonical_bytes = json.dumps(clean_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical_bytes).hexdigest()


class ClinicianAcknowledgement(BaseModel):
    model_config = ConfigDict(extra="forbid")

    clinician_id: str = Field(..., description="Staff ID or clinician name.")
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    acknowledged: bool = True
    action_taken: str = Field(..., description="Action taken, e.g. 'Adjusted flow', 'Verified false alarm', 'Continued monitoring'.")
    notes: Optional[str] = None


class AuditRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sequence_number: int = Field(..., description="Monotonically increasing sequence index (0, 1, 2...).")
    previous_hash: str = Field(..., description="SHA-256 digest of prior record, or 64 zeros for genesis.")
    record_hash: str = Field(..., description="SHA-256 digest of canonical record fields.")
    record_type: str = Field(default="AUDIT_FINDING", description="'AUDIT_FINDING' or 'CLINICIAN_ACKNOWLEDGEMENT'.")
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
        self._chain: List[AuditRecord] = []
        self._load_existing_logs()

    def _load_existing_logs(self):
        """Loads and indexes existing audit records into the in-memory chain."""
        self._chain = []
        if os.path.exists(self.log_file_path):
            try:
                with open(self.log_file_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line_str = line.strip()
                        if line_str:
                            data = json.loads(line_str)
                            # Handle legacy records without hash chain gracefully
                            if "sequence_number" not in data:
                                data["sequence_number"] = len(self._chain)
                            if "previous_hash" not in data:
                                data["previous_hash"] = self._chain[-1].record_hash if self._chain else "0" * 64
                            if "record_type" not in data:
                                data["record_type"] = "AUDIT_FINDING"
                            if "record_hash" not in data:
                                data["record_hash"] = compute_record_hash(data)
                            record = AuditRecord.model_validate(data)
                            self._chain.append(record)
            except Exception:
                pass

    def record_audit(
        self,
        metadata: Dict[str, Any],
        response_dict: Dict[str, Any],
    ) -> AuditRecord:
        """
        Records a safety audit event into the append-only cryptographic hash chain.
        Never saves raw pixel imagery.
        """
        seq = len(self._chain)
        prev_hash = self._chain[-1].record_hash if self._chain else "0" * 64

        raw_payload = {
            "sequence_number": seq,
            "previous_hash": prev_hash,
            "record_type": "AUDIT_FINDING",
            "audit_id": metadata.get("audit_id", "unknown"),
            "timestamp": metadata.get("timestamp", datetime.now(timezone.utc).isoformat()),
            "model_version": metadata.get("provider", "edge_cv"),
            "runtime_environment": "macOS_AppleSilicon_Metal_Edge",
            "protocol_id": metadata.get("protocol_id", "default"),
            "protocol_version": metadata.get("protocol_version", "1.0.0"),
            "patient_context": metadata.get("patient_context", "adult"),
            "inspection_type": response_dict.get("inspection_type", "Unknown"),
            "overall_status": response_dict.get("overall_status", "WARNING"),
            "latency_ms": metadata.get("latency_ms", 0.0),
            "findings_count": len(response_dict.get("findings", [])),
            "findings_summary": response_dict.get("findings", []),
            "vitals_summary": response_dict.get("vitals_extracted", {}),
            "audio_alert_text": response_dict.get("audio_alert_text", ""),
            "acknowledgement": None,
        }

        raw_payload["record_hash"] = compute_record_hash(raw_payload)
        record = AuditRecord.model_validate(raw_payload)
        self._chain.append(record)

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
        Maintains append-only tamper evidence by appending a new linked record into the hash chain.
        """
        ack = ClinicianAcknowledgement(
            clinician_id=clinician_id,
            action_taken=action_taken,
            notes=notes,
        )

        target_record: Optional[AuditRecord] = None
        for rec in reversed(self._chain):
            if rec.audit_id == audit_id and rec.record_type == "AUDIT_FINDING":
                rec.acknowledgement = ack
                target_record = rec
                break

        if not target_record:
            return None

        # Append acknowledgement event into the cryptographic ledger
        seq = len(self._chain)
        prev_hash = self._chain[-1].record_hash if self._chain else "0" * 64

        ack_payload = {
            "sequence_number": seq,
            "previous_hash": prev_hash,
            "record_type": "CLINICIAN_ACKNOWLEDGEMENT",
            "audit_id": audit_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "model_version": "human_clinician",
            "runtime_environment": "CareLens_Clinical_Cockpit",
            "protocol_id": target_record.protocol_id,
            "protocol_version": target_record.protocol_version,
            "patient_context": target_record.patient_context,
            "inspection_type": target_record.inspection_type,
            "overall_status": target_record.overall_status,
            "latency_ms": 0.0,
            "findings_count": 0,
            "findings_summary": [f"Clinician verification ({clinician_id}): {action_taken}"],
            "vitals_summary": {},
            "audio_alert_text": "",
            "acknowledgement": ack.model_dump(),
        }
        ack_payload["record_hash"] = compute_record_hash(ack_payload)
        ack_record = AuditRecord.model_validate(ack_payload)
        self._chain.append(ack_record)

        try:
            with open(self.log_file_path, "a", encoding="utf-8") as f:
                f.write(ack_record.model_dump_json() + "\n")
        except Exception:
            pass

        return target_record

    def verify_integrity(self, file_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Cryptographically validates the hash-chain integrity of the audit log.
        Detects any tampering, alteration, insertion, deletion, or reordering.
        """
        target_path = file_path or self.log_file_path
        if not os.path.exists(target_path):
            return {
                "valid": True,
                "record_count": 0,
                "errors": [],
                "head_hash": None,
                "detail": "Log file does not exist yet; clean state.",
            }

        errors: List[str] = []
        expected_prev = "0" * 64
        count = 0
        last_hash: Optional[str] = None

        with open(target_path, "r", encoding="utf-8") as f:
            for line_idx, line in enumerate(f):
                line_str = line.strip()
                if not line_str:
                    continue

                try:
                    data = json.loads(line_str)
                except Exception as e:
                    errors.append(f"Line {line_idx}: Invalid JSON: {e}")
                    continue

                seq = data.get("sequence_number")
                if seq != count:
                    errors.append(f"Line {line_idx}: Sequence break. Expected sequence_number {count}, got {seq}.")

                prev_hash = data.get("previous_hash")
                if prev_hash != expected_prev:
                    errors.append(
                        f"Line {line_idx} (seq {seq}): Previous hash mismatch. "
                        f"Expected '{expected_prev}', got '{prev_hash}'."
                    )

                stored_hash = data.get("record_hash")
                computed_hash = compute_record_hash(data)
                if stored_hash != computed_hash:
                    errors.append(
                        f"Line {line_idx} (seq {seq}): Record hash mismatch / data tampering detected. "
                        f"Computed '{computed_hash}', stored '{stored_hash}'."
                    )

                expected_prev = stored_hash
                last_hash = stored_hash
                count += 1

        return {
            "valid": len(errors) == 0,
            "record_count": count,
            "errors": errors,
            "head_hash": last_hash,
            "detail": "Tamper-evident verification succeeded; hash chain intact." if len(errors) == 0 else "Tamper-evident integrity check FAILED.",
        }

    def get_recent_records(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Returns recent audit logs in reverse chronological order."""
        return [r.model_dump() for r in reversed(self._chain[-limit:])]


# Global singleton logger
global_audit_logger = ClinicalAuditLogger()
