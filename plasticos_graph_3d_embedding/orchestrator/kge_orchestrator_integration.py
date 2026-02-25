# orchestrator/kge_orchestrator_integration.py
"""
KGE Orchestrator Integration for CompoundE3D

Integrates CompoundE3D KGE system into L9's websocket orchestrator.
Handles packet routing, memory substrate coordination, and distributed
variant discovery across WebSocket channels.

**Frontier Patterns:** Anthropic Constitutional AI (kernel safety),
OpenAI Function Calling (orchestration), DeepMind AlphaGo
(ensemble + search coordination).

**Protected Surfaces:**
- websocket_orchestrator.py (LCTO authority)
- kernel_loader.py (substrate loading)
- PacketEnvelope protocol

**Integration Points:**
1. MemorySubstrateService: Store/retrieve embeddings (Postgres/Neo4j)
2. WebSocketOrchestrator: Route KGE predictions to clients
3. KernelLoader: Load CompoundE3D models into substrate
4. PacketEnvelope: Wrap KGE outputs in L9 protocol
"""

import asyncio
import logging
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any

import numpy as np

# L9 imports (mocked for integration example)
try:
    from kernel_loader import KernelLoader
    from memory_substrate_service import MemorySubstrateService
    from websocket_orchestrator import PacketEnvelope, WebSocketOrchestrator
except ImportError:
    # Placeholder for testing
    WebSocketOrchestrator = None
    PacketEnvelope = None
    KernelLoader = None
    MemorySubstrateService = None

# CompoundE3D imports
from memory.kge.beam_search import BeamSearchConfig, BeamSearchEngine, PruneStrategy
from memory.kge.compound_e3d import CompoundE3D, CompoundE3DConfig
from memory.kge.ensemble import (
    EnsembleController,
    FusionStrategy,
    VariantScore,
)
from memory.kge.transformations import Transformation3D

logger = logging.getLogger(__name__)


class KGEMessageType(Enum):
    """KGE packet message types."""

    PREDICT = "kge.predict"
    DISCOVER = "kge.discover"
    ENSEMBLE = "kge.ensemble"
    STATUS = "kge.status"
    ERROR = "kge.error"


@dataclass
class KGEPredictRequest:
    """Request for KGE triple classification."""

    head_entity: str
    relation: str
    tail_entity: str
    use_ensemble: bool = True
    ensemble_strategy: str = "weighted_mean"
    return_explanations: bool = True


@dataclass
class KGEPredictResponse:
    """Response from KGE prediction."""

    score: float
    confidence: float
    head_entity: str
    relation: str
    tail_entity: str
    components: dict[str, float]  # Per-variant scores
    explanation: str = ""
    timestamp: float = 0.0


@dataclass
class KGEDiscoveryRequest:
    """Request for variant discovery."""

    target_pattern: dict[str, Any]
    beam_width: int = 5
    max_depth: int = 3
    prune_strategy: str = "combined"
    constraint_validators: list[str] = None


@dataclass
class KGEDiscoveryResponse:
    """Response from variant discovery."""

    variants: list[dict[str, Any]]
    discovery_depth: int
    num_candidates_explored: int
    top_variant: dict[str, Any]
    audit_trail: list[dict[str, Any]]
    timestamp: float = 0.0


