"""Logistics Live Control Tower (TASK-032; DEC-007 KPI-drill parity, DEC-011 Linda cases).

Every Control Tower KPI is declared once; its value is ``search_count`` of the domain
its drill opens. The dashboard's SQL attention columns agree with the KPI domains on the
same fixtures. Company isolation and the sales-rep own rule hold; an unreadable source
reads as unavailable, never as zero. The first dashboard tests of this module.
"""

from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests.common import tagged
from odoo.tools import SQL

from .test_s9_logistics_features import LOAD
from .test_s11_linda_approval import LOGISTICS_OPS, MANAGER, _LindaCase

DASHBOARD = "plasticos.load.dashboard"
APPROVAL = "plasticos.linda.approval"


@tagged("post_install", "-at_install", "plasticos", "logistics")
class TestLogisticsControlTower(_LindaCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ops = cls._make_user("ct-logistics-ops", LOGISTICS_OPS)

    def _set(self, load, **values):
        """Fixture only: put a load straight into a state the Control Tower must classify.

        The dashboard is read-only; these tests check its classification, not the
        state machine that the load's own tests cover.
        """
        assignments = SQL(", ").join(SQL("%s = %s", SQL.identifier(name), value) for name, value in values.items())
        # justification: fixture construction for a read-only SQL VIEW; bypasses the state machine on purpose
        self.env.cr.execute(SQL("UPDATE plasticos_load SET %s WHERE id = %s", assignments, load.id))
        load.invalidate_recordset()

    def _kpis(self, user=None):
        model = self.env[DASHBOARD].with_user(user) if user else self.env[DASHBOARD]
        return {kpi["key"]: kpi for kpi in model.control_tower_kpis()}

    def _fixture(self):
        now = fields.Datetime.now()
        loads = {
            name: self._load(name=f"CT-{name}")
            for name in (
                "today",
                "soon",
                "delivering",
                "sla",
                "exception",
                "nobol",
                "carrier",
                "nocarrier",
                "fine",
            )
        }
        self._set(loads["today"], state="scheduled", pickup_datetime=now + timedelta(minutes=5))
        self._set(loads["soon"], state="scheduled", pickup_datetime=now + timedelta(hours=30))
        self._set(loads["delivering"], state="dispatched", delivery_datetime=now + timedelta(hours=20))
        self._set(loads["sla"], state="dispatched", sla_breached=True)
        self._set(loads["exception"], state="exception")
        self._set(loads["nobol"], state="picked_up", bol_pickup_attached=False)
        self._set(loads["carrier"], state="ready_confirmed")
        self._set(loads["nocarrier"], state="scheduled", carrier_id=None)
        self._set(loads["fine"], state="delivered", bol_pickup_attached=True, bol_delivery_attached=True)
        self.env.flush_all()
        return loads

    def test_every_kpi_value_equals_its_drill_count(self):
        """DEC-007: search_count(drill domain) == displayed value, for every declared KPI."""
        self._fixture()
        kpis = self._kpis(self.ops)
        self.assertEqual(
            set(kpis),
            {
                "pickups_today",
                "pickups_next_48h",
                "deliveries_next_48h",
                "needs_attention",
                "linda_held",
                "linda_held_logistics",
                "missing_bol",
                "carrier_unconfirmed",
                "release_blocked",
                "sla_breached",
            },
        )
        for key, kpi in kpis.items():
            with self.subTest(kpi=key):
                self.assertTrue(kpi["available"])
                action = self.env[DASHBOARD].with_user(self.ops).action_drill_kpi(key)
                self.assertEqual(action["res_model"], kpi["model"], "the drill opens the source model")
                self.assertEqual(action["domain"], kpi["domain"])
                drilled = self.env[action["res_model"]].with_user(self.ops).search_count(action["domain"])
                self.assertEqual(drilled, kpi["value"])

    def test_fixture_loads_land_in_their_kpis(self):
        loads = self._fixture()
        kpis = self._kpis(self.ops)

        def ids(key):
            return set(self.env[kpis[key]["model"]].search(kpis[key]["domain"]).ids)

        self.assertIn(loads["today"].id, ids("pickups_next_48h"))
        self.assertIn(loads["soon"].id, ids("pickups_next_48h"))
        self.assertIn(loads["delivering"].id, ids("deliveries_next_48h"))
        self.assertIn(loads["sla"].id, ids("sla_breached"))
        self.assertIn(loads["nobol"].id, ids("missing_bol"))
        self.assertTrue({loads["carrier"].id, loads["nocarrier"].id} <= ids("carrier_unconfirmed"))
        attention = ids("needs_attention")
        for name in ("sla", "exception", "nobol", "carrier", "nocarrier"):
            self.assertIn(loads[name].id, attention, name)
        self.assertNotIn(loads["fine"].id, attention)
        self.assertNotIn(loads["fine"].id, ids("missing_bol"), "a delivered load with both BOLs is not missing one")

    def test_sql_attention_columns_agree_with_kpi_domains(self):
        """The dashboard's Needs Attention / Missing BOL / Carrier filters count what the KPIs count."""
        loads = self._fixture()
        load = loads["today"]
        self._set(load, state="awaiting_ready")
        self._held(load.with_user(self.linda).action_confirm_ready(), "acceptance", "confirm_ready")
        self.env.flush_all()
        kpis = self._kpis(self.ops)
        dashboard = self.env[DASHBOARD].with_user(self.ops)
        mine = [("load_id", "in", self.env[LOAD].search([("name", "like", "CT-")]).ids)]
        source = self.env[LOAD].with_user(self.ops)
        for column, key in (
            ("needs_attention", "needs_attention"),
            ("missing_bol", "missing_bol"),
            ("carrier_unconfirmed", "carrier_unconfirmed"),
        ):
            with self.subTest(column=column):
                rows = dashboard.search([*mine, (column, "=", True)]).mapped("load_id")
                counted = source.search([*kpis[key]["domain"], ("name", "like", "CT-")])
                self.assertEqual(rows, counted)
        row = dashboard.search([("load_id", "=", load.id)])
        self.assertEqual((row.linda_pending, row.attention_reason), (True, "linda"))

    def test_linda_held_counts_and_the_case_is_resolvable_in_place(self):
        load = self._load(name="CT-LINDA")
        self._set(load, state="awaiting_ready")
        approval = self._held(load.with_user(self.linda).action_confirm_ready(), "acceptance", "confirm_ready")
        kpis = self._kpis(self.ops)
        self.assertIn(approval.id, self.env[APPROVAL].search(kpis["linda_held"]["domain"]).ids)
        self.assertIn(approval.id, self.env[APPROVAL].search(kpis["linda_held_logistics"]["domain"]).ids)
        case = approval.with_user(self.ops)
        self.assertEqual(case.affected_load_id, load)
        self.assertTrue(case.can_decide)
        self.assertFalse(approval.with_user(self.logistics).can_decide, "a plain Logistics user cannot decide")
        self.assertEqual(case.action_view_affected_load()["res_id"], load.id)
        self.assertEqual(case.action_approve()["status"], "applied")
        self.assertFalse(approval.with_user(self.ops).can_decide, "a decided case offers no decision")

    def test_unverified_reply_case_shows_the_original_reply(self):
        po, _tx, loads = self._five_container_order()
        reply = self._linda_reply(po, disposition="identity_unverified")
        held = self._linda("plasticos.shipment.event.proposal").action_propose_shipment_event(
            self._loaded_values(loads[0], reply), "ct-reply"
        )
        approval = self._held(held, "unverified_linda_reply", "propose_shipment_event")
        self.assertEqual(approval.with_user(self.ops).original_reply_id, reply)

    def test_release_blocked_is_a_drillable_snapshot(self):
        load = self._load(name="CT-BLOCKED")
        self._set(load, state="scheduled")
        clear = self._load(name="CT-CLEAR")
        self._set(clear, state="scheduled")
        self.env.flush_all()
        original = type(self.env[LOAD])._physical_release_errors

        def errors(record, operation_kind):
            return ["held by owner"] if record.id == load.id else original(record, operation_kind)

        with patch.object(type(self.env[LOAD]), "_physical_release_errors", errors):
            kpi = self._kpis(self.ops)["release_blocked"]
            drilled = self.env[LOAD].search(self.env[DASHBOARD].action_drill_kpi("release_blocked")["domain"])
        self.assertIn(load, drilled)
        self.assertNotIn(clear, drilled)
        self.assertEqual(kpi["value"], len(drilled))

    def test_an_unreadable_source_is_unavailable_not_zero(self):
        real = type(self.env[APPROVAL]).search_count

        def refuse(records, domain, *args, **kwargs):
            raise AccessError("no read on Linda approvals")

        with patch.object(type(self.env[APPROVAL]), "search_count", refuse):
            kpis = self._kpis(self.ops)
        self.assertEqual((kpis["linda_held"]["available"], kpis["linda_held"]["value"]), (False, None))
        self.assertTrue(kpis["sla_breached"]["available"])
        self.assertIsInstance(kpis["sla_breached"]["value"], int)
        self.assertIs(type(self.env[APPROVAL]).search_count, real)

    def test_company_isolation(self):
        other = self.env["res.company"].create({"name": "CT Other Co"})
        mine = self._load(name="CT-MINE")
        theirs = self._load(name="CT-THEIRS", company_id=other.id)
        for load in (mine, theirs):
            self._set(load, state="exception")
        self.env.flush_all()
        ids = set(self.env[LOAD].with_user(self.ops).search(self._kpis(self.ops)["needs_attention"]["domain"]).ids)
        self.assertIn(mine.id, ids)
        self.assertNotIn(theirs.id, ids)
        rows = self.env[DASHBOARD].with_user(self.ops).search([("load_id", "in", (mine | theirs).ids)])
        self.assertEqual(rows.mapped("load_id"), mine)

    def test_sales_rep_sees_only_own_loads(self):
        _po, tx, loads = self._five_container_order()
        rep = self._make_user("ct-rep", "plasticos_security_base.group_sales_rep")
        other_rep = self._make_user("ct-rep-2", "plasticos_security_base.group_sales_rep")
        tx.sudo().user_id = rep  # sudo: fixture ownership of the deal
        self.env.flush_all()
        own = self.env[DASHBOARD].with_user(rep).search([("load_id", "in", loads.ids)])
        self.assertEqual(own.mapped("load_id"), loads)
        self.assertFalse(self.env[DASHBOARD].with_user(other_rep).search([("load_id", "in", loads.ids)]))

    def test_an_unknown_kpi_is_refused(self):
        with self.assertRaises(UserError):
            self.env[DASHBOARD].action_drill_kpi("no_such_kpi")

    def test_operations_manager_sees_the_same_counts(self):
        self._fixture()
        manager = self._kpis(self.manager)
        ops = self._kpis(self.ops)
        for key in ("needs_attention", "missing_bol", "carrier_unconfirmed", "sla_breached"):
            self.assertEqual(manager[key]["value"], ops[key]["value"], key)
        self.assertTrue(self.manager.has_group(MANAGER))
