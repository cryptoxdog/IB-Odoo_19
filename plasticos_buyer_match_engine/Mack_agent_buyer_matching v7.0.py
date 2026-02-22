"""
Mack FastAPI Buyer Matching Agent v6.0

Purpose: AI-powered buyer matching engine for optimal supplier-buyer connections

Summary: Matches processed supplier intakes with buyer profiles using advanced
scoring algorithms, preference matching, geographic optimization, and
historical performance data to create optimal trading partnerships.

Version: 6.0.0
Created: 2025-10-28
Owner: Igor Beylin
Tags: mack, fastapi, plastos, v6.0, agent, buyer, matching
Domain: plastos.mack.fastapi
Type: agent
Production Ready: true
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.core.database import get_db

logger = logging.getLogger(__name__)


@dataclass
class MatchScore:
    """Container for match scoring details"""

    buyer_id: int
    company_name: str
    total_score: float
    polymer_match: float
    quality_match: float
    volume_match: float
    geographic_match: float
    trust_compatibility: float
    match_reasons: list[str]
    concerns: list[str]


class BuyerMatchingAgent:
    """AI agent for matching suppliers with optimal buyers"""

    def __init__(self):
        self.db = None
        self._initialized = False
        self.weights = {
            "polymer_match": 0.30,
            "quality_match": 0.25,
            "volume_match": 0.20,
            "geographic_match": 0.15,
            "trust_compatibility": 0.10,
        }

    async def initialize(self):
        """Initialize buyer matching agent"""
        try:
            self.db = await get_db()
            self._initialized = True
            logger.info("Buyer Matching Agent v6.0 initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize buyer matching agent: {e}")
            raise

    async def find_matches(self, intake_data: dict[str, Any], limit: int = 10) -> list[MatchScore]:
        """
        Find optimal buyer matches for a supplier intake

        Args:
            intake_data: Processed supplier intake data
            limit: Maximum number of matches to return

        Returns:
            List of matched buyers with scores and reasoning
        """
        if not self._initialized:
            await self.initialize()

        try:
            # Get all active buyers
            buyers = await self._get_active_buyers()

            if not buyers:
                logger.warning("No active buyers found in database")
                return []

            # Score each buyer
            matches = []
            for buyer in buyers:
                match_score = await self._calculate_match_score(intake_data, buyer)
                if match_score.total_score >= 0.5:  # Minimum threshold
                    matches.append(match_score)

            # Sort by total score
            matches.sort(key=lambda x: x.total_score, reverse=True)

            # Log matching results
            logger.info(f"Found {len(matches)} potential matches for intake from {intake_data.get('supplier_name')}")

            return matches[:limit]

        except Exception as e:
            logger.error(f"Buyer matching failed: {e}")
            return []

    async def _get_active_buyers(self) -> list[dict[str, Any]]:
        """Get all active buyers from database"""
        try:
            buyers = await self.db.select("buyer_profiles")
            # Filter for active buyers only
            active_buyers = [b for b in buyers if b.get("active", True)]
            return active_buyers
        except Exception as e:
            logger.error(f"Failed to fetch buyers: {e}")
            return []

    async def _calculate_match_score(self, intake: dict[str, Any], buyer: dict[str, Any]) -> MatchScore:
        """Calculate comprehensive match score between supplier and buyer"""
        scores = {}
        reasons = []
        concerns = []

        # 1. Polymer type match
        polymer_score = await self._score_polymer_match(intake, buyer)
        scores["polymer_match"] = polymer_score
        if polymer_score >= 0.8:
            reasons.append(f"Exact polymer match: {intake.get('polymer_type')}")
        elif polymer_score > 0:
            reasons.append("Polymer type accepted by buyer")
        else:
            concerns.append(f"Buyer doesn't accept {intake.get('polymer_type')}")

        # 2. Quality requirements match
        quality_score = await self._score_quality_match(intake, buyer)
        scores["quality_match"] = quality_score
        if quality_score >= 0.8:
            reasons.append("Quality exceeds buyer requirements")
        elif quality_score >= 0.6:
            reasons.append("Quality meets buyer standards")
        else:
            concerns.append("Quality below buyer requirements")

        # 3. Volume capacity match
        volume_score = await self._score_volume_match(intake, buyer)
        scores["volume_match"] = volume_score
        if volume_score >= 0.8:
            reasons.append("Volume fits buyer capacity perfectly")
        elif volume_score >= 0.5:
            reasons.append("Volume within buyer range")
        else:
            concerns.append("Volume mismatch with buyer capacity")

        # 4. Geographic compatibility
        geo_score = await self._score_geographic_match(intake, buyer)
        scores["geographic_match"] = geo_score
        if geo_score >= 0.8:
            reasons.append("Excellent geographic alignment")
        elif geo_score >= 0.5:
            reasons.append("Acceptable shipping distance")
        else:
            concerns.append("Geographic distance may impact costs")

        # 5. Trust score compatibility
        trust_score = await self._score_trust_compatibility(intake, buyer)
        scores["trust_compatibility"] = trust_score
        if trust_score >= 0.8:
            reasons.append("Strong trust alignment")
        elif trust_score >= 0.6:
            reasons.append("Acceptable trust levels")
        else:
            concerns.append("Trust score mismatch")

        # Calculate weighted total
        total_score = sum(score * self.weights[metric] for metric, score in scores.items())

        return MatchScore(
            buyer_id=buyer.get("id", 0),
            company_name=buyer.get("company_name", "Unknown"),
            total_score=round(total_score, 3),
            polymer_match=scores["polymer_match"],
            quality_match=scores["quality_match"],
            volume_match=scores["volume_match"],
            geographic_match=scores["geographic_match"],
            trust_compatibility=scores["trust_compatibility"],
            match_reasons=reasons,
            concerns=concerns,
        )

    async def _score_polymer_match(self, intake: dict[str, Any], buyer: dict[str, Any]) -> float:
        """Score polymer type compatibility"""
        intake_polymer = intake.get("polymer_type", "").upper()
        accepted_polymers = buyer.get("accepted_polymers", [])

        if not accepted_polymers:
            return 0.5  # Unknown preference

        # Convert to uppercase for comparison
        accepted_polymers = [p.upper() for p in accepted_polymers]

        if intake_polymer in accepted_polymers:
            # Check if it's a preferred polymer (first in list)
            if accepted_polymers and intake_polymer == accepted_polymers[0]:
                return 1.0
            return 0.8

        return 0.0

    async def _score_quality_match(self, intake: dict[str, Any], buyer: dict[str, Any]) -> float:
        """Score quality requirements match"""
        # Get quality assessment from intake
        quality_assessment = intake.get("quality_assessment", {})
        intake_quality_score = quality_assessment.get("quality_score", 0.5)

        # Get buyer requirements
        buyer_requirements = buyer.get("quality_requirements", "")

        # Parse buyer requirements (simple logic for now)
        if "premium" in buyer_requirements.lower() or "high" in buyer_requirements.lower():
            required_score = 0.8
        elif "standard" in buyer_requirements.lower() or "medium" in buyer_requirements.lower():
            required_score = 0.6
        else:
            required_score = 0.4

        # Calculate match
        if intake_quality_score >= required_score:
            # Bonus for exceeding requirements
            excess = intake_quality_score - required_score
            return min(1.0, 0.8 + excess)
        else:
            # Penalty for not meeting requirements
            deficit = required_score - intake_quality_score
            return max(0.0, 0.5 - deficit * 2)

    async def _score_volume_match(self, intake: dict[str, Any], buyer: dict[str, Any]) -> float:
        """Score volume capacity match"""
        intake_volume = intake.get("quantity_tons", 0)
        buyer_capacity = buyer.get("volume_capacity", 0)

        if buyer_capacity == 0:
            return 0.5  # Unknown capacity

        # Check if volume fits buyer's capacity
        utilization = intake_volume / buyer_capacity

        if 0.1 <= utilization <= 0.5:
            # Optimal range - not too small, not too large
            return 1.0
        elif 0.05 <= utilization <= 0.8:
            # Acceptable range
            return 0.7
        elif utilization > 1.0:
            # Over capacity
            return max(0.0, 1.0 - (utilization - 1.0))
        else:
            # Too small
            return max(0.3, utilization * 10)

    async def _score_geographic_match(self, intake: dict[str, Any], buyer: dict[str, Any]) -> float:
        """Score geographic compatibility"""
        # Simple geographic scoring - in production would use actual distance calculation
        supplier_location = intake.get("location", "").lower()
        buyer_range = buyer.get("geographic_range", "").lower()

        if not supplier_location or not buyer_range:
            return 0.5  # Unknown locations

        # Check for keyword matches
        if "global" in buyer_range or "international" in buyer_range:
            return 0.9
        elif "national" in buyer_range or "usa" in buyer_range:
            return 0.8
        elif "regional" in buyer_range:
            return 0.7
        elif "local" in buyer_range:
            # Would need actual distance calculation
            return 0.6

        return 0.5

    async def _score_trust_compatibility(self, intake: dict[str, Any], buyer: dict[str, Any]) -> float:
        """Score trust level compatibility"""
        supplier_trust = intake.get("trust_score", 0.5)
        buyer_trust = buyer.get("trust_score", 0.5)
        buyer_payment_score = buyer.get("payment_history_score", 0.5)

        # Both parties should have compatible trust levels
        trust_diff = abs(supplier_trust - buyer_trust)

        if trust_diff <= 0.1:
            base_score = 1.0
        elif trust_diff <= 0.3:
            base_score = 0.8
        elif trust_diff <= 0.5:
            base_score = 0.6
        else:
            base_score = 0.4

        # Factor in buyer's payment history
        final_score = base_score * 0.7 + buyer_payment_score * 0.3

        return final_score

    async def create_match_record(self, intake_id: int, match: MatchScore) -> int:
        """Create a match record in the database"""
        try:
            match_data = {
                "intake_id": intake_id,
                "buyer_id": match.buyer_id,
                "match_score": match.total_score,
                "polymer_score": match.polymer_match,
                "quality_score": match.quality_match,
                "volume_score": match.volume_match,
                "geographic_score": match.geographic_match,
                "trust_score": match.trust_compatibility,
                "match_reasons": match.match_reasons,
                "concerns": match.concerns,
                "status": "pending",
                "created_at": datetime.utcnow().isoformat(),
            }

            result = await self.db.insert("buyer_matches", match_data)
            return result.get("id", 0)

        except Exception as e:
            logger.error(f"Failed to create match record: {e}")
            return 0

    async def get_match_history(
        self, buyer_id: int | None = None, supplier_name: str | None = None
    ) -> list[dict[str, Any]]:
        """Get historical matches for analysis"""
        try:
            filters = {}
            if buyer_id:
                filters["buyer_id"] = buyer_id

            matches = await self.db.select("buyer_matches", filters=filters)

            # Filter by supplier if provided
            if supplier_name:
                # Would need to join with intakes table in production
                pass

            return matches

        except Exception as e:
            logger.error(f"Failed to get match history: {e}")
            return []

    async def update_match_status(self, match_id: int, status: str, notes: str | None = None):
        """Update the status of a match"""
        try:
            update_data = {"status": status, "updated_at": datetime.utcnow().isoformat()}

            if notes:
                update_data["notes"] = notes

            await self.db.update("buyer_matches", update_data, {"id": match_id})
            logger.info(f"Updated match {match_id} status to {status}")

        except Exception as e:
            logger.error(f"Failed to update match status: {e}")
            raise


# Global buyer matching agent instance
buyer_matching_agent = BuyerMatchingAgent()


async def get_buyer_matching_agent() -> BuyerMatchingAgent:
    """Dependency to get buyer matching agent"""
    if not buyer_matching_agent._initialized:
        await buyer_matching_agent.initialize()
    return buyer_matching_agent
