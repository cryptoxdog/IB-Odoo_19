"""Install witness for the S5A scaffold: installed, versioned, and still empty.

Contract PLASTICOS-EXPORT-C04-S5A-SCAFFOLD-AND-BRS: the addon installs with no
data side effect and owns no model, menu, view or record yet. A later slice that
adds the first model, view or record changes these expectations on purpose.
"""

from __future__ import annotations

import ast

from odoo.modules.module import get_module_path
from odoo.tests import TransactionCase, tagged

MODULE = "plasticos_export"


@tagged("post_install", "-at_install", "plasticos", "plasticos_export")
class TestExportScaffoldInstall(TransactionCase):
    def _manifest(self) -> dict:
        path = get_module_path(MODULE)
        with open(f"{path}/__manifest__.py", encoding="utf-8") as handle:
            return ast.literal_eval(handle.read())

    def test_module_is_installed_at_the_manifest_version(self):
        module = self.env["ir.module.module"].search([("name", "=", MODULE)])
        self.assertEqual(len(module), 1)
        self.assertEqual(module.state, "installed")
        self.assertEqual(module.latest_version, self._manifest()["version"])
        self.assertEqual(module.latest_version, "19.0.1.0.0")
        self.assertFalse(module.auto_install)
        self.assertTrue(module.application)

    def test_dependency_is_documents_native_and_it_is_installed(self):
        module = self.env["ir.module.module"].search([("name", "=", MODULE)])
        self.assertEqual(module.dependencies_id.mapped("name"), ["plasticos_documents_native"])
        dependency = self.env["ir.module.module"].search([("name", "=", "plasticos_documents_native")])
        self.assertEqual(dependency.state, "installed")

    def test_scaffold_owns_no_model_menu_view_or_record(self):
        # Every model, field, ACL, view, menu, action and data record an addon
        # loads gets an ir.model.data row under its own module name.
        ir_data = self.env["ir.model.data"].search([("module", "=", MODULE)])
        self.assertEqual(sorted(ir_data.mapped("name")), [])
        self.assertEqual(self.env["ir.model"].search_count([("model", "=like", "plasticos.export%")]), 0)
