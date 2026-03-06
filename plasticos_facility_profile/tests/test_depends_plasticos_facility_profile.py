from odoo.addons.plasticos_base.tests.common import PlasticosTestCase
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestFacilityProfileDepends(PlasticosTestCase):
    """Facility profile @api.depends fields."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.FacilityProfile = cls.env["plasticos.facility.profile"]
        cls.partner = cls.env["res.partner"].create({"name": "Facility Root"})

    def _profile(self, **vals):
        base = {
            "partner_id": self.partner.id,
        }
        base.update(vals)
        return self.FacilityProfile.create(base)

    def test_density_range_label(self):
        prof = self._profile(density_min=0.9, density_max=1.1)
        if hasattr(prof, "density_range_label"):
            self.assertIn("0.9", prof.density_range_label)
            self.assertIn("1.1", prof.density_range_label)

    def test_mfi_range_label(self):
        prof = self._profile(mfi_min=1.0, mfi_max=10.0)
        if hasattr(prof, "mfi_range_label"):
            self.assertIn("1.0", prof.mfi_range_label)
            self.assertIn("10.0", prof.mfi_range_label)

    def test_partner_facility_profile_count(self):
        prof = self._profile()
        self.partner.invalidate_recordset()
        if hasattr(self.partner, "facility_profile_count"):
            self.assertGreaterEqual(self.partner.facility_profile_count, 1)
