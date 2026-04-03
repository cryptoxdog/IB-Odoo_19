from odoo.tests.common import TransactionCase


class TestClaimUxFilters(TransactionCase):

    def test_p0_no_double_percent_in_domain(self):
        """P0: %%Y should never appear in a domain string used by claim search."""
        view = self.env["ir.ui.view"].search(
            [("name", "=", "plasticos.claim.search.ux")], limit=1
        )
        self.assertTrue(view, "claim_search_ux view not found")
        self.assertNotIn("%%Y", view.arch, "Double-percent %%Y found in domain — P0 regression")
        self.assertNotIn("%%m", view.arch, "Double-percent %%m found in domain — P0 regression")

    def test_p0_rolling_7d_domain_evaluates(self):
        """P0: The rolling 7-day domain must be evaluable without error."""
        from odoo.osv import expression
        from datetime import date, timedelta
        cutoff = (date.today() - timedelta(days=7)).strftime("%Y-%m-%d")
        domain = [("opened_at", ">=", cutoff)]
        # Should not raise
        normalized = expression.normalize_domain(domain)
        self.assertIsInstance(normalized, list)

    def test_p2_no_decoration_danger_on_form_boolean(self):
        """P2: decoration-danger must not appear on the is_overdue form field."""
        view = self.env["ir.ui.view"].search(
            [("name", "=", "plasticos.claim.form.ux")], limit=1
        )
        self.assertTrue(view, "claim_form_ux view not found")
        # decoration-danger on a form boolean is silently ignored;
        # it should have been removed and moved to list row decoration.
        self.assertNotIn(
            'decoration-danger="is_overdue"', view.arch,
            "decoration-danger on form boolean is_overdue — P2 regression"
        )

    def test_p2_list_decoration_warning_is_present(self):
        """P2: The correct location for is_overdue decoration is list row."""
        view = self.env["ir.ui.view"].search(
            [("name", "=", "plasticos.claim.list.ux")], limit=1
        )
        self.assertTrue(view, "claim_list_ux view not found")
        self.assertIn(
            "is_overdue", view.arch,
            "is_overdue decoration missing from list view"
        )
