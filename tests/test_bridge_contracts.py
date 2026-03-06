"""Bridge Model Contract Tests for PlastOS.

Contract tests validate that models expose the fields, methods, and behaviors
that OTHER modules depend on. Unlike unit tests (which test a module in isolation),
contract tests ensure cross-module integration won't break.

WHY CONTRACT TESTS MATTER:
- Module A adds field `intake_ids` to res.partner
- Module B's view references `intake_ids` in a smart button
- If Module A removes `intake_ids`, Module B breaks silently
- Contract tests catch this BEFORE deployment

WHAT MAKES A STRONG CONTRACT TEST:
1. Tests SPECIFIC fields/methods, not just "model exists"
2. Tests TYPES (Many2one, One2many, computed, stored)
3. Tests METHOD SIGNATURES (parameters, return types)
4. Tests SELECTION VALUES that other modules depend on
5. Tests COMPUTED FIELD DEPENDENCIES (source fields must exist)

WEAK (useless):
    def test_model_exists(self):
        self.assertTrue(hasattr(self.Model, "_fields"))  # Always passes!

STRONG (catches real bugs):
    def test_intake_has_transaction_ids_one2many(self):
        field = self.env["plasticos.intake"]._fields.get("transaction_ids")
        self.assertIsNotNone(field, "transaction_ids field missing")
        self.assertEqual(field.type, "one2many", "transaction_ids must be One2many")
        self.assertEqual(field.comodel_name, "plasticos.transaction")
        self.assertEqual(field.inverse_name, "intake_id")
"""

import unittest

from odoo.addons.plasticos_base.tests.common import PlasticosTestCase
from odoo.tests.common import tagged

# ═══════════════════════════════════════════════════════════════════════════
# INTAKE MODEL CONTRACT
# ═══════════════════════════════════════════════════════════════════════════
# plasticos.intake is inherited by 7 modules:
#   - plasticos_transaction.models.intake_bridge (transaction_ids, transaction_count)
#   - plasticos_offer.models.intake_offers_bridge (offer_ids, offer_count)
#   - plasticos_buyer_match_engine.models.intake_graph_hooks (write override)
#   - plasticos_buyer_match_engine.models.intake_extension (match_mode field)
#   - plasticos_intake_normalizer.models.intake_normalizer (normalized, match_status, packet fields)
#   - plasticos_geolocalize.models.intake_geo (lat, lon)
#   - plasticos_matching (match_result_ids)


