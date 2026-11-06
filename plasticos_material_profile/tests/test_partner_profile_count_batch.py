"""Partner material profile count is one grouped query per recordset."""

import uuid

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.tests import tagged


@tagged("post_install", "-at_install", "plasticos")
class TestPartnerProfileCountBatch(PlasticosTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        suffix = uuid.uuid4().hex[:8].upper()
        cls.first = cls.env["res.partner"].create({"name": f"Profile Count A {suffix}", "is_company": True})
        cls.second = cls.env["res.partner"].create({"name": f"Profile Count B {suffix}", "is_company": True})
        polymer = cls.env["plasticos.polymer"].create({"name": f"Count Polymer {suffix}", "code": f"PCNT-{suffix}"})
        other = cls.env["plasticos.polymer"].create({"name": f"Count Polymer B {suffix}", "code": f"PCNTB-{suffix}"})
        form = cls.env["plasticos.material.form"].create({"name": f"Count Form {suffix}", "code": f"PCNTF-{suffix}"})
        profile_model = cls.env["plasticos.material.profile"]
        profile_model.create(
            [
                {"partner_id": cls.first.id, "polymer_id": polymer.id, "form_id": form.id},
                {"partner_id": cls.first.id, "polymer_id": other.id, "form_id": form.id},
            ]
        )

    def _count_cost(self, partners):
        partners.invalidate_recordset(["material_profile_count"])
        before = self.env.cr.sql_log_count
        partners.mapped("material_profile_count")
        return self.env.cr.sql_log_count - before

    def test_counts_are_grouped_across_partners(self):
        pair = self.first | self.second
        pair.invalidate_recordset(["material_profile_count"])
        self.assertEqual(pair.mapped("material_profile_count"), [2, 0])
        fresh = self.env["res.partner"].new({})
        self.assertEqual((fresh | pair).mapped("material_profile_count"), [0, 2, 0])
        one_cost = self._count_cost(self.first)
        two_cost = self._count_cost(pair)
        self.assertGreaterEqual(one_cost, 1)
        self.assertLess(two_cost, one_cost * 2)
