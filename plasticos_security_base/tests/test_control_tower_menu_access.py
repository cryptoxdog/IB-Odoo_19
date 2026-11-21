"""DEC-005: the Logistics Control Tower menu and server action are role-restricted (TASK-032).

The binding lives in this module (security/control_tower_menu_groups.xml) because
plasticos_logistics owns the records but cannot name these groups.
"""

from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase, tagged

MENU = "plasticos_logistics.menu_logistics_control_tower"
ACTION = "plasticos_logistics.action_logistics_control_tower"
TOWER = "plasticos.logistics.control.tower"
ALLOWED = (
    "plasticos_security_base.group_logistics",
    "plasticos_security_base.group_logistics_ops",
    "plasticos_security_base.group_operations_manager",
)


@tagged("post_install", "-at_install", "plasticos", "security")
class TestControlTowerMenuAccess(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.menu = cls.env.ref(MENU)
        cls.action = cls.env.ref(ACTION)

    def _user(self, login, group_xmlid=None):
        groups = self.env.ref("base.group_user")
        if group_xmlid:
            groups |= self.env.ref(group_xmlid)
        return self.env["res.users"].create({"name": login, "login": login, "group_ids": [(6, 0, groups.ids)]})

    def _sees_menu(self, user):
        return self.menu.id in self.env["ir.ui.menu"].with_user(user)._visible_menu_ids()

    def test_menu_and_action_carry_exactly_the_three_roles(self):
        expected = {self.env.ref(xmlid) for xmlid in ALLOWED}
        self.assertEqual(set(self.menu.group_ids), expected)
        self.assertEqual(set(self.action.group_ids), expected)

    def test_a_plain_internal_user_does_not_see_the_menu_and_is_refused(self):
        plain = self._user("ct-menu-plain")
        rep = self._user("ct-menu-rep", "plasticos_security_base.group_sales_rep")
        for user in (plain, rep):
            with self.subTest(user=user.login):
                self.assertFalse(self._sees_menu(user))
                with self.assertRaises(AccessError):
                    self.action.with_user(user).run()

    def test_each_allowed_role_sees_the_menu_and_opens_the_tiles(self):
        for xmlid in ALLOWED:
            with self.subTest(group=xmlid):
                user = self._user(f"ct-menu-{xmlid.rsplit('.', 1)[1]}", xmlid)
                self.assertTrue(self._sees_menu(user))
                result = self.action.with_user(user).with_context(active_model=TOWER).run()
                self.assertEqual((result["res_model"], result["view_mode"]), (TOWER, "form"))