@tagged("post_install", "-at_install", "plasticos", "contract", "intake")
class TestIntakeModelContract(PlasticosTestCase):
    """Contract tests for plasticos.intake — fields/methods other modules depend on."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if "plasticos.intake" not in cls.env:
            raise unittest.SkipTest("plasticos.intake not installed")
        cls.Intake = cls.env["plasticos.intake"]
        cls.fields = cls.Intake._fields

    # ── Core Fields (base module) ────────────────────────────────────────

    def test_intake_has_partner_id_many2one(self):
        """partner_id is required by all bridge modules for linking."""
        field = self.fields.get("partner_id")
        self.assertIsNotNone(field, "partner_id field missing from intake")
        self.assertEqual(field.type, "many2one", "partner_id must be Many2one")
        self.assertEqual(field.comodel_name, "res.partner")

    def test_intake_has_polymer_id_many2one(self):
        """polymer_id is required by normalizer for validation."""
        field = self.fields.get("polymer_id")
        self.assertIsNotNone(field, "polymer_id field missing from intake")
        self.assertEqual(field.type, "many2one", "polymer_id must be Many2one")
        self.assertEqual(field.comodel_name, "plasticos.polymer")

    def test_intake_has_form_id_many2one(self):
        """form_id is required by normalizer for validation."""
        field = self.fields.get("form_id")
        self.assertIsNotNone(field, "form_id field missing from intake")
        self.assertEqual(field.type, "many2one", "form_id must be Many2one")
        self.assertEqual(field.comodel_name, "plasticos.material.form")

    def test_intake_has_state_selection(self):
        """state field is used by multiple modules for workflow."""
        field = self.fields.get("state")
        self.assertIsNotNone(field, "state field missing from intake")
        self.assertEqual(field.type, "selection", "state must be Selection")

    def test_intake_state_has_required_values(self):
        """State values that other modules depend on."""
        field = self.fields.get("state")
        self.assertIsNotNone(field)
        values = [s[0] for s in field.selection]
        required_states = ["draft", "confirmed", "cancelled"]
        for state in required_states:
            self.assertIn(state, values, f"Missing required state: {state}")

    def test_intake_has_quantity_per_load_lbs(self):
        """quantity_per_load_lbs is used by normalizer and matcher."""
        field = self.fields.get("quantity_per_load_lbs")
        self.assertIsNotNone(field, "quantity_per_load_lbs field missing")
        self.assertIn(field.type, ("integer", "float"), "quantity must be numeric")

    def test_intake_has_crm_lead_id(self):
        """crm_lead_id links intake to CRM — used by CRM bridge."""
        field = self.fields.get("crm_lead_id")
        self.assertIsNotNone(field, "crm_lead_id field missing from intake")
        self.assertEqual(field.type, "many2one")
        self.assertEqual(field.comodel_name, "crm.lead")

    # ── Transaction Bridge Contract ──────────────────────────────────────

    def test_intake_has_transaction_ids_one2many(self):
        """transaction_ids added by plasticos_transaction.intake_bridge."""
        field = self.fields.get("transaction_ids")
        self.assertIsNotNone(field, "transaction_ids field missing — plasticos_transaction bridge not installed?")
        self.assertEqual(field.type, "one2many", "transaction_ids must be One2many")
        self.assertEqual(field.comodel_name, "plasticos.transaction")
        self.assertEqual(field.inverse_name, "intake_id", "inverse_name must be intake_id")

    def test_intake_has_transaction_count_computed(self):
        """transaction_count is computed from transaction_ids."""
        field = self.fields.get("transaction_count")
        self.assertIsNotNone(field, "transaction_count field missing")
        self.assertEqual(field.type, "integer")
        self.assertTrue(field.compute, "transaction_count must be computed")

    def test_intake_has_action_view_transactions(self):
        """action_view_transactions method for smart button navigation."""
        self.assertTrue(
            hasattr(self.Intake, "action_view_transactions"),
            "action_view_transactions method missing — transaction bridge not installed?",
        )
        self.assertTrue(
            callable(self.Intake.action_view_transactions),
            "action_view_transactions must be callable",
        )

    # ── Offer Bridge Contract ────────────────────────────────────────────

    def test_intake_has_offer_ids_one2many(self):
        """offer_ids added by plasticos_offer.intake_offers_bridge."""
        field = self.fields.get("offer_ids")
        self.assertIsNotNone(field, "offer_ids field missing — plasticos_offer bridge not installed?")
        self.assertEqual(field.type, "one2many", "offer_ids must be One2many")
        self.assertEqual(field.comodel_name, "plasticos.offer")

    def test_intake_has_offer_count_computed(self):
        """offer_count is computed from offer_ids."""
        field = self.fields.get("offer_count")
        self.assertIsNotNone(field, "offer_count field missing")
        self.assertTrue(field.compute, "offer_count must be computed")

    def test_intake_has_action_view_offers(self):
        """action_view_offers method for smart button navigation."""
        self.assertTrue(
            hasattr(self.Intake, "action_view_offers"),
            "action_view_offers method missing",
        )

    # ── Normalizer Bridge Contract ───────────────────────────────────────

    def test_intake_has_normalized_boolean(self):
        """normalized field added by plasticos_intake_normalizer."""
        field = self.fields.get("normalized")
        self.assertIsNotNone(field, "normalized field missing — normalizer not installed?")
        self.assertEqual(field.type, "boolean", "normalized must be Boolean")

    def test_intake_has_match_status_selection(self):
        """match_status field added by normalizer."""
        field = self.fields.get("match_status")
        self.assertIsNotNone(field, "match_status field missing")
        self.assertEqual(field.type, "selection")

    def test_intake_match_status_has_required_values(self):
        """match_status values that cron and views depend on."""
        field = self.fields.get("match_status")
        if not field:
            self.skipTest("match_status not installed")
        values = [s[0] for s in field.selection]
        required = ["pending", "normalized", "error"]
        for val in required:
            self.assertIn(val, values, f"Missing match_status value: {val}")

    def test_intake_has_packet_fields(self):
        """Packet fields written by normalizer, read by L9 adapter."""
        packet_fields = ["last_packet_id", "last_packet_version", "last_packet_payload", "last_packet_ts"]
        for fname in packet_fields:
            self.assertIn(fname, self.fields, f"Missing packet field: {fname}")

    def test_intake_has_action_normalize(self):
        """action_normalize method for manual normalization."""
        self.assertTrue(
            hasattr(self.Intake, "action_normalize"),
            "action_normalize method missing — normalizer not installed?",
        )

    def test_intake_has_cron_batch_normalize(self):
        """cron_batch_normalize method for scheduled normalization."""
        self.assertTrue(
            hasattr(self.Intake, "cron_batch_normalize"),
            "cron_batch_normalize method missing",
        )

    # ── Geo Bridge Contract ──────────────────────────────────────────────

    def test_intake_has_lat_lon_fields(self):
        """lat/lon fields added by plasticos_geolocalize."""
        for fname in ("lat", "lon"):
            field = self.fields.get(fname)
            self.assertIsNotNone(field, f"{fname} field missing — geolocalize not installed?")
            self.assertEqual(field.type, "float", f"{fname} must be Float")

    # ── Match Result Bridge Contract ─────────────────────────────────────

    def test_intake_has_match_result_ids(self):
        """match_result_ids links to matching results."""
        field = self.fields.get("match_result_ids")
        if not field:
            self.skipTest("match_result_ids not installed — plasticos_matching not present")
        self.assertEqual(field.type, "one2many")
        self.assertEqual(field.comodel_name, "plasticos.match.result")


# ═══════════════════════════════════════════════════════════════════════════
# TRANSACTION MODEL CONTRACT
# ═══════════════════════════════════════════════════════════════════════════
# plasticos.transaction is inherited by:
#   - plasticos_claims.models.transaction_claims (claim_ids, claim_count, has_quality_claim)
#   - plasticos_claims.models.transaction_claims_bridge (action_view_claims)
#   - plasticos_logistics.models.transaction_inherit (load_ids)
#   - plasticos_documents.models.transaction_docs (document_ids)


@tagged("post_install", "-at_install", "plasticos", "contract", "transaction")
class TestTransactionModelContract(PlasticosTestCase):
    """Contract tests for plasticos.transaction."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if "plasticos.transaction" not in cls.env:
            raise unittest.SkipTest("plasticos.transaction not installed")
        cls.Tx = cls.env["plasticos.transaction"]
        cls.fields = cls.Tx._fields

    # ── Core Fields ──────────────────────────────────────────────────────

    def test_transaction_has_intake_id(self):
        """intake_id links transaction back to source intake."""
        field = self.fields.get("intake_id")
        self.assertIsNotNone(field, "intake_id field missing")
        self.assertEqual(field.type, "many2one")
        self.assertEqual(field.comodel_name, "plasticos.intake")

    def test_transaction_has_offer_id(self):
        """offer_id links transaction to accepted offer."""
        field = self.fields.get("offer_id")
        self.assertIsNotNone(field, "offer_id field missing")
        self.assertEqual(field.type, "many2one")
        self.assertEqual(field.comodel_name, "plasticos.offer")

    def test_transaction_has_supplier_and_buyer(self):
        """supplier_id and buyer_id are required for partner bridge."""
        for fname in ("supplier_id", "buyer_id"):
            field = self.fields.get(fname)
            self.assertIsNotNone(field, f"{fname} field missing")
            self.assertEqual(field.type, "many2one")
            self.assertEqual(field.comodel_name, "res.partner")

    def test_transaction_has_state_selection(self):
        """state field for workflow."""
        field = self.fields.get("state")
        self.assertIsNotNone(field)
        self.assertEqual(field.type, "selection")

    # ── Claims Bridge Contract ───────────────────────────────────────────

    def test_transaction_has_claim_ids_one2many(self):
        """claim_ids added by plasticos_claims.transaction_claims."""
        field = self.fields.get("claim_ids")
        self.assertIsNotNone(field, "claim_ids field missing — claims module not installed?")
        self.assertEqual(field.type, "one2many")
        self.assertEqual(field.comodel_name, "plasticos.claim")
        self.assertEqual(field.inverse_name, "transaction_id")

    def test_transaction_has_claim_count_computed_stored(self):
        """claim_count is computed AND stored (for performance)."""
        field = self.fields.get("claim_count")
        self.assertIsNotNone(field, "claim_count field missing")
        self.assertTrue(field.compute, "claim_count must be computed")
        self.assertTrue(field.store, "claim_count should be stored for performance")

    def test_transaction_has_has_quality_claim_computed(self):
        """has_quality_claim is computed from claim_ids.state."""
        field = self.fields.get("has_quality_claim")
        self.assertIsNotNone(field, "has_quality_claim field missing")
        self.assertEqual(field.type, "boolean")
        self.assertTrue(field.compute)

    def test_transaction_has_action_view_claims(self):
        """action_view_claims method for smart button."""
        self.assertTrue(
            hasattr(self.Tx, "action_view_claims"),
            "action_view_claims method missing — claims bridge not installed?",
        )

    # ── Logistics Bridge Contract ────────────────────────────────────────

    def test_transaction_has_load_ids(self):
        """load_ids added by plasticos_logistics."""
        field = self.fields.get("load_ids")
        self.assertIsNotNone(field, "load_ids field missing — logistics not installed?")
        self.assertEqual(field.type, "one2many")
        self.assertEqual(field.comodel_name, "plasticos.load")

    # ── Documents Bridge Contract ────────────────────────────────────────

    def test_transaction_has_document_ids(self):
        """document_ids added by plasticos_documents."""
        field = self.fields.get("document_ids")
        if not field:
            self.skipTest("document_ids not installed — documents module not present")
        self.assertEqual(field.type, "one2many")
        self.assertEqual(field.comodel_name, "plasticos.document")


