"""GMP-NC-B: the configured import-path lookup follows the service's own ACL.

``resolve_default_csv_path`` is public, and Odoo does not check model access
before calling a public method. The elevated parameter read must therefore be
preceded by the service ACL check (internal users may read; portal may not).
Runs under ``odoo --test-enable --test-tags /plasticos_partner_import``.
"""

from __future__ import annotations

from odoo import Command
from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestImportPathAccess(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Users = cls.env["res.users"].with_context(no_reset_password=True)
        cls.internal_user = Users.create(
            {
                "name": "Import Internal",
                "login": "nc_b_import_internal",
                "group_ids": [Command.set([cls.env.ref("base.group_user").id])],
            }
        )
        cls.portal_user = Users.create(
            {
                "name": "Import Portal",
                "login": "nc_b_import_portal",
                "group_ids": [Command.set([cls.env.ref("base.group_portal").id])],
            }
        )

    def _service(self, user):
        return self.env["plasticos.partner.import.service"].with_user(user)

    def test_internal_user_resolves_the_default_path(self):
        path = self._service(self.internal_user).resolve_default_csv_path("corporate")
        self.assertTrue(path.endswith(".csv"))

    def test_portal_user_is_denied_before_the_parameter_read(self):
        with self.assertRaises(AccessError):
            self._service(self.portal_user).resolve_default_csv_path("corporate")
