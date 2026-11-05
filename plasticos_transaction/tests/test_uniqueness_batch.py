"""Uniqueness preflight searches stay one query and keep their error messages."""

from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import tagged


def _plasticos_test_case():
    from odoo.addons.plasticos_base.test_common import PlasticosTestCase

    return PlasticosTestCase


@tagged("post_install", "-at_install")
class TestUniquenessBatch(_plasticos_test_case()):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        journal = cls.env["account.journal"].search(
            [("type", "=", "purchase"), ("company_id", "=", cls.env.company.id)],
            limit=1,
        )
        if not journal:
            journal = cls.env["account.journal"].create(
                {
                    "name": "Uniqueness Purchase",
                    "type": "purchase",
                    "code": "UNIQ",
                    "company_id": cls.env.company.id,
                }
            )
        cls.purchase_journal = journal

    def _absent_name(self, label):
        transaction = self.env["plasticos.transaction"]
        for index in range(1, 50):
            name = f"TX-UNIQ-{label}-{index}"
            if not transaction.search_count([("name", "=", name)]):
                return name
        self.fail(f"no absent transaction name for {label}")

    def _vendor_bill(self, label):
        return self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": self.default_partner.id,
                "journal_id": self.purchase_journal.id,
                "invoice_date": "2026-11-05",
                "invoice_line_ids": [(0, 0, {"name": label, "quantity": 1, "price_unit": 10.0})],
            }
        )

    def test_batch_create_rejects_an_existing_name_before_insert(self):
        existing = self._absent_name("existing")
        fresh = self._absent_name("fresh")
        self.env["plasticos.transaction"].create({"name": existing})
        with self.assertRaises(ValidationError) as caught:
            self.env["plasticos.transaction"].create([{"name": fresh}, {"name": existing}])
        self.assertIn("already exists", str(caught.exception))
        transaction = self.env["plasticos.transaction"]
        self.assertEqual(transaction.search_count([("name", "=", fresh)]), 0)
        self.assertEqual(transaction.search_count([("name", "=", existing)]), 1)

    def test_multi_record_write_of_a_held_name_raises(self):
        held = self._absent_name("held")
        other = self._absent_name("other")
        first = self.env["plasticos.transaction"].create({"name": held})
        second = self.env["plasticos.transaction"].create({"name": other})
        with self.assertRaises(ValidationError) as caught:
            (first | second).write({"name": held})
        self.assertIn("already exists", str(caught.exception))

    def test_write_of_a_free_name_is_immutable(self):
        current = self._absent_name("current")
        free = self._absent_name("free")
        record = self.env["plasticos.transaction"].create({"name": current})
        with self.assertRaises(UserError) as caught:
            record.write({"name": free})
        self.assertIn("cannot be modified", str(caught.exception))

    def test_command_4_rejects_a_bill_linked_elsewhere(self):
        bill = self._vendor_bill("linked")
        self.env["plasticos.transaction"].create(
            {"name": self._absent_name("owner4"), "vendor_bill_ids": [(6, 0, [bill.id])]}
        )
        other = self.env["plasticos.transaction"].create({"name": self._absent_name("other4")})
        with self.assertRaises(UserError) as caught:
            other.write({"vendor_bill_ids": [(4, bill.id)]})
        self.assertIn("already linked", str(caught.exception))

    def test_command_6_rejects_a_taken_bill_and_accepts_free_bills(self):
        taken = self._vendor_bill("taken")
        free_a = self._vendor_bill("free-a")
        free_b = self._vendor_bill("free-b")
        self.env["plasticos.transaction"].create(
            {"name": self._absent_name("owner6"), "vendor_bill_ids": [(4, taken.id)]}
        )
        candidate = self.env["plasticos.transaction"].create({"name": self._absent_name("candidate6")})
        with self.assertRaises(UserError) as caught:
            candidate.write({"vendor_bill_ids": [(6, 0, [free_a.id, taken.id])]})
        self.assertIn("already linked", str(caught.exception))
        candidate.write({"vendor_bill_ids": [(6, 0, [free_a.id, free_b.id])]})
        self.assertEqual(set(candidate.vendor_bill_ids.ids), {free_a.id, free_b.id})

    def test_relink_on_the_same_transaction_does_not_raise(self):
        bill = self._vendor_bill("same")
        record = self.env["plasticos.transaction"].create(
            {"name": self._absent_name("same"), "vendor_bill_ids": [(6, 0, [bill.id])]}
        )
        record.write({"vendor_bill_ids": [(4, bill.id)]})
        self.assertEqual(record.vendor_bill_ids, bill)