# ═══════════════════════════════════════════════════════════════════════════
# PARTNER MODEL CONTRACT
# ═══════════════════════════════════════════════════════════════════════════
# res.partner is inherited by 8+ PlastOS modules


@tagged("post_install", "-at_install", "plasticos", "contract", "partner")
class TestPartnerModelContract(PlasticosTestCase):
    """Contract tests for res.partner PlastOS extensions."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Partner = cls.env["res.partner"]
        cls.fields = cls.Partner._fields

    # ── Intake Bridge Contract ───────────────────────────────────────────

    def test_partner_has_intake_count(self):
        """intake_count added by plasticos_intake.res_partner_intake."""
        field = self.fields.get("intake_count")
        self.assertIsNotNone(field, "intake_count field missing — intake module not installed?")
        self.assertEqual(field.type, "integer")
        self.assertTrue(field.compute, "intake_count must be computed")

    def test_partner_has_action_view_intakes(self):
        """action_view_intakes for smart button navigation."""
        self.assertTrue(
            hasattr(self.Partner, "action_view_intakes"),
            "action_view_intakes method missing",
        )

    def test_partner_has_action_create_intake(self):
        """action_create_intake for quick intake creation."""
        self.assertTrue(
            hasattr(self.Partner, "action_create_intake"),
            "action_create_intake method missing",
        )

    # ── Transaction Bridge Contract ──────────────────────────────────────

    def test_partner_has_transaction_as_supplier_ids(self):
        """transaction_as_supplier_ids added by transaction.partner_bridge."""
        field = self.fields.get("transaction_as_supplier_ids")
        self.assertIsNotNone(field, "transaction_as_supplier_ids field missing")
        self.assertEqual(field.type, "one2many")
        self.assertEqual(field.comodel_name, "plasticos.transaction")

    def test_partner_has_transaction_as_buyer_ids(self):
        """transaction_as_buyer_ids added by transaction.partner_bridge."""
        field = self.fields.get("transaction_as_buyer_ids")
        self.assertIsNotNone(field, "transaction_as_buyer_ids field missing")
        self.assertEqual(field.type, "one2many")

    def test_partner_has_plasticos_transaction_count(self):
        """plasticos_transaction_count computed from both supplier and buyer."""
        field = self.fields.get("plasticos_transaction_count")
        self.assertIsNotNone(field, "plasticos_transaction_count field missing")
        self.assertTrue(field.compute)

    def test_partner_has_action_view_plasticos_transactions(self):
        """action_view_plasticos_transactions for smart button."""
        self.assertTrue(
            hasattr(self.Partner, "action_view_plasticos_transactions"),
            "action_view_plasticos_transactions method missing",
        )

    # ── Geo Bridge Contract ──────────────────────────────────────────────

    def test_partner_has_lat_lon_fields(self):
        """lat/lon fields added by plasticos_geolocalize."""
        for fname in ("lat", "lon"):
            field = self.fields.get(fname)
            if not field:
                self.skipTest(f"{fname} not installed — geolocalize not present")
            self.assertEqual(field.type, "float")

    # ── Material Profile Bridge Contract ─────────────────────────────────

    def test_partner_has_material_profile_ids(self):
        """material_profile_ids added by plasticos_material_profile."""
        field = self.fields.get("material_profile_ids")
        if not field:
            self.skipTest("material_profile_ids not installed")
        self.assertEqual(field.type, "one2many")
        self.assertEqual(field.comodel_name, "plasticos.material.profile")

    # ── Facility Profile Bridge Contract ─────────────────────────────────

    def test_partner_has_facility_profile_ids(self):
        """facility_profile_ids added by plasticos_facility_profile."""
        field = self.fields.get("facility_profile_ids")
        if not field:
            self.skipTest("facility_profile_ids not installed")
        self.assertEqual(field.type, "one2many")
        self.assertEqual(field.comodel_name, "plasticos.facility.profile")


# ═══════════════════════════════════════════════════════════════════════════
# CRM LEAD MODEL CONTRACT
# ═══════════════════════════════════════════════════════════════════════════
# crm.lead is inherited by plasticos_crm_bridge


@tagged("post_install", "-at_install", "plasticos", "contract", "crm")
class TestCrmLeadModelContract(PlasticosTestCase):
    """Contract tests for crm.lead PlastOS extensions."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if "crm.lead" not in cls.env:
            raise unittest.SkipTest("crm module not installed")
        cls.Lead = cls.env["crm.lead"]
        cls.fields = cls.Lead._fields

    # ── Web Lead Bridge ──────────────────────────────────────────────────

    def test_lead_has_web_lead_ids(self):
        """web_lead_ids links CRM lead to web leads."""
        field = self.fields.get("web_lead_ids")
        self.assertIsNotNone(field, "web_lead_ids field missing — CRM bridge not installed?")
        self.assertEqual(field.type, "one2many")
        self.assertEqual(field.comodel_name, "plasticos.web.lead")

    def test_lead_has_web_lead_count(self):
        """web_lead_count computed for smart button."""
        field = self.fields.get("web_lead_count")
        self.assertIsNotNone(field)
        self.assertTrue(field.compute)

    # ── Intake Bridge ────────────────────────────────────────────────────

    def test_lead_has_intake_ids(self):
        """intake_ids links CRM lead to intakes."""
        field = self.fields.get("intake_ids")
        self.assertIsNotNone(field, "intake_ids field missing")
        self.assertEqual(field.type, "one2many")
        self.assertEqual(field.comodel_name, "plasticos.intake")
        self.assertEqual(field.inverse_name, "crm_lead_id")

    def test_lead_has_intake_count(self):
        """intake_count computed for smart button."""
        field = self.fields.get("intake_count")
        self.assertIsNotNone(field)
        self.assertTrue(field.compute)

    # ── Profile Summary Fields ───────────────────────────────────────────

    def test_lead_has_profile_summary_fields(self):
        """Profile summary fields computed from partner's profiles."""
        summary_fields = [
            "material_profile_count",
            "total_match_count",
            "total_transaction_count",
        ]
        for fname in summary_fields:
            field = self.fields.get(fname)
            self.assertIsNotNone(field, f"{fname} field missing")
            self.assertTrue(field.compute, f"{fname} must be computed")

    # ── Action Methods ───────────────────────────────────────────────────

    def test_lead_has_action_convert_to_intake(self):
        """action_convert_to_intake is the primary CRM→PlastOS conversion."""
        self.assertTrue(
            hasattr(self.Lead, "action_convert_to_intake"),
            "action_convert_to_intake method missing — this is critical for CRM integration!",
        )

    def test_action_convert_to_intake_returns_action(self):
        """action_convert_to_intake must return an action dict."""
        partner = self.env["res.partner"].create({"name": "Contract Test Co", "is_company": True})
        lead = self.Lead.create(
            {
                "name": "Contract Test Lead",
                "partner_id": partner.id,
                "type": "lead",
            }
        )
        result = lead.action_convert_to_intake()
        self.assertIsInstance(result, dict, "action_convert_to_intake must return dict")
        self.assertEqual(result.get("type"), "ir.actions.act_window")
        self.assertEqual(result.get("res_model"), "plasticos.intake")

    def test_lead_has_action_view_intakes(self):
        """action_view_intakes for smart button."""
        self.assertTrue(hasattr(self.Lead, "action_view_intakes"))

    def test_lead_has_action_view_web_leads(self):
        """action_view_web_leads for smart button."""
        self.assertTrue(hasattr(self.Lead, "action_view_web_leads"))

    def test_lead_has_action_view_material_profiles(self):
        """action_view_material_profiles for smart button."""
        self.assertTrue(hasattr(self.Lead, "action_view_material_profiles"))

    def test_lead_has_action_view_match_results(self):
        """action_view_match_results for smart button."""
        self.assertTrue(hasattr(self.Lead, "action_view_match_results"))

    def test_lead_has_action_view_transactions(self):
        """action_view_transactions for smart button."""
        self.assertTrue(hasattr(self.Lead, "action_view_transactions"))


