from odoo.tests.common import TransactionCase


class TestDomainIsolation(TransactionCase):
    def test_commission_rule_does_not_expose_transaction_state(self):
        commission_model = self.env["plasticos.commission.rule"]
        methods = [m for m in dir(commission_model) if not m.startswith("_")]
        forbidden = [m for m in methods if "state" in m.lower()]
        self.assertFalse(forbidden, "Commission rule should not expose transaction state.")
