"""Settings / ICP path resolution for plasticos_partner_import legacy ERP import."""

import os
import tempfile

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.exceptions import UserError
from odoo.tests.common import tagged

CONFIG_CORPORATE = "plasticos_partner_import.default_corporate_csv"
CONFIG_FACILITY = "plasticos_partner_import.default_facility_csv"


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

    def test_settings_fields_persist_to_icp(self):
        settings = self.env["res.config.settings"].create(
            {
                "plasticos_partner_import_corporate_csv": "/tmp/corp-test.csv",
                "plasticos_partner_import_facility_csv": "/tmp/fac-test.csv",
            }
        )
        settings.set_values()
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

    def test_settings_action_missing_path_raises(self):
        settings = self.env["res.config.settings"].create(
            {
                "plasticos_partner_import_corporate_csv": "/nonexistent/path/corporate.csv",
                "plasticos_partner_import_facility_csv": "",
            }
        )
        with self.assertRaises(UserError):
            settings.action_plasticos_partner_import_run_default()
