"""CRM role-tag adoption before seed records. Native name uniqueness is measured."""

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestCrmTagAdoption(TransactionCase):
    def _data(self, xml_name):
        return self.env["ir.model.data"].search([("module", "=", "plasticos_crm_bridge"), ("name", "=", xml_name)])

    def test_preexisting_tag_without_xmlid_is_adopted_once(self):
        tag = self.env["crm.tag"].create({"name": "Yard Buyer"})
        self.assertFalse(self._data("crm_tag_yard_buyer"))
        self.assertTrue(
            self.env["crm.lead"]._plasticos_adopt_crm_role_tag("Yard Buyer", "plasticos_crm_bridge.crm_tag_yard_buyer")
        )
        data = self._data("crm_tag_yard_buyer")
        self.assertEqual(data.res_id, tag.id)
        self.assertEqual(data.model, "crm.tag")
        self.assertTrue(
            self.env["crm.lead"]._plasticos_adopt_crm_role_tag("Yard Buyer", "plasticos_crm_bridge.crm_tag_yard_buyer")
        )
        self.assertEqual(self.env["crm.tag"].search_count([("name", "=", "Yard Buyer")]), 1)
        self.assertEqual(self._data("crm_tag_yard_buyer").res_id, tag.id)

    def test_fresh_name_creates_one_tag(self):
        self.assertFalse(self.env["crm.tag"].search([("name", "=", "Scale House")]))
        self.assertTrue(
            self.env["crm.lead"]._plasticos_adopt_crm_role_tag("Scale House", "plasticos_crm_bridge.crm_tag_scale")
        )
        tags = self.env["crm.tag"].search([("name", "=", "Scale House")])
        self.assertEqual(len(tags), 1)
        self.assertEqual(self._data("crm_tag_scale").res_id, tags.id)
        self.assertTrue(
            self.env["crm.lead"]._plasticos_adopt_crm_role_tag("Scale House", "plasticos_crm_bridge.crm_tag_scale")
        )
        self.assertEqual(self.env["crm.tag"].search_count([("name", "=", "Scale House")]), 1)

    def test_stale_xmlid_is_not_rebound(self):
        tag = self.env["crm.tag"].create({"name": "Stale Role"})
        data = self.env["ir.model.data"].create(
            {
                "module": "plasticos_crm_bridge",
                "name": "crm_tag_stale",
                "model": "crm.tag",
                "res_id": tag.id,
                "noupdate": True,
            }
        )
        self.env.cr.execute("UPDATE ir_model_data SET res_id = 0 WHERE id = %s", [data.id])
        data.invalidate_recordset()
        self.assertFalse(
            self.env["crm.lead"]._plasticos_adopt_crm_role_tag("Stale Role", "plasticos_crm_bridge.crm_tag_stale")
        )
        data.invalidate_recordset()
        self.assertEqual(data.res_id, 0)
        self.assertEqual(self.env["crm.tag"].search_count([("name", "=", "Stale Role")]), 1)

    def test_wrong_model_xmlid_is_not_rebound(self):
        partner = self.env["res.partner"].create({"name": "Not A Tag", "is_company": True})
        data = self.env["ir.model.data"].create(
            {
                "module": "plasticos_crm_bridge",
                "name": "crm_tag_wrong_model",
                "model": "res.partner",
                "res_id": partner.id,
                "noupdate": True,
            }
        )
        self.assertFalse(
            self.env["crm.lead"]._plasticos_adopt_crm_role_tag("Not A Tag", "plasticos_crm_bridge.crm_tag_wrong_model")
        )
        self.assertEqual(data.model, "res.partner")
        self.assertEqual(data.res_id, partner.id)
        self.assertFalse(self.env["crm.tag"].search([("name", "=", "Not A Tag")]))

    def test_native_name_constraint_rejects_a_second_buyer(self):
        self.env.ref("plasticos_crm_bridge.crm_tag_buyer")
        with self.assertRaises(Exception), self.env.cr.savepoint():
            self.env["crm.tag"].create({"name": "Buyer"})
        self.assertEqual(self.env["crm.tag"].search_count([("name", "=", "Buyer")]), 1)
