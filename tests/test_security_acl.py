"""Security and ACL tests for PlastOS modules.

Validates ir.model.access.csv rules, group-based CRUD, protected write()
constraints, and unlink restrictions at ORM level.
"""

from odoo.addons.plasticos_base.tests.common import PlasticosTestCase
from odoo.exceptions import AccessError, UserError
from odoo.tests.common import tagged


@tagged("post_install", "-at_install", "plasticos", "security")
class TestTransactionACL(PlasticosTestCase):
    """ACL enforcement for plasticos.transaction."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        base_grp = cls.env.ref("base.group_user", raise_if_not_found=False)
        mgr_grp = cls.env.ref("plasticos_transaction.group_plasticos_manager", raise_if_not_found=False)
        base_grp_id = base_grp.id if base_grp else False
        mgr_grp_id = mgr_grp.id if mgr_grp else False
        cls.base_user = cls.env["res.users"].create(
            {
                "name": "TX Base User",
                "login": "tx_base_user",
                "groups_id": [(6, 0, [base_grp_id])] if base_grp_id else [],
            }
        )
        cls.manager_user = cls.env["res.users"].create(
            {
                "name": "TX Manager",
                "login": "tx_manager",
                "groups_id": [(6, 0, [g for g in [base_grp_id, mgr_grp_id] if g])],
            }
        )
        cls.supplier = cls.env["res.partner"].create({"name": "ACL Supplier", "is_company": True, "supplier_rank": 1})
        cls.buyer = cls.env["res.partner"].create({"name": "ACL Buyer", "is_company": True, "customer_rank": 1})

    def _create_tx(self, user=None):
        Tx = self.env["plasticos.transaction"].with_user(user or self.env.user)
        return Tx.create({"supplier_id": self.supplier.id, "buyer_id": self.buyer.id})

    def test_base_user_can_read(self):
        tx = self._create_tx()
        tx.with_user(self.base_user).read(["name", "state"])

    def test_base_user_can_create(self):
        tx = self._create_tx(user=self.base_user)
        self.assertTrue(tx.id)

    def test_base_user_cannot_unlink(self):
        tx = self._create_tx()
        with self.assertRaises(AccessError):
            tx.with_user(self.base_user).unlink()

    def test_base_user_cannot_write_tx_line(self):
        tx = self._create_tx()
        line = self.env["plasticos.transaction.line"].sudo().create({"transaction_id": tx.id})
        with self.assertRaises(AccessError):
            line.with_user(self.base_user).write({"sale_amount": 999.0})

    def test_manager_can_write_tx_line(self):
        tx = self._create_tx()
        line = self.env["plasticos.transaction.line"].sudo().create({"transaction_id": tx.id})
        line.with_user(self.manager_user).write({"sale_amount": 500.0})
        self.assertEqual(line.sale_amount, 500.0)

    def test_commission_rule_admin_only(self):
        Rule = self.env["plasticos.commission.rule"].with_user(self.base_user)
        with self.assertRaises(AccessError):
            Rule.create({"name": "Hacker Rule", "rate_pct": 50})

    def test_closed_tx_immutable_fields(self):
        tx = self._create_tx()
        tx.action_activate()
        tx.sudo().write({"state": "closed", "commission_locked": True})
        with self.assertRaises(UserError):
            tx.write({"sale_order_id": False})

    def test_name_immutable(self):
        tx = self._create_tx()
        with self.assertRaises(UserError):
            tx.write({"name": "HACKED"})

    def test_locked_commission_immutable(self):
        tx = self._create_tx()
        tx.action_activate()
        tx.sudo().write({"commission_locked": True})
        with self.assertRaises(UserError):
            tx.write({"commission_rule_id": False})


@tagged("post_install", "-at_install", "plasticos", "security")
class TestClaimACL(PlasticosTestCase):
    """ACL enforcement for plasticos.claim."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        base_grp = cls.env.ref("base.group_user", raise_if_not_found=False)
        claim_user_grp = cls.env.ref("plasticos_claims.group_claims_user", raise_if_not_found=False)
        claim_mgr_grp = cls.env.ref("plasticos_claims.group_claims_manager", raise_if_not_found=False)
        base_grp_id = base_grp.id if base_grp else False
        claim_user_grp_id = claim_user_grp.id if claim_user_grp else False
        claim_mgr_grp_id = claim_mgr_grp.id if claim_mgr_grp else False
        cls.claim_user = cls.env["res.users"].create(
            {
                "name": "Claim User",
                "login": "claim_u",
                "groups_id": [(6, 0, [g for g in [base_grp_id, claim_user_grp_id] if g])],
            }
        )
        cls.no_claim_user = cls.env["res.users"].create(
            {
                "name": "No Claim",
                "login": "no_claim",
                "groups_id": [(6, 0, [base_grp_id])] if base_grp_id else [],
            }
        )
        cls.claim_mgr = cls.env["res.users"].create(
            {
                "name": "Claim Mgr",
                "login": "claim_m",
                "groups_id": [(6, 0, [g for g in [base_grp_id, claim_mgr_grp_id] if g])],
            }
        )
        cls.tx = cls.env["plasticos.transaction"].create(
            {
                "supplier_id": cls.env["res.partner"].create({"name": "CS", "is_company": True, "supplier_rank": 1}).id,
            }
        )

    def _claim(self, user=None):
        C = self.env["plasticos.claim"].with_user(user or self.env.user)
        return C.create({"transaction_id": self.tx.id, "case_type": "quality", "summary": "T"})

    def test_claim_user_can_create(self):
        self.assertTrue(self._claim(self.claim_user).id)

    def test_claim_user_cannot_unlink(self):
        c = self._claim()
        with self.assertRaises(AccessError):
            c.with_user(self.claim_user).unlink()

    def test_claim_manager_can_unlink(self):
        c = self._claim()
        c.with_user(self.claim_mgr).unlink()

    def test_no_group_cannot_read(self):
        c = self._claim()
        with self.assertRaises(AccessError):
            c.with_user(self.no_claim_user).read(["name"])


@tagged("post_install", "-at_install", "plasticos", "security")
class TestBillExclusivity(PlasticosTestCase):
    """Vendor/freight bill exclusivity guards."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.supplier = cls.env["res.partner"].create({"name": "BS", "is_company": True, "supplier_rank": 1})
        cls.journal = cls.env["account.journal"].search([("type", "=", "purchase")], limit=1)

    def _tx(self):
        return self.env["plasticos.transaction"].create({"supplier_id": self.supplier.id})

    def _bill(self):
        if not self.journal:
            self.skipTest("No purchase journal")
        return self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": self.supplier.id,
                "journal_id": self.journal.id,
            }
        )

    def test_vendor_bill_exclusivity(self):
        tx1, tx2, bill = self._tx(), self._tx(), self._bill()
        tx1.write({"vendor_bill_ids": [(4, bill.id)]})
        with self.assertRaises(UserError):
            tx2.write({"vendor_bill_ids": [(4, bill.id)]})

    def test_freight_bill_exclusivity(self):
        tx1, tx2, bill = self._tx(), self._tx(), self._bill()
        tx1.write({"freight_bill_ids": [(4, bill.id)]})
        with self.assertRaises(UserError):
            tx2.write({"freight_bill_ids": [(4, bill.id)]})
