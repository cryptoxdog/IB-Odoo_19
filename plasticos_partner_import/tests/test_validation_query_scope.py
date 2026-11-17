"""GMP-NC-D D-07 / D-08: the import validations read only the rows they judge.

``validate_partner_graph`` reads only contacts that can fail (no parent, or a
stale ``is_company``), and ``audit_import_integrity`` reads only locations
without a ``facility_role``. Both must report exactly what the original
whole-population scans reported.

The graph check is global, so each case asserts the change in the reported
error count rather than an absolute count: the database may already hold
partners that the check rejects (Odoo's own parentless partners, for example).

Runs under ``odoo --test-enable --test-tags /plasticos_partner_import``.
"""

from __future__ import annotations

import re
from unittest.mock import patch

from odoo import Command
from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


def _original_graph_errors(env):
    """The pre-D-07 algorithm, verbatim, as the equivalence oracle."""
    partners = env["res.partner"].search(["|", ("company_type", "=", "company"), ("company_type", "=", "person")])
    errors = []
    for p in partners:
        if p.company_type == "company":
            continue
        if p.company_type == "person":
            if not p.parent_id and not p.user_ids:
                errors.append(f"Contact '{p.name}' (id={p.id}) missing parent_id")
            if p.is_company:
                errors.append(f"Contact '{p.name}' (id={p.id}) has is_company=True")
    return errors


def _original_missing_role(env):
    """The pre-D-08 algorithm, verbatim, as the equivalence oracle."""
    facilities = env["res.partner"].search([("company_type", "=", "company"), ("parent_id", "!=", False)])
    return [{"id": p.id, "name": p.name, "parent": p.parent_id.name} for p in facilities if not p.facility_role]


