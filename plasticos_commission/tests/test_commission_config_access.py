"""GMP-NC-B B-01: the public commission budget setter is a Settings-only operation.

Runs under ``odoo --test-enable --test-tags /plasticos_commission``.
"""

from __future__ import annotations

from odoo import Command
from odoo.exceptions import AccessError
from odoo.service.model import get_public_method
from odoo.tests import TransactionCase, tagged

NEW_KEY = "plasticos.commission.max_budget_tokens"
LEGACY_KEY = "plasticos.commission.max_tokens"


@tagged("post_install", "-at_install")
class TestCommissionConfigAccess(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Users = cls.env["res.users"].with_context(no_reset_password=True)
        cls.internal_user = Users.create(
            {
                "name": "Budget Internal",
                "login": "nc_b_budget_internal",
                "group_ids": [Command.set([cls.env.ref("base.group_user").id])],
            }
        )
        cls.commission_manager = Users.create(
            {
                "name": "Budget Commission Manager",
                "login": "nc_b_budget_commission_mgr",
                "group_ids": [
                    Command.set(
                        [
                            cls.env.ref("base.group_user").id,
                            cls.env.ref("plasticos_commission.group_plasticos_commission_manager").id,
                        ]
                    )
                ],
            }
        )
        cls.settings_admin = Users.create(
            {
                "name": "Budget Settings Admin",
                "login": "nc_b_budget_settings",
                "group_ids": [Command.set([cls.env.ref("base.group_system").id])],
            }
        )
        cls.icp = cls.env["ir.config_parameter"].sudo()
        cls.icp.set_param(NEW_KEY, "1000")
        cls.icp.set_param(LEGACY_KEY, "1000")

    def _params(self):
        return self.icp.get_param(NEW_KEY), self.icp.get_param(LEGACY_KEY)

    def _config(self, user):
        return self.env["plasticos.commission.config"].with_user(user)

    def test_setter_is_rpc_reachable(self):
        model = self.env["plasticos.commission.config"]
        self.assertTrue(get_public_method(model, "set_max_budget_tokens"))

    def test_settings_admin_sets_both_keys(self):
        self._config(self.settings_admin).set_max_budget_tokens(2048)
        self.assertEqual(self._params(), ("2048", "2048"))

    def test_internal_user_is_denied_and_nothing_changes(self):
        with self.assertRaises(AccessError):
            self._config(self.internal_user).set_max_budget_tokens(999999)
        self.assertEqual(self._params(), ("1000", "1000"))

    def test_commission_manager_without_settings_is_denied(self):
        with self.assertRaises(AccessError):
            self._config(self.commission_manager).set_max_budget_tokens(999999)
        self.assertEqual(self._params(), ("1000", "1000"))

    def test_unauthorized_invalid_value_is_denied_before_validation(self):
        with self.assertRaises(AccessError):
            self._config(self.internal_user).set_max_budget_tokens(-1)
        self.assertEqual(self._params(), ("1000", "1000"))

    def test_invalid_values_remain_rejected_for_admin(self):
        for bad in (0, -5):
            with self.assertRaises(ValueError):
                self._config(self.settings_admin).set_max_budget_tokens(bad)
        self.assertEqual(self._params(), ("1000", "1000"))

    def test_getter_still_serves_ordinary_users_with_fallbacks(self):
        config = self._config(self.internal_user)
        self.assertEqual(config.get_max_budget_tokens(), 1000)
        self.icp.set_param(NEW_KEY, False)
        self.icp.set_param(LEGACY_KEY, "3000")
        self.assertEqual(config.get_max_budget_tokens(), 3000)
        self.icp.set_param(LEGACY_KEY, False)
        self.assertEqual(config.get_max_budget_tokens(), 4096)

    def test_no_broader_parameter_access_for_internal_user(self):
        icp = self.env["ir.config_parameter"].with_user(self.internal_user)
        with self.assertRaises(AccessError):
            icp.get_param(NEW_KEY)
        with self.assertRaises(AccessError):
            icp.set_param(NEW_KEY, "5")
        self.assertEqual(self._params(), ("1000", "1000"))
