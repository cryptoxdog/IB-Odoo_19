from odoo.tests.common import TransactionCase


class TestOfferUxIcons(TransactionCase):

    def _get_offer_form_arch(self):
        view = self.env["ir.ui.view"].search(
            [("name", "=", "plasticos.offer.form.ux")], limit=1
        )
        self.assertTrue(view, "offer_form_ux view not found")
        return view.arch

    def test_p2_fa_dollar_absent(self):
        """P2: fa-dollar (invalid FA4 class) must not appear in offer form."""
        arch = self._get_offer_form_arch()
        self.assertNotIn("fa-dollar", arch, "fa-dollar found — blank icon regression (P2)")

    def test_p2_fa_usd_present(self):
        """P2: fa-usd (correct FA4 class) must appear on the price stat button."""
        arch = self._get_offer_form_arch()
        self.assertIn("fa-usd", arch, "fa-usd missing from offer form stat button (P2)")

    def test_offer_form_has_sent_banner(self):
        arch = self._get_offer_form_arch()
        self.assertIn("Offer Sent", arch)

    def test_offer_form_has_accepted_banner(self):
        arch = self._get_offer_form_arch()
        self.assertIn("Offer Accepted", arch)
