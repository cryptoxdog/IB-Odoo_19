"""S11 (contract C12): journey-fact corrections and the Linda sweep cursor.

Witnesses, all as non-superuser users:

* OP11-E01: a correction is revision ``n + 1``; the superseded row stays byte
  identical (same ``ctid``, same stored columns); the reason, author and time are
  stored; ``plasticos.iso.journey.current_fact`` returns the new value. An empty
  reason, an unchanged value, a stale revision, evidence not on the journey, a
  foreign-company journey and a reused operation key are refused. Corrections
  pass the S9 order guard (gate-in before departure) and the Documents guards.
* OP11-E03 (F6): the load sweep keeps its cursor in ``plasticos.linda.sweep.cursor``
  and writes no ``ir.config_parameter``; the 19.0.1.14.24 step moves a stored
  parameter once.
"""

import importlib.util
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests.common import tagged

from .test_s9_logistics_features import FACT, JOURNEY, _S9Case

CURSOR = "plasticos.linda.sweep.cursor"
REQUEST = "plasticos.logistics.request"
PARAM_PREFIX = "plasticos_logistics.linda_load_sweep_cursor."
MIGRATION = Path(__file__).resolve().parents[1] / "migrations" / "19.0.1.14.24"


def _migration(name):
    spec = importlib.util.spec_from_file_location(f"plasticos_logistics_s11_{name}", MIGRATION / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _S11Case(_S9Case):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.lb = cls.env.ref("uom.product_uom_lb")
        cls.logistics = cls._make_user("s11-logistics", "plasticos_security_base.group_logistics")

    @classmethod
    def _make_user(cls, login, group_xmlid, company=None):
        company = company or cls.company
        groups = cls.env.ref("base.group_user") | cls.env.ref(group_xmlid)
        return cls.env["res.users"].create(
            {
                "name": login,
                "login": login,
                "company_id": company.id,
                "company_ids": [(6, 0, company.ids)],
                "group_ids": [(6, 0, groups.ids)],
            }
        )

    def _as(self, user=None):
        return self.env[FACT].with_user(user or self.logistics)

    def _raw(self, fact):
        """The stored row exactly as PostgreSQL holds it: physical id and every column."""
        self.env.flush_all()
        self.env.cr.execute(
            "SELECT ctid::text, row_to_json(f)::text FROM plasticos_iso_journey_fact f WHERE id = %s", [fact.id]
        )
        return self.env.cr.fetchone()

    def _gate_in(self, journey, hours=6, key="g1"):
        doc = self._attach(journey, f"eir-{key}.pdf")
        result = self._as().action_record_gate_in(journey.id, self._ago(hours), self.terminal.id, doc.id, key)
        self.assertEqual(result["status"], "applied", result)
        return self.env[FACT].browse(result["record_id"]), doc


@tagged("post_install", "-at_install", "plasticos", "logistics", "export")
class TestJourneyFactCorrections(_S11Case):
    """OP11-E01 positive witnesses."""

    def test_correction_appends_a_revision_and_keeps_the_original_byte_identical(self):
        journey = self._journey("S11-CORR")
        first, _doc = self._gate_in(journey)
        before = self._raw(first)
        new_time = self._ago(7)
        result = self._as().action_correct_fact(
            first.id, {"occurred_at": new_time}, "EIR shows 07:00, typed as 08:00", "c1"
        )
        self.assertEqual(result["status"], "applied", result)
        corrected = self.env[FACT].browse(result["record_id"])
        self.assertEqual(self._raw(first), before, "the superseded row is untouched, ctid included")
        self.assertEqual((corrected.revision, corrected.supersedes_id, corrected.fact_kind), (2, first, "gate_in"))
        self.assertEqual(corrected.correction_reason, "EIR shows 07:00, typed as 08:00")
        self.assertEqual((corrected.corrected_by, corrected.recorded_by), (self.logistics, self.logistics))
        self.assertTrue(corrected.corrected_at)
        self.assertEqual(corrected.occurred_at, new_time)
        self.assertEqual(corrected.facility_partner_id, self.terminal, "an omitted value keeps the current one")
        current = journey.with_user(self.logistics).current_fact("gate_in")
        self.assertEqual((current, current.occurred_at), (corrected, new_time))
        self.assertEqual(journey.with_user(self.logistics).current_facts(), {"gate_in": corrected})

    def test_same_operation_key_replays_and_writes_nothing(self):
        journey = self._journey("S11-REPLAY")
        first, _doc = self._gate_in(journey)
        args = (first.id, {"occurred_at": self._ago(7)}, "typo", "c-replay")
        applied = self._as().action_correct_fact(*args)
        again = self._as().action_correct_fact(*args)
        self.assertEqual(again, {"status": "already_applied", "record_id": applied["record_id"]})
        self.assertEqual(self.env[FACT].search_count([("journey_id", "=", journey.id)]), 2)

    def test_a_correction_of_the_current_revision_chains(self):
        journey = self._journey("S11-CHAIN")
        first, _doc = self._gate_in(journey)
        second = self._as().action_correct_fact(first.id, {"occurred_at": self._ago(7)}, "first fix", "c1")
        third = self._as().action_correct_fact(second["record_id"], {"occurred_at": self._ago(8)}, "second fix", "c2")
        self.assertEqual(third["status"], "applied", third)
        fact = self.env[FACT].browse(third["record_id"])
        self.assertEqual((fact.revision, fact.supersedes_id.id), (3, second["record_id"]))
        self.assertEqual(journey.current_fact("gate_in"), fact)

    def test_weight_correction_keeps_unit_and_evidence_guards(self):
        journey = self._journey("S11-WEIGHT")
        ticket = self._attach(journey, "scale-ticket.pdf")
        tare = self._as().action_record_container_tare(
            journey.id, 8775, self.lb.id, "scale_ticket", ticket.id, "T-1", "t"
        )
        corrected = self._as().action_correct_fact(tare["record_id"], {"weight": 8757}, "digits transposed", "ct")
        self.assertEqual(corrected["status"], "applied", corrected)
        self.assertEqual(journey.current_fact("container_tare").weight, 8757)
        unit = self.env.ref("uom.product_uom_unit")
        wrong = self._as().action_correct_fact(corrected["record_id"], {"weight_uom_id": unit.id}, "unit", "cu")
        self.assertEqual(wrong["status"], "blocked")
        self.assertIn("not a unit of weight", wrong["reason"])
        documents = self._as().action_correct_fact(
            corrected["record_id"], {"weight_basis": "documents_verified_gross_mass"}, "basis", "cd"
        )
        self.assertEqual(documents["status"], "blocked")
        self.assertIn("not container tare", documents["reason"])


@tagged("post_install", "-at_install", "plasticos", "logistics", "export")
class TestJourneyFactCorrectionRefusals(_S11Case):
    """OP11-E01 negative witnesses: each refusal writes no row."""

    def _refused(self, journey, result, fragment):
        self.assertEqual(result["status"], "blocked", result)
        self.assertIn(fragment, result["reason"])
        self.assertEqual(
            self.env[FACT].search_count([("journey_id", "=", journey.id), ("revision", ">", 1)]), 0, "nothing written"
        )

    def test_empty_reason_is_refused(self):
        journey = self._journey("S11-NOREASON")
        first, _doc = self._gate_in(journey)
        for reason in ("", "   ", None):
            result = self._as().action_correct_fact(first.id, {"occurred_at": self._ago(7)}, reason, "c")
            self._refused(journey, result, "needs its reason")

    def test_unchanged_value_is_refused(self):
        journey = self._journey("S11-NOOP")
        first, _doc = self._gate_in(journey)
        result = self._as().action_correct_fact(first.id, {"occurred_at": first.occurred_at}, "same", "c")
        self._refused(journey, result, "changes nothing")
        result = self._as().action_correct_fact(first.id, {}, "nothing given", "c2")
        self._refused(journey, result, "changes nothing")

    def test_evidence_not_on_the_journey_is_refused(self):
        journey = self._journey("S11-EVID")
        first, _doc = self._gate_in(journey)
        elsewhere = self._attach(self._load(), "unrelated.pdf")
        result = self._as().action_correct_fact(first.id, {"evidence_attachment_id": elsewhere.id}, "new EIR", "c")
        self._refused(journey, result, "attach the original to this container journey first")

    def test_foreign_company_journey_is_refused(self):
        other = self.env["res.company"].create({"name": "S11 Other Co"})
        result = self.env[JOURNEY].action_register_iso_journey(
            other.id, "S11-FOREIGN", "40HC", None, "MSCU7654321", "SL-11", "op-foreign"
        )
        journey = self.env[JOURNEY].browse(result["record_id"])
        doc = self._attach(journey, "eir.pdf")
        doc.company_id = other
        fact_id = self.env[FACT].action_record_gate_in(journey.id, self._ago(5), self.terminal.id, doc.id, "g")[
            "record_id"
        ]
        with self.assertRaises(AccessError):
            self._as().action_correct_fact(fact_id, {"occurred_at": self._ago(6)}, "not mine", "c")
        self.assertEqual(self.env[FACT].search_count([("journey_id", "=", journey.id)]), 1)

    def test_stale_revision_and_reused_key_are_refused(self):
        journey = self._journey("S11-STALE")
        first, _doc = self._gate_in(journey)
        self.assertEqual(
            self._as().action_correct_fact(first.id, {"occurred_at": self._ago(7)}, "fix", "c1")["status"], "applied"
        )
        stale = self._as().action_correct_fact(first.id, {"occurred_at": self._ago(8)}, "late fix", "c2")
        self.assertEqual(stale["status"], "blocked")
        self.assertIn("current revision (2)", stale["reason"])
        reused = self._as().action_correct_fact(first.id, {"occurred_at": self._ago(9)}, "other", "c1")
        self.assertEqual(reused["status"], "blocked")
        self.assertIn("different correction", reused["reason"])
        self.assertEqual(self.env[FACT].search_count([("journey_id", "=", journey.id)]), 2)

    def test_corrections_keep_gate_in_before_departure(self):
        journey = self._journey("S11-ORDER")
        gate_in, _doc = self._gate_in(journey, hours=10)
        sailed = self._as().action_record_departure(
            journey.id, self._ago(5), "MSC Aurora", "AU1", self._attach(journey, "sailed.pdf").id, "d"
        )
        self.assertEqual(sailed["status"], "applied")
        late_gate = self._as().action_correct_fact(gate_in.id, {"occurred_at": self._ago(4)}, "wrong", "c1")
        self._refused(journey, late_gate, "cannot follow its vessel's departure")
        early_sail = self._as().action_correct_fact(sailed["record_id"], {"departed_at": self._ago(11)}, "wrong", "c2")
        self._refused(journey, early_sail, "cannot sail before")

    def test_unknown_field_future_time_and_missing_key_are_refused(self):
        journey = self._journey("S11-SHAPE")
        first, _doc = self._gate_in(journey)
        self._refused(journey, self._as().action_correct_fact(first.id, {"vessel": "X"}, "r", "c"), "has no vessel")
        future = fields.Datetime.now() + timedelta(hours=2)
        self._refused(
            journey, self._as().action_correct_fact(first.id, {"occurred_at": future}, "r", "c"), "in the future"
        )
        self._refused(
            journey, self._as().action_correct_fact(first.id, {"occurred_at": self._ago(7)}, "r", " "), "operation_key"
        )

    def test_a_non_logistics_user_cannot_correct(self):
        journey = self._journey("S11-SALES")
        first, _doc = self._gate_in(journey)
        rep = self._make_user("s11-sales-rep", "plasticos_security_base.group_sales_rep")
        with self.assertRaises(AccessError):
            self._as(rep).action_correct_fact(first.id, {"occurred_at": self._ago(7)}, "r", "c")

    def test_rows_stay_immutable_and_a_first_record_cannot_overwrite(self):
        journey = self._journey("S11-IMMUTABLE")
        first, doc = self._gate_in(journey)
        corrected = self._as().action_correct_fact(first.id, {"occurred_at": self._ago(7)}, "fix", "c1")
        row = self.env[FACT].browse(corrected["record_id"])
        with self.assertRaises(UserError):
            row.with_user(self.logistics).write({"correction_reason": "edited"})
        with self.assertRaises(UserError):
            first.with_user(self.logistics).unlink()
        again = self._as().action_record_gate_in(journey.id, self._ago(9), self.terminal.id, doc.id, "g9")
        self.assertEqual(again["status"], "blocked", "a first-record command never stands in for a correction")
        replay = self._as().action_record_gate_in(journey.id, row.occurred_at, self.terminal.id, doc.id, "g10")
        self.assertEqual(replay, {"status": "already_applied", "record_id": row.id}, "replays the current revision")


@tagged("post_install", "-at_install", "plasticos", "logistics")
class TestLindaSweepCursor(_S11Case):
    """OP11-E03 (F6): the sweep cursor is a Logistics row, not a system parameter."""

    def _domain(self, loads):
        return [("id", "in", loads.ids)]

    def test_sweep_writes_no_system_parameter_and_the_cursor_survives(self):
        self.env[CURSOR].search([]).unlink()
        loads = self._load() | self._load() | self._load()
        Request = self.env[REQUEST].with_context(linda_load_sweep_batch=2)
        Param = type(self.env["ir.config_parameter"])
        with patch.object(Param, "set_param", side_effect=AssertionError("the sweep wrote ir.config_parameter")):
            first = Request._load_sweep_page(self._domain(loads), "ack")
            second = Request._load_sweep_page(self._domain(loads), "ack")
        self.assertEqual(first, loads[:2], "one page of two loads, oldest first")
        cursor = self.env[CURSOR].search([("lane", "=", "ack"), ("company_id", "=", self.env.company.id)])
        self.assertEqual(len(cursor), 1)
        self.assertEqual(second[:1], loads[2:], "the next run continues after the stored cursor")
        self.assertFalse(
            self.env["ir.config_parameter"].sudo().search([("key", "=like", PARAM_PREFIX + "%")]),
            "no sweep cursor parameter exists",
        )
        cursor.invalidate_recordset()
        self.assertEqual(cursor.last_load_id, second[-1].id, "a full page leaves its last id for the next run")

    def test_cursor_is_not_writable_by_logistics_users(self):
        with self.assertRaises(AccessError):
            self.env[CURSOR].with_user(self.logistics).create(
                {"lane": "ack", "company_id": self.company.id, "last_load_id": 1}
            )

    def test_migration_moves_a_stored_parameter_once(self):
        self.env[CURSOR].search([]).unlink()
        params = self.env["ir.config_parameter"].sudo()
        params.set_param(PARAM_PREFIX + "ack", "4242")
        params.set_param(PARAM_PREFIX + "chase", "not-a-number")
        self.env.flush_all()
        post = _migration("post-migrate")
        post.migrate(self.env.cr, "19.0.1.14.23")
        self.env.invalidate_all()
        rows = {row.lane: row.last_load_id for row in self.env[CURSOR].search([])}
        self.assertEqual(rows, {"ack": 4242, "chase": 0})
        self.assertFalse(params.search([("key", "=like", PARAM_PREFIX + "%")]), "the parameters are removed")
        post.migrate(self.env.cr, "19.0.1.14.23")
        self.env.invalidate_all()
        self.assertEqual({row.lane: row.last_load_id for row in self.env[CURSOR].search([])}, rows, "rerun: no change")

    def test_fact_migration_rerun_changes_nothing(self):
        journey = self._journey("S11-MIG")
        first, _doc = self._gate_in(journey)
        before = self._raw(first)
        _migration("pre-migrate").migrate(self.env.cr, "19.0.1.14.23")
        self.env.invalidate_all()
        self.assertEqual(self._raw(first), before)
        self.assertEqual(first.revision, 1)
