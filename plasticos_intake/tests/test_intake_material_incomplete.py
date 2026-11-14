"""An intake may be saved without polymer or form, is flagged incomplete, and cannot start a match.

Web-lead triage creates an intake before the material is identified (PR #492
dropped NOT NULL on ``polymer_id`` / ``form_id``). Saving stays allowed; the
stored ``material_incomplete`` flag makes the gap visible and the one
predicate (``plasticos_intake/match_material.py``) refuses every match start.
"""

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.addons.plasticos_intake.match_material import REQUIRED_MATCH_MATERIAL, missing_match_material
from odoo.exceptions import UserError
from odoo.tests.common import tagged


@tagged("post_install", "-at_install", "plasticos", "intake")
class TestIntakeMaterialIncomplete(PlasticosTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Intake = cls.env["plasticos.intake"]
        cls.polymer = cls._get_or_create_polymer()
        cls.form = cls._get_or_create_form()
        cls.partner = cls._create_partner("Material Incomplete Supplier", supplier_rank=1)

    # ── the predicate ─────────────────────────────────────────

    def test_predicate_names_exactly_the_missing_facts(self):
        self.assertEqual([key for key, _label in REQUIRED_MATCH_MATERIAL], ["polymer_type", "form"])
        self.assertEqual(missing_match_material({}), ["Polymer", "Form"])
        self.assertEqual(missing_match_material({"polymer_type": "HDPE"}), ["Form"])
        self.assertEqual(missing_match_material({"form": "pellet", "polymer_type": False}), ["Polymer"])
        self.assertEqual(missing_match_material({"polymer_type": "HDPE", "form": "pellet", "color": "blue"}), [])

    # ── saving stays allowed; the flag is stored and searchable ──

    def test_triage_shaped_intake_without_material_saves_and_is_flagged(self):
        """The shape triage writes when no material was identified: a company name and nothing else."""
        intake = self.Intake.create({"pending_company_name": "Unidentified Material Co"})
        self.assertTrue(intake.id)
        self.assertFalse(intake.polymer_id)
        self.assertFalse(intake.form_id)
        self.assertTrue(intake.material_incomplete)
        self.assertEqual(intake._plasticos_missing_match_material(), ["Polymer", "Form"])
        self.assertIn(intake, self.Intake.search([("material_incomplete", "=", True)]))

    def test_flag_follows_polymer_and_form(self):
        intake = self.Intake.create({"partner_id": self.partner.id, "polymer_id": self.polymer.id})
        self.assertTrue(intake.material_incomplete, "a polymer without a form is still incomplete")
        intake.form_id = self.form
        self.assertFalse(intake.material_incomplete)
        self.assertEqual(intake._plasticos_missing_match_material(), [])
        self.assertNotIn(intake, self.Intake.search([("material_incomplete", "=", True)]))
        intake.polymer_id = False
        self.assertTrue(intake.material_incomplete, "clearing the polymer flags the intake again")
        self.assertIn(intake, self.Intake.search([("material_incomplete", "=", True)]))

    def test_polymer_and_form_stay_optional_on_the_model(self):
        self.assertFalse(self.Intake._fields["polymer_id"].required)
        self.assertFalse(self.Intake._fields["form_id"].required)

    # ── the refusal ───────────────────────────────────────────

    def test_require_refuses_an_incomplete_intake_and_names_what_is_missing(self):
        intake = self.Intake.create({"partner_id": self.partner.id, "polymer_id": self.polymer.id})
        with self.assertRaisesRegex(UserError, r"cannot be matched: Form not set"):
            intake._plasticos_require_match_material()
        intake.write({"polymer_id": False})
        with self.assertRaisesRegex(UserError, r"Polymer and Form not set"):
            intake._plasticos_require_match_material()

    def test_require_passes_a_complete_intake(self):
        intake = self._create_intake(partner=self.partner, polymer=self.polymer, form=self.form)
        self.assertFalse(intake.material_incomplete)
        intake._plasticos_require_match_material()

    # ── visibility ────────────────────────────────────────────

    def test_views_expose_the_flag_without_requiring_the_fields(self):
        views = self.Intake.get_views([(False, "list"), (False, "form"), (False, "search")])["views"]
        self.assertIn('decoration-danger="material_incomplete"', views["list"]["arch"])
        self.assertIn("filter_material_incomplete", views["search"]["arch"])
        self.assertIn("material_incomplete", views["form"]["arch"])
