"""
Buyer Matching Engine v2.0
Orchestrates matching suppliers to buyers via facility.profile and graph service.

Major changes from v1.x:
- Direct facility.profile queries (buyer.capability model removed)
- Null-safe gate checks (missing dimension = pass)
- Neutral geo scoring (missing coords = 0.0, not penalty)
- Mode-aware gate checking (strict vs relaxed)
- Stage 1 (Python) filters, Stage 2 (Cypher) scores
"""

import logging

from odoo import _, api, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class BuyerMatcher(models.Model):
    _name = "plasticos.buyer.matcher"
    _description = "Buyer Matching Orchestrator"

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
        facility_ids = [b["profile"].id for b in passed_buyers]

        # Step 4: Call graph service for Stage 2 scoring
        graph_svc = self.env["plasticos.graph.service"]

        # Use new match_buyers method if available, else fall back to per-buyer scoring
        if hasattr(graph_svc, "match_buyers") and intake:
            try:
                scored_results = graph_svc.match_buyers(intake, facility_ids, mode=mode)
                # Map results back to our format
                scored_buyers = []
                for row in scored_results:
                    buyer_data = next((b for b in passed_buyers if b["profile"].id == row.get("facility_id")), None)
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

        Returns:
            dict: {
                'material_category_id': int or None,
                'polymer_family_id': int or None,
                'form_factor_ids': [int, ...],
                'color_family_ids': [int, ...],
                'quantity_available': float or None,
                'quality_level_id': int or None,
                'additive_ids': [int, ...],
                'contamination_level': float or None,
                'certification_ids': [int, ...],
                'latitude': float or None,
                'longitude': float or None
            }
        """
        if intake:
            # Primary source: intake record
            return {
                "material_category_id": intake.material_category_id.id if intake.material_category_id else None,
                "polymer_family_id": intake.polymer_family_id.id if intake.polymer_family_id else None,
                "form_factor_ids": intake.form_factor_ids.ids if intake.form_factor_ids else [],
                "color_family_ids": intake.color_family_ids.ids if intake.color_family_ids else [],
                "quantity_available": intake.quantity_available or None,
                "quality_level_id": intake.quality_level_id.id if intake.quality_level_id else None,
                "additive_ids": intake.additive_ids.ids if intake.additive_ids else [],
                "contamination_level": intake.contamination_level if intake.contamination_level else None,
                "certification_ids": intake.certification_ids.ids if intake.certification_ids else [],
                "latitude": intake.latitude if intake.latitude else None,
                "longitude": intake.longitude if intake.longitude else None,
                # Enhancement #6: Color Matching
                "color_id": intake.color_id.id if intake.color_id else None,
                "color_code": intake.color_id.code if intake.color_id else None,
                # Enhancement #7: Filler Matching
                "filler_pct": intake.filler_pct if intake.filler_pct else 0,
                "filler_type_id": intake.filler_type_id.id if intake.filler_type_id else None,
            }

        # Fallback: supplier facility profile
        profile = self.env["plasticos.facility.profile"].search([("partner_id", "=", supplier.id)], limit=1)

        if not profile:
            return None

        return {
            "material_category_id": profile.material_category_id.id if profile.material_category_id else None,
            "polymer_family_id": profile.polymer_family_id.id if profile.polymer_family_id else None,
            "form_factor_ids": profile.form_factor_ids.ids if profile.form_factor_ids else [],
            "color_family_ids": profile.color_family_ids.ids if profile.color_family_ids else [],
            "quantity_available": profile.monthly_capacity or None,
            "quality_level_id": profile.quality_level_id.id if profile.quality_level_id else None,
            "additive_ids": [],  # Not tracked in profile
            "contamination_level": None,  # Not tracked in profile
            "certification_ids": profile.certification_ids.ids if profile.certification_ids else [],
            "latitude": profile.latitude if profile.latitude else None,
            "longitude": profile.longitude if profile.longitude else None,
            # Enhancement #6: Color Matching (not tracked in facility profile)
            "color_id": None,
            "color_code": None,
            # Enhancement #7: Filler Matching (not tracked in facility profile)
            "filler_pct": 0,
            "filler_type_id": None,
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

        Returns:
            dict: {
                'passed': bool,  # True if all gates passed
                'gates_passed': int,  # Count of passed gates
                'gates_failed': [str, ...]  # List of failed gate names
            }
        """
        gates_failed = []

        # Gate 1: Material Category
        if material_req.get("material_category_id") and buyer_profile.material_category_id:
            if material_req["material_category_id"] != buyer_profile.material_category_id.id:
                gates_failed.append("material_category")

        # Gate 2: Polymer Family (HARD in both modes)
        if material_req.get("polymer_family_id") and buyer_profile.polymer_family_id:
            if material_req["polymer_family_id"] != buyer_profile.polymer_family_id.id:
                gates_failed.append("polymer")

        # Gate 3: Form Factor (any match)
        if material_req.get("form_factor_ids") and buyer_profile.form_factor_ids:
            if not any(ff_id in buyer_profile.form_factor_ids.ids for ff_id in material_req["form_factor_ids"]):
                gates_failed.append("form_factor")

        # Gate 4: Color Family (any match)
        if material_req.get("color_family_ids") and buyer_profile.color_family_ids:
            if not any(cf_id in buyer_profile.color_family_ids.ids for cf_id in material_req["color_family_ids"]):
                gates_failed.append("color_family")

        # Gate 5: Quantity Range
        if material_req.get("quantity_available") and buyer_profile.min_order_quantity:
            if material_req["quantity_available"] < buyer_profile.min_order_quantity:
                gates_failed.append("quantity_range")

        # Gate 6: Quality Level
        if material_req.get("quality_level_id") and buyer_profile.quality_level_id:
            if material_req["quality_level_id"] != buyer_profile.quality_level_id.id:
                gates_failed.append("quality_level")

        # Gate 7: Additive Tolerance
        if material_req.get("additive_ids") and buyer_profile.prohibited_additives:
            prohibited_ids = buyer_profile.prohibited_additives.ids
            if any(add_id in prohibited_ids for add_id in material_req["additive_ids"]):
                gates_failed.append("additive_tolerance")

        # Gate 8: Contamination Threshold
        if material_req.get("contamination_level") is not None and buyer_profile.max_contamination_level is not None:
            if material_req["contamination_level"] > buyer_profile.max_contamination_level:
                gates_failed.append("contamination")

        # Gate 9: Regulatory Compliance
        if material_req.get("certification_ids") and buyer_profile.required_certifications:
            required_ids = buyer_profile.required_certifications.ids
            if not all(cert_id in material_req["certification_ids"] for cert_id in required_ids):
                gates_failed.append("certifications")

        # Gate 10: Geographic Range (handled in graph service Stage 2)

        # Gate 11: Color Matching (Enhancement #6)
        # Natural color accepted by everyone. Mixed requires accepts_any_color.
        # Otherwise, buyer's accepted_color_ids must include material color.
        material_color_id = material_req.get("color_id")
        material_color_code = material_req.get("color_code")
        if material_color_id:
            # Natural is universally accepted
            if material_color_code != "natural":
                # Mixed color requires accepts_any_color
                if material_color_code == "mixed":
                    if not buyer_profile.accepts_any_color:
                        gates_failed.append("color_mixed_rejected")
                # Specific color must be in buyer's accepted list (if they have one)
                elif buyer_profile.accepted_color_ids:
                    if material_color_id not in buyer_profile.accepted_color_ids.ids:
                        if not buyer_profile.accepts_any_color:
                            gates_failed.append("color_not_accepted")

        # Gate 12: Filler Matching (Enhancement #7)
        # Unfilled material (filler_pct == 0) always passes.
        # Filled material requires accepts_filled_materials and filler_pct <= max_filler_pct.
        material_filler_pct = material_req.get("filler_pct", 0) or 0
        material_filler_type_id = material_req.get("filler_type_id")
        if material_filler_pct > 0:
            # Buyer must accept filled materials
            if not buyer_profile.accepts_filled_materials:
                gates_failed.append("filled_material_rejected")
            # Check filler percentage limit
            elif buyer_profile.max_filler_pct and material_filler_pct > buyer_profile.max_filler_pct:
                gates_failed.append("filler_pct_exceeds_limit")
            # Check filler type if buyer has restrictions
            elif material_filler_type_id and buyer_profile.accepted_filler_type_ids:
                if material_filler_type_id not in buyer_profile.accepted_filler_type_ids.ids:
                    gates_failed.append("filler_type_not_accepted")

        return {"passed": len(gates_failed) == 0, "gates_passed": 10 - len(gates_failed), "gates_failed": gates_failed}

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

        # ONLY HARD GATE: Polymer Family
        if material_req.get("polymer_family_id") and buyer_profile.polymer_family_id:
            if material_req["polymer_family_id"] != buyer_profile.polymer_family_id.id:
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
