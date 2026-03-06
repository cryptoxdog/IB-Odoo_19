"""Test 13 — Intake Onchange Cascade Tests.

Source: plasticos_intake/models/intake.py
Risk: HIGH — UX. 9 @api.onchange methods cascade data silently.

Validates:
  - _onchange_partner_id auto-selects single facility or flagship
  - _onchange_facility_id auto-selects preferred contact
  - _onchange_material_profile prefills snapshot fields
  - _onchange_material_attributes syncs boolean flags
  - _onchange_has_metal syncs attribute IDs bidirectionally
  - _onchange_is_metalized syncs attribute IDs
  - _onchange_has_fr syncs attribute IDs
  - _onchange_lead_source_id syncs to partner
"""

from odoo.tests import Form, TransactionCase, tagged


@tagged("post_install", "-at_install", "intake", "onchange")
class TestIntakePartnerCascade(TransactionCase):
    """partner_id → facility_id → contact_id cascade."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env["res.partner"].create(
            {
                "name": "Cascade Corp",
                "is_company": True,
            }
        )
        cls.facility = cls.env["res.partner"].create(
            {
                "name": "Cascade Facility",
                "is_company": True,
                "parent_id": cls.company.id,
            }
        )
        cls.contact = cls.env["res.partner"].create(
            {
                "name": "John Cascade",
                "is_company": False,
                "parent_id": cls.facility.id,
                "type": "contact",
            }
        )

    def test_single_facility_auto_selected(self):
        """When company has exactly one child facility, auto-select it."""
        form = Form(self.env["plasticos.intake"])
        form.quantity_per_load_lbs = 40000
        form.partner_id = self.company
        self.assertEqual(form.facility_id, self.facility)

    def test_standalone_company_is_own_facility(self):
        """Company with no children becomes its own facility."""
        standalone = self.env["res.partner"].create(
            {
                "name": "Standalone Inc",
                "is_company": True,
            }
        )
        form = Form(self.env["plasticos.intake"])
        form.quantity_per_load_lbs = 40000
        form.partner_id = standalone
        self.assertEqual(form.facility_id, standalone)

    def test_multiple_facilities_no_auto_select(self):
        """Multiple children: user must pick, facility_id stays empty."""
        second_fac = self.env["res.partner"].create(
            {
                "name": "Second Facility",
                "is_company": True,
                "parent_id": self.company.id,
            }
        )
        form = Form(self.env["plasticos.intake"])
        form.quantity_per_load_lbs = 40000
        form.partner_id = self.company
        self.assertFalse(form.facility_id)
        second_fac.unlink()  # cleanup

    def test_single_contact_auto_selected(self):
        """Facility with one contact auto-selects it."""
        form = Form(self.env["plasticos.intake"])
        form.quantity_per_load_lbs = 40000
        form.partner_id = self.company
        # facility auto-selected → contact should follow
        self.assertEqual(form.contact_id, self.contact)

    def test_changing_partner_clears_downstream(self):
        """Changing partner_id clears facility and contact."""
        other = self.env["res.partner"].create(
            {
                "name": "Other Corp",
                "is_company": True,
            }
        )
        form = Form(self.env["plasticos.intake"])
        form.quantity_per_load_lbs = 40000
        form.partner_id = self.company
        self.assertTrue(form.facility_id)
        form.partner_id = other
        # Facility should reset (other has no children → is own facility)
        self.assertEqual(form.facility_id, other)


@tagged("post_install", "-at_install", "intake", "onchange")
class TestIntakeMaterialProfilePrefill(TransactionCase):
    """_onchange_material_profile prefills snapshot fields."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "Profile Test Co",
                "is_company": True,
            }
        )
        Polymer = cls.env.get("plasticos.polymer")
        FormModel = cls.env.get("plasticos.material.form")
        cls.polymer = Polymer.create({"name": "HDPE-Test"}) if Polymer else None
        cls.form = FormModel.create({"name": "Pellet-Test"}) if FormModel else None

        MP = cls.env.get("plasticos.material.profile")
        if MP and cls.polymer and cls.form:
            cls.profile = MP.create(
                {
                    "name": "Test Profile",
                    "partner_id": cls.partner.id,
                    "polymer_id": cls.polymer.id,
                    "form_id": cls.form.id,
                    "melt_flow_index": 12.5,
                    "density": 0.95,
                    "contamination_percent": 2.0,
                }
            )
            cls.has_profile = True
        else:
            cls.has_profile = False

    def test_material_profile_prefills_polymer(self):
        if not self.has_profile:
            self.skipTest("material profile model not available")
        form = Form(self.env["plasticos.intake"])
        form.quantity_per_load_lbs = 40000
        form.partner_id = self.partner
        form.material_profile_id = self.profile
        self.assertEqual(form.polymer_id, self.polymer)

    def test_material_profile_prefills_form(self):
        if not self.has_profile:
            self.skipTest("material profile model not available")
        form = Form(self.env["plasticos.intake"])
        form.quantity_per_load_lbs = 40000
        form.partner_id = self.partner
        form.material_profile_id = self.profile
        self.assertEqual(form.form_id, self.form)

    def test_material_profile_prefills_quality_numerics(self):
        if not self.has_profile:
            self.skipTest("material profile model not available")
        form = Form(self.env["plasticos.intake"])
        form.quantity_per_load_lbs = 40000
        form.partner_id = self.partner
        form.material_profile_id = self.profile
        self.assertAlmostEqual(form.mfi_value, 12.5, places=1)
        self.assertAlmostEqual(form.density_value, 0.95, places=2)


@tagged("post_install", "-at_install", "intake", "onchange")
class TestIntakeAttributeBooleanSync(TransactionCase):
    """Boolean ↔ attribute bidirectional sync."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Attr = cls.env.get("plasticos.material.attribute")
        if not Attr:
            cls.has_attrs = False
            return
        cls.has_attrs = True
        cls.with_metal = Attr.search([("code", "=", "with_metal")], limit=1)
        cls.no_metal = Attr.search([("code", "=", "no_metal")], limit=1)
        cls.metalized = Attr.search([("code", "=", "metalized")], limit=1)

    def test_has_metal_true_adds_with_metal_attr(self):
        if not self.has_attrs or not self.with_metal:
            self.skipTest("Material attributes not seeded")
        form = Form(self.env["plasticos.intake"])
        form.quantity_per_load_lbs = 40000
        form.has_metal = True
        # After onchange, with_metal attribute should be present
        attr_ids = form.material_attribute_ids._get_ids()
        self.assertIn(self.with_metal.id, attr_ids)

    def test_has_metal_false_adds_no_metal_attr(self):
        if not self.has_attrs or not self.no_metal:
            self.skipTest("Material attributes not seeded")
        form = Form(self.env["plasticos.intake"])
        form.quantity_per_load_lbs = 40000
        form.has_metal = False
        # Trigger the onchange explicitly
        attr_ids = form.material_attribute_ids._get_ids()
        # no_metal should be present (or with_metal removed)
        if self.no_metal:
            self.assertIn(self.no_metal.id, attr_ids)
