"""Contract tests for stored computed field dependency declarations.

A stored computed field with missing @api.depends triggers will silently
serve stale data. These tests verify that the declared depends include
all fields that should trigger recomputation.
"""

from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "contract")
class TestIntakeComputedFieldDeps(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Intake = cls.env["plasticos.intake"]
        cls.fields = cls.Intake._fields

    def _get_depends(self, field_name):
        """Get the depends list for a computed field."""
        f = self.fields.get(field_name)
        if not f or not f.compute:
            return None
        return list(f.depends) if f.depends else []

    def test_match_count_depends_on_match_line_ids(self):
        deps = self._get_depends("match_count")
        self.assertIsNotNone(deps, "match_count should be computed")
        self.assertIn("match_line_ids", deps)

    def test_selected_count_depends_on_selected(self):
        deps = self._get_depends("selected_count")
        self.assertIsNotNone(deps)
        # Should depend on match_line_ids.selected
        has_selected_dep = any("selected" in d for d in deps)
        self.assertTrue(has_selected_dep, "selected_count must depend on match_line_ids.selected")

    def test_best_match_score_depends_on_match_score(self):
        deps = self._get_depends("best_match_score")
        self.assertIsNotNone(deps)
        has_score_dep = any("match_score" in d for d in deps)
        self.assertTrue(has_score_dep)

    def test_has_residue_depends_on_contamination_pct(self):
        deps = self._get_depends("has_residue")
        self.assertIsNotNone(deps)
        self.assertIn("contamination_pct", deps)

    def test_display_name_depends_on_name(self):
        deps = self._get_depends("display_name")
        self.assertIsNotNone(deps)
        self.assertIn("name", deps)

    def test_company_display_depends_on_partner_and_pending(self):
        deps = self._get_depends("company_display")
        self.assertIsNotNone(deps)
        self.assertIn("partner_id", deps)
        self.assertIn("pending_company_name", deps)
