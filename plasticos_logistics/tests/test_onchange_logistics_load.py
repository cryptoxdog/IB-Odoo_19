from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestLoadOnchange(PlasticosTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Load = cls.env["plasticos.load"]
        cls.partner = cls.env["res.partner"].create({"name": "Log Partner"})

    def test_onchange_partner_sets_partner_display(self):
        load = cls.Load.new({"supplier_partner_id": cls.partner.id})
        load._onchange_supplier_partner_id()
        cls.assertTrue(load.partner_display_name)

    def test_onchange_dates_sets_eta(self):
        load = cls.Load.new({})
        load.pickup_date = fields.Date.today()
        load.delivery_date = fields.Date.today()
        load._onchange_dates()
        cls.assertTrue(load.eta_days is None or load.eta_days >= 0)
