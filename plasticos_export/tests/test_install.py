"""Install witness: installed, versioned, and owning exactly the declared S5B set.

S5A (contract PLASTICOS-EXPORT-C04-S5A-SCAFFOLD-AND-BRS) installed an empty
scaffold. S5B (PLASTICOS-EXPORT-C05-S5B-EXPORT-MODELS-UI-REPORTS, coordinator
C05-SCOPE-2) adds the four Export models and their views, actions, menus, rules,
reports and the booking reply trigger, as this witness anticipated. A later
slice that adds a record changes these explicit lists on purpose.
"""

from __future__ import annotations

import ast
import os

from lxml import etree

from odoo.modules.module import get_module_path
from odoo.tests import TransactionCase, tagged

MODULE = "plasticos_export"
VERSION = "19.0.1.1.0"
DEPENDS = [
    "base_automation",
    "plasticos_documents",
    "plasticos_documents_native",
    "plasticos_logistics",
    "plasticos_security_base",
    "purchase",
    "sale",
    "stock",
]
MODELS = [
    "plasticos.export.booking",
    "plasticos.export.booking.cargo.link",
    "plasticos.export.booking.revision",
    "plasticos.export.booking.slot",
]
# Every record the data files declare, by model. Nothing else is Export data.
DECLARED = {
    "base.automation": ["automation_linda_incoming_booking_reply"],
    "ir.actions.act_window": [
        "action_export_booking",
        "action_export_booking_deadlines",
        "action_export_cargo_link",
        "action_export_report_availability",
        "action_export_report_exceptions",
        "action_export_report_fulfillment",
        "action_export_report_manifest",
        "action_export_report_missing_documents",
        "action_export_report_register",
        "action_export_shipments",
        "action_export_slot",
    ],
    "ir.actions.report": ["action_report_booking_summary", "action_report_container_manifest"],
    "ir.actions.server": ["action_linda_record_booking_reply"],
    "ir.model.access": [
        f"access_export_{model}_{role}"
        for model in ("booking", "cargo_link", "revision", "slot")
        for role in ("logistics", "ops_manager", "sales")
    ],
    "ir.rule": [
        "rule_export_booking_company",
        "rule_export_cargo_link_company",
        "rule_export_revision_company",
        "rule_export_slot_company",
    ],
    "ir.ui.menu": [
        "menu_export_allocations",
        "menu_export_bookings",
        "menu_export_cargo",
        "menu_export_deadlines",
        "menu_export_overview",
        "menu_export_report_availability",
        "menu_export_report_exceptions",
        "menu_export_report_fulfillment",
        "menu_export_report_manifest",
        "menu_export_report_missing_documents",
        "menu_export_report_register",
        "menu_export_reporting",
        "menu_export_root",
        "menu_export_shipments",
    ],
    "ir.ui.view": [
        "report_booking_summary",
        "report_container_manifest",
        "view_export_booking_calendar",
        "view_export_booking_form",
        "view_export_booking_list",
        "view_export_booking_revision_form",
        "view_export_booking_revision_list",
        "view_export_booking_search",
        "view_export_cargo_link_form",
        "view_export_cargo_link_list",
        "view_export_cargo_link_pivot",
        "view_export_cargo_link_search",
        "view_export_shipment_list",
        "view_export_slot_form",
        "view_export_slot_graph",
        "view_export_slot_list",
        "view_export_slot_pivot",
        "view_export_slot_search",
    ],
}
# Rows Odoo writes itself when it reflects the models a module defines or extends.
REFLECTION = {"ir.model", "ir.model.fields", "ir.model.fields.selection", "ir.model.constraint", "ir.model.inherit"}


@tagged("post_install", "-at_install", "plasticos", "plasticos_export")
class TestExportInstall(TransactionCase):
    def _manifest(self) -> dict:
        path = get_module_path(MODULE)
        with open(f"{path}/__manifest__.py", encoding="utf-8") as handle:
            return ast.literal_eval(handle.read())

    def test_module_is_installed_at_the_manifest_version(self):
        module = self.env["ir.module.module"].search([("name", "=", MODULE)])
        self.assertEqual(len(module), 1)
        self.assertEqual(module.state, "installed")
        self.assertEqual(module.latest_version, self._manifest()["version"])
        self.assertEqual(module.latest_version, VERSION)
        self.assertFalse(module.auto_install)
        self.assertTrue(module.application)

    def test_dependencies_are_its_owners_and_installed(self):
        module = self.env["ir.module.module"].search([("name", "=", MODULE)])
        self.assertEqual(sorted(module.dependencies_id.mapped("name")), DEPENDS)
        self.assertEqual(sorted(self._manifest()["depends"]), DEPENDS)
        installed = self.env["ir.module.module"].search([("name", "in", DEPENDS)])
        self.assertEqual(set(installed.mapped("state")), {"installed"})
        self.assertEqual(len(installed), len(DEPENDS))

    def test_no_owner_module_depends_on_export(self):
        dependants = self.env["ir.module.module.dependency"].search([("name", "=", MODULE)])
        self.assertFalse(dependants.module_id.mapped("name"))

    def test_export_owns_exactly_the_declared_models_and_records(self):
        defined = sorted(name for name, model in self.env.registry.items() if model._original_module == MODULE)
        self.assertEqual(defined, MODELS)
        ir_data = self.env["ir.model.data"].search([("module", "=", MODULE)])
        owned = {}
        for row in ir_data:
            owned.setdefault(row.model, []).append(row.name)
        self.assertEqual(set(owned) - REFLECTION, set(DECLARED))
        for model, names in DECLARED.items():
            self.assertEqual(sorted(owned[model]), sorted(names), model)
        reflected = (
            self.env["ir.model"]
            .browse(ir_data.filtered(lambda row: row.model == "ir.model").mapped("res_id"))
            .mapped("model")
        )
        # Reflection of extended owners is methods only; models it defines are exactly MODELS.
        self.assertTrue(set(MODELS) <= set(reflected))

    def test_installing_export_writes_no_other_modules_record(self):
        """Every data record id is Export's own; another module's record is only ever referenced."""
        path = get_module_path(MODULE)
        for data_file in self._manifest()["data"]:
            if not data_file.endswith(".xml"):
                continue
            tree = etree.parse(os.path.join(path, data_file))
            for node in tree.iter("record", "template", "menuitem"):
                record_id = node.get("id")
                self.assertTrue(record_id and "." not in record_id, f"{data_file}: {record_id}")
        with open(os.path.join(path, "security", "ir.model.access.csv"), encoding="utf-8") as handle:
            for line in handle.read().splitlines()[1:]:
                self.assertNotIn(".", line.split(",")[0], line)
