"""Lead image counts and material profile transaction stats are one query per recordset."""

import base64
from unittest.mock import patch

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.tests.common import tagged

_PNG_DATAS = base64.b64encode(b"png")


def _counting_search(model_cls, calls):
    real = model_cls.search

    def search(self, *args, **kwargs):
        calls.append(args[0] if args else kwargs.get("domain"))
        return real(self, *args, **kwargs)

    return patch.object(model_cls, "search", search)


@tagged("post_install", "-at_install", "crm_bridge")
class TestBridgeCountsBatch(PlasticosTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.parent = cls.env["res.partner"].create({"name": "Bridge Count Parent", "is_company": True})
        cls.supplier = cls.env["res.partner"].create(
            {"name": "Bridge Count Plant", "is_company": True, "parent_id": cls.parent.id, "supplier_rank": 1}
        )
        cls.polymer = cls.env.ref("plasticos_material_profile.polymer_pp")
        cls.other_polymer = cls.env.ref("plasticos_material_profile.polymer_hdpe")
        cls.form = cls.env.ref("plasticos_material_profile.form_bale")
        profile_model = cls.env["plasticos.material.profile"]
        cls.profile = profile_model.create(
            {"partner_id": cls.supplier.id, "polymer_id": cls.polymer.id, "form_id": cls.form.id}
        )
        cls.other_profile = profile_model.create(
            {"partner_id": cls.supplier.id, "polymer_id": cls.other_polymer.id, "form_id": cls.form.id}
        )
        cls.product = cls.env["product.product"].create({"name": "Bridge Count PP", "type": "consu"})
        cls.product.product_tmpl_id.polymer_id = cls.polymer

    def _lead_image_cost(self, leads):
        leads.invalidate_recordset(["commercial_image_count"])
        before = self.env.cr.sql_log_count
        leads.mapped("commercial_image_count")
        return self.env.cr.sql_log_count - before

    def test_commercial_image_count_is_grouped_across_leads(self):
        leads = self.env["crm.lead"].create([{"name": "Bridge Lead A"}, {"name": "Bridge Lead B"}])
        first, second = leads
        self.env["ir.attachment"].create(
            [
                {
                    "name": "a.png",
                    "res_model": "crm.lead",
                    "res_id": first.id,
                    "mimetype": "image/png",
                    "datas": _PNG_DATAS,
                },
                {"name": "a.pdf", "res_model": "crm.lead", "res_id": first.id, "mimetype": "application/pdf"},
                {
                    "name": "o.png",
                    "res_model": "res.partner",
                    "res_id": first.id,
                    "mimetype": "image/png",
                    "datas": _PNG_DATAS,
                },
            ]
        )
        leads.invalidate_recordset(["commercial_image_count"])
        self.assertEqual(leads.mapped("commercial_image_count"), [1, 0])
        fresh = self.env["crm.lead"].new({})
        self.assertEqual((fresh | leads).mapped("commercial_image_count"), [0, 1, 0])
        one_cost = self._lead_image_cost(first)
        two_cost = self._lead_image_cost(leads)
        self.assertGreaterEqual(one_cost, 1)
        self.assertLess(two_cost, one_cost * 2)

    def test_tx_stats_run_one_transaction_search_for_the_recordset(self):
        transaction_model = self.env["plasticos.transaction"]
        tx = transaction_model.create(
            {"name": "TX-BRIDGE-COUNT-1", "supplier_id": self.supplier.id, "product_id": self.product.id}
        )
        tx._compute_profile_refs()
        self.assertEqual(tx.supplier_profile_id, self.profile)
        pair = self.profile | self.other_profile
        calls = []
        with _counting_search(type(transaction_model), calls):
            pair._compute_tx_stats()
        self.assertEqual(pair.mapped("transaction_count"), [1, 0])
        self.assertEqual(len(calls), 1, calls)
        fresh = self.env["plasticos.material.profile"].new({})
        fresh._compute_tx_stats()
        self.assertEqual(fresh.transaction_count, 0)
