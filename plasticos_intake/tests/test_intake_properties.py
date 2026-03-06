# tests/test_intake_properties.py
"""Property-based tests for intake model.

Requires hypothesis library. Skipped if not installed.
"""

from hypothesis import given
from hypothesis import strategies as st

from odoo.addons.plasticos_base.tests.common import PlasticosTestCase


class TestIntakeProperties(PlasticosTestCase):
    """Property-based tests for intake model"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.test_partner = cls.env.ref("base.res_partner_1", raise_if_not_found=False)
        if not cls.test_partner:
            cls.test_partner = cls.env["res.partner"].create({"name": "Property Test Partner", "is_company": True})

    @given(
        quantity=st.integers(min_value=1, max_value=1000000),
        material_type=st.sampled_from(["PET", "HDPE", "PP", "LDPE", "PS"]),
    )
    def test_create_with_random_valid_inputs(self, quantity, material_type):
        """Test intake creation with randomly generated valid inputs"""
        intake = self.env["plasticos.intake"].create(
            {
                "partner_id": self.test_partner.id,
                "material_type": material_type,
                "quantity_per_load_lbs": quantity,
            }
        )

        self.assertTrue(intake.exists())
        self.assertGreater(intake.quantity_per_load_lbs, 0)
        self.assertIn(intake.state, ["draft", "confirmed", "approved", "cancelled"])
        self.assertRegex(intake.name, r"^INT/\d{4}/\d{5}$")

    @given(quantities=st.lists(st.integers(min_value=1, max_value=10000), min_size=1, max_size=100))
    def test_bulk_create_sequences_always_unique(self, quantities):
        """Property: bulk creation always generates unique sequences"""
        intakes = self.env["plasticos.intake"].create(
            [
                {
                    "partner_id": self.test_partner.id,
                    "material_type": "PET",
                    "quantity_per_load_lbs": qty,
                }
                for qty in quantities
            ]
        )

        names = intakes.mapped("name")
        self.assertEqual(len(names), len(set(names)), "Sequence uniqueness violated")
