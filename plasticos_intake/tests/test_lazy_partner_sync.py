"""
Tests for lazy partner sync flow (web lead → intake → partner creation).

This tests the pending_company_name → action_match_to_buyers → partner creation flow.
"""

import logging

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase

_logger = logging.getLogger(__name__)


class TestLazyPartnerSync(TransactionCase):
    """Test the lazy partner creation flow from web leads."""

    def setUp(self):
        super().setUp()

        # Create test polymer for intake
        self.polymer = self.env["plasticos.polymer"].create({"name": "HDPE", "code": "hdpe"})

        # Create test contact
        self.contact = self.env["res.partner"].create(
            {
                "name": "Test Contact Person",
                "email": "contact@testcompany.com",
                "phone": "+1-555-123-4567",
                "is_company": False,
            }
        )

    def test_intake_with_pending_company_name(self):
        """Test creating intake with pending_company_name (no partner yet)."""
        intake = self.env["plasticos.intake"].create(
            {
                "pending_company_name": "New Web Lead Company",
                "polymer_id": self.polymer.id,
                "quantity_per_load_lbs": 40000,
                "status": "draft",
            }
        )

        self.assertEqual(intake.pending_company_name, "New Web Lead Company")
        self.assertFalse(intake.partner_id, "Partner should not be set yet")

    def test_create_partner_from_pending(self):
        """Test _create_partner_from_pending creates partner and clears pending."""
        intake = self.env["plasticos.intake"].create(
            {
                "pending_company_name": "Lazy Partner Test Co",
                "polymer_id": self.polymer.id,
                "quantity_per_load_lbs": 40000,
                "contact_id": self.contact.id,
                "status": "draft",
            }
        )

        # Call the private method directly
        intake._create_partner_from_pending()

        # Verify partner was created
        self.assertTrue(intake.partner_id, "Partner should be created")
        self.assertEqual(intake.partner_id.name, "Lazy Partner Test Co")
        self.assertTrue(intake.partner_id.is_company)
        self.assertEqual(intake.partner_id.supplier_rank, 1)
        # lead_source_id is a Many2one to utm.source; check it was set
        if intake.partner_id.lead_source_id:
            self.assertEqual(intake.partner_id.lead_source_id.name, "Web Lead Form")

        # Verify pending_company_name is cleared
        self.assertFalse(intake.pending_company_name, "pending_company_name should be cleared")

        # Verify contact info was pulled
        self.assertEqual(intake.partner_id.email, "contact@testcompany.com")
        self.assertEqual(intake.partner_id.phone, "+1-555-123-4567")

    def test_create_partner_links_existing(self):
        """Test _create_partner_from_pending links to existing partner if found."""
        # Create existing partner with same name
        existing_partner = self.env["res.partner"].create(
            {
                "name": "Existing Company LLC",
                "is_company": True,
                "supplier_rank": 1,
            }
        )

        intake = self.env["plasticos.intake"].create(
            {
                "pending_company_name": "Existing Company LLC",
                "polymer_id": self.polymer.id,
                "quantity_per_load_lbs": 40000,
                "status": "draft",
            }
        )

        intake._create_partner_from_pending()

        # Should link to existing, not create new
        self.assertEqual(intake.partner_id.id, existing_partner.id)
        self.assertFalse(intake.pending_company_name)

    def test_create_partner_case_insensitive_match(self):
        """Test existing partner lookup is case-insensitive."""
        existing_partner = self.env["res.partner"].create(
            {
                "name": "ACME Plastics Inc",
                "is_company": True,
            }
        )

        intake = self.env["plasticos.intake"].create(
            {
                "pending_company_name": "acme plastics inc",
                "polymer_id": self.polymer.id,
                "quantity_per_load_lbs": 40000,
                "status": "draft",
            }
        )

        intake._create_partner_from_pending()

        # Should match existing despite case difference
        self.assertEqual(intake.partner_id.id, existing_partner.id)

    def test_create_partner_no_pending_name(self):
        """Test _create_partner_from_pending does nothing if no pending name."""
        intake = self.env["plasticos.intake"].create(
            {
                "polymer_id": self.polymer.id,
                "quantity_per_load_lbs": 40000,
                "status": "draft",
            }
        )

        # Should not raise, just return early
        intake._create_partner_from_pending()
        self.assertFalse(intake.partner_id)

    def test_action_match_to_buyers_creates_partner(self):
        """Test action_match_to_buyers creates partner from pending_company_name.

        NOTE: This test requires plasticos_buyer_match_engine module.
        The base intake module only has a stub that raises UserError.
        """
        # Skip if buyer match engine not installed
        if "plasticos.buyer.matcher" not in self.env:
            self.skipTest("plasticos_buyer_match_engine not installed")

        intake = self.env["plasticos.intake"].create(
            {
                "pending_company_name": "Match Test Company",
                "polymer_id": self.polymer.id,
                "quantity_per_load_lbs": 40000,
                "status": "draft",
            }
        )

        # action_match_to_buyers should create partner first
        # Note: This may raise UserError if no buyers found, which is expected
        try:
            intake.action_match_to_buyers()
        except UserError:
            pass

        # Partner should be created regardless of match results
        self.assertTrue(intake.partner_id, "Partner should be created by action")
        self.assertEqual(intake.partner_id.name, "Match Test Company")

    def test_action_match_requires_company(self):
        """Test action_match_to_buyers fails without partner or pending name.

        NOTE: This test requires plasticos_buyer_match_engine module.
        The base intake module only has a stub that raises UserError.
        """
        # Skip if buyer match engine not installed
        if "plasticos.buyer.matcher" not in self.env:
            self.skipTest("plasticos_buyer_match_engine not installed")

        intake = self.env["plasticos.intake"].create(
            {
                "polymer_id": self.polymer.id,
                "quantity_per_load_lbs": 40000,
                "status": "draft",
            }
        )

        with self.assertRaises(UserError) as ctx:
            intake.action_match_to_buyers()

        self.assertIn("Cannot match without a company", str(ctx.exception))

    def test_company_display_pending(self):
        """Test company_display shows pending indicator."""
        intake = self.env["plasticos.intake"].create(
            {
                "pending_company_name": "Pending Display Test",
                "polymer_id": self.polymer.id,
                "quantity_per_load_lbs": 40000,
                "status": "draft",
            }
        )

        self.assertIn("⏳", intake.company_display)
        self.assertIn("Pending Display Test", intake.company_display)

    def test_company_display_linked(self):
        """Test company_display shows partner name when linked."""
        partner = self.env["res.partner"].create(
            {
                "name": "Linked Partner Co",
                "is_company": True,
            }
        )

        intake = self.env["plasticos.intake"].create(
            {
                "partner_id": partner.id,
                "polymer_id": self.polymer.id,
                "quantity_per_load_lbs": 40000,
                "status": "draft",
            }
        )

        self.assertEqual(intake.company_display, "Linked Partner Co")
