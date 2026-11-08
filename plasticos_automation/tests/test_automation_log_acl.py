"""An internal user cannot forge a plasticos.automation.log row."""

from odoo import Command
from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestAutomationLogAcl(TransactionCase):
    def test_internal_user_cannot_create_automation_log_directly(self):
        user = (
            self.env["res.users"]
            .with_context(no_reset_password=True)
            .create(
                {
                    "name": "Automation Log Internal",
                    "login": "automation_log_internal_acl",
                    "group_ids": [Command.set([self.env.ref("base.group_user").id])],
                }
            )
        )
        with self.assertRaises(AccessError):
            self.env["plasticos.automation.log"].with_user(user).create(
                {
                    "name": "forged",
                    "model_name": "res.partner",
                    "res_id": user.partner_id.id,
                    "action_type": "stock_alert",
                }
            )
