"""
plasticos_inference — Standalone polymer inference engine.

Usage
-----
    from plasticos_inference import InferenceEngine
    from plasticos_inference.models import InferenceRequest

    engine = InferenceEngine(kb_dir="./kb")
    response = engine.infer(InferenceRequest(
        entity_type="supplier",
        polymer="LDPE",
        form="FILM",
        source_type="PI",
    ))
    print(response.to_dict())
"""

from .engine import InferenceEngine
from .models import (
    EntityType,
    InferenceRequest,
    InferenceResponse,
    InferenceResult,
    QualityTier,
)

__all__ = [
    "InferenceEngine",
    "InferenceRequest",
    "InferenceResponse",
    "InferenceResult",
    "QualityTier",
    "EntityType",
]
__version__ = "1.0.0"
