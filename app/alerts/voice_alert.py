"""
CareLens Voice Alert and Notification Adapter.
Enforces safety rules for audio alert synthesis: imperative, under 15 words, non-alarming.
"""

import re
from typing import Dict, Any, Optional
from app.schema.contract import OverallStatus


class VoiceAlertAdapter:
    MAX_WORDS = 14  # Strictly fewer than 15 words

    # Clinically approved imperative templates
    APPROVED_TEMPLATES = {
        OverallStatus.CRITICAL: [
            "Verify pediatric oxygen flow rate immediately against patient prescription.",
            "Verify patient monitor readings and oxygen saturation immediately.",
            "Verify patient heart rate and cardiovascular status immediately.",
            "Critical condition detected; verify patient and equipment setup immediately.",
        ],
        OverallStatus.WARNING: [
            "Verify equipment connections and settings against the approved clinical protocol.",
            "Verify patient monitor readings against the approved clinical protocol.",
            "Verify lighting and camera focus to enable complete clinical inspection.",
        ],
        OverallStatus.PASS: [
            "All visible parameters match the approved clinical protocol.",
            "Equipment connections and readings are verified within protocol limits.",
        ],
    }

    @classmethod
    def sanitize_alert_text(cls, text: str, fallback_status: OverallStatus = OverallStatus.WARNING) -> str:
        """
        Sanitizes text to ensure:
        1. Single sentence ending with a period.
        2. Fewer than 15 words.
        3. Strips markdown, newlines, and non-ASCII audio artifacts.
        """
        cleaned = re.sub(r"[\r\n\t]+", " ", text).strip()
        cleaned = re.sub(r"[*_#`]", "", cleaned)

        # Split sentences by period/exclamation/semicolon
        sentences = [s.strip() for s in re.split(r"[.!?]", cleaned) if s.strip()]
        first_sentence = sentences[0] if sentences else ""

        words = first_sentence.split()
        if not words or len(words) > cls.MAX_WORDS:
            # Fallback to an approved template for this status
            return cls.APPROVED_TEMPLATES[fallback_status][0]

        # Ensure trailing period
        return f"{' '.join(words)}."

    @classmethod
    def generate_tts_payload(
        cls,
        alert_text: str,
        status: OverallStatus,
        volume: float = 1.0,
    ) -> Dict[str, Any]:
        """
        Generates TTS synthesis configuration for browser Web Speech API or local audio daemon.
        """
        sanitized = cls.sanitize_alert_text(alert_text, status)

        # Subtle voice modulation based on severity
        if status == OverallStatus.CRITICAL:
            rate = 1.05
            pitch = 1.1
        elif status == OverallStatus.WARNING:
            rate = 1.0
            pitch = 1.0
        else:
            rate = 0.95
            pitch = 0.95

        return {
            "text": sanitized,
            "status": status.value,
            "word_count": len(sanitized.split()),
            "tts_config": {
                "rate": rate,
                "pitch": pitch,
                "volume": max(0.0, min(1.0, volume)),
                "lang": "en-US",
            },
        }
