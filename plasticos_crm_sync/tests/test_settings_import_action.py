"""TransactionCase: Settings API sync action find-or-create + sync path."""

from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestCrmSyncSettingsImportAction(TransactionCase):
    def test_get_or_create_vanillasoft_connection_idempotent(self):
        Conn = self.env["plasticos.crm.connection"]
        self.env["ir.config_parameter"].sudo().set_param(
            "plasticos_crm_sync.vanillasoft_project_id",
            "139705",
        )
        first = Conn.get_or_create_vanillasoft_connection()
        second = Conn.get_or_create_vanillasoft_connection()
        self.assertEqual(first.id, second.id)
        self.assertEqual(first.provider, "vanillasoft")
        self.assertEqual(first.project_id, "139705")
        self.assertFalse(first.enabled)

    def test_settings_action_requires_api_key(self):
        self.env["ir.config_parameter"].sudo().set_param(
            "plasticos_crm_sync.vanillasoft_api_key",
            "",
        )
        self.env["ir.config_parameter"].sudo().set_param(
            "plasticos_crm_sync.vanillasoft_project_id",
            "139705",
        )
        settings = self.env["res.config.settings"].create(
            {
                "plasticos_crm_sync_vanillasoft_api_key": False,
                "plasticos_crm_sync_vanillasoft_project_id": "139705",
            }
        )
        with self.assertRaises(UserError):
            settings.action_plasticos_crm_sync_run_vanillasoft()

    def test_settings_action_calls_sync_now(self):
        self.env["ir.config_parameter"].sudo().set_param(
            "plasticos_crm_sync.vanillasoft_api_key",
            "test-key-not-real",
        )
        self.env["ir.config_parameter"].sudo().set_param(
            "plasticos_crm_sync.vanillasoft_project_id",
            "139705",
        )
        settings = self.env["res.config.settings"].create(
            {
                "plasticos_crm_sync_vanillasoft_api_key": "test-key-not-real",
                "plasticos_crm_sync_vanillasoft_project_id": "139705",
            }
        )
        with patch.object(
            type(self.env["plasticos.crm.connection"]),
            "action_sync_now",
            return_value={
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {},
            },
        ) as mock_sync:
            action = settings.action_plasticos_crm_sync_run_vanillasoft()
            mock_sync.assert_called_once()
        connection = self.env["plasticos.crm.connection"].search(
            [("provider", "=", "vanillasoft"), ("active", "=", True)],
            limit=1,
        )
        self.assertTrue(connection)
        # No sync.run without real orchestrator — notification fallback
        self.assertEqual(action.get("type"), "ir.actions.client")
