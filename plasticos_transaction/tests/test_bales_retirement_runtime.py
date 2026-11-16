"""Bales retirement on a live registry: merge, fill empty fields, repoint, delete.

Covers ``plasticos_material_profile.bales_retirement.OdooOps`` (the pure planner
and orchestrator are covered by ``tests/test_bales_form_migration_collisions.py``).
Lives here because ``plasticos_transaction`` depends on ``plasticos_intake``, whose
``material_profile_id`` is a plain reference to repoint.
"""

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.addons.plasticos_material_profile import bales_retirement
from odoo.tests.common import tagged


@tagged("post_install", "-at_install", "material_profile")
class TestBalesRetirementRuntime(PlasticosTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.form_bale = cls.env.ref(bales_retirement.FORM_BALE).with_context(active_test=False)
        cls.bales = cls.env.ref(bales_retirement.PACKAGING_BALES)
        company = cls._create_partner("Bales Retirement Co", supplier_rank=1)
        cls.site = cls._create_partner("Bales Retirement Site", parent_id=company.id, is_company=False)
        cls.Profile = cls.env["plasticos.material.profile"].with_context(active_test=False)

    def test_duplicate_is_merged_and_free_key_is_moved(self):
        survivor = self.Profile.create({"partner_id": self.site.id, "polymer_id": self.default_polymer.id})
        duplicate = self.Profile.create(
            {
                "partner_id": self.site.id,
                "polymer_id": self.default_polymer.id,
                "form_id": self.form_bale.id,
                "freeform_notes": "from the Bales row",
            }
        )
        other_polymer = self._get_or_create_polymer("PP")
        mover = self.Profile.create(
            {"partner_id": self.site.id, "polymer_id": other_polymer.id, "form_id": self.form_bale.id}
        )
        intake = self._create_intake(partner=self.site, polymer=self.default_polymer)
        intake.write({"material_profile_id": duplicate.id})

        counts = bales_retirement.retire_bales_form(self.env)

        self.assertEqual((counts.moved, counts.merged, counts.unresolved), (1, 1, 0))
        self.assertFalse(duplicate.exists())
        self.assertEqual(intake.material_profile_id, survivor)
        self.assertEqual(survivor.packaging_type_id, self.bales)
        self.assertEqual(survivor.freeform_notes, "from the Bales row")
        self.assertFalse(mover.form_id)
        self.assertEqual(mover.packaging_type_id, self.bales)
        self.assertFalse(self.Profile.search_count([("form_id", "=", self.form_bale.id)]))
        self.assertFalse(self.form_bale.active)

    def test_packaging_conflict_leaves_both_rows(self):
        gaylords = self.env["plasticos.packaging.type"].search([("id", "!=", self.bales.id)], limit=1)
        survivor = self.Profile.create(
            {"partner_id": self.site.id, "polymer_id": self.default_polymer.id, "packaging_type_id": gaylords.id}
        )
        duplicate = self.Profile.create(
            {"partner_id": self.site.id, "polymer_id": self.default_polymer.id, "form_id": self.form_bale.id}
        )
        counts = bales_retirement.retire_bales_form(self.env)
        self.assertEqual(counts.unresolved, 1)
        self.assertEqual(duplicate.form_id, self.form_bale)
        self.assertEqual(survivor.packaging_type_id, gaylords)
