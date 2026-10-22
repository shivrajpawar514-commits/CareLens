"""
CareLens Inference Adapter Base Class.
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from app.schema.contract import CareLensResponse
from app.protocol_engine.protocols import ClinicalProtocol


class BaseInferenceAdapter(ABC):
    @abstractmethod
    def audit_image(
        self,
        image_b64: str,
        protocol: ClinicalProtocol,
        patient_context: str = "adult",
        inspection_type_hint: Optional[str] = None,
    ) -> CareLensResponse:
        """
        Performs visual audit of an equipment or monitor frame and returns
        the strictly validated CareLensResponse.
        """
        pass