# ═══════════════════════════════════════════════════════════════════════════
# CLAIM MODEL CONTRACT
# ═══════════════════════════════════════════════════════════════════════════


@tagged("post_install", "-at_install", "plasticos", "contract", "claim")
class TestClaimModelContract(PlasticosTestCase):
    """Contract tests for plasticos.claim."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if "plasticos.claim" not in cls.env:
            raise unittest.SkipTest("plasticos.claim not installed")
        cls.Claim = cls.env["plasticos.claim"]
        cls.fields = cls.Claim._fields

    def test_claim_has_transaction_id(self):
        """transaction_id links claim to transaction."""
        field = self.fields.get("transaction_id")
        self.assertIsNotNone(field, "transaction_id field missing")
        self.assertEqual(field.type, "many2one")
        self.assertEqual(field.comodel_name, "plasticos.transaction")

    def test_claim_has_state_selection(self):
        """state field for workflow."""
        field = self.fields.get("state")
        self.assertIsNotNone(field)
        self.assertEqual(field.type, "selection")

    def test_claim_state_has_required_values(self):
        """State values that transaction bridge depends on."""
        field = self.fields.get("state")
        values = [s[0] for s in field.selection]
        # transaction_claims.py filters by these states
        required = ["resolved", "archived"]
        for state in required:
            self.assertIn(state, values, f"Missing required state: {state}")

    def test_claim_has_case_type_selection(self):
        """case_type used by transaction for chargeback/penalty calculation."""
        field = self.fields.get("case_type")
        self.assertIsNotNone(field, "case_type field missing")
        self.assertEqual(field.type, "selection")

    def test_claim_case_type_has_required_values(self):
        """case_type values used by _compute_chargebacks_penalties."""
        field = self.fields.get("case_type")
        values = [s[0] for s in field.selection]
        # These are used in transaction_claims.py
        required = ["buyer_claim", "freight_chargeback", "lightweight_penalty"]
        for val in required:
            self.assertIn(val, values, f"Missing case_type: {val}")

    def test_claim_has_recovery_amount(self):
        """recovery_amount used by transaction for chargeback calculation."""
        field = self.fields.get("recovery_amount")
        self.assertIsNotNone(field, "recovery_amount field missing")
        self.assertIn(field.type, ("float", "monetary"))


# ═══════════════════════════════════════════════════════════════════════════
# OFFER MODEL CONTRACT
# ═══════════════════════════════════════════════════════════════════════════


@tagged("post_install", "-at_install", "plasticos", "contract", "offer")
class TestOfferModelContract(PlasticosTestCase):
    """Contract tests for plasticos.offer."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if "plasticos.offer" not in cls.env:
            raise unittest.SkipTest("plasticos.offer not installed")
        cls.Offer = cls.env["plasticos.offer"]
        cls.fields = cls.Offer._fields

    def test_offer_has_intake_id(self):
        """intake_id links offer to source intake."""
        field = self.fields.get("intake_id")
        self.assertIsNotNone(field, "intake_id field missing")
        self.assertEqual(field.type, "many2one")
        self.assertEqual(field.comodel_name, "plasticos.intake")

    def test_offer_has_transaction_id(self):
        """transaction_id links to created transaction after acceptance."""
        field = self.fields.get("transaction_id")
        self.assertIsNotNone(field, "transaction_id field missing")
        self.assertEqual(field.type, "many2one")
        self.assertEqual(field.comodel_name, "plasticos.transaction")

    def test_offer_has_buyer_partner_id(self):
        """buyer_partner_id is required for offer creation."""
        field = self.fields.get("buyer_partner_id")
        self.assertIsNotNone(field, "buyer_partner_id field missing")
        self.assertEqual(field.type, "many2one")
        self.assertEqual(field.comodel_name, "res.partner")

    def test_offer_has_state_selection(self):
        """state field for workflow."""
        field = self.fields.get("state")
        self.assertIsNotNone(field)
        self.assertEqual(field.type, "selection")

    def test_offer_state_has_required_values(self):
        """State values for offer lifecycle."""
        field = self.fields.get("state")
        values = [s[0] for s in field.selection]
        required = ["draft", "sent", "accepted", "rejected", "expired", "cancelled"]
        for state in required:
            self.assertIn(state, values, f"Missing required state: {state}")

    def test_offer_has_action_accept(self):
        """action_accept creates transaction from offer."""
        self.assertTrue(
            hasattr(self.Offer, "action_accept"),
            "action_accept method missing — critical for transaction creation!",
        )

    def test_offer_has_action_send(self):
        """action_send transitions offer to sent state."""
        self.assertTrue(hasattr(self.Offer, "action_send"))

    def test_offer_has_action_reject(self):
        """action_reject transitions offer to rejected state."""
        self.assertTrue(hasattr(self.Offer, "action_reject"))


