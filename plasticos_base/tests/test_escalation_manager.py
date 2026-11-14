"""The shared escalation resolver and routing write (operator decision: managers only, never silent).

An unresolved exception is owned by an eligible manager of the named group. It is never the
salesperson, the cron service user, the superuser or the acting user, and a missing manager is
logged and noted once instead of being dropped.
"""

from odoo import SUPERUSER_ID, fields
from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.tests.common import tagged

LOGGER = "odoo.addons.plasticos_base.models.res_users"
GROUP_XMLID = "plasticos_base.test_escalation_managers"


@tagged("post_install", "-at_install", "escalation_routing")
class TestEscalationManager(PlasticosTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Users = cls.env["res.users"]
        cls.managers = cls.env["res.groups"].create({"name": "Base Escalation Managers"})
        cls.env["ir.model.data"].create(
            {
                "module": "plasticos_base",
                "name": "test_escalation_managers",
                "model": "res.groups",
                "res_id": cls.managers.id,
            }
        )
        cls.cron_user = cls.env.ref("plasticos_base.user_system_cron")
        cls.record = cls.env["res.partner"].create({"name": "Escalation Subject", "is_company": True})

    def _user(self, login, groups=None, **vals):
        group_ids = [self.env.ref("base.group_user").id, *(groups.ids if groups else [])]
        return self.Users.create({"name": login, "login": login, "group_ids": [(6, 0, group_ids)], **vals})

    def _activities(self, summary):
        return self.env["mail.activity"].search(
            [("res_model", "=", "res.partner"), ("res_id", "=", self.record.id), ("summary", "=", summary)]
        )

    def _notes(self):
        self.record.invalidate_recordset(["message_ids"])
        return self.record.message_ids.filtered(lambda message: "Not routed:" in (message.body or ""))

    def _escalate(self, users=None, **kwargs):
        values = {"summary": "ESCALATION: base subject", "note": "Needs a manager.", "label": "base subject escalation"}
        values.update(kwargs)
        return (users or self.Users)._plasticos_escalate_to_manager(self.record, GROUP_XMLID, **values)

    # ── resolver ─────────────────────────────────────────────────────────

    def test_unknown_or_foreign_xmlid_has_no_manager(self):
        self._user("base.esc.present", self.managers)
        self.assertFalse(self.Users._plasticos_escalation_manager("plasticos_base.no_such_group"))
        self.assertFalse(self.Users._plasticos_escalation_manager(""))
        self.assertFalse(self.Users._plasticos_escalation_manager(None))
        # An XML id that names a record of another model is not a group.
        self.assertFalse(self.Users._plasticos_escalation_manager("plasticos_base.user_system_cron"))
        self.assertFalse(self.Users._plasticos_escalation_manager_in_group(self.env["res.groups"]))

    def test_cron_user_superuser_inactive_and_portal_are_never_eligible(self):
        self.assertFalse(self.Users._plasticos_escalation_manager(GROUP_XMLID))
        self.cron_user.write({"group_ids": [fields.Command.link(self.managers.id)]})
        self.Users.browse(SUPERUSER_ID).write({"group_ids": [fields.Command.link(self.managers.id)]})
        self._user("base.esc.inactive", self.managers, active=False)
        self.assertFalse(self.Users._plasticos_escalation_manager(GROUP_XMLID))
        plain = self._user("base.esc.plain")
        self.assertFalse(self.Users._plasticos_escalation_manager(GROUP_XMLID))
        first = self._user("base.esc.first", self.managers)
        self._user("base.esc.second", self.managers)
        owner = self.Users._plasticos_escalation_manager(GROUP_XMLID)
        self.assertEqual(owner, first)
        self.assertNotIn(owner, plain | self.cron_user | self.Users.browse(SUPERUSER_ID))
        self.assertEqual(self.Users._plasticos_escalation_manager(GROUP_XMLID), first, "the pick is deterministic")

    def test_implied_membership_counts(self):
        senior = self.env["res.groups"].create(
            {"name": "Base Senior Managers", "implied_ids": [fields.Command.link(self.managers.id)]}
        )
        owner = self._user("base.esc.implied", senior)
        self.assertEqual(self.Users._plasticos_escalation_manager(GROUP_XMLID), owner)

    def test_company_scopes_the_manager(self):
        home = self.env.company
        other = self.env["res.company"].create({"name": "Base Escalation Other Company"})
        foreign = self._user("base.esc.foreign", self.managers, company_id=other.id, company_ids=[(6, 0, [other.id])])
        self.assertFalse(self.Users._plasticos_escalation_manager(GROUP_XMLID, home))
        self.assertEqual(self.Users._plasticos_escalation_manager(GROUP_XMLID, other), foreign)
        self.assertEqual(self.Users._plasticos_escalation_manager(GROUP_XMLID), foreign)
        local = self._user("base.esc.local", self.managers)
        self.assertEqual(self.Users._plasticos_escalation_manager(GROUP_XMLID, home), local)
        self.assertEqual(self.Users._plasticos_escalation_manager(GROUP_XMLID, other), foreign)

    def test_a_user_without_access_rights_resolves_the_same_manager(self):
        owner = self._user("base.esc.owner", self.managers)
        plain = self._user("base.esc.caller")
        self.assertEqual(self.Users.with_user(plain)._plasticos_escalation_manager(GROUP_XMLID), owner)

    # ── routing write ────────────────────────────────────────────────────

    def test_manager_receives_one_activity_and_reruns_add_none(self):
        owner = self._user("base.esc.route.owner", self.managers)
        caller = self._user("base.esc.route.caller")
        self.assertEqual(self._escalate(), owner)
        self.assertEqual(self._escalate(self.Users.with_user(caller)), owner)
        activities = self._activities("ESCALATION: base subject")
        self.assertEqual(len(activities), 1)
        self.assertEqual(activities.user_id, owner)
        self.assertNotIn(activities.user_id, caller | self.cron_user | self.env.user)
        self.assertFalse(self._notes())

    def test_one_open_off_leaves_idempotency_to_the_caller(self):
        self._user("base.esc.route.repeat", self.managers)
        self._escalate(one_open=False)
        self._escalate(one_open=False)
        self.assertEqual(len(self._activities("ESCALATION: base subject")), 2)

    def test_no_manager_logs_notes_once_and_creates_no_activity(self):
        caller = self._user("base.esc.none.caller")
        with self.assertLogs(LOGGER, level="ERROR") as captured:
            owner = self._escalate(self.Users.with_user(caller))
        self.assertFalse(owner)
        self.assertTrue(any("Not routed: base subject escalation." in line for line in captured.output))
        with self.assertLogs(LOGGER, level="ERROR"):
            self._escalate()
        self.assertEqual(len(self._notes()), 1)
        self.assertFalse(
            self.env["mail.activity"].search([("res_model", "=", "res.partner"), ("res_id", "=", self.record.id)])
        )

    def test_another_obligation_gets_its_own_note(self):
        with self.assertLogs(LOGGER, level="ERROR"):
            self._escalate()
            self._escalate(summary="ESCALATION: other", label="other obligation escalation")
        self.assertEqual(len(self._notes()), 2)

    def test_conflicting_companies_route_to_nobody(self):
        self._user("base.esc.conflict", self.managers)
        other = self.env["res.company"].create({"name": "Base Escalation Conflict Company"})
        with self.assertLogs(LOGGER, level="ERROR") as captured:
            owner = self._escalate(companies=self.env.company | other)
        self.assertFalse(owner)
        self.assertTrue(any("more than one company" in line for line in captured.output))
        self.assertFalse(self._activities("ESCALATION: base subject"))
        self.assertEqual(len(self._notes()), 1)

    def test_company_scoped_route_ignores_a_manager_of_another_company(self):
        other = self.env["res.company"].create({"name": "Base Escalation Scoped Company"})
        self._user("base.esc.scoped.foreign", self.managers, company_id=other.id, company_ids=[(6, 0, [other.id])])
        with self.assertLogs(LOGGER, level="ERROR"):
            self.assertFalse(self._escalate(companies=self.env.company))
        self.assertFalse(self._activities("ESCALATION: base subject"))
        local = self._user("base.esc.scoped.local", self.managers)
        self.assertEqual(self._escalate(companies=self.env.company), local)
        self.assertEqual(self._activities("ESCALATION: base subject").user_id, local)

    # ── owner exclusion and stale owners ────────────────────────────────

    def test_the_record_owner_never_owns_its_escalation(self):
        owner_manager = self._user("base.esc.owner.self", self.managers)
        with self.assertLogs(LOGGER, level="ERROR") as captured:
            self.assertFalse(self._escalate(exclude_users=owner_manager))
        self.assertTrue(any("Not routed: base subject escalation." in line for line in captured.output))
        self.assertFalse(self._activities("ESCALATION: base subject"))
        other = self._user("base.esc.owner.other", self.managers)
        self.assertEqual(self._escalate(exclude_users=owner_manager), other)
        self.assertEqual(self._activities("ESCALATION: base subject").user_id, other)

    def test_the_acting_manager_never_owns_the_escalation_they_raise(self):
        acting = self._user("base.esc.acting", self.managers)
        other = self._user("base.esc.acting.other", self.managers)
        self.assertEqual(self._escalate(self.Users.with_user(acting)), other)
        self.assertEqual(self._activities("ESCALATION: base subject").user_id, other)

    def test_an_open_activity_of_an_ineligible_owner_is_reassigned(self):
        salesperson = self._user("base.esc.stale.sales")
        manager = self._user("base.esc.stale.manager", self.managers)
        self.record.activity_schedule(
            "mail.mail_activity_data_todo", user_id=salesperson.id, summary="ESCALATION: base subject"
        )
        self.assertEqual(self._escalate(), manager)
        activities = self._activities("ESCALATION: base subject")
        self.assertEqual(len(activities), 1, "the old activity is reassigned, not duplicated")
        self.assertEqual(activities.user_id, manager)
        self.assertEqual(self._escalate(), manager)
        self.assertEqual(len(self._activities("ESCALATION: base subject")), 1)

    def test_an_open_activity_of_the_excluded_owner_is_reassigned(self):
        owner_manager = self._user("base.esc.stale.owner", self.managers)
        other = self._user("base.esc.stale.other", self.managers)
        self.record.activity_schedule(
            "mail.mail_activity_data_todo", user_id=owner_manager.id, summary="ESCALATION: base subject"
        )
        self.assertEqual(self._escalate(exclude_users=owner_manager), other)
        self.assertEqual(self._activities("ESCALATION: base subject").user_id, other)

    def test_an_ineligible_open_activity_with_no_manager_is_noted(self):
        salesperson = self._user("base.esc.stale.alone")
        self.record.activity_schedule(
            "mail.mail_activity_data_todo", user_id=salesperson.id, summary="ESCALATION: base subject"
        )
        with self.assertLogs(LOGGER, level="ERROR"):
            self.assertFalse(self._escalate())
        self.assertEqual(len(self._notes()), 1)
        self.assertEqual(self._activities("ESCALATION: base subject").user_id, salesperson)
