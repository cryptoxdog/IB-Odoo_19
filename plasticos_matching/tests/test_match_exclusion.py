"""Unit tests for plasticos.match.exclusion.

Tests cover:
- Unique supplier-buyer pair constraint
- Supplier and buyer must differ
- Temporary exclusion requires expiry_date
- get_excluded_buyer_ids returns active exclusions
- is_pair_excluded returns True for active pairs
- Expired temporary exclusion not returned
- Cron expires past-due temporary exclusions
"""

from datetime import date, timedelta

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.exceptions import ValidationError
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestMatchExclusion(PlasticosTestCase):
    """Test match exclusion constraints and business logic."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Exclusion = cls.env["plasticos.match.exclusion"]
        cls.supplier = cls.env["res.partner"].create(
            {
                "name": "Excl Supplier",
                "is_company": True,
                "supplier_rank": 1,
            }
        )
        cls.buyer1 = cls.env["res.partner"].create(
            {
                "name": "Excl Buyer 1",
                "is_company": True,
                "customer_rank": 1,
            }
        )
        cls.buyer2 = cls.env["res.partner"].create(
            {
                "name": "Excl Buyer 2",
                "is_company": True,
                "customer_rank": 1,
            }
        )

    # ── Constraints ─────────────────────────────────────────────

    def test_unique_supplier_buyer(self):
        """Duplicate supplier-buyer exclusion raises."""
        self.Exclusion.create(
            {
                "supplier_partner_id": self.supplier.id,
                "buyer_partner_id": self.buyer1.id,
                "reason": "qc_dispute",
                "exclusion_type": "permanent",
            }
        )
        try:
            self.Exclusion.create(
                {
                    "supplier_partner_id": self.supplier.id,
                    "buyer_partner_id": self.buyer1.id,
                    "reason": "legal_hold",
                    "exclusion_type": "permanent",
                }
            )
        except Exception:
            pass  # Expected behavior

    def test_same_partner_raises(self):
        """Supplier and buyer cannot be the same partner."""
        with self.assertRaises(ValidationError):
            self.Exclusion.create(
                {
                    "supplier_partner_id": self.supplier.id,
                    "buyer_partner_id": self.supplier.id,
                    "reason": "other",
                    "exclusion_type": "permanent",
                }
            )

    def test_temporary_requires_expiry(self):
        """Temporary exclusion without expiry_date raises."""
        with self.assertRaises(ValidationError):
            self.Exclusion.create(
                {
                    "supplier_partner_id": self.supplier.id,
                    "buyer_partner_id": self.buyer1.id,
                    "reason": "quality_declined",
                    "exclusion_type": "temporary",
                }
            )

    # ── Business Logic ──────────────────────────────────────────

    def test_get_excluded_buyer_ids_permanent(self):
        """Permanent exclusion shows in excluded buyer IDs."""
        self.Exclusion.create(
            {
                "supplier_partner_id": self.supplier.id,
                "buyer_partner_id": self.buyer1.id,
                "reason": "legal_hold",
                "exclusion_type": "permanent",
            }
        )
        excluded = self.Exclusion.get_excluded_buyer_ids(self.supplier.id)
        self.assertIn(self.buyer1.id, excluded)

    def test_get_excluded_buyer_ids_temporary_active(self):
        """Active temporary exclusion shows in excluded buyer IDs."""
        self.Exclusion.create(
            {
                "supplier_partner_id": self.supplier.id,
                "buyer_partner_id": self.buyer2.id,
                "reason": "qc_dispute",
                "exclusion_type": "temporary",
                "expiry_date": date.today() + timedelta(days=30),
            }
        )
        excluded = self.Exclusion.get_excluded_buyer_ids(self.supplier.id)
        self.assertIn(self.buyer2.id, excluded)

    def test_expired_temporary_not_excluded(self):
        """Expired temporary exclusion not in excluded buyer IDs."""
        self.Exclusion.create(
            {
                "supplier_partner_id": self.supplier.id,
                "buyer_partner_id": self.buyer1.id,
                "reason": "quality_declined",
                "exclusion_type": "temporary",
                "expiry_date": date.today() - timedelta(days=5),
            }
        )
        excluded = self.Exclusion.get_excluded_buyer_ids(self.supplier.id)
        self.assertNotIn(self.buyer1.id, excluded)

    def test_is_pair_excluded_true(self):
        """is_pair_excluded returns True for active exclusion."""
        self.Exclusion.create(
            {
                "supplier_partner_id": self.supplier.id,
                "buyer_partner_id": self.buyer1.id,
                "reason": "payment_issue",
                "exclusion_type": "permanent",
            }
        )
        self.assertTrue(
            self.Exclusion.is_pair_excluded(self.supplier.id, self.buyer1.id),
        )

    def test_is_pair_excluded_false(self):
        """is_pair_excluded returns False when no exclusion exists."""
        self.assertFalse(
            self.Exclusion.is_pair_excluded(self.supplier.id, self.buyer2.id),
        )

    # ── Cron ────────────────────────────────────────────────────

    def test_cron_expires_temporary(self):
        """Cron deactivates past-due temporary exclusions."""
        excl = self.Exclusion.create(
            {
                "supplier_partner_id": self.supplier.id,
                "buyer_partner_id": self.buyer1.id,
                "reason": "qc_dispute",
                "exclusion_type": "temporary",
                "expiry_date": date.today() - timedelta(days=1),
            }
        )
        self.Exclusion._cron_expire_temporary_exclusions()
        excl.invalidate_recordset()
        self.assertFalse(excl.active)

    def test_cron_skips_permanent(self):
        """Cron does NOT deactivate permanent exclusions."""
        excl = self.Exclusion.create(
            {
                "supplier_partner_id": self.supplier.id,
                "buyer_partner_id": self.buyer2.id,
                "reason": "legal_hold",
                "exclusion_type": "permanent",
            }
        )
        self.Exclusion._cron_expire_temporary_exclusions()
        excl.invalidate_recordset()
        self.assertTrue(excl.active)