# ═══════════════════════════════════════════════════════════════════════════
# LOAD MODEL CONTRACT
# ═══════════════════════════════════════════════════════════════════════════


@tagged("post_install", "-at_install", "plasticos", "contract", "load")
class TestLoadModelContract(PlasticosTestCase):
    """Contract tests for plasticos.load."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if "plasticos.load" not in cls.env:
            raise unittest.SkipTest("plasticos.load not installed")
        cls.Load = cls.env["plasticos.load"]
        cls.fields = cls.Load._fields

    def test_load_has_transaction_id(self):
        """transaction_id links load to transaction."""
        field = self.fields.get("transaction_id")
        self.assertIsNotNone(field, "transaction_id field missing")
        self.assertEqual(field.type, "many2one")
        self.assertEqual(field.comodel_name, "plasticos.transaction")

    def test_load_has_state_selection(self):
        """state field for logistics workflow."""
        field = self.fields.get("state")
        self.assertIsNotNone(field)
        self.assertEqual(field.type, "selection")

    def test_load_state_has_required_values(self):
        """State values for logistics lifecycle."""
        field = self.fields.get("state")
        values = [s[0] for s in field.selection]
        required = ["draft", "scheduled", "dispatched", "delivered", "cancelled"]
        for state in required:
            self.assertIn(state, values, f"Missing required state: {state}")

    def test_load_has_logistics_actions(self):
        """Logistics action methods for state transitions."""
        actions = [
            "action_confirm_ready",
            "action_dispatch",
            "action_deliver",
            "action_cancel",
        ]
        for action in actions:
            self.assertTrue(
                hasattr(self.Load, action),
                f"{action} method missing",
            )

    # ── Document Bridge Contract ─────────────────────────────────────────

    def test_load_has_document_ids(self):
        """document_ids added by plasticos_documents."""
        field = self.fields.get("document_ids")
        if not field:
            self.skipTest("document_ids not installed")
        self.assertEqual(field.type, "one2many")

    def test_load_has_bol_attachment_id(self):
        """bol_attachment_id for Bill of Lading document."""
        field = self.fields.get("bol_attachment_id")
        if not field:
            self.skipTest("bol_attachment_id not installed")
        self.assertEqual(field.type, "many2one")