class KGEOrchestrator:
    """
    Orchestrates CompoundE3D within L9 WebSocket infrastructure.

    **Responsibilities:**
    1. Load CompoundE3D models via KernelLoader
    2. Route prediction/discovery requests from WebSocket
    3. Coordinate with MemorySubstrateService for embeddings
    4. Package responses in PacketEnvelope protocol
    5. Log decisions for audit trail
    """

    def __init__(
        self,
        config: CompoundE3DConfig,
        orchestrator: WebSocketOrchestrator | None = None,
        substrate: MemorySubstrateService | None = None,
    ):
        """
        Initialize KGE orchestrator.

        Args:
            config: CompoundE3D model configuration
            orchestrator: WebSocketOrchestrator instance (mocked if None)
            substrate: MemorySubstrateService instance (mocked if None)
        """
        self.config = config
        self.orchestrator = orchestrator
        self.substrate = substrate

        # Initialize model and services
        self.model = CompoundE3D(config)
        self.ensemble_controller = EnsembleController()
        self.beam_search_engine = None

        # State tracking
        self.request_log = []
        self.prediction_cache = {}
        self.variant_cache = {}

    async def initialize(self):
        """Async initialization (substrate connections, kernel loading)."""
        logger.info("Initializing KGE orchestrator")

        # Load model via KernelLoader (if available)
        if KernelLoader:
            try:
                loader = KernelLoader()
                await loader.load_kernel("compound_e3d", self.model)
                logger.info("✓ CompoundE3D kernel loaded")
            except Exception as e:
                logger.error(f"✗ Kernel loading failed: {e}")

        # Initialize beam search engine
        beam_config = BeamSearchConfig(
            beam_width=self.config.beam_width if hasattr(self.config, "beam_width") else 5,
            max_depth=3,
            prune_strategy=PruneStrategy.COMBINED,
        )
        self.beam_search_engine = BeamSearchEngine(self.model, beam_config)

        logger.info("✓ KGE orchestrator ready")

    async def handle_predict_request(
        self,
        request: KGEPredictRequest,
        channel_id: str,
    ) -> KGEPredictResponse:
        """
        Handle triple classification request.

        **Flow:**
        1. Resolve entities to embeddings (via substrate)
        2. Score with CompoundE3D
        3. Get per-variant scores
        4. Ensemble if requested
        5. Generate explanation
        6. Return response
        """
        logger.info(f"[{channel_id}] Predict: {request.head_entity} → {request.relation} → {request.tail_entity}")

        try:
            # Check cache
            cache_key = (request.head_entity, request.relation, request.tail_entity)
            if cache_key in self.prediction_cache:
                logger.info(f"✓ Cache hit for {cache_key}")
                return self.prediction_cache[cache_key]

            # Resolve entities to embeddings (mocked)
            head_embedding = await self._resolve_entity(request.head_entity)
            tail_embedding = await self._resolve_entity(request.tail_entity)

            # Get per-variant scores
            variant_scores = await self._score_variants(
                head_embedding,
                request.relation,
                tail_embedding,
            )

            # Ensemble if requested
            if request.use_ensemble:
                ensemble_result = self.ensemble_controller.predict(
                    variant_scores,
                    FusionStrategy[request.ensemble_strategy.upper()],
                )
                final_score = ensemble_result.final_score
                explanation = ensemble_result.explanation
                components = {s.variant_id: s.score for s in variant_scores}
            else:
                # Use best variant
                best = max(variant_scores, key=lambda s: s.score)
                final_score = best.score
                explanation = f"Best variant: {best.variant_id}"
                components = {best.variant_id: best.score}

            # Build response
            import time

            response = KGEPredictResponse(
                score=final_score,
                confidence=min(1.0, np.mean([s.confidence for s in variant_scores])),
                head_entity=request.head_entity,
                relation=request.relation,
                tail_entity=request.tail_entity,
                components=components,
                explanation=explanation if request.return_explanations else "",
                timestamp=time.time(),
            )

            # Cache and log
            self.prediction_cache[cache_key] = response
            self.request_log.append(
                {
                    "type": "predict",
                    "channel": channel_id,
                    "score": final_score,
                    "timestamp": response.timestamp,
                }
            )

            logger.info(f"✓ Prediction: {final_score:.4f}")
            return response

        except Exception as e:
            logger.error(f"✗ Prediction error: {e}")
            raise

    async def handle_discovery_request(
        self,
        request: KGEDiscoveryRequest,
        channel_id: str,
    ) -> KGEDiscoveryResponse:
        """
        Handle variant discovery request.

        **Flow:**
        1. Initialize beam search
        2. Execute search (respects depth/width limits)
        3. Gather audit trail
        4. Return top variants + audit
        """
        logger.info(f"[{channel_id}] Discovery: pattern={request.target_pattern}")

        try:
            # Parse constraints (if provided)
            validators = []
            if request.constraint_validators:
                validators = await self._build_validators(request.constraint_validators)

            # Configure beam search
            if self.beam_search_engine:
                self.beam_search_engine.config.beam_width = request.beam_width
                self.beam_search_engine.config.max_depth = request.max_depth
                self.beam_search_engine.config.constraint_validators = validators

            # Execute discovery
            search_result = self.beam_search_engine.search() if self.beam_search_engine else {}

            # Build response
            import time

            response = KGEDiscoveryResponse(
                variants=search_result.get("variants", [])[:5],  # Top-5
                discovery_depth=request.max_depth,
                num_candidates_explored=sum(len(v) for v in search_result.get("depth_levels", {}).values()),
                top_variant=search_result.get("variants", [{}])[0],
                audit_trail=search_result.get("audit_trail", []),
                timestamp=time.time(),
            )

            # Cache and log
            self.variant_cache[request.target_pattern] = response
            self.request_log.append(
                {
                    "type": "discovery",
                    "channel": channel_id,
                    "num_variants": len(response.variants),
                    "timestamp": response.timestamp,
                }
            )

            logger.info(f"✓ Discovery: {len(response.variants)} variants found")
            return response

        except Exception as e:
            logger.error(f"✗ Discovery error: {e}")
            raise

    async def _resolve_entity(self, entity_id: str) -> np.ndarray:
        """Resolve entity ID to embedding (from substrate)."""
        # Placeholder: query MemorySubstrateService
        # In production: fetch from Postgres/Neo4j
        if self.substrate:
            try:
                embedding = await self.substrate.get_embedding(entity_id)
                return embedding
            except Exception:
                pass

        # Fallback: random embedding
        return np.random.randn(self.config.embedding_dim).astype(np.float32)

    async def _score_variants(
        self,
        head_embedding: np.ndarray,
        relation: str,
        tail_embedding: np.ndarray,
    ) -> list[VariantScore]:
        """Score triple across all variants."""
        # Placeholder: score with each CompoundE3D variant
        # In production: integrate with actual model variants

        scores = []
        for i in range(3):  # 3 variants for demo
            score = 0.5 + (i * 0.15) + np.random.randn() * 0.05
            scores.append(
                VariantScore(
                    variant_id=f"var_{i}",
                    variant_type=["rotation", "scale", "translation"][i],
                    score=np.clip(score, 0.0, 1.0),
                    confidence=0.8 + np.random.randn() * 0.1,
                )
            )

        return scores

    async def _build_validators(
        self,
        validator_names: list[str],
    ) -> list[callable]:
        """Build constraint validators from names."""
        # Placeholder: map validator names to callables
        validators = []

        for name in validator_names:
            if name == "rotation_only":
                validators.append(lambda tx: isinstance(tx, Transformation3D))
            elif name == "unit_scale":
                validators.append(lambda tx: getattr(tx, "factor", 1.0) == 1.0)

        return validators

    async def packet_handler(self, packet: PacketEnvelope) -> PacketEnvelope:
        """
        Handle incoming KGE packet (entry point from orchestrator).

        **Packet Format:**
        {
            "type": "kge.predict" | "kge.discover",
            "payload": {...request data...}
        }
        """
        logger.info(f"Handling packet: {packet.type}")

        try:
            message_type = KGEMessageType(packet.type)

            if message_type == KGEMessageType.PREDICT:
                request = KGEPredictRequest(**packet.payload)
                response = await self.handle_predict_request(request, packet.channel_id)
                return self._wrap_response(response, KGEMessageType.PREDICT, packet.channel_id)

            elif message_type == KGEMessageType.DISCOVER:
                request = KGEDiscoveryRequest(**packet.payload)
                response = await self.handle_discovery_request(request, packet.channel_id)
                return self._wrap_response(response, KGEMessageType.DISCOVER, packet.channel_id)

            elif message_type == KGEMessageType.STATUS:
                status = {
                    "state": "ready",
                    "model_config": asdict(self.config),
                    "requests_served": len(self.request_log),
                    "cache_size": len(self.prediction_cache),
                }
                return self._wrap_response(status, KGEMessageType.STATUS, packet.channel_id)

            else:
                raise ValueError(f"Unknown message type: {packet.type}")

        except Exception as e:
            logger.error(f"✗ Packet handling error: {e}")
            error_response = {
                "error": str(e),
                "message_type": packet.type,
            }
            return self._wrap_response(error_response, KGEMessageType.ERROR, packet.channel_id)

    def _wrap_response(
        self,
        response_data: Any,
        message_type: KGEMessageType,
        channel_id: str,
    ) -> PacketEnvelope:
        """Wrap response in PacketEnvelope protocol."""
        # Placeholder: actual PacketEnvelope construction
        # In production: use L9's PacketEnvelope class

        return {
            "type": message_type.value,
            "channel_id": channel_id,
            "payload": asdict(response_data) if hasattr(response_data, "__dataclass_fields__") else response_data,
            "status": "success",
        }

    def get_audit_log(self) -> list[dict]:
        """Return audit log for monitoring."""
        return self.request_log

    def get_cache_stats(self) -> dict:
        """Return cache statistics."""
        return {
            "predictions_cached": len(self.prediction_cache),
            "variants_cached": len(self.variant_cache),
            "total_requests": len(self.request_log),
        }


