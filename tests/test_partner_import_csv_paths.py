"""Legacy ERP CSV partner import: ICP path resolution kept, UI retired.

The importer service still resolves the configured / bundled CSV paths for a
shell caller (``plasticos_partner_import/scripts/run_import.py``). The Settings
block, the wizard window action / form view and the wizard execution actions
are retired (``plasticos_partner_import/migrations/<manifest version>``). Runs under
``odoo --test-enable``; the pure-Python twin is ``test_legacy_import_ui_retired``.
"""

import ast
import importlib.util
import os
import tempfile

from odoo import SUPERUSER_ID, Command
from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.exceptions import AccessError, UserError
from odoo.tests.common import tagged

CONFIG_CORPORATE = "plasticos_partner_import.default_corporate_csv"
CONFIG_FACILITY = "plasticos_partner_import.default_facility_csv"
WIZARD_MODEL = "plasticos.partner.import.wizard"
RETIRED_XML_IDS = (
    "plasticos_partner_import.res_config_settings_view_form_partner_import",
    "plasticos_partner_import.action_partner_import_wizard",
    "plasticos_partner_import.view_partner_import_wizard_form",
)
RETIRED_SETTINGS_VIEW_NAME = "res.config.settings.view.form.plasticos.partner.import"
RETIRED_SETTINGS_FIELDS = (
    "plasticos_partner_import_corporate_csv",
    "plasticos_partner_import_facility_csv",
)
RETIRED_WIZARD_ACTIONS = ("action_import", "action_audit_import", "action_repair_import")


