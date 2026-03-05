"""Constraint and onchange coverage tests for PlastOS modules.

Covers @api.constrains validators (positive, negative, boundary),
SQL constraints, @api.onchange auto-population, and computed field edge cases.
"""

from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "plasticos", "constraint")
class TestTransactionConstraintsConsolidated(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.supplier = cls.env["res.partner"].create({"name": "CS", "is_company": True, "supplier_rank": 1})
        cls.buyer = cls.env["res.partner"].create({"name": "CB", "is_company": True, "customer_rank": 1})

    def _tx(self, **kw):
        v = {"supplier_id": self.supplier.id, "buyer_id": self.buyer.id}
        v.update(kw)
        return self.env["plasticos.transaction"].create(v)

    def test_commission_override_valid_50(self):
        tx = self._tx()
        tx.write({"commission_override_pct": 50.0})
        self.assertEqual(tx.commission_override_pct, 50.0)

    def test_commission_override_boundary_0(self):
        tx = self._tx()
        tx.write({"commission_override_pct": 0.0})

    def test_commission_override_boundary_100(self):
        tx = self._tx()
        tx.write({"commission_override_pct": 100.0})

    def test_commission_override_negative_rejected(self):
        tx = self._tx()
        with self.assertRaises(ValidationError):
            tx.write({"commission_override_pct": -5.0})

    def test_commission_override_over_100_rejected(self):
        tx = self._tx()
        with self.assertRaises(ValidationError):
            tx.write({"commission_override_pct": 150.0})

    def test_unlink_with_invoice_blocked(self):
        tx = self._tx()
        journal = self.env["account.journal"].search([("type", "=", "sale")], limit=1)
        if journal:
            inv = self.env["account.move"].create(
                {
                    "move_type": "out_invoice",
                    "partner_id": self.buyer.id,
                    "journal_id": journal.id,
                }
            )
            tx.sudo().write({"customer_invoice_id": inv.id})
            with self.assertRaises(UserError):
                tx.unlink()

    def test_unlink_closed_blocked(self):
        tx = self._tx()
        tx.action_activate()
        tx.sudo().write({"state": "closed", "commission_locked": True})
        with self.assertRaises(UserError):
            tx.unlink()


@tagged("post_install", "-at_install", "plasticos", "constraint")
class TestIntakeConstraintsConsolidated(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({"name": "IP", "is_company": True, "supplier_rank": 1})

    def _intake(self, **kw):
        v = {"partner_id": self.partner.id, "quantity_per_load_lbs": 40000}
        v.update(kw)
        return self.env["plasticos.intake"].create(v)

    def test_quantity_zero_rejected(self):
        with self.assertRaises(ValidationError):
            self._intake(quantity_per_load_lbs=0)

    def test_quantity_negative_rejected(self):
        with self.assertRaises(ValidationError):
            self._intake(quantity_per_load_lbs=-100)

    def test_quantity_valid(self):
        self.assertEqual(self._intake(quantity_per_load_lbs=25000).quantity_per_load_lbs, 25000)

    def test_loads_per_month_negative_rejected(self):
        with self.assertRaises(ValidationError):
            self._intake(loads_per_month=-1)

    def test_loads_per_month_zero_valid(self):
        self.assertEqual(self._intake(loads_per_month=0).loads_per_month, 0)


@tagged("post_install", "-at_install", "plasticos", "onchange")
class TestIntakeOnchangesConsolidated(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env["res.partner"].create(
            {
                "name": "OC",
                "is_company": True,
                "supplier_rank": 1,
                "phone": "555-0001",
            }
        )
        cls.contact = cls.env["res.partner"].create({"name": "John", "is_company": False, "parent_id": cls.company.id})

    def test_onchange_partner_does_not_crash(self):
        intake = self.env["plasticos.intake"].new({"partner_id": self.company.id, "contact_id": self.contact.id})
        new_p = self.env["res.partner"].create({"name": "NP", "is_company": True, "supplier_rank": 1})
        intake.partner_id = new_p
        if hasattr(intake, "_onchange_partner_id"):
            intake._onchange_partner_id()

    def test_onchange_contact_does_not_crash(self):
        intake = self.env["plasticos.intake"].new({"partner_id": self.company.id})
        intake.contact_id = self.contact
        if hasattr(intake, "_onchange_contact_id"):
            intake._onchange_contact_id()


@tagged("post_install", "-at_install", "plasticos", "constraint")
class TestClaimConstraintsConsolidated(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tx = cls.env["plasticos.transaction"].create(
            {
                "supplier_id": cls.env["res.partner"].create({"name": "CC", "is_company": True, "supplier_rank": 1}).id,
            }
        )

    def _claim(self, **kw):
        v = {"transaction_id": self.tx.id, "case_type": "quality", "summary": "T"}
        v.update(kw)
        return self.env["plasticos.claim"].create(v)

    def test_resolved_without_note_raises(self):
        c = self._claim()
        c.action_start()
        with self.assertRaises(ValidationError):
            c.write({"state": "resolved", "resolution_note": False})

    def test_resolved_with_note_ok(self):
        c = self._claim()
        c.action_start()
        c.write({"state": "resolved", "resolution_note": "Fixed."})
        self.assertEqual(c.state, "resolved")


@tagged("post_install", "-at_install", "plasticos", "compute")
class TestTransactionComputesConsolidated(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.supplier = cls.env["res.partner"].create({"name": "TC", "is_company": True, "supplier_rank": 1})

    def _tx(self, **kw):
        v = {"supplier_id": self.supplier.id}
        v.update(kw)
        return self.env["plasticos.transaction"].create(v)

    def test_weight_variance_zero_no_crash(self):
        tx = self._tx(expected_weight=0, actual_weight=0)
        self.assertFalse(tx.weight_variance_percent)

    def test_weight_source_scale_priority(self):
        tx = self._tx(scale_weight=1000, buyer_weight=900, supplier_weight=800)
        self.assertEqual(tx.weight_source, "scale")

    def test_weight_source_buyer_fallback(self):
        tx = self._tx(scale_weight=0, buyer_weight=900, supplier_weight=800)
        self.assertEqual(tx.weight_source, "buyer")

    def test_weight_source_supplier_fallback(self):
        tx = self._tx(scale_weight=0, buyer_weight=0, supplier_weight=800)
        self.assertEqual(tx.weight_source, "supplier")

    def test_weight_source_none(self):
        tx = self._tx(scale_weight=0, buyer_weight=0, supplier_weight=0)
        self.assertEqual(tx.weight_source, "none")

    def test_tare_auto_set_by_unit_type(self):
        tx = self._tx(unit_type="bale")
        self.assertTrue(tx.tare_per_unit > 0)

    def test_total_tare_calculation(self):
        tx = self._tx(unit_type="gaylord", unit_count=10)
        self.assertAlmostEqual(tx.total_tare, 10 * tx.tare_per_unit, places=2)

    def test_final_weight_net_of_tare(self):
        tx = self._tx(scale_weight=10000, unit_type="bale", unit_count=5)
        self.assertAlmostEqual(tx.final_weight, tx.gross_weight - tx.total_tare, places=2)

    def test_discrepancy_flags_above_5pct(self):
        tx = self._tx(supplier_weight=10000, buyer_weight=8000)
        self.assertTrue(tx.weight_discrepancy_flagged)

    def test_discrepancy_within_threshold(self):
        tx = self._tx(supplier_weight=10000, buyer_weight=9800)
        self.assertFalse(tx.weight_discrepancy_flagged)

    def test_light_weight_deduction_below_min(self):
        tx = self._tx(scale_weight=35000, minimum_net_weight=40000, light_weight_deduction_rate=0.01, unit_count=0)
        if tx.final_weight < tx.minimum_net_weight:
            self.assertTrue(tx.light_weight_deduction > 0)

    def test_light_weight_deduction_above_min(self):
        tx = self._tx(scale_weight=45000, minimum_net_weight=40000, light_weight_deduction_rate=0.01, unit_count=0)
        self.assertEqual(tx.light_weight_deduction, 0)
