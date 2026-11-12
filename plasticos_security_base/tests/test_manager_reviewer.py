"""res.users._plasticos_manager_reviewer names one deterministic manager, or nobody."""

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.tests.common import tagged

GROUP_XMLID = "plasticos_security_base.test_manager_reviewer_group"


@tagged("post_install", "-at_install", "plasticos", "security")
class TestManagerReviewer(PlasticosTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Users = cls.env["res.users"]
        cls.group = cls.env["res.groups"].create({"name": "Manager Reviewer Test Group"})
        cls.env["ir.model.data"].create(
            {
                "module": "plasticos_security_base",
                "name": "test_manager_reviewer_group",
                "model": "res.groups",
                "res_id": cls.group.id,
            }
        )
        cls.internal = cls.env.ref("base.group_user")

    def _user(self, login, groups):
        return self.Users.create({"name": login, "login": login, "group_ids": [(6, 0, groups.ids)]})

    def test_empty_group_returns_nobody(self):
        self.assertFalse(self.Users._plasticos_manager_reviewer(GROUP_XMLID))

    def test_unknown_or_non_group_xmlid_returns_nobody(self):
        self.assertFalse(self.Users._plasticos_manager_reviewer("plasticos_security_base.no_such_group"))
        self.assertFalse(self.Users._plasticos_manager_reviewer("base.main_company"))

    def test_lowest_id_eligible_member_wins(self):
        self._user("reviewer_outsider", self.internal)
        first = self._user("reviewer_first", self.internal | self.group)
        second = self._user("reviewer_second", self.internal | self.group)
        self.assertLess(first.id, second.id)
        self.assertEqual(self.Users._plasticos_manager_reviewer(GROUP_XMLID), first)
        self.assertEqual(self.Users.with_user(second)._plasticos_manager_reviewer(GROUP_XMLID), first)

    def test_cron_user_archived_and_portal_members_are_not_eligible(self):
        cron_user = self.env.ref("plasticos_base.user_system_cron")
        cron_user.write({"group_ids": [(4, self.group.id)]})
        self.assertTrue(cron_user.has_group(GROUP_XMLID))
        self.assertFalse(self.Users._plasticos_manager_reviewer(GROUP_XMLID))

        archived = self._user("reviewer_archived", self.internal | self.group)
        archived.active = False
        portal = self._user("reviewer_portal", self.env.ref("base.group_portal") | self.group)
        self.assertTrue(portal.share)
        self.assertFalse(self.Users._plasticos_manager_reviewer(GROUP_XMLID))

        eligible = self._user("reviewer_eligible", self.internal | self.group)
        self.assertEqual(self.Users._plasticos_manager_reviewer(GROUP_XMLID), eligible)
