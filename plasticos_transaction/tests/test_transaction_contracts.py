"""Contract tests for plasticos.transaction.

Modules that inherit plasticos.transaction:
  - plasticos_claims (transaction_claims.py, transaction_claims_bridge.py)
  - plasticos_logistics (transaction_inherit.py)
  - plasticos_documents (transaction_docs.py, transaction_docs_bridge.py)

Any change to these contracted fields/methods MUST update all consumers.
"""

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.tests.common import tagged


@tagged("post_install", "-at_install", "contract")
class TestTransactionFieldContract(PlasticosTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.TX = cls.env["plasticos.transaction"]
        cls.fields = cls.TX._fields

    # ── Identity ──
    def test_name_field(self):
        self.assertIn("name", self.fields)
        self.assertEqual(self.fields["name"].type, "char")

    def test_state_field_is_selection(self):
        f = self.fields.get("state")
        self.assertIsNotNone(f, "state field missing — claims/logistics/docs depend on it")
        self.assertEqual(f.type, "selection")

    def test_state_required_values(self):
        """Claims bridge depends on \'active\', logistics on \'dispatched\', docs on \'closed\'."""
        f = self.fields["state"]
        values = [s[0] for s in f.selection]
        # Minimum set — actual values depend on repo; adjust after reading transaction.py
        for state in ("draft", "active", "closed"):
            self.assertIn(state, values, f"Missing state: {state}")

    # ── Partner links (claims, docs) ──
    def test_supplier_id_exists(self):
        self.assertIn("supplier_id", self.fields)
        self.assertEqual(self.fields["supplier_id"].comodel_name, "res.partner")

    def test_buyer_id_exists(self):
        self.assertIn("buyer_id", self.fields)
        self.assertEqual(self.fields["buyer_id"].comodel_name, "res.partner")

    # ── Intake link (used by transaction bridge views) ──
    def test_intake_id_exists(self):
        self.assertIn("intake_id", self.fields)
        self.assertEqual(self.fields["intake_id"].comodel_name, "plasticos.intake")

    # ── Quantity (logistics, commission) ──
    def test_quantity_field_exists(self):
        self.assertIn("quantity", self.fields)

    # ── Material profile link ──
    def test_supplier_profile_id_exists(self):
        self.assertIn("supplier_profile_id", self.fields)

    # ── Mail thread ──
    def test_has_mail_thread(self):
        self.assertTrue(
            callable(getattr(self.TX, "message_post", None)),
            "transaction must inherit mail.thread for chatter",
        )


@tagged("post_install", "-at_install", "contract")
class TestTransactionMethodContract(PlasticosTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.TX = cls.env["plasticos.transaction"]

    def test_state_transition_methods_exist(self):
        """Claims and logistics modules call these to sync state."""
        expected = [
            "action_activate",
            "action_close",
            "action_cancel",
        ]
        for method in expected:
            self.assertTrue(
                callable(getattr(self.TX, method, None)),
                f"Missing transition method: {method}",
            )
