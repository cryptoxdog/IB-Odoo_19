"""Contract tests for plasticos.intake — the most-inherited model in PlastOS.

Modules that inherit plasticos.intake:
  - plasticos_transaction (intake_bridge.py)
  - plasticos_offer (intake_offers_bridge.py)
  - plasticos_matching (intake_extension.py — action_match_to_buyers override)
  - plasticos_intake_normalizer (intake_normalizer.py)
  - plasticos_geolocalize (intake_geo.py)
  - plasticos_web_leads (web_lead_bridge.py)
  - plasticos_crm_bridge (web_lead.py — links via crm_lead_id)

Any change to these contracted fields/methods MUST update all consumers.
"""

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.tests.common import tagged


@tagged("post_install", "-at_install", "contract")
class TestIntakeFieldContract(PlasticosTestCase):
    """Fields that downstream bridge modules depend on."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Intake = cls.env["plasticos.intake"]
        cls.fields = cls.Intake._fields

    # ── Identity fields (used by ALL bridges) ───────────────
    def test_name_field_exists_and_is_char(self):
        self.assertIn("name", self.fields)
        self.assertEqual(self.fields["name"].type, "char")

    def test_partner_id_exists_and_targets_res_partner(self):
        self.assertIn("partner_id", self.fields)
        self.assertEqual(self.fields["partner_id"].comodel_name, "res.partner")

    def test_facility_id_exists_and_targets_res_partner(self):
        self.assertIn("facility_id", self.fields)
        self.assertEqual(self.fields["facility_id"].comodel_name, "res.partner")

    def test_contact_id_exists_and_targets_res_partner(self):
        self.assertIn("contact_id", self.fields)
        self.assertEqual(self.fields["contact_id"].comodel_name, "res.partner")

    # ── Material fields (used by plasticos_matching, normalizer) ──
    def test_polymer_id_exists(self):
        f = self.fields.get("polymer_id")
        self.assertIsNotNone(f, "polymer_id missing — plasticos_matching depends on it")
        self.assertEqual(f.comodel_name, "plasticos.polymer")

    def test_form_id_exists(self):
        f = self.fields.get("form_id")
        self.assertIsNotNone(f, "form_id missing — plasticos_matching depends on it")
        self.assertEqual(f.comodel_name, "plasticos.material.form")

    def test_color_id_exists(self):
        self.assertIn("color_id", self.fields)

    def test_source_type_id_exists(self):
        self.assertIn("source_type_id", self.fields)

    def test_material_profile_id_exists(self):
        f = self.fields.get("material_profile_id")
        self.assertIsNotNone(f)
        self.assertEqual(f.comodel_name, "plasticos.material.profile")

    def test_material_attribute_ids_exists(self):
        self.assertIn("material_attribute_ids", self.fields)
        self.assertEqual(self.fields["material_attribute_ids"].type, "many2many")

    def test_quality_boolean_fields(self):
        """has_residue is computed from contamination_pct."""
        required_booleans = [
            "has_residue",
        ]
        for fname in required_booleans:
            self.assertIn(fname, self.fields, f"Missing boolean: {fname}")
            self.assertEqual(
                self.fields[fname].type,
                "boolean",
                f"{fname} must be boolean, got {self.fields[fname].type}",
            )

    # ── Numeric quality (used by inference engine, normalizer) ──
    def test_numeric_quality_fields(self):
        required_floats = [
            "mfi_value",
            "density_value",
            "moisture_pct",
            "contamination_pct",
            "filler_pct",
        ]
        for fname in required_floats:
            self.assertIn(fname, self.fields, f"Missing float: {fname}")
            self.assertEqual(self.fields[fname].type, "float")

    # ── Volume fields (used by transaction bridge, logistics) ──
    def test_quantity_per_load_lbs_exists(self):
        self.assertIn("quantity_per_load_lbs", self.fields)
        self.assertEqual(self.fields["quantity_per_load_lbs"].type, "integer")

    def test_loads_per_month_exists(self):
        self.assertIn("loads_per_month", self.fields)

    # ── Status field (used by ALL downstream state machines) ──
    def test_status_field_exists_and_is_selection(self):
        f = self.fields.get("status")
        self.assertIsNotNone(f, "status field missing — all bridges depend on it")
        self.assertEqual(f.type, "selection")

    def test_status_has_required_values(self):
        """Every bridge module depends on these status values existing."""
        f = self.fields["status"]
        values = [s[0] for s in f.selection]
        required = [
            "draft",
            "matched",
            "offer_sent",
            "processing",
            "won",
            "lost",
            "expired",
        ]
        for state in required:
            self.assertIn(state, values, f"Missing status value: {state}")

    # ── Geo fields (used by geolocalize, freight automation) ──
    def test_geo_fields_exist(self):
        for fname in ("lat", "lon"):
            self.assertIn(fname, self.fields, f"Missing geo field: {fname}")
            self.assertEqual(self.fields[fname].type, "float")

    # ── CRM link (used by crm_bridge) ──
    def test_crm_lead_id_exists(self):
        self.assertIn("crm_lead_id", self.fields)
        self.assertEqual(self.fields["crm_lead_id"].comodel_name, "crm.lead")

    def test_source_lead_id_exists(self):
        """Integer FK to web lead (avoids circular dep)."""
        self.assertIn("source_lead_id", self.fields)
        self.assertEqual(self.fields["source_lead_id"].type, "integer")

    # ── Match results (used by offer bridge, transaction bridge) ──
    def test_match_line_ids_exists(self):
        f = self.fields.get("match_line_ids")
        self.assertIsNotNone(f)
        self.assertEqual(f.comodel_name, "plasticos.intake.match")

    def test_match_count_is_stored_computed(self):
        f = self.fields.get("match_count")
        self.assertIsNotNone(f)
        self.assertTrue(f.store, "match_count should be stored for list view perf")

    def test_best_match_score_exists(self):
        self.assertIn("best_match_score", self.fields)

    # ── Assignment (used by web_leads routing) ──
    def test_assigned_user_id_exists(self):
        self.assertIn("assigned_user_id", self.fields)
        self.assertEqual(self.fields["assigned_user_id"].comodel_name, "res.users")

    # ── Pending company (web lead flow) ──
    def test_pending_company_name_exists(self):
        self.assertIn("pending_company_name", self.fields)

    # ── Origin intelligence (used by inference engine) ──
    def test_origin_fields_exist(self):
        for fname in ("origin_application", "origin_sector", "origin_process_type"):
            self.assertIn(fname, self.fields, f"Missing origin field: {fname}")

    def test_origin_sector_selection_values(self):
        f = self.fields["origin_sector"]
        values = [s[0] for s in f.selection]
        required = ["automotive", "construction", "food", "industrial", "packaging"]
        for v in required:
            self.assertIn(v, values)

    def test_origin_process_type_selection_values(self):
        f = self.fields["origin_process_type"]
        values = [s[0] for s in f.selection]
        required = ["injection", "extrusion", "blow_mold", "film_blown"]
        for v in required:
            self.assertIn(v, values)


@tagged("post_install", "-at_install", "contract")
class TestIntakeMethodContract(PlasticosTestCase):
    """Methods that downstream modules call or override."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Intake = cls.env["plasticos.intake"]

    # ── Status transition methods (offer, transaction bridges) ──
    def test_action_send_offer_exists(self):
        self.assertTrue(callable(getattr(self.Intake, "action_send_offer", None)))

    def test_action_mark_processing_exists(self):
        self.assertTrue(callable(getattr(self.Intake, "action_mark_processing", None)))

    def test_action_mark_won_exists(self):
        self.assertTrue(callable(getattr(self.Intake, "action_mark_won", None)))

    def test_action_mark_lost_exists(self):
        self.assertTrue(callable(getattr(self.Intake, "action_mark_lost", None)))

    def test_action_mark_expired_exists(self):
        self.assertTrue(callable(getattr(self.Intake, "action_mark_expired", None)))

    def test_action_reset_to_draft_exists(self):
        self.assertTrue(callable(getattr(self.Intake, "action_reset_to_draft", None)))

    # ── Buyer matching (plasticos_matching overrides this) ──
    def test_action_match_to_buyers_exists(self):
        self.assertTrue(callable(getattr(self.Intake, "action_match_to_buyers", None)))

    # ── Offer flow (offer module overrides this) ──
    def test_action_send_offers_exists(self):
        self.assertTrue(callable(getattr(self.Intake, "action_send_offers", None)))

    # ── PO creation (transaction bridge) ──
    def test_action_make_po_exists(self):
        self.assertTrue(callable(getattr(self.Intake, "action_make_po", None)))

    # ── Navigation actions (used in XML buttons) ──
    def test_navigation_actions_exist(self):
        actions = [
            "action_view_material_profile",
            "action_view_supplier",
            "action_view_facility",
            "action_view_matches",
            "action_view_best_match",
        ]
        for method in actions:
            self.assertTrue(
                callable(getattr(self.Intake, method, None)),
                f"Missing navigation method: {method}",
            )

    # ── Internal helpers (plasticos_matching calls these) ──
    def test_create_material_profile_from_intake_exists(self):
        self.assertTrue(callable(getattr(self.Intake, "_create_material_profile_from_intake", None)))

    def test_create_partner_from_pending_exists(self):
        self.assertTrue(callable(getattr(self.Intake, "_create_partner_from_pending", None)))

    def test_assert_status_guard_exists(self):
        self.assertTrue(callable(getattr(self.Intake, "_assert_status", None)))


@tagged("post_install", "-at_install", "contract")
class TestIntakeMailMixin(PlasticosTestCase):
    """Verify intake inherits mail.thread for chatter integration."""

    def test_intake_has_mail_thread(self):
        self.assertIn("mail.thread", self.env["plasticos.intake"]._inherit)

    def test_intake_has_message_post(self):
        self.assertTrue(callable(getattr(self.env["plasticos.intake"], "message_post", None)))
