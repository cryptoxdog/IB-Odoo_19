"""Purchase-order visibility is least privilege: a sales representative sees the orders they own.

Runs under ``odoo --test-enable --test-tags /plasticos_security_base``.
"""

from __future__ import annotations

from odoo import Command
from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestPurchaseOrderAccess(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        rep_group = cls.env.ref("plasticos_security_base.group_sales_rep")
        accounting_group = cls.env.ref("plasticos_security_base.group_accounting")
        all_leads_group = cls.env.ref("sales_team.group_sale_salesman_all_leads")
        Users = cls.env["res.users"].with_context(no_reset_password=True)
        cls.rep_a = Users.create(
            {"name": "Rep A", "login": "po_access_rep_a", "group_ids": [Command.set([rep_group.id])]}
        )
        cls.rep_b = Users.create(
            {"name": "Rep B", "login": "po_access_rep_b", "group_ids": [Command.set([rep_group.id])]}
        )
        cls.rep_all_leads = Users.create(
            {
                "name": "Rep All Leads",
                "login": "po_access_rep_all",
                "group_ids": [Command.set([rep_group.id, all_leads_group.id])],
            }
        )
        cls.accountant = Users.create(
            {"name": "Accountant", "login": "po_access_accounting", "group_ids": [Command.set([accounting_group.id])]}
        )
        vendor = cls.env["res.partner"].create({"name": "PO access vendor", "is_company": True, "supplier_rank": 1})
        cls.po_a = cls.env["purchase.order"].create({"partner_id": vendor.id, "user_id": cls.rep_a.id})
        cls.po_b = cls.env["purchase.order"].create({"partner_id": vendor.id, "user_id": cls.rep_b.id})
        cls.po_unowned = cls.env["purchase.order"].create({"partner_id": vendor.id, "user_id": False})

    def _visible(self, user):
        return (
            self.env["purchase.order"]
            .with_user(user)
            .search([("id", "in", (self.po_a | self.po_b | self.po_unowned).ids)])
        )

    def test_all_documents_rule_is_gone(self):
        self.assertFalse(
            self.env.ref("plasticos_security_base.rule_purchase_order_all_documents", raise_if_not_found=False)
        )
        po_model = self.env["ir.model"]._get("purchase.order")
        open_rules = self.env["ir.rule"].search([("model_id", "=", po_model.id), ("domain_force", "like", "(1,")])
        self.assertFalse(open_rules, open_rules.mapped("name"))

    def test_sales_rep_sees_own_purchase_orders_only(self):
        self.assertEqual(self._visible(self.rep_a), self.po_a)
        self.assertEqual(self._visible(self.rep_b), self.po_b)
        with self.assertRaises(AccessError):
            self.po_b.with_user(self.rep_a).read(["name"])
        with self.assertRaises(AccessError):
            self.po_a.with_user(self.rep_b).write({"origin": "touched"})

    def test_all_leads_group_does_not_widen_purchase_order_access(self):
        self.assertFalse(self._visible(self.rep_all_leads))
        with self.assertRaises(AccessError):
            self.po_b.with_user(self.rep_all_leads).read(["name"])
        with self.assertRaises(AccessError):
            self.po_unowned.with_user(self.rep_all_leads).unlink()

    def test_accounting_reads_every_purchase_order_without_write(self):
        self.assertEqual(self._visible(self.accountant), self.po_a | self.po_b | self.po_unowned)
        with self.assertRaises(AccessError):
            self.po_a.with_user(self.accountant).write({"origin": "touched"})
