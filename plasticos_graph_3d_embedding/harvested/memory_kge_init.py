CompoundE3D Knowledge Graph Embedding Module for L9

Implements 3D compound geometric transformations for link prediction:
- Translation (T): SE(3) group
- Scaling (S): Aff(3) group
- Rotation (R): SO(3) group (non-commutative)
- Reflection (F): SO(3) group (Householder reflection)
- Shear (H): Aff(3) group

Exports:
- CompoundE3D: Main KGE model class
- AffineOperator3D: 3D affine transformation operators
- BeamSearch: Variant discovery algorithm
- WeightedDistanceSum, RankFusion: Ensemble methods
"""

from .transformations import AffineOperator3D
from .compound_e3d import CompoundE3D, KGEInferenceRequest, KGEPrediction
from .beam_search import BeamSearch, BeamSearchResult
from .ensemble import WeightedDistanceSum, RankFusion, EnsembleResult

__version__ = "1.0.0"
__all__ = [
    "CompoundE3D",
    "KGEInferenceRequest",
    "KGEPrediction",
    "AffineOperator3D",
    "BeamSearch",
    "BeamSearchResult",
    "WeightedDistanceSum",
    "RankFusion",
    "EnsembleResult",
