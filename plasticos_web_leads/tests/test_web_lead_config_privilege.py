"""GMP-NC-B: re-triage reads provider keys with the caller's own rights.

``action_retry_triage`` is public and ``base.group_user`` may call it, but only
``base.group_system`` may write a web lead or read provider API keys. The
pipeline must deny an ordinary user before any key is read or any provider is
called. Runs under ``odoo --test-enable --test-tags /plasticos_web_leads``.
"""

from __future__ import annotations

from unittest.mock import patch

from odoo import Command
from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged

from .test_broker_one_pass import one_pass_orchestration

_WEB_LEAD = "odoo.addons.plasticos_web_leads.models.web_lead"


@tagged("post_install", "-at_install")
class TestWebLeadConfigPrivilege(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.config = cls.env["plasticos.web.lead.config"].sudo().get_config()
        cls.config.write(
            {
                "ai_enabled": True,
                "vision_enabled": False,
                "text_inference_provider": "openai",
                "openai_api_key": "sk-nc-b-test-not-real",
            }
        )
        cls.internal_user = (
            cls.env["res.users"]
            .with_context(no_reset_password=True)
            .create(
                {
                    "name": "Web Lead Internal",
                    "login": "nc_b_web_lead_internal",
                    "group_ids": [Command.set([cls.env.ref("base.group_user").id])],
                }
            )
        )
        cls.admin = cls.env.ref("base.user_admin")
        cls.lead = cls.env["plasticos.web.lead"].create(
            {"lead_id": "NC-B-RETRY-001", "state": "error", "company_name": "NC-B Retry Co"}
        )

    def test_internal_user_is_denied_before_any_provider_call(self):
        with (
            patch(f"{_WEB_LEAD}.ai_normalizer.normalize_with_provider") as normalize,
            patch(f"{_WEB_LEAD}.evaluate_economic_opportunity") as economic,
            self.assertRaises(AccessError),
            self.env.cr.savepoint(),
        ):
            self.lead.with_user(self.internal_user).action_retry_triage()
        normalize.assert_not_called()
        economic.assert_not_called()
        self.assertEqual(self.lead.state, "error")

    def test_internal_user_cannot_read_provider_key_through_config(self):
        config = self.env["plasticos.web.lead.config"].with_user(self.internal_user).get_config()
        with self.assertRaises(AccessError):
            config.get_inference_provider("text_normalization")

    def test_settings_admin_still_reaches_the_provider(self):
        if one_pass_orchestration():
            with (
                patch(f"{_WEB_LEAD}.run_broker_inference", return_value={"status": "skipped"}) as broker,
                patch(f"{_WEB_LEAD}.ai_normalizer.normalize_with_provider") as normalize,
                patch(f"{_WEB_LEAD}.evaluate_economic_opportunity", return_value={"status": "skipped"}) as economic,
            ):
                self.lead.with_user(self.admin).action_retry_triage()
            broker.assert_called_once()
            normalize.assert_not_called()
            economic.assert_not_called()
            return
        with (
            patch(
                f"{_WEB_LEAD}.ai_normalizer.normalize_with_provider",
                return_value={"_provider_used": "openai"},
            ) as normalize,
            patch(f"{_WEB_LEAD}.evaluate_economic_opportunity", return_value={"status": "skipped"}),
        ):
            self.lead.with_user(self.admin).action_retry_triage()
        normalize.assert_called_once()
