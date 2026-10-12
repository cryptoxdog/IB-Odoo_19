"""GMP-NC-B B-03: normalization needs no elevation and forges no audit log.

Runs under ``odoo --test-enable --test-tags /plasticos_intake_normalizer``.
"""

from __future__ import annotations

from odoo import Command
from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestNormalizerPrivilege(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.internal_user = (
            cls.env["res.users"]
            .with_context(no_reset_password=True)
            .create(
                {
                    "name": "Normalizer Internal",
                    "login": "nc_b_normalizer_internal",
                    "group_ids": [Command.set([cls.env.ref("base.group_user").id])],
                }
            )
        )
        polymer = cls.env["plasticos.polymer"].search([("code", "=", "HDPE")], limit=1) or cls.env[
            "plasticos.polymer"
        ].create({"name": "HDPE", "code": "HDPE"})
        form = cls.env["plasticos.material.form"].create({"name": "NC-B Pellet", "code": "ncbpellet"})
        partner = cls.env["res.partner"].create({"name": "NC-B Normalizer Supplier", "is_company": True})
        cls.intake = cls.env["plasticos.intake"].create(
            {
                "partner_id": partner.id,
                "polymer_id": polymer.id,
                "form_id": form.id,
                "quantity_per_load_lbs": 36000,
            }
        )

    def _log_count(self):
        if "plasticos.automation.log" not in self.env:
            return 0
        return self.env["plasticos.automation.log"].sudo().search_count([("res_id", "=", self.intake.id)])

    def test_internal_user_reads_config_without_elevation(self):
        config = self.env["plasticos.normalizer.config"].with_user(self.internal_user).get_config()
        self.assertTrue(config.batch_limit)

    def test_internal_user_normalizes_without_forging_a_log(self):
        before = self._log_count()
        self.intake.with_user(self.internal_user).action_normalize()
        self.assertTrue(self.intake.normalized)
        self.assertEqual(self.intake.match_status, "normalized")
        self.assertEqual(self._log_count(), before)

    def test_internal_user_cannot_create_automation_log_directly(self):
        if "plasticos.automation.log" not in self.env:
            return
        with self.assertRaises(AccessError):
            self.env["plasticos.automation.log"].with_user(self.internal_user).create(
                {
                    "name": "forged",
                    "model_name": "plasticos.intake",
                    "res_id": self.intake.id,
                    "action_type": "stock_alert",
                }
            )
