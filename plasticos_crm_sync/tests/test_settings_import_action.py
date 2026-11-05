"""TransactionCase: Settings API sync action find-or-create + sync path."""

from unittest.mock import MagicMock, patch

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

REGISTRY_GET_ADAPTER = "odoo.addons.plasticos_crm_sync.adapters.registry.get_adapter"
VS_CLIENT_REQUEST = "odoo.addons.plasticos_crm_sync.adapters.vanillasoft.client.VanillaSoftClient._request"
ORCHESTRATOR_RUN_CONNECTION = "odoo.addons.plasticos_crm_sync.services.orchestrator.SyncOrchestrator.run_connection"


@tagged("post_install", "-at_install")
class TestCrmSyncSettingsImportAction(TransactionCase):
    def _make_connection(self):
        icp = self.env["ir.config_parameter"].sudo()
        icp.set_param("plasticos_crm_sync.vanillasoft_api_key", "test-key-not-real")
        icp.set_param("plasticos_crm_sync.vanillasoft_project_id", "139705")
        return self.env["plasticos.crm.connection"].get_or_create_vanillasoft_connection()

    def test_action_test_connection_live_adapter_succeeds(self):
        connection = self._make_connection()
        adapter = MagicMock()
        with (
            patch(REGISTRY_GET_ADAPTER, return_value=adapter) as mock_get_adapter,
            patch(VS_CLIENT_REQUEST) as mock_request,
        ):
            action = connection.action_test_connection()
        mock_get_adapter.assert_called_once()
        self.assertEqual(mock_get_adapter.call_args.args[0], "vanillasoft")
        adapter.healthcheck.assert_called_once_with()
        mock_request.assert_not_called()
        self.assertEqual(action.get("tag"), "display_notification")
        self.assertEqual(action["params"]["type"], "success")
        self.assertFalse(connection.last_error)

    def test_action_test_connection_adapter_rejection_fails_closed(self):
        from odoo.addons.plasticos_crm_sync.adapters.base import CrmAdapterError

        connection = self._make_connection()
        with (
            patch(REGISTRY_GET_ADAPTER, side_effect=CrmAdapterError("Unknown CRM provider")),
            patch(VS_CLIENT_REQUEST) as mock_request,
            self.assertRaises(UserError) as ctx,
        ):
            connection.action_test_connection()
        mock_request.assert_not_called()
        self.assertIn("Connection test failed", str(ctx.exception))
        self.assertIn("Unknown CRM provider", str(ctx.exception))

    def test_action_sync_now_failure_propagates(self):
        from odoo.addons.plasticos_crm_sync.adapters.base import CrmAdapterError

        connection = self._make_connection()
        with (
            patch(ORCHESTRATOR_RUN_CONNECTION, side_effect=CrmAdapterError("VerifyKey failed")) as mock_run,
            patch(VS_CLIENT_REQUEST) as mock_request,
            self.assertRaises(UserError) as ctx,
        ):
            connection.action_sync_now()
        mock_run.assert_called_once()
        mock_request.assert_not_called()
        self.assertIn("Sync failed", str(ctx.exception))
        self.assertIn("VerifyKey failed", str(ctx.exception))

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
