"""S11 (OP11-E02, coordinator C12-SCOPE-2): Linda's edge cases wait for an Operations Manager.

Linda is ``plasticos_logistics.user_linda``. Each edge-case class has a positive
witness (Linda is held; an Operations Manager's approval applies it as Linda) and
a negative one (Linda and a Logistics user without manager rights cannot
approve; a person needs no second approver; a straight-through Linda outcome
applies at once). All actors are non-superuser users.
"""

import importlib.util
import tempfile
from pathlib import Path
from unittest.mock import patch

from odoo.exceptions import AccessError, UserError
from odoo.modules.module import get_module_path
from odoo.tests.common import tagged
from odoo.tools import mute_logger

from . import test_s9_logistics_features as s9
from .test_s9_logistics_features import FACT, JOURNEY, PROPOSAL
from .test_s11_fact_corrections import _S11Case

APPROVAL = "plasticos.linda.approval"
MANAGER = "plasticos_security_base.group_operations_manager"
LOGISTICS = "plasticos_security_base.group_logistics"


def _reach_module():
    path = Path(__file__).with_name("linda_gate_reach.py")
    spec = importlib.util.spec_from_file_location("plasticos_logistics_linda_gate_reach", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _LindaCase(_S11Case):
    # Borrowed through the module, so the S9 class is not collected a second time here.
    _five_container_order = s9.TestShipmentEventProposals._five_container_order
    _linda_reply = s9.TestShipmentEventProposals._linda_reply

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.linda = cls.env.ref("plasticos_logistics.user_linda")
        cls.manager = cls._make_user("s11-ops-manager", MANAGER)

    def _linda(self, model=FACT):
        return self.env[model].with_user(self.linda)

    def _held(self, result, edge_case, command):
        self.assertEqual(result["status"], "pending", result)
        approval = self.env[APPROVAL].browse(result["approval_id"])
        self.assertEqual((approval.state, approval.edge_case, approval.command), ("pending", edge_case, command))
        self.assertEqual(approval.requested_by, self.linda)
        return approval

    def _approve(self, approval, user=None):
        return approval.with_user(user or self.manager).action_approve("checked against the original")

    def _no_approvals(self, key):
        self.assertFalse(self.env[APPROVAL].search([("operation_key", "=", key)]))


@tagged("post_install", "-at_install", "plasticos", "logistics", "export")
class TestLindaIdentity(_LindaCase):
    def test_linda_is_a_logistics_service_user_and_nothing_more(self):
        linda = self.linda
        self.assertTrue(linda.active)
        self.assertFalse(linda.share)
        self.assertTrue(linda.has_group(LOGISTICS))
        for group in (
            MANAGER,
            "plasticos_security_base.group_logistics_ops",
            "plasticos_security_base.group_sales_rep",
            "plasticos_security_base.group_accounting",
            "base.group_system",
            "base.group_erp_manager",
        ):
            self.assertFalse(linda.has_group(group), group)
        explicit = linda.group_ids - self.env.ref("base.group_user") - self.env.ref(LOGISTICS)
        self.assertFalse(explicit, "Linda holds no group besides Logistics (and the internal user type)")
        self.env.cr.execute("SELECT password FROM res_users WHERE id = %s", [linda.id])
        self.assertFalse(self.env.cr.fetchone()[0], "Linda has no password and cannot log in")

    def test_no_cron_runs_as_linda(self):
        crons = self.env["ir.cron"].with_context(active_test=False).search([("user_id", "=", self.linda.id)])
        self.assertFalse(crons, "crons are not reassigned to Linda")


@tagged("post_install", "-at_install", "plasticos", "logistics", "export")
class TestLindaCorrections(_LindaCase):
    """Edge case: every Linda correction."""

    def test_linda_correction_waits_for_an_operations_manager(self):
        journey = self._journey("S11-L-CORR")
        first, _doc = self._gate_in(journey)
        new_time = self._ago(7)
        held = self._linda().action_correct_fact(first.id, {"occurred_at": new_time}, "EIR says 07:00", "lc1")
        approval = self._held(held, "correction", "correct_fact")
        self.assertEqual(self.env[FACT].search_count([("journey_id", "=", journey.id)]), 1, "nothing written yet")
        self.assertEqual(
            self._linda().action_correct_fact(first.id, {"occurred_at": new_time}, "EIR says 07:00", "lc1"),
            held,
            "a repeated held command answers the same pending approval",
        )
        result = self._approve(approval)
        self.assertEqual(result["status"], "applied", result)
        corrected = journey.current_fact("gate_in")
        self.assertEqual((corrected.revision, corrected.occurred_at), (2, new_time))
        self.assertEqual((corrected.corrected_by, corrected.recorded_by), (self.linda, self.linda))
        self.assertEqual(
            (approval.state, approval.decided_by, approval.result_status), ("approved", self.manager, "applied")
        )
        replay = self._linda().action_correct_fact(first.id, {"occurred_at": new_time}, "EIR says 07:00", "lc1")
        self.assertEqual(replay, {"status": "already_applied", "record_id": corrected.id})

    def test_linda_and_non_manager_logistics_cannot_approve(self):
        journey = self._journey("S11-L-NOAPPROVE")
        first, _doc = self._gate_in(journey)
        approval = self._held(
            self._linda().action_correct_fact(first.id, {"occurred_at": self._ago(7)}, "fix", "lc2"),
            "correction",
            "correct_fact",
        )
        for user in (self.linda, self.logistics):
            with self.subTest(user=user.login), self.assertRaises(AccessError):
                approval.with_user(user).action_approve()
            with self.subTest(user=user.login), self.assertRaises(AccessError):
                approval.with_user(user).action_reject()
        self.assertEqual(approval.state, "pending")
        with self.assertRaises(UserError):
            approval.with_user(self.manager).write({"state": "approved"})
        self.assertEqual(self.env[FACT].search_count([("journey_id", "=", journey.id)]), 1)

    def test_a_person_needs_no_second_approver(self):
        journey = self._journey("S11-L-HUMAN")
        first, _doc = self._gate_in(journey)
        result = self._as().action_correct_fact(first.id, {"occurred_at": self._ago(7)}, "fix", "hc1")
        self.assertEqual(result["status"], "applied")
        self._no_approvals("hc1")

    def test_a_plain_refusal_is_not_held(self):
        journey = self._journey("S11-L-PLAIN")
        first, _doc = self._gate_in(journey)
        refused = self._linda().action_correct_fact(first.id, {"occurred_at": self._ago(7)}, "", "lc3")
        self.assertEqual(refused["status"], "blocked")
        self._no_approvals("lc3")


@tagged("post_install", "-at_install", "plasticos", "logistics", "export")
class TestLindaRecords(_LindaCase):
    """Edge cases of a first record: conflict, sequence, unit, evidence, retry; and straight-through."""

    def test_straight_through_record_applies_as_linda(self):
        journey = self._journey("S11-L-STRAIGHT")
        doc = self._attach(journey, "eir.pdf")
        when = self._ago(5)
        result = self._linda().action_record_gate_in(journey.id, when, self.terminal.id, doc.id, "ls1")
        self.assertEqual(result["status"], "applied", result)
        self.assertEqual(self.env[FACT].browse(result["record_id"]).recorded_by, self.linda)
        self._no_approvals("ls1")
        same = self._linda().action_record_gate_in(journey.id, when, self.terminal.id, doc.id, "ls1b")
        self.assertEqual(same["status"], "already_applied", "the same fact again is straight-through")

    def test_conflicting_value_is_held_and_approval_supersedes(self):
        journey = self._journey("S11-L-CONFLICT")
        first, doc = self._gate_in(journey, hours=6)
        later = self._ago(5)
        held = self._linda().action_record_gate_in(journey.id, later, self.terminal.id, doc.id, "lv1")
        approval = self._held(held, "value_conflict", "record_gate_in")
        self.assertEqual(journey.current_fact("gate_in"), first)
        result = self._approve(approval)
        self.assertEqual(result["status"], "applied", result)
        current = journey.current_fact("gate_in")
        self.assertEqual((current.revision, current.supersedes_id, current.occurred_at), (2, first, later))
        self.assertIn(f"Linda approval {approval.id}", current.correction_reason)
        human = self._as().action_record_gate_in(journey.id, self._ago(4), self.terminal.id, doc.id, "hv1")
        self.assertEqual(human["status"], "blocked", "a person's conflicting record is refused, not held")
        self._no_approvals("hv1")

    def test_out_of_sequence_is_held(self):
        journey = self._journey("S11-L-SEQ")
        doc = self._attach(journey, "sailed.pdf")
        held = self._linda().action_record_departure(journey.id, self._ago(2), "MSC Aurora", "A1", doc.id, "lq1")
        approval = self._held(held, "out_of_sequence", "record_departure")
        self.assertFalse(self.env[FACT].search([("journey_id", "=", journey.id)]))
        result = self._approve(approval)
        self.assertEqual(result["status"], "blocked", "approval runs the owner command; its guard still refuses")
        self.assertEqual((approval.state, approval.result_status), ("approved", "blocked"))
        self.assertFalse(self.env[FACT].search([("journey_id", "=", journey.id)]))
        human = self._as().action_record_departure(journey.id, self._ago(2), "MSC Aurora", "A1", doc.id, "hq1")
        self.assertEqual(human["status"], "blocked")
        self._no_approvals("hq1")

    def test_unit_mismatch_is_held(self):
        journey = self._journey("S11-L-UNIT")
        ticket = self._attach(journey, "ticket.pdf")
        unit = self.env.ref("uom.product_uom_unit")
        held = self._linda().action_record_container_tare(
            journey.id, 8775, unit.id, "scale_ticket", ticket.id, "T-1", "lu1"
        )
        self._held(held, "unit_mismatch", "record_container_tare")
        self.assertFalse(self.env[FACT].search([("journey_id", "=", journey.id)]))
        ok = self._linda().action_record_container_tare(
            journey.id, 8775, self.lb.id, "scale_ticket", ticket.id, "T-1", "lu2"
        )
        self.assertEqual(ok["status"], "applied", "the right unit is straight-through")

    def test_unverified_evidence_is_held(self):
        journey = self._journey("S11-L-EVID")
        elsewhere = self._attach(self._load(), "unrelated.pdf")
        held = self._linda().action_record_gate_in(journey.id, self._ago(5), self.terminal.id, elsewhere.id, "le1")
        self._held(held, "evidence_unverified", "record_gate_in")
        missing = self._linda().action_record_gate_in(journey.id, self._ago(5), self.terminal.id, None, "le2")
        self._held(missing, "evidence_unverified", "record_gate_in")
        self.assertFalse(self.env[FACT].search([("journey_id", "=", journey.id)]))

    def test_unreadable_evidence_is_held_without_disclosure(self):
        """Codex P2: an original Linda cannot read is unverified evidence, held, not an AccessError."""
        other = self.env["res.company"].create({"name": "S11 Linda Other Co"})
        foreign = self.env[JOURNEY].browse(
            self.env[JOURNEY].action_register_iso_journey(
                other.id, "S11-L-FOREIGN", "40HC", None, "MSCU7654321", "SL-11", "op-l-foreign"
            )["record_id"]
        )
        hidden = self._attach(foreign, "other-company-eir.pdf")
        hidden.company_id = other
        journey = self._journey("S11-L-HIDDEN")
        held = self._linda().action_record_gate_in(journey.id, self._ago(5), self.terminal.id, hidden.id, "lh1")
        approval = self._held(held, "evidence_unverified", "record_gate_in")
        self.assertNotIn("other-company-eir", approval.edge_reason, "the refusal names nothing it cannot show")
        self.assertFalse(self.env[FACT].search([("journey_id", "=", journey.id)]))
        with self.assertRaises(AccessError):
            self._as().action_record_gate_in(journey.id, self._ago(5), self.terminal.id, hidden.id, "hh1")

    def test_concurrent_filing_answers_the_winning_approval(self):
        """Codex P2: a filing that loses the pending index answers the winner, never an IntegrityError."""
        journey = self._journey("S11-L-RACE")
        doc = self._attach(journey, "sailed.pdf")
        args = (journey.id, self._ago(2), "MSC Aurora", "A1", doc.id, "lrace")
        winner = self._held(self._linda().action_record_departure(*args), "out_of_sequence", "record_departure")
        approval_class = type(self.env[APPROVAL])
        original = approval_class.search
        calls = []

        def miss_first(model, domain, *rest, **kwargs):
            calls.append(domain)
            if len(calls) == 1:
                return model.browse()
            return original(model, domain, *rest, **kwargs)

        with patch.object(approval_class, "search", miss_first), mute_logger("odoo.sql_db"):
            again = self._linda().action_record_departure(*args)
        self.assertEqual(again["status"], "pending")
        self.assertEqual(again["approval_id"], winner.id)
        self.assertEqual(self.env[APPROVAL].search_count([("operation_key", "=", "lrace")]), 1)

    def test_retry_after_a_rejection_is_held_again(self):
        journey = self._journey("S11-L-RETRY")
        doc = self._attach(journey, "sailed.pdf")
        args = (journey.id, self._ago(2), "MSC Aurora", "A1", doc.id, "lr1")
        first = self._held(self._linda().action_record_departure(*args), "out_of_sequence", "record_departure")
        first.with_user(self.manager).action_reject("no gate-in on file")
        self.assertEqual((first.state, first.decided_by), ("rejected", self.manager))
        gate_in, _eir = self._gate_in(journey, hours=5)
        retried = self._linda().action_record_departure(*args)
        retry = self._held(retried, "refusal_retry", "record_departure")
        self.assertNotEqual(retry, first)
        self.assertEqual(self._approve(retry)["status"], "applied")
        self.assertEqual(journey.current_fact("departure").recorded_by, self.linda)


@tagged("post_install", "-at_install", "plasticos", "logistics", "export")
class TestLindaProposals(_LindaCase):
    """Edge cases: a proposal citing an unverified Linda reply, and any Linda acceptance."""

    def _loaded_values(self, load, reply=None):
        values = {
            "event_kind": "loaded",
            "load_id": load.id,
            "occurred_at": self._ago(30),
            "evidence_attachment_id": self._attach(load, "booking complete.eml").id,
            "asserted_by": "supplier_reported",
        }
        if reply:
            values["linda_response_id"] = reply.id
        return values

    def test_unverified_linda_reply_proposal_is_held(self):
        po, _tx, loads = self._five_container_order()
        for disposition in ("unresolved", "identity_unverified"):
            with self.subTest(disposition=disposition):
                reply = self._linda_reply(po, disposition=disposition)
                key = f"lp-{disposition}"
                held = self._linda(PROPOSAL).action_propose_shipment_event(self._loaded_values(loads[0], reply), key)
                approval = self._held(held, "unverified_linda_reply", "propose_shipment_event")
                self.assertFalse(self.env[PROPOSAL].search([("operation_key", "=", key)]), "no proposal yet")
                result = self._approve(approval)
                self.assertEqual(result["status"], "applied", result)
                proposal = self.env[PROPOSAL].browse(result["record_id"])
                self.assertEqual((proposal.state, proposal.create_uid), ("candidate", self.linda))

    def test_invalid_linda_proposal_is_refused_not_held(self):
        po, _tx, loads = self._five_container_order()
        reply = self._linda_reply(po)
        values = self._loaded_values(loads[0], reply)
        values["asserted_by"] = "carrier_issued"
        refused = self._linda(PROPOSAL).action_propose_shipment_event(values, "lp-bad")
        self.assertEqual(refused["status"], "blocked")
        self._no_approvals("lp-bad")
        self.assertFalse(self.env[PROPOSAL].search([("operation_key", "=", "lp-bad")]))

    def test_straight_through_proposal_and_human_citation_apply(self):
        po, _tx, loads = self._five_container_order()
        plain = self._linda(PROPOSAL).action_propose_shipment_event(self._loaded_values(loads[0]), "lp-plain")
        self.assertEqual(plain["status"], "applied", "Linda without a cited reply is straight-through")
        reply = self._linda_reply(po)
        human = (
            self.env[PROPOSAL]
            .with_user(self.logistics)
            .action_propose_shipment_event(self._loaded_values(loads[1], reply), "hp-1")
        )
        self.assertEqual(human["status"], "applied", "a person citing the same reply needs no approver")
        self._no_approvals("lp-plain")
        self._no_approvals("hp-1")

    def test_linda_acceptance_is_held_until_approved(self):
        _po, _tx, loads = self._five_container_order()
        proposed = (
            self.env[PROPOSAL]
            .with_user(self.logistics)
            .action_propose_shipment_event(self._loaded_values(loads[0]), "la-1")
        )
        proposal = self.env[PROPOSAL].browse(proposed["record_id"])
        held = proposal.with_user(self.linda).action_accept("ticket matches")
        approval = self._held(held, "acceptance", "accept_shipment_event")
        self.assertEqual(proposal.state, "candidate")
        self.assertFalse(loads[0].actual_pickup_at)
        for user in (self.linda, self.logistics):
            with self.subTest(user=user.login), self.assertRaises(AccessError):
                approval.with_user(user).action_approve()
        result = self._approve(approval)
        self.assertEqual(result["status"], "applied", result)
        proposal.invalidate_recordset()
        self.assertEqual((proposal.state, proposal.decided_by), ("accepted", self.linda))
        self.assertTrue(loads[0].actual_pickup_at)

    def test_rejected_acceptance_retry_is_held_as_retry(self):
        _po, _tx, loads = self._five_container_order()
        proposed = (
            self.env[PROPOSAL]
            .with_user(self.logistics)
            .action_propose_shipment_event(self._loaded_values(loads[0]), "la-2")
        )
        proposal = self.env[PROPOSAL].browse(proposed["record_id"])
        first = self._held(proposal.with_user(self.linda).action_accept(), "acceptance", "accept_shipment_event")
        first.with_user(self.manager).action_reject("wrong load")
        retry = self._held(proposal.with_user(self.linda).action_accept(), "refusal_retry", "accept_shipment_event")
        self.assertNotEqual(retry, first)
        self.assertEqual(proposal.state, "candidate")

    def test_a_person_accepts_without_an_approver(self):
        _po, _tx, loads = self._five_container_order()
        proposed = (
            self.env[PROPOSAL]
            .with_user(self.logistics)
            .action_propose_shipment_event(self._loaded_values(loads[0]), "ha-1")
        )
        proposal = self.env[PROPOSAL].browse(proposed["record_id"])
        self.assertTrue(proposal.with_user(self.logistics).action_accept())
        self.assertEqual(proposal.state, "accepted")
        self.assertFalse(
            self.env[APPROVAL].search([("subject_model", "=", PROPOSAL), ("subject_id", "=", proposal.id)])
        )


@tagged("post_install", "-at_install", "plasticos", "logistics")
class TestLindaGateReach(_LindaCase):
    """Static witness: no cron, base.automation or server action reaches a gated command except as Linda."""

    def test_no_automated_entry_point_reaches_a_gated_command(self):
        reach = _reach_module()
        root = Path(get_module_path("plasticos_logistics")).parent
        entries = reach.entry_points(root)
        self.assertTrue(entries, "the scan found the PlasticOS crons and automations")
        self.assertFalse([entry for entry in entries if entry[3] in reach.LINDA_REFS], "no entry runs as Linda")
        self.assertEqual(reach.gated_paths(root), [])

    def test_the_scan_detects_a_planted_path(self):
        reach = _reach_module()
        with tempfile.TemporaryDirectory() as tmp:
            addon = Path(tmp) / "plasticos_planted"
            (addon / "data").mkdir(parents=True)
            (addon / "models").mkdir()
            (addon / "__manifest__.py").write_text("{'name': 'planted'}")
            (addon / "data" / "cron.xml").write_text(
                '<odoo><record id="cron_planted" model="ir.cron">'
                '<field name="code">model._cron_planted()</field></record></odoo>'
            )
            (addon / "models" / "planted.py").write_text(
                "def _cron_planted(self):\n    self._helper()\n\n"
                "def _helper(self):\n    self.env['x'].action_correct_fact(1, {}, 'r', 'k')\n"
            )
            hits = reach.gated_paths(tmp)
        self.assertEqual(
            hits, [("cron_planted", "action_correct_fact", ("_cron_planted", "_helper", "action_correct_fact"))]
        )