@tagged("post_install", "-at_install")
class TestValidationQueryScope(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.Partner = cls.env["res.partner"]
        cls.validation = cls.env["plasticos.partner.import.validation"]
        role = cls.Partner._fields["facility_role"].get_values(cls.env)[0]
        cls.corporate = cls.Partner.create({"name": "NC-D Corporate", "is_company": True})
        cls.location_without_role = cls.Partner.create(
            {"name": "NC-D Location Pending", "is_company": True, "parent_id": cls.corporate.id}
        )
        cls.location_with_role = cls.Partner.create(
            {
                "name": "NC-D Location Classified",
                "is_company": True,
                "parent_id": cls.corporate.id,
                "facility_role": role,
            }
        )
        cls.contact = cls.Partner.create({"name": "NC-D Contact", "parent_id": cls.corporate.id})

    # -- helpers --------------------------------------------------------------

    def _graph_error_count(self):
        try:
            self.validation.validate_partner_graph()
        except ValidationError as exc:
            match = re.search(r"\((\d+) errors\)", str(exc))
            self.assertTrue(match, str(exc))
            return int(match.group(1))
        return 0

    def _graph_search_results(self):
        """Call through the real ORM search and keep what it returned."""
        Partner = type(self.Partner)
        original = Partner.search
        results = []

        def spy(model, *args, **kwargs):
            found = original(model, *args, **kwargs)
            results.append(found)
            return found

        with patch.object(Partner, "search", autospec=True, side_effect=spy):
            try:
                self.validation.validate_partner_graph()
            except ValidationError:
                pass
        self.assertTrue(results, "validate_partner_graph issued no res.partner search")
        return results[0]

    def _stale_company_flag(self, partner):
        """A person whose stored is_company disagrees with company_type."""
        self.env.flush_all()
        self.env.cr.execute("UPDATE res_partner SET is_company = true WHERE id = %s", [partner.id])
        partner.invalidate_recordset(["is_company"])
        self.assertEqual(partner.company_type, "person")
        self.assertTrue(partner.is_company)

    # -- D-07 -----------------------------------------------------------------

    def test_graph_errors_match_the_original_scan(self):
        orphan = self.Partner.create({"name": "NC-D Orphan Contact"})
        self._stale_company_flag(self.Partner.create({"name": "NC-D Stale Flag", "parent_id": self.corporate.id}))
        expected = _original_graph_errors(self.env)
        self.assertIn(f"Contact '{orphan.name}' (id={orphan.id}) missing parent_id", expected)
        self.assertEqual(self._graph_error_count(), len(expected))

    def test_graph_query_reads_no_company(self):
        candidates = self._graph_search_results()
        self.assertFalse(candidates.filtered(lambda p: p.company_type == "company"))
        self.assertNotIn(self.corporate, candidates)
        self.assertNotIn(self.location_without_role, candidates)
        self.assertNotIn(self.contact, candidates, "a contact with a parent cannot fail and is not read")

    def test_graph_query_reads_every_contact_that_can_fail(self):
        orphan = self.Partner.create({"name": "NC-D Orphan Candidate"})
        stale = self.Partner.create({"name": "NC-D Stale Candidate", "parent_id": self.corporate.id})
        self._stale_company_flag(stale)
        candidates = self._graph_search_results()
        self.assertIn(orphan, candidates)
        self.assertIn(stale, candidates)

    def test_valid_companies_locations_and_contacts_add_no_error(self):
        before = self._graph_error_count()
        corporate = self.Partner.create({"name": "NC-D Valid Corporate", "is_company": True})
        self.Partner.create({"name": "NC-D Valid Location", "is_company": True, "parent_id": corporate.id})
        self.Partner.create({"name": "NC-D Valid Contact", "parent_id": corporate.id})
        self.assertEqual(self._graph_error_count(), before)

    def test_contact_missing_a_parent_is_reported(self):
        before = self._graph_error_count()
        self.Partner.create({"name": "NC-D Missing Parent"})
        self.assertEqual(self._graph_error_count(), before + 1)

    def test_user_linked_contact_stays_exempt(self):
        before = self._graph_error_count()
        user = (
            self.env["res.users"]
            .with_context(no_reset_password=True)
            .create(
                {
                    "name": "NC-D Linked User",
                    "login": "nc_d_linked_user",
                    "group_ids": [Command.set([self.env.ref("base.group_user").id])],
                }
            )
        )
        self.assertFalse(user.partner_id.parent_id)
        self.assertEqual(self._graph_error_count(), before)

    def test_incorrect_company_flag_is_reported(self):
        before = self._graph_error_count()
        self._stale_company_flag(self.Partner.create({"name": "NC-D Flag With Parent", "parent_id": self.corporate.id}))
        self.assertEqual(self._graph_error_count(), before + 1)
        self._stale_company_flag(self.Partner.create({"name": "NC-D Flag Without Parent"}))
        self.assertEqual(self._graph_error_count(), before + 3, "no parent and a stale flag are two errors")

    # -- D-08 -----------------------------------------------------------------

    def test_missing_role_report_matches_the_original_scan(self):
        self.Partner.create({"name": "NC-D Person", "parent_id": self.location_without_role.id})
        report = self.validation.audit_import_integrity()
        self.assertEqual(report["facilities_missing_role"], _original_missing_role(self.env))

    def test_missing_role_report_lists_only_unclassified_locations(self):
        listed = {item["id"] for item in self.validation.audit_import_integrity()["facilities_missing_role"]}
        # A child created as a company becomes a site. The report lists company children only.
        self.assertNotIn(self.location_without_role.id, listed)
        self.assertNotIn(self.location_with_role.id, listed)
        self.assertNotIn(self.corporate.id, listed)
        self.assertNotIn(self.contact.id, listed)

    def test_missing_role_entry_shape_and_report_keys_are_unchanged(self):
        report = self.validation.audit_import_integrity()
        self.assertEqual(
            set(report),
            {
                "old_external_ids",
                "facilities_missing_role",
                "contacts_missing_parent",
                "duplicate_external_ids",
                "summary",
            },
        )
        self.assertFalse(any(item["id"] == self.location_without_role.id for item in report["facilities_missing_role"]))
        for entry in report["facilities_missing_role"]:
            self.assertEqual(set(entry), {"id", "name", "parent"})

    def test_missing_role_stays_informational(self):
        report = self.validation.audit_import_integrity()
        self.assertTrue(
            "enrichment pending; not an error" in report["summary"] or report["summary"] == "No issues found."
        )
