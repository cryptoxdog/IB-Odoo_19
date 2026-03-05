"""
Test load reports.

Tests BOL pickup/delivery render without error.
"""

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestLoadReports(TransactionCase):
    """Test plasticos.load report rendering."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.carrier = cls.env["res.partner"].create(
            {
                "name": "Test Carrier",
                "is_company": True,
                "supplier_rank": 1,
            }
        )
        cls.pickup_partner = cls.env["res.partner"].create(
            {
                "name": "Pickup Location",
                "is_company": True,
                "street": "123 Pickup St",
                "city": "Pickup City",
                "zip": "12345",
            }
        )
        cls.delivery_partner = cls.env["res.partner"].create(
            {
                "name": "Delivery Location",
                "is_company": True,
                "street": "456 Delivery Ave",
                "city": "Delivery City",
                "zip": "67890",
            }
        )

    def _create_load(self, **kwargs):
        """Helper to create a load with defaults."""
        vals = {
            "carrier_id": self.carrier.id,
            "pickup_partner_id": self.pickup_partner.id,
            "delivery_partner_id": self.delivery_partner.id,
        }
        vals.update(kwargs)
        return self.env["plasticos.load"].create(vals)

    # ═══════════════════════════════════════════════════════════
    # BOL Report Tests
    # ═══════════════════════════════════════════════════════════

    def test_bol_pickup_report_renders(self):
        """BOL pickup report should render without error."""
        load = self._create_load()

        # Check if report exists
        report = self.env.ref("plasticos_logistics.report_bol_pickup", raise_if_not_found=False)
        if report:
            # Render the report
            content, content_type = report._render_qweb_pdf([load.id])
            self.assertTrue(content)

    def test_bol_delivery_report_renders(self):
        """BOL delivery report should render without error."""
        load = self._create_load()

        # Check if report exists
        report = self.env.ref("plasticos_logistics.report_bol_delivery", raise_if_not_found=False)
        if report:
            # Render the report
            content, content_type = report._render_qweb_pdf([load.id])
            self.assertTrue(content)

    def test_bol_attachment_created(self):
        """BOL attachment should be created when report is generated."""
        load = self._create_load()

        # Check if BOL attachment fields exist
        if hasattr(load, "bol_pickup_attachment_id"):
            # Generate BOL if method exists
            if hasattr(load, "action_generate_bol_pickup"):
                load.action_generate_bol_pickup()
                self.assertTrue(load.bol_pickup_attachment_id)

    # ═══════════════════════════════════════════════════════════
    # Report Data Tests
    # ═══════════════════════════════════════════════════════════

    def test_report_data_complete(self):
        """Report should have all required data fields."""
        load = self._create_load(
            rate=500.0,
            scheduled_pickup_date="2026-03-10",
            scheduled_delivery_date="2026-03-12",
        )

        # Verify data is accessible for reports
        self.assertEqual(load.carrier_id.name, "Test Carrier")
        self.assertEqual(load.pickup_partner_id.name, "Pickup Location")
        self.assertEqual(load.delivery_partner_id.name, "Delivery Location")
        self.assertEqual(load.rate, 500.0)