@tagged("post_install", "-at_install", "plasticos", "partner_import")
class TestPartnerImportCsvPaths(PlasticosTestCase):
    """ICP persistence, default vs configured path, missing-file fail-closed."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.svc = cls.env["plasticos.partner.import.service"]
        cls.icp = cls.env["ir.config_parameter"].sudo()
        cls._prev_corp = cls.icp.get_param(CONFIG_CORPORATE)
        cls._prev_fac = cls.icp.get_param(CONFIG_FACILITY)

    @classmethod
    def tearDownClass(cls):
        cls.icp.set_param(CONFIG_CORPORATE, cls._prev_corp or "")
        cls.icp.set_param(CONFIG_FACILITY, cls._prev_fac or "")
        super().tearDownClass()

    def test_icp_values_survive_without_settings_fields(self):
        """The retired Settings fields are gone; the stored parameters are not."""
        for field_name in RETIRED_SETTINGS_FIELDS:
            self.assertNotIn(field_name, self.env["res.config.settings"]._fields)
        self.icp.set_param(CONFIG_CORPORATE, "/tmp/corp-test.csv")
        self.icp.set_param(CONFIG_FACILITY, "/tmp/fac-test.csv")
        self.assertEqual(self.icp.get_param(CONFIG_CORPORATE), "/tmp/corp-test.csv")
        self.assertEqual(self.icp.get_param(CONFIG_FACILITY), "/tmp/fac-test.csv")

    def test_empty_icp_uses_module_default(self):
        self.icp.set_param(CONFIG_CORPORATE, "")
        self.icp.set_param(CONFIG_FACILITY, "")
        corp = self.svc.resolve_default_csv_path("corporate")
        fac = self.svc.resolve_default_csv_path("facility")
        self.assertTrue(corp.endswith("CORPORATE-Ready To Import.csv"))
        self.assertTrue(fac.endswith("FACILITY LOCATIONS.csv"))
        module_path = self.svc.get_module_path()
        self.assertTrue(corp.startswith(module_path))
        self.assertTrue(fac.startswith(module_path))

    def test_configured_existing_path_is_used(self):
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
            tmp.write(b"id,name\n1,x\n")
            path = tmp.name
        try:
            self.icp.set_param(CONFIG_CORPORATE, path)
            self.assertEqual(self.svc.resolve_default_csv_path("corporate"), path)
        finally:
            os.unlink(path)

    def test_configured_missing_path_raises(self):
        self.icp.set_param(CONFIG_CORPORATE, "/nonexistent/path/corporate.csv")
        with self.assertRaises(UserError) as ctx:
            self.svc.resolve_default_csv_path("corporate")
        self.assertIn("does not exist", str(ctx.exception))

    def test_run_default_missing_configured_path_raises(self):
        self.icp.set_param(CONFIG_CORPORATE, "/nonexistent/path/corporate.csv")
        self.icp.set_param(CONFIG_FACILITY, "")
        with self.assertRaises(UserError):
            self.svc.run_default_csv_import()


@tagged("post_install", "-at_install", "plasticos", "partner_import")
class TestLegacyImportUiRetired(PlasticosTestCase):
    """No UI entry point, no RPC path for ordinary users, importer code preserved."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.internal_user = (
            cls.env["res.users"]
            .with_context(no_reset_password=True)
            .create(
                {
                    "name": "Legacy Import Internal",
                    "login": "legacy_import_internal",
                    "group_ids": [Command.set([cls.env.ref("base.group_user").id])],
                }
            )
        )

    def test_retired_xml_ids_are_absent(self):
        for xml_id in RETIRED_XML_IDS:
            self.assertFalse(self.env.ref(xml_id, raise_if_not_found=False), xml_id)

    def test_no_action_view_or_menu_targets_the_wizard(self):
        self.assertFalse(self.env["ir.actions.act_window"].search([("res_model", "=", WIZARD_MODEL)]))
        self.assertFalse(self.env["ir.ui.view"].search([("model", "=", WIZARD_MODEL)]))
        self.assertFalse(
            self.env["ir.ui.menu"]
            .search([("action", "like", "ir.actions.act_window,%")])
            .filtered(lambda menu: menu.action and menu.action.res_model == WIZARD_MODEL)
        )

    def test_settings_has_no_legacy_button_method(self):
        settings = self.env["res.config.settings"]
        self.assertFalse(hasattr(settings, "action_plasticos_partner_import_run_default"))
        self.assertFalse(
            self.env["ir.ui.view"].search(
                [("model", "=", "res.config.settings"), ("name", "=", RETIRED_SETTINGS_VIEW_NAME)]
            )
        )

    def test_internal_user_cannot_reach_the_wizard(self):
        wizard = self.env[WIZARD_MODEL].with_user(self.internal_user)
        with self.assertRaises(AccessError):
            wizard.check_access("read")
        with self.assertRaises(AccessError):
            wizard.create({})

    def test_execution_actions_refuse_even_for_system_users(self):
        self.assertTrue(self.env.is_system())
        wizard = self.env[WIZARD_MODEL].create({})
        for action in RETIRED_WIZARD_ACTIONS:
            with self.subTest(action=action), self.assertRaises(UserError) as ctx:
                getattr(wizard, action)()
            self.assertIn("retired", str(ctx.exception))

    def test_internal_user_cannot_run_the_importer_through_rpc(self):
        """The service ACL grants read; its public import methods must still refuse non-system callers."""
        service = self.env["plasticos.partner.import.service"].with_user(self.internal_user)
        with self.assertRaises(AccessError):
            service.run_default_csv_import()
        with self.assertRaises(AccessError):
            service.run_csv_import("/nonexistent/corporate.csv", "/nonexistent/facility.csv")
        with self.assertRaises(AccessError):
            service.run_full_import()
        validation = self.env["plasticos.partner.import.validation"].with_user(self.internal_user)
        with self.assertRaises(AccessError):
            validation.repair_import_data(dry_run=True)

    def test_operator_shell_and_system_users_pass_the_guard(self):
        service = self.env["plasticos.partner.import.service"]
        self.assertIsNone(service._check_import_operator())
        self.assertIsNone(service.with_user(SUPERUSER_ID)._check_import_operator())
        self.assertIsNone(service.with_user(self.internal_user).sudo()._check_import_operator())

    def test_importer_logic_is_preserved(self):
        service = self.env["plasticos.partner.import.service"]
        for method in ("run_csv_import", "run_default_csv_import", "resolve_default_csv_path", "run_full_import"):
            self.assertTrue(callable(getattr(service, method, None)), method)
        validation = self.env["plasticos.partner.import.validation"]
        for method in ("audit_import_integrity", "repair_import_data"):
            self.assertTrue(callable(getattr(validation, method, None)), method)
        from odoo.addons.plasticos_partner_import.scripts import run_import

        self.assertTrue(callable(run_import.run_csv))
        self.assertTrue(callable(run_import.run))
        self.assertIn("plasticos.erp.import", self.env)

    def test_upgrade_migration_retires_persisted_records_and_keeps_icp(self):
        """A database that still carries the old action is cleaned by the migration."""
        module_path = self.env["plasticos.partner.import.service"].get_module_path()
        # The retirement migration lives under the manifest version (enforced by
        # test_legacy_import_ui_retired), so a version bump cannot strand this path.
        with open(os.path.join(module_path, "__manifest__.py"), encoding="utf-8") as handle:
            version = ast.literal_eval(handle.read())["version"]
        script = os.path.join(module_path, "migrations", version, "post-migrate.py")
        spec = importlib.util.spec_from_file_location("legacy_ui_post_migrate", script)
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)

        action = self.env["ir.actions.act_window"].create(
            {"name": "Import Partners (stale)", "res_model": WIZARD_MODEL, "view_mode": "form", "target": "new"}
        )
        self.env["ir.model.data"].create(
            {
                "module": "plasticos_partner_import",
                "name": "action_partner_import_wizard",
                "model": "ir.actions.act_window",
                "res_id": action.id,
            }
        )
        self.env.registry.clear_cache()
        icp = self.env["ir.config_parameter"].sudo()
        icp.set_param(CONFIG_CORPORATE, "/tmp/keep-me.csv")
        self.assertTrue(self.env.ref(RETIRED_XML_IDS[1], raise_if_not_found=False))

        migration.migrate(self.env.cr, "19.0.2.10.21")
        self.env.registry.clear_cache()

        self.assertFalse(self.env.ref(RETIRED_XML_IDS[1], raise_if_not_found=False))
        self.assertFalse(action.exists())
        self.assertEqual(icp.get_param(CONFIG_CORPORATE), "/tmp/keep-me.csv")
        # Idempotent: a second run on the cleaned database is a no-op.
        migration.migrate(self.env.cr, "19.0.2.10.21")
