"""
Buyer Matching Engine v2.0
Orchestrates matching suppliers to buyers via facility.profile and graph service.

Major changes from v1.x:
- Direct facility.profile queries (buyer.capability model removed)
- Null-safe gate checks (missing dimension = pass)
- Neutral geo scoring (missing coords = 0.0, not penalty)
- Mode-aware gate checking (strict vs relaxed)
- Stage 1 (Python) filters, Stage 2 (Cypher) scores

SCHEMA ALIGNMENT (2026-02-25):
- intake uses: polymer_id, form_id, color_id, source_type_id
- facility.profile uses: accepted_polymer_ids, form_preference, accepted_color_ids
- Quantity: intake.quantity_per_load_lbs, profile.min_lot_size_lbs
- Geo: intake.lat/lon (not latitude/longitude)
"""

import logging

from odoo import _, api, models
from odoo.addons.plasticos_facility_profile.process_codes import check_mfi_compatibility
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class BuyerMatcher(models.Model):
    _name = "plasticos.buyer.matcher"
    _inherit = "plasticos.feature.gate.mixin"
    _description = "Buyer Matching Orchestrator"

    @api.model
    def _matching_stub_enabled(self):
        """Return True when buyer matching must run as deterministic empty-result stub."""
        return (
            not self._is_feature_enabled("plasticos.matching_engine.enabled")
            or self._is_feature_stubbed("plasticos.matching_engine.stubbed")
        )

    @api.model
    def find_matches_for_supplier(self, supplier_partner_id, intake_id=None, max_results=20, mode="strict"):
        """
        Find buyer matches for a supplier based on material requirements.

        Args:
            supplier_partner_id: res.partner ID of supplier
            intake_id: Optional plasticos.intake ID for context
            max_results: Maximum number of buyers to return (default 20)
            mode: 'strict' (all gates hard) or 'relaxed' (only polymer hard)

        Returns:
            list[dict]: Match results with buyer info and scores, sorted by score descending
            [
                {
                    'buyer_id': 123,
                    'buyer_name': 'Acme Recycling',
                    'total_score': 0.85,
                    'gates_passed': 8,
                    'gates_failed': ['gate_3', 'gate_7'],
                    'match_details': {...},  # From graph service
                    'facility_profile_id': 456
                },
                ...
            ]
        """
        if self._matching_stub_enabled():
            _logger.warning(
                "Buyer matcher stub enabled; returning no candidates for supplier %s (intake=%s).",
                supplier_partner_id,
                intake_id,
            )
            return []

        # Validate supplier exists and has intake data
        supplier = self.env["res.partner"].browse(supplier_partner_id)
        if not supplier.exists():
            raise ValidationError(_("Supplier partner %s not found") % supplier_partner_id)

        intake = None
        if intake_id:
            intake = self.env["plasticos.intake"].browse(intake_id)
            if not intake.exists() or intake.partner_id.id != supplier_partner_id:
                raise ValidationError(_("Intake %s not found or doesn't match supplier") % intake_id)

        _logger.info(
            "Starting buyer match for supplier %s (intake: %s, max_results: %d, mode: %s)",
            supplier.name,
            intake.name if intake else "N/A",
            max_results,
            mode,
        )

        # Step 1: Get supplier material requirements (from intake or profile)
        material_req = self._extract_material_requirements(supplier, intake)
        if not material_req:
            _logger.warning("No material requirements found for supplier %s", supplier.name)
            return []

        # Step 2: Query all buyer facility profiles (with exclusion filtering)
        buyer_profiles = self._get_buyer_profiles(supplier_partner_id=supplier_partner_id)
        _logger.info("Found %d buyer profiles to evaluate", len(buyer_profiles))

        # Step 3: Apply gate filtering based on mode
        passed_buyers = []
        for profile in buyer_profiles:
            if mode == "relaxed":
                gate_results = self._check_gates_relaxed(profile, material_req)
            else:
                gate_results = self._check_gates_strict(profile, material_req)

            if gate_results["passed"]:
                passed_buyers.append(
                    {
                        "profile": profile,
                        "gates_passed": gate_results["gates_passed"],
                        "gates_failed": gate_results["gates_failed"],
                    }
                )

        _logger.info("%d/%d buyers passed Stage 1 gates (mode=%s)", len(passed_buyers), len(buyer_profiles), mode)

        if not passed_buyers:
            return []

        # Collect facility_ids for Stage 2
        # Neo4j stores facility_id = partner.id, so pass partner IDs not profile IDs
        facility_ids = [b["profile"].partner_id.id for b in passed_buyers]

        # Step 4: Call graph service for Stage 2 scoring
        graph_svc = self.env["plasticos.graph.service"]

        # Use new match_buyers method if available, else fall back to per-buyer scoring
        if hasattr(graph_svc, "match_buyers") and intake:
            try:
                scored_results = graph_svc.match_buyers(intake, facility_ids, mode=mode)
                # Map results back to our format
                scored_buyers = []
                for row in scored_results:
                    buyer_data = next(
                        (b for b in passed_buyers if b["profile"].partner_id.id == row.get("facility_id")),
                        None,
                    )
                    if buyer_data:
                        scored_buyers.append(
                            {
                                "buyer_id": buyer_data["profile"].partner_id.id,
                                "buyer_name": buyer_data["profile"].partner_id.name,
                                "total_score": row.get("total_score", 0.0),
                                "gates_passed": buyer_data["gates_passed"],
                                "gates_failed": buyer_data["gates_failed"],
                                "match_details": row,
                                "facility_profile_id": buyer_data["profile"].id,
                            }
                        )
            except (UserError, ValidationError):
                raise
            except Exception as e:
                _logger.error("Error in graph service match_buyers: %s", str(e))
                scored_buyers = self._fallback_scoring(passed_buyers, supplier_partner_id, material_req, graph_svc)
        else:
            scored_buyers = self._fallback_scoring(passed_buyers, supplier_partner_id, material_req, graph_svc)

        # Step 5: Sort by score and limit results
        scored_buyers.sort(key=lambda x: x["total_score"], reverse=True)
        final_matches = scored_buyers[:max_results]

        _logger.info(
            "Returning %d matches (top score: %.2f, mode: %s)",
            len(final_matches),
            final_matches[0]["total_score"] if final_matches else 0.0,
            mode,
        )

        return final_matches

    def _fallback_scoring(self, passed_buyers, supplier_partner_id, material_req, graph_svc):
        """Fallback to per-buyer scoring when match_buyers not available."""
        scored_buyers = []
        for buyer_data in passed_buyers:
            try:
                score_result = graph_svc.calculate_match_score(
                    supplier_partner_id=supplier_partner_id,
                    buyer_partner_id=buyer_data["profile"].partner_id.id,
                    material_requirements=material_req,
                )

                scored_buyers.append(
                    {
                        "buyer_id": buyer_data["profile"].partner_id.id,
                        "buyer_name": buyer_data["profile"].partner_id.name,
                        "total_score": score_result.get("total_score", 0.0),
                        "gates_passed": buyer_data["gates_passed"],
                        "gates_failed": buyer_data["gates_failed"],
                        "match_details": score_result,
                        "facility_profile_id": buyer_data["profile"].id,
                    }
                )
            except Exception as e:
                _logger.error("Error scoring buyer %s: %s", buyer_data["profile"].partner_id.name, str(e))
        return scored_buyers

    def _extract_material_requirements(self, supplier, intake=None):
        """
        Extract material requirements from supplier intake or profile.

        SCHEMA ALIGNMENT (2026-02-25):
        - intake.polymer_id (canonical Many2one)
        - intake.form_id (not form_factor_ids)
        - intake.color_id (not color_family_ids)
        - intake.quantity_per_load_lbs (not quantity_available)
        - intake.lat/lon (not latitude/longitude)

        Returns:
            dict: Material requirements for gate checking
        """
        if intake:
            # Primary source: intake record (ACTUAL SCHEMA)
            return {
                # Core material identifiers
                "polymer_id": intake.polymer_id.id if intake.polymer_id else None,
                "polymer_code": intake.polymer_id.code if intake.polymer_id else None,
                "form_id": intake.form_id.id if intake.form_id else None,
                "form_code": intake.form_id.code if intake.form_id else None,
                "color_id": intake.color_id.id if intake.color_id else None,
                "color_code": intake.color_id.code if intake.color_id else None,
                "source_type_id": intake.source_type_id.id if intake.source_type_id else None,
                "source_type_code": intake.source_type_id.code if intake.source_type_id else None,
                # Quantity
                "quantity_available": intake.quantity_per_load_lbs or None,
                # Quality metrics
                "mfi": intake.mfi_value or None,
                "density": intake.density_value or None,
                "moisture_pct": intake.moisture_pct or 0.0,
                "contamination_pct": intake.contamination_pct or 0.0,
                # Filler
                "filler_pct": intake.filler_pct or 0,
                "filler_type_id": intake.filler_type_id.id if intake.filler_type_id else None,
                # Origin/application
                "origin_sector": intake.origin_sector or None,
                "food_grade_required": intake.origin_sector == "food",
                "medical_grade_required": intake.origin_sector == "medical",
                # Geo (intake uses lat/lon, not latitude/longitude)
                "latitude": intake.lat or None,
                "longitude": intake.lon or None,
                # Attributes
                "has_metal": intake.has_metal or False,
                "is_metalized": intake.is_metalized or False,
                "has_fr": intake.has_fr or False,
            }

        # Fallback: supplier facility profile
        profile = self.env["plasticos.facility.profile"].search([("partner_id", "=", supplier.id)], limit=1)

        if not profile:
            return None

        # Extract first accepted polymer if available
        first_polymer = profile.accepted_polymer_ids[:1] if profile.accepted_polymer_ids else None

        return {
            # Core material identifiers (from facility profile)
            "polymer_id": first_polymer.id if first_polymer else None,
            "polymer_code": first_polymer.code if first_polymer else None,
            "form_id": profile.form_preference_id.id if profile.form_preference_id else None,
            "form_code": profile.form_preference_id.code if profile.form_preference_id else None,
            "color_id": None,  # Profile uses accepted_color_ids, not single color
            "color_code": None,
            "source_type_id": profile.source_type_id.id if profile.source_type_id else None,
            "source_type_code": profile.source_type_id.code if profile.source_type_id else None,
            # Quantity
            "quantity_available": profile.capacity_lbs_month or None,
            # Quality metrics (not tracked in facility profile)
            "mfi": None,
            "density": None,
            "moisture_pct": 0.0,
            "contamination_pct": 0.0,
            # Filler (not tracked in facility profile as supplier)
            "filler_pct": 0,
            "filler_type_id": None,
            # Origin/application
            "origin_sector": None,
            "food_grade_required": False,
            "medical_grade_required": False,
            # Geo (from partner, not profile)
            "latitude": getattr(supplier, "partner_latitude", None),
            "longitude": getattr(supplier, "partner_longitude", None),
            # Attributes
            "has_metal": False,
            "is_metalized": False,
            "has_fr": False,
        }

    def _get_buyer_profiles(self, supplier_partner_id=None):
        """
        Get all facility profiles for buyers (partner.customer_rank > 0).

        Args:
            supplier_partner_id: Optional supplier ID to filter out excluded buyers

        Returns:
            recordset: plasticos.facility.profile records
        """
        domain = [("partner_id.customer_rank", ">", 0), ("active", "=", True)]

        # Enhancement #11: Exclusion List
        # Filter out buyers excluded for this supplier
        if supplier_partner_id:
            ExclusionModel = self.env["plasticos.match.exclusion"]
            excluded_buyer_ids = ExclusionModel.get_excluded_buyer_ids(supplier_partner_id)
            if excluded_buyer_ids:
                domain.append(("partner_id", "not in", excluded_buyer_ids))

        return self.env["plasticos.facility.profile"].search(domain)

    def _check_gates_strict(self, buyer_profile, material_req):
        """
        Check all gates for a buyer profile in STRICT mode.
        All gates are hard exclusions. Null-safe: missing dimension = pass.

        SCHEMA ALIGNMENT (2026-02-25):
        - buyer_profile.accepted_polymer_ids (Many2many to plasticos.polymer)
        - buyer_profile.form_preference_id (Many2one to material.form; empty = any)
        - buyer_profile.accepted_color_ids (Many2many, not color_family_ids)
        - buyer_profile.min_lot_size_lbs (not min_order_quantity)

        Returns:
            dict: {
                'passed': bool,  # True if all gates passed
                'gates_passed': int,  # Count of passed gates
                'gates_failed': [str, ...]  # List of failed gate names
            }
        """
        gates_failed = []

        # Gate 1: Polymer (HARD in both modes)
        # Buyer's accepted_polymer_ids must include material's polymer
        material_polymer_id = material_req.get("polymer_id")
        if material_polymer_id and buyer_profile.accepted_polymer_ids:
            if material_polymer_id not in buyer_profile.accepted_polymer_ids.ids:
                gates_failed.append("polymer")

        # Gate 2: Form Factor
        # Compare material form_code against buyer's form_preference_id.code
        # Empty form_preference_id means "any form accepted" (no gate).
        material_form_code = material_req.get("form_code")
        buyer_form_code = buyer_profile.form_preference_id.code if buyer_profile.form_preference_id else None
        if material_form_code and buyer_form_code:
            if material_form_code != buyer_form_code:
                gates_failed.append("form_factor")

        # Gate 3: Color
        # NOTE: facility.profile does NOT have accepted_color_ids or
        # accepts_any_color.  Color matching is deferred to Neo4j Stage 2.
        # Natural is universally accepted; for other colors we pass here
        # (null-safe: missing dimension = pass) and let graph scoring
        # apply the color_match weight.
        # This gate is intentionally a no-op until facility.profile
        # gains color fields.
        # material_color_id = material_req.get("color_id")
        # material_color_code = material_req.get("color_code")

        # Gate 4: Quantity Range
        # Material quantity must meet buyer's minimum lot size
        quantity_available = material_req.get("quantity_available")
        if quantity_available and buyer_profile.min_lot_size_lbs:
            if quantity_available < buyer_profile.min_lot_size_lbs:
                gates_failed.append("quantity_range")

        # Gate 5: Source Type (PCR/PIR/Virgin)
        # facility.profile uses feedstock_type Selection (not source_type_id)
        # Mapping: post_consumer~pcr, post_industrial~pir, virgin~virgin, mixed=any
        material_source = material_req.get("source_type_code")
        if material_source and buyer_profile.feedstock_type:
            _fs = buyer_profile.feedstock_type
            # mixed/unknown = accept anything
            if _fs not in ("mixed", "unknown"):
                fs_map = {"post_consumer": "pcr", "post_industrial": "pir", "virgin": "virgin"}
                buyer_source = fs_map.get(_fs, _fs)
                if buyer_source == "pcr" and material_source not in ("pcr",):
                    gates_failed.append("source_type")
                elif buyer_source == "pir" and material_source not in ("pcr", "pir"):
                    gates_failed.append("source_type")

        # Gate 6: Contamination Threshold
        contamination_pct = material_req.get("contamination_pct") or 0.0
        if contamination_pct > 0 and buyer_profile.contamination_tolerance_pct:
            if contamination_pct > buyer_profile.contamination_tolerance_pct:
                gates_failed.append("contamination")

        # Gate 7: Moisture (dryer capability)
        moisture_pct = material_req.get("moisture_pct") or 0.0
        if moisture_pct > 0.5:
            has_drying = buyer_profile.has_wash_line or buyer_profile.can_reduce_moisture
            if not has_drying:
                gates_failed.append("moisture_capability")

        # Gate 8: Filler Matching
        # NOTE: facility.profile only has accepts_filled_materials (Boolean).
        # max_filler_pct and accepted_filler_type_ids do NOT exist yet.
        material_filler_pct = material_req.get("filler_pct") or 0
        if material_filler_pct > 0:
            if not buyer_profile.accepts_filled_materials:
                gates_failed.append("filled_material_rejected")

        # Gate 9: Process Type (MFI compatibility)
        material_mfi = material_req.get("mfi")
        if material_mfi is not None and buyer_profile.process_type:
            if not check_mfi_compatibility(
                buyer_profile.process_type,
                material_mfi,
            ):
                gates_failed.append("process_type")

        # Gate 10: Food Grade
        if material_req.get("food_grade_required"):
            if not buyer_profile.food_grade_certified:
                gates_failed.append("food_grade")

        # Gate 11: Medical Grade
        if material_req.get("medical_grade_required"):
            if not buyer_profile.medical_grade_capable:
                gates_failed.append("medical_grade")

        # Gate 12: Geo (Python fallback)
        # sudo: ir.config_parameter requires elevated access
        ICP = self.env["ir.config_parameter"].sudo()
        max_distance = float(ICP.get_param("plasticos_graph.match_geo_radius_miles", "0"))
        if max_distance > 0:
            mat_lat = material_req.get("latitude")
            mat_lon = material_req.get("longitude")
            buyer_lat = getattr(buyer_profile.partner_id, "partner_latitude", None)
            buyer_lon = getattr(buyer_profile.partner_id, "partner_longitude", None)
            if mat_lat and mat_lon and buyer_lat and buyer_lon:
                distance = self._haversine_miles(mat_lat, mat_lon, buyer_lat, buyer_lon)
                if distance > max_distance:
                    gates_failed.append("geo_distance")

        total_gates = 12
        return {
            "passed": len(gates_failed) == 0,
            "gates_passed": total_gates - len(gates_failed),
            "gates_failed": gates_failed,
        }

    def _check_gates_relaxed(self, buyer_profile, material_req):
        """
        Check gates for a buyer profile in RELAXED mode.
        Only polymer is a hard gate. All other gates become soft signals in Stage 2.

        Returns:
            dict: {
                'passed': bool,  # True if polymer gate passed
                'gates_passed': int,  # Always 1 if passed (polymer only)
                'gates_failed': [str, ...]  # Only polymer if failed
            }
        """
        gates_failed = []

        # ONLY HARD GATE: Polymer
        material_polymer_id = material_req.get("polymer_id")
        if material_polymer_id and buyer_profile.accepted_polymer_ids:
            if material_polymer_id not in buyer_profile.accepted_polymer_ids.ids:
                gates_failed.append("polymer")

        # All other gates are deferred to Stage 2 as soft scoring signals

        return {
            "passed": len(gates_failed) == 0,
            "gates_passed": 1 if len(gates_failed) == 0 else 0,
            "gates_failed": gates_failed,
        }

    def _check_all_gates(self, buyer_profile, material_req):
        """Backward compatibility wrapper - defaults to strict mode."""
        return self._check_gates_strict(buyer_profile, material_req)

    # ═════════════════════════════════════════════════════════════════
    # Helper Methods (previously missing — caused AttributeError)
    # ═════════════════════════════════════════════════════════════════

    @staticmethod
    def _haversine_miles(lat1, lon1, lat2, lon2):
        """Calculate the great-circle distance between two points (in miles).

        Uses the Haversine formula.  Inputs are in decimal degrees.
        """
        import math

        R = 3958.8  # Earth radius in miles
        d_lat = math.radians(lat2 - lat1)
        d_lon = math.radians(lon2 - lon1)
        a = (
            math.sin(d_lat / 2) ** 2
            + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(d_lon / 2) ** 2
        )
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c

    # _check_mfi_process_compatibility removed: use check_mfi_compatibility
    # from plasticos_facility_profile.process_codes (canonical registry).