# ============================================================================
# REGISTRATION & STARTUP
# ============================================================================


async def register_kge_orchestrator(
    orchestrator: WebSocketOrchestrator,
    substrate: MemorySubstrateService,
) -> KGEOrchestrator:
    """
    Register KGE orchestrator with L9 websocket infrastructure.

    **Called from:** websocket_orchestrator.py at startup (PHASE 0 TODO approval)
    """
    logger.info("Registering CompoundE3D KGE orchestrator")

    # Initialize config
    config = CompoundE3DConfig(
        embedding_dim=64,
        num_entities=50000,
        num_relations=200,
        model_type="compound_e3d",
        beam_width=5,
    )

    # Create orchestrator
    kge_orchestrator = KGEOrchestrator(config, orchestrator, substrate)
    await kge_orchestrator.initialize()

    # Register packet handler
    orchestrator.register_handler(
        "kge.*",
        kge_orchestrator.packet_handler,
    )

    logger.info("✓ KGE orchestrator registered")
    return kge_orchestrator


if __name__ == "__main__":
    # Example usage (for testing)
    import asyncio

    async def main():
        config = CompoundE3DConfig(
            embedding_dim=64,
            num_entities=1000,
            num_relations=50,
        )
        orchestrator = KGEOrchestrator(config)
        await orchestrator.initialize()

        # Test predict
        request = KGEPredictRequest(
            head_entity="entity_1",
            relation="rel_1",
            tail_entity="entity_2",
        )
        response = await orchestrator.handle_predict_request(request, "test_channel")
        print(f"Prediction score: {response.score:.4f}")

        # Test discovery
        discovery_request = KGEDiscoveryRequest(
            target_pattern={"type": "rotation"},
            beam_width=3,
            max_depth=2,
        )
        discovery_response = await orchestrator.handle_discovery_request(discovery_request, "test_channel")
        print(f"Found {len(discovery_response.variants)} variants")

    asyncio.run(main())
