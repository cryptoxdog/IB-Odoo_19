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

from odoo.exceptions import AccessDenied, AccessError, UserError
from odoo.modules.module import get_module_path
from odoo.tests.common import tagged
from odoo.tools import mute_logger
from odoo.tools.convert import convert_file

from . import test_linda_inbound as inbound_tests
from . import test_linda_po_issuance as po_tests
from . import test_s9_logistics_features as s9
from .test_s9_logistics_features import FACT, JOURNEY, LOAD, PROPOSAL
from .test_s11_fact_corrections import _S11Case

APPROVAL = "plasticos.linda.approval"
PAUSE_SUPPLIER = "sales@s11-pause.example"
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

    def test_linda_is_updatable_and_her_grant_survives_upgrades(self):
        """Runtime B1: the Linda xmlid is not noupdate, so the security_base grant applies on upgrade too.

        A Logistics-only reload never removes the grant (it only adds), and reloading the
        security_base grant restores Logistics after it was taken away.
        """
        data = self.env["ir.model.data"].search([("module", "=", "plasticos_logistics"), ("name", "=", "user_linda")])
        self.assertEqual((len(data), data.noupdate), (1, False))
        logistics = self.env.ref(LOGISTICS)
        convert_file(self.env, "plasticos_logistics", "data/linda_user.xml", {}, mode="update", noupdate=False)
        self.linda.invalidate_recordset()
        self.assertTrue(self.linda.has_group(LOGISTICS), "a Logistics-only upgrade keeps the grant")
        self.linda.write({"group_ids": [(3, logistics.id)]})
        self.assertFalse(self.linda.has_group(LOGISTICS))
        convert_file(
            self.env, "plasticos_security_base", "security/record_rules.xml", {}, mode="update", noupdate=False
        )
        self.linda.invalidate_recordset()
        self.assertTrue(self.linda.has_group(LOGISTICS), "a security_base upgrade grants Logistics again")

    def test_linda_cannot_authenticate(self):
        """No password, no API key: no credential of Linda's is accepted."""
        for password in ("", "plasticos_linda", "linda"):
            with self.subTest(password=password), self.assertRaises(AccessDenied):
                self.linda.with_user(self.linda)._check_credentials(
                    {"login": "plasticos_linda", "password": password, "type": "password"}, {"interactive": True}
                )
        self.assertFalse(self.env["res.users.apikeys"].sudo().search_count([("user_id", "=", self.linda.id)]))
        if "oauth_uid" in self.linda._fields:
            self.assertFalse(self.linda.oauth_uid)

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
            if ("state", "=", "pending") in domain:
                calls.append(domain)
                if len(calls) == 1:
                    return model.browse()
            return original(model, domain, *rest, **kwargs)

        with patch.object(approval_class, "search", miss_first), mute_logger("odoo.sql_db"):
            again = self._linda().action_record_departure(*args)
        self.assertEqual(again["status"], "pending")
        self.assertEqual(again["approval_id"], winner.id)
        self.assertEqual(self.env[APPROVAL].search_count([("operation_key", "=", "lrace")]), 1)

    def test_unseen_journey_original_is_held_without_its_name(self):
        """R8: an original on a record Linda cannot read is held neutrally on the journey side too."""
        other = self.env["res.company"].create({"name": "S11 R8 Other Co"})
        foreign = self._load(company_id=other.id)
        hidden = self._attach(foreign, "r8-foreign-eir.pdf")
        journey = self._journey("S11-R8")
        held = self._linda().action_record_gate_in(journey.id, self._ago(5), self.terminal.id, hidden.id, "r8")
        approval = self._held(held, "evidence_unverified", "record_gate_in")
        self.assertNotIn("r8-foreign-eir", f"{approval.edge_reason} {held['reason']}")

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
        rows = self.env[APPROVAL].search([("operation_key", "=", "lp-bad")])
        self.assertEqual(rows.mapped("state"), ["refused"], "the refusal is recorded, nothing is held")
        self.assertEqual(rows.subject_key, f"load:{loads[0].id}")
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

    def test_the_scan_follows_getattr_dispatch(self):
        """I5: ``getattr(obj, f"action_record_{kind}")`` reaches every gated command it can name."""
        reach = _reach_module()
        with tempfile.TemporaryDirectory() as tmp:
            addon = Path(tmp) / "plasticos_planted"
            (addon / "data").mkdir(parents=True)
            (addon / "models").mkdir()
            (addon / "__manifest__.py").write_text("{'name': 'planted'}")
            (addon / "data" / "cron.xml").write_text(
                '<odoo><record id="cron_dynamic" model="ir.cron">'
                '<field name="code">model._cron_dynamic()</field></record></odoo>'
            )
            (addon / "models" / "planted.py").write_text(
                "def _cron_dynamic(self, kind):\n    getattr(self.env['x'], f'action_record_{kind}')(1)\n"
            )
            hits = reach.gated_paths(tmp)
        self.assertIn("action_record_gate_in", {hit[1] for hit in hits})
        self.assertIn("action_record_actual_event", {hit[1] for hit in hits})

    def test_the_scan_follows_a_write_override(self):
        """R4: ``self.write(...)`` reaching a PlasticOS ``write`` override is followed."""
        reach = _reach_module()
        with tempfile.TemporaryDirectory() as tmp:
            addon = Path(tmp) / "plasticos_planted"
            (addon / "data").mkdir(parents=True)
            (addon / "models").mkdir()
            (addon / "__manifest__.py").write_text("{'name': 'planted'}")
            (addon / "data" / "cron.xml").write_text(
                '<odoo><record id="cron_write" model="ir.cron">'
                '<field name="code">model._cron_touch()</field></record></odoo>'
            )
            (addon / "models" / "planted.py").write_text(
                "def _cron_touch(self):\n    self.write({'x': 1})\n\n"
                "def write(self, vals):\n    self.env['y'].action_correct_fact(1, {}, 'r', 'k')\n"
            )
            hits = reach.gated_paths(tmp)
        self.assertEqual(hits, [("cron_write", "action_correct_fact", ("_cron_touch", "write", "action_correct_fact"))])


@tagged("post_install", "-at_install", "plasticos", "logistics", "export")
class TestLindaReviewClosure(_LindaCase):
    """C12-SCOPE-3 criterion 6: review closure, as non-superuser users."""

    # B2 ──────────────────────────────────────────────────────────────
    def test_linda_cannot_create_a_proposal_directly(self):
        po, _tx, loads = self._five_container_order()
        reply = self._linda_reply(po)
        values = {
            "event_kind": "loaded",
            "load_id": loads[0].id,
            "occurred_at": self._ago(30),
            "evidence_attachment_id": self._attach(loads[0], "booking complete.eml").id,
            "asserted_by": "supplier_reported",
            "linda_response_id": reply.id,
        }
        with self.assertRaises(AccessError):
            self._linda(PROPOSAL).create(values)
        self.assertFalse(self.env[PROPOSAL].search([("linda_response_id", "=", reply.id)]))
        created = self.env[PROPOSAL].with_user(self.logistics).create(values)
        self.assertTrue(created, "a person may still create a proposal from the form")

    # B3 ──────────────────────────────────────────────────────────────
    def test_retry_after_a_plain_refusal_is_held_under_a_new_key(self):
        journey = self._journey("S11-R-NEWKEY")
        doc = self._attach(journey, "eir.pdf")
        future = self._ago(-2)
        refused = self._linda().action_record_gate_in(journey.id, future, self.terminal.id, doc.id, "rk1")
        self.assertEqual(refused["status"], "blocked")
        ledger = self.env[APPROVAL].search([("operation_key", "=", "rk1")])
        self.assertEqual((ledger.state, ledger.subject_key), ("refused", f"journey:{journey.id}:gate_in"))
        retried = self._linda().action_record_gate_in(journey.id, self._ago(5), self.terminal.id, doc.id, "rk2")
        approval = self._held(retried, "refusal_retry", "record_gate_in")
        self.assertFalse(self.env[FACT].search([("journey_id", "=", journey.id)]))
        self.assertEqual(self._approve(approval)["status"], "applied")
        after = self._linda().action_record_regulatory_parties(
            journey.id, self.filer.id, self.consignee.id, self._attach(journey, "filing.pdf").id, "rk3"
        )
        self.assertEqual(after["status"], "applied", "another fact kind is another subject")

    def test_retry_after_a_plain_refusal_is_held_under_the_same_key(self):
        journey = self._journey("S11-R-SAMEKEY")
        doc = self._attach(journey, "eir.pdf")
        refused = self._linda().action_record_gate_in(journey.id, self._ago(-2), self.terminal.id, doc.id, "rs1")
        self.assertEqual(refused["status"], "blocked")
        retried = self._linda().action_record_gate_in(journey.id, self._ago(5), self.terminal.id, doc.id, "rs1")
        self._held(retried, "refusal_retry", "record_gate_in")

    def test_a_person_after_linda_refusal_is_not_held(self):
        journey = self._journey("S11-R-HUMAN")
        doc = self._attach(journey, "eir.pdf")
        self._linda().action_record_gate_in(journey.id, self._ago(-2), self.terminal.id, doc.id, "rh1")
        human = self._as().action_record_gate_in(journey.id, self._ago(5), self.terminal.id, doc.id, "hh2")
        self.assertEqual(human["status"], "applied")

    # I2 ──────────────────────────────────────────────────────────────
    def test_linda_confirm_ready_is_held(self):
        load = self._load()
        load._transition("awaiting_ready")
        held = load.with_user(self.linda).action_confirm_ready()
        approval = self._held(held, "acceptance", "confirm_ready")
        self.assertFalse(load.ready_confirmed_at)
        result = self._approve(approval)
        self.assertEqual(result["status"], "applied", result)
        self.assertTrue(load.ready_confirmed_at)
        self.assertEqual(load.ready_confirmed_by, self.linda.name)

    def test_linda_actual_event_first_record_straight_and_correction_held(self):
        load = self._load()
        ticket = self._attach(load, "ticket.pdf")
        first = load.with_user(self.linda).action_record_actual_event("pickup", self._ago(6), ticket)
        self.assertEqual(first["status"], "applied", "a first record from evidence on the load is straight-through")
        self.assertEqual(load.pickup_evidence_attachment_id, ticket)
        recorded = load.actual_pickup_at
        held = load.with_user(self.linda).action_record_actual_event("pickup", self._ago(5), ticket, "re-read")
        approval = self._held(held, "correction", "record_actual_event")
        self.assertEqual(load.actual_pickup_at, recorded, "nothing changes before approval")
        self.assertEqual(self._approve(approval)["status"], "applied")
        self.assertNotEqual(load.actual_pickup_at, recorded)

    def test_linda_actual_event_edge_cases_are_held_and_plain_refusals_returned(self):
        load = self._load()
        elsewhere = self._attach(self._load(), "other.pdf")
        missing = load.with_user(self.linda).action_record_actual_event("pickup", self._ago(6), elsewhere)
        self._held(missing, "evidence_unverified", "record_actual_event")
        ticket = self._attach(load, "ticket.pdf")
        future = load.with_user(self.linda).action_record_actual_event("delivery", self._ago(-3), ticket)
        self.assertEqual(future["status"], "blocked", "a plain refusal is returned, not raised")
        self.assertFalse(load.actual_delivery_at)

    def test_a_person_records_actual_events_without_an_approver(self):
        load = self._load()
        ticket = self._attach(load, "ticket.pdf")
        user = self._make_user("s11-freight-op", LOGISTICS)
        self.assertEqual(
            load.with_user(user).action_record_actual_event("pickup", self._ago(6), ticket)["status"], "applied"
        )
        with self.assertRaises(UserError):
            load.with_user(user).action_record_actual_event("pickup", self._ago(5), ticket)

    # I1 ──────────────────────────────────────────────────────────────
    def test_a_multi_company_manager_approves_in_the_approval_company(self):
        other = self.env["res.company"].create({"name": "S11 Manager Second Co"})
        manager = self._make_user("s11-two-company-manager", MANAGER)
        manager.write({"company_ids": [(4, other.id)]})
        journey = self._journey("S11-I1")
        first, _doc = self._gate_in(journey)
        approval = self._held(
            self._linda().action_correct_fact(first.id, {"occurred_at": self._ago(7)}, "fix", "i1"),
            "correction",
            "correct_fact",
        )
        result = (
            approval.with_user(manager).with_context(allowed_company_ids=[other.id, self.company.id]).action_approve()
        )
        self.assertEqual(result["status"], "applied", result)

    # I3 ──────────────────────────────────────────────────────────────
    def test_a_stale_conflict_approval_is_refused(self):
        journey = self._journey("S11-I3")
        first, doc = self._gate_in(journey, hours=8)
        approval = self._held(
            self._linda().action_record_gate_in(journey.id, self._ago(7), self.terminal.id, doc.id, "i3"),
            "value_conflict",
            "record_gate_in",
        )
        self.assertEqual(approval.conflict_fact_id, first.id)
        person = self._as().action_correct_fact(first.id, {"occurred_at": self._ago(6)}, "EIR reread", "i3-h")
        self.assertEqual(person["status"], "applied")
        result = self._approve(approval)
        self.assertEqual(result["status"], "blocked")
        self.assertIn("stale", result["reason"])
        self.assertEqual(journey.current_fact("gate_in").id, person["record_id"], "the person's correction stands")

    # I4 ──────────────────────────────────────────────────────────────
    def test_linda_no_op_and_stale_corrections_are_refused_not_held(self):
        journey = self._journey("S11-I4")
        first, _doc = self._gate_in(journey)
        noop = self._linda().action_correct_fact(first.id, {"occurred_at": first.occurred_at}, "same", "i4a")
        self.assertEqual(noop["status"], "blocked")
        self.assertIn("changes nothing", noop["reason"])
        self.assertEqual(self.env[APPROVAL].search([("operation_key", "=", "i4a")]).state, "refused")
        self._as().action_correct_fact(first.id, {"occurred_at": self._ago(7)}, "fix", "i4-h")
        stale = self._linda().action_correct_fact(first.id, {"occurred_at": self._ago(8)}, "late", "i4b")
        self.assertEqual(stale["status"], "blocked")
        self.assertIn("current revision (2)", stale["reason"])
        self.assertFalse(
            self.env[APPROVAL].search([("state", "=", "pending"), ("operation_key", "in", ["i4a", "i4b"])])
        )

    # I6 / N2 / N3 ─────────────────────────────────────────────────────
    def test_double_approval_and_approval_after_rejection(self):
        journey = self._journey("S11-DOUBLE")
        first, _doc = self._gate_in(journey)
        approval = self._held(
            self._linda().action_correct_fact(first.id, {"occurred_at": self._ago(7)}, "fix", "dbl"),
            "correction",
            "correct_fact",
        )
        self.assertEqual(self._approve(approval)["status"], "applied")
        again = self._approve(approval)
        self.assertEqual(again["status"], "already_applied")
        self.assertEqual(self.env[FACT].search_count([("journey_id", "=", journey.id)]), 2, "approved once")
        rejected = self._held(
            self._linda().action_correct_fact(
                journey.current_fact("gate_in").id, {"occurred_at": self._ago(8)}, "fix 2", "dbl2"
            ),
            "correction",
            "correct_fact",
        )
        rejected.with_user(self.manager).action_reject("no")
        self.assertEqual(self._approve(rejected)["status"], "rejected")
        self.assertEqual(self.env[APPROVAL].with_user(self.manager).browse().action_approve(), [])

    def test_same_key_with_different_arguments_is_refused(self):
        journey = self._journey("S11-N3")
        first, _doc = self._gate_in(journey)
        self._held(
            self._linda().action_correct_fact(first.id, {"occurred_at": self._ago(7)}, "fix", "n3"),
            "correction",
            "correct_fact",
        )
        other = self._linda().action_correct_fact(first.id, {"occurred_at": self._ago(9)}, "fix", "n3")
        self.assertEqual(other["status"], "blocked")
        self.assertIn("different arguments", other["reason"])

    def test_linda_documents_vgm_evidence_is_held(self):
        journey = self._journey("S11-VGM")
        held = self._linda().action_record_verified_gross_mass(
            journey.id, 48975, self.lb.id, "documents_verified_gross_mass", None, "rev-1", "vgm1"
        )
        self._held(held, "evidence_unverified", "record_verified_gross_mass")
        self.assertFalse(self.env[FACT].search([("journey_id", "=", journey.id)]))


@tagged("post_install", "-at_install", "plasticos", "logistics", "export")
class TestLindaRound2(_LindaCase):
    """C12 review round 2 (R1-R6), as non-superuser users."""

    # R1 ──────────────────────────────────────────────────────────────
    def test_linda_raw_load_writes_are_refused(self):
        load = self._load()
        load._transition("awaiting_ready")
        as_linda = load.with_user(self.linda)
        for vals in (
            {"ready_confirmed_at": self._ago(1)},
            {"ready_confirmed_by": "Linda"},
            {"state": "ready_confirmed"},
            {"actual_pickup_at": self._ago(1)},
        ):
            with self.subTest(vals=list(vals)), self.assertRaises(AccessError):
                as_linda.write(vals)
        with self.assertRaises(AccessError):
            self.env[LOAD].with_user(self.linda).create(
                {"company_id": self.company.id, "pickup_partner_id": self.supplier.id, "ready_confirmed_by": "Linda"}
            )
        load.invalidate_recordset()
        self.assertEqual((load.state, load.ready_confirmed_at), ("awaiting_ready", False))

    def test_a_stale_ready_timestamp_is_not_readiness(self):
        load = self._load()
        load._transition("awaiting_ready")
        load.write({"ready_confirmed_at": self._ago(9)})  # a stale stamp, as a raw write by someone else left it
        held = load.with_user(self.linda).action_confirm_ready()
        self._held(held, "acceptance", "confirm_ready")
        doc = self._attach(load, "ready.eml")
        proposed = (
            self.env[PROPOSAL]
            .with_user(self.logistics)
            .action_propose_shipment_event(
                {
                    "event_kind": "supplier_ready",
                    "load_id": load.id,
                    "evidence_attachment_id": doc.id,
                    "asserted_by": "supplier_reported",
                },
                "r1-ready",
            )
        )
        proposal = self.env[PROPOSAL].browse(proposed["record_id"])
        proposal.with_user(self.logistics).action_accept()
        self.assertEqual((proposal.command_status, load.state), ("applied", "ready_confirmed"))

    # R2 ──────────────────────────────────────────────────────────────
    def test_unreadable_actual_event_evidence_is_held_without_disclosure(self):
        other = self.env["res.company"].create({"name": "S11 R2 Other Co"})
        foreign = self._load(company_id=other.id)
        hidden = self._attach(foreign, "other-company-ticket.pdf")
        hidden.company_id = other
        load = self._load()
        held = load.with_user(self.linda).action_record_actual_event("pickup", self._ago(6), hidden)
        approval = self._held(held, "evidence_unverified", "record_actual_event")
        self.assertEqual(approval.edge_reason, "the original document is not visible to Linda")
        self.assertNotIn("other-company-ticket", held["reason"])
        stored = self.env[APPROVAL].search([("subject_key", "=", f"load:{load.id}")])
        for row in stored:
            text = " ".join(filter(None, (row.edge_reason, row.result_reason, row.arguments)))
            self.assertNotIn("other-company-ticket", text, "nothing stored for Linda names an original she cannot see")
        self.assertFalse(load.actual_pickup_at)
        with self.assertRaises(AccessError) as refused:
            load.with_user(self.logistics).action_record_actual_event("pickup", self._ago(6), hidden)
        self.assertNotIn("other-company-ticket", str(refused.exception))

    # R9 ──────────────────────────────────────────────────────────────
    def test_approving_a_hidden_original_stores_no_attachment_name(self):
        other = self.env["res.company"].create({"name": "S11 R9 Other Co"})
        foreign = self._load(company_id=other.id)
        hidden = self._attach(foreign, "other-company-ticket.pdf")
        hidden.company_id = other
        load = self._load()
        held = load.with_user(self.linda).action_record_actual_event("pickup", self._ago(6), hidden)
        approval = self._held(held, "evidence_unverified", "record_actual_event")
        self._approve(approval)
        self.assertEqual(approval.state, "approved")
        self.assertNotEqual(approval.result_status, "applied")
        self.assertFalse(load.actual_pickup_at)
        for row in self.env[APPROVAL].search([("subject_key", "=", f"load:{load.id}")]):
            text = " ".join(filter(None, (row.edge_reason, row.result_reason, row.arguments)))
            self.assertNotIn(
                "other-company-ticket", text, "an approved run stores nothing that names a hidden original"
            )

    # R5 ──────────────────────────────────────────────────────────────
    def test_actual_event_correction_without_reason_is_refused_not_held(self):
        load = self._load()
        ticket = self._attach(load, "ticket.pdf")
        self.assertEqual(
            load.with_user(self.linda).action_record_actual_event("pickup", self._ago(6), ticket)["status"], "applied"
        )
        refused = load.with_user(self.linda).action_record_actual_event("pickup", self._ago(5), ticket)
        self.assertEqual((refused["status"], refused["reason"]), ("blocked", "a correction needs a reason"))
        rows = self.env[APPROVAL].search([("subject_key", "=", f"load:{load.id}")])
        self.assertEqual(rows.mapped("state"), ["refused"])

    # R6 ──────────────────────────────────────────────────────────────
    def test_a_hold_without_company_answers_blocked(self):
        from odoo.addons.plasticos_logistics.models.linda_approval import hold_for_approval

        env = self.env(user=self.linda.id, su=False)
        result = hold_for_approval(
            env, "confirm_ready", "acceptance", "r6", {"load_id": 0}, "r6-key", env["res.company"]
        )
        self.assertEqual(result["status"], "blocked")
        self.assertFalse(self.env[APPROVAL].search([("operation_key", "=", "r6-key")]))

    # R3 ──────────────────────────────────────────────────────────────
    def test_archived_linda_stays_archived_with_her_grant_across_upgrades(self):
        self.linda.write({"active": False})
        convert_file(self.env, "plasticos_logistics", "data/linda_user.xml", {}, mode="update", noupdate=False)
        convert_file(
            self.env, "plasticos_security_base", "security/record_rules.xml", {}, mode="update", noupdate=False
        )
        self.linda.invalidate_recordset()
        self.assertFalse(self.linda.active, "an upgrade never reactivates Linda")
        self.assertTrue(self.linda.has_group(LOGISTICS), "her grant is intact")

    def test_archived_linda_is_refused_everywhere_and_writes_nothing(self):
        journey = self._journey("S11-STOP")
        first, doc = self._gate_in(journey)
        load = self._load()
        load._transition("awaiting_ready")
        ticket = self._attach(load, "ticket.pdf")
        held = self._held(
            self._linda().action_correct_fact(first.id, {"occurred_at": self._ago(7)}, "fix", "stop-held"),
            "correction",
            "correct_fact",
        )
        candidate = self.env[PROPOSAL].browse(
            self.env[PROPOSAL]
            .with_user(self.logistics)
            .action_propose_shipment_event(
                {
                    "event_kind": "loaded",
                    "load_id": load.id,
                    "occurred_at": self._ago(3),
                    "evidence_attachment_id": ticket.id,
                    "asserted_by": "carrier_issued",
                },
                "stop-candidate",
            )["record_id"]
        )
        self.linda.write({"active": False})
        approvals_before = self.env[APPROVAL].search_count([])
        facts_before = self.env[FACT].search_count([("journey_id", "=", journey.id)])
        calls = {
            "correction": lambda: self._linda().action_correct_fact(first.id, {"occurred_at": self._ago(8)}, "x", "s1"),
            "record": lambda: self._linda().action_record_regulatory_parties(
                journey.id, self.filer.id, False, doc.id, "s2"
            ),
            "proposal": lambda: self._linda(PROPOSAL).action_propose_shipment_event(
                {
                    "event_kind": "loaded",
                    "load_id": load.id,
                    "occurred_at": self._ago(3),
                    "evidence_attachment_id": ticket.id,
                    "asserted_by": "carrier_issued",
                },
                "s3",
            ),
            "accept": lambda: candidate.with_user(self.linda).action_accept(),
            "confirm_ready": lambda: load.with_user(self.linda).action_confirm_ready(),
            "actual_event": lambda: load.with_user(self.linda).action_record_actual_event(
                "pickup", self._ago(4), ticket
            ),
        }
        for name, call in calls.items():
            with self.subTest(command=name):
                result = call()
                self.assertEqual(result["status"], "blocked")
                self.assertIn("archived", result["reason"])
        requests = self.env["plasticos.logistics.request"].with_user(self.linda)
        sweep = requests.sudo()._run_load_obligations(loads=load)
        self.assertEqual(sweep[0]["status"], "blocked")
        with self.assertRaises(UserError):
            held.with_user(self.manager).action_approve()
        self.assertEqual(self.env[APPROVAL].search_count([]), approvals_before)
        self.assertEqual(self.env[FACT].search_count([("journey_id", "=", journey.id)]), facts_before)
        self.assertEqual(self.env[PROPOSAL].search([("load_id", "=", load.id)]), candidate)
        self.assertEqual(candidate.state, "candidate", "an archived Linda cannot accept")
        load.invalidate_recordset()
        self.assertEqual((load.state, load.actual_pickup_at), ("awaiting_ready", False))
        self.assertEqual(held.state, "pending")


@tagged("post_install", "-at_install", "plasticos", "logistics", "linda")
class TestLindaPause(_LindaCase):
    """C12 review round 3 (R7): archiving Linda pauses her; it never turns her mode off."""

    # Borrowed through their modules, so those classes are not collected a second time here.
    _mail_sink = po_tests.TestLindaPoIssuance._mail_sink
    _process_queue = po_tests.TestLindaPoIssuance._process_queue
    # The inbound email builder is borrowed under its own name: ``_S11Case._raw(fact)`` reads a
    # stored fact row, and replacing it with the email builder would change what ``_raw`` means here.
    _raw_email = inbound_tests.TestLindaInbound._raw
    _receive = inbound_tests.TestLindaInbound._receive

    def _reply_to(self, request, body, sender=None, **kwargs):
        """The inbound tests' ``_reply_to``, built with ``_raw_email``."""
        reference = request.mail_id.message_id
        raw = self._raw_email(
            body, sender or request.recipient_email, in_reply_to=reference, references=reference, **kwargs
        )
        return self._receive(raw)

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company.po_double_validation = "one_step"
        cls.env["plasticos.automation.config"].get_config().sale_approval_threshold = 1000000.0
        cls.mail_supplier = cls.env["res.partner"].create(
            {"name": "S11 Pause Mill", "is_company": True, "supplier_rank": 1, "email": PAUSE_SUPPLIER}
        )
        cls.mail_buyer = cls.env["res.partner"].create(
            {"name": "S11 Pause Buyer", "is_company": True, "customer_rank": 1, "email": "buy@s11-pause.example"}
        )
        cls.product = cls.env["product.product"].create(
            {"name": "S11 PP Regrind", "type": "consu", "purchase_ok": True, "sale_ok": True}
        )
        cls.Request = cls.env["plasticos.logistics.request"]

    def setUp(self):
        super().setUp()
        self.env["ir.config_parameter"].sudo().set_param("plasticos_logistics.linda_mode", "live")

    def _po(self):
        return self.env["purchase.order"].create(
            {
                "partner_id": self.mail_supplier.id,
                "company_id": self.company.id,
                "order_line": [(0, 0, {"product_id": self.product.id, "product_qty": 40000, "price_unit": 0.1})],
            }
        )

    def _requests(self, po, purpose):
        return self.Request.search([("purchase_order_id", "=", po.id), ("purpose", "=", purpose)], order="revision")

    def _issued_po(self):
        po = self._po()
        po.button_confirm()
        issue = self._requests(po, "po_issue")
        with self._mail_sink():
            self._process_queue(issue)
        self.assertEqual(issue.state, "sent")
        return po, issue

    def _archive(self):
        self.linda.write({"active": False})

    def _chatter(self, order, text):
        return order.message_ids.filtered(lambda message: text in (message.body or ""))

    def test_archived_linda_keeps_issuance_and_the_legacy_sender_stays_silent(self):
        self._archive()
        self.assertEqual(self.Request._linda_mode(), "live", "archiving pauses Linda; it is not a mode change")
        po = self._po()
        po.button_confirm()
        self.assertTrue(po._linda_owns_po_issuance())
        self.assertFalse(self._chatter(po, "Supplier confirmation request sent"), "no legacy PO send")
        issue = self._requests(po, "po_issue")
        self.assertEqual((len(issue), issue.mail_id.state), (1, "outgoing"), "the obligation still queues")
        so = self.env["sale.order"].create(
            {
                "partner_id": self.mail_buyer.id,
                "company_id": self.company.id,
                "order_line": [(0, 0, {"product_id": self.product.id, "product_uom_qty": 40000, "price_unit": 0.2})],
            }
        )
        so.action_confirm()
        self.assertTrue(so._linda_owns_so_issuance())
        self.assertFalse(self._chatter(so, "Sales order confirmation sent to buyer"), "no legacy SO send")

    def test_send_guard_withholds_while_archived_and_releases_on_return(self):
        po = self._po()
        po.button_confirm()
        issue = self._requests(po, "po_issue")
        self._archive()
        withheld, sendable, _held = self.Request.sudo()._guard_mails_before_send(issue.mail_id)
        self.assertEqual((withheld, sendable), (issue.mail_id, self.env["mail.mail"]))
        with self._mail_sink() as sent:
            self._process_queue(issue)
        self.assertFalse(sent, "nothing leaves while Linda is archived")
        self.assertEqual((issue.state, issue.mail_id.state), ("queued", "outgoing"), "withheld untouched")
        self.linda.write({"active": True})
        with self._mail_sink() as sent:
            self._process_queue(issue)
        self.assertEqual(issue.state, "sent")
        self.assertEqual([message["To"] for message in sent], [PAUSE_SUPPLIER])

    def test_cancellation_notice_queues_while_archived_and_is_sent_on_return(self):
        po, _issue = self._issued_po()
        self._archive()
        po.button_cancel()
        notice = self._requests(po, "po_cancel")
        self.assertEqual((len(notice), notice.state, notice.mail_id.state), (1, "queued", "outgoing"))
        with self._mail_sink() as sent:
            self._process_queue(notice)
        self.assertFalse(sent)
        self.linda.write({"active": True})
        with self._mail_sink() as sent:
            self._process_queue(notice)
        self.assertEqual(notice.state, "sent", "the supplier is told after Linda returns")
        self.assertEqual([message["To"] for message in sent], [PAUSE_SUPPLIER])

    def test_inbound_reply_is_recorded_while_archived(self):
        _po, issue = self._issued_po()
        self._archive()
        message = self._reply_to(issue, "CONFIRMED")
        response = self.env["plasticos.logistics.response"].search([("mail_message_id", "=", message.id)])
        self.assertEqual((len(response), response.request_id), (1, issue), "a reply is evidence, recorded while paused")


LOGISTICS_OPS = "plasticos_security_base.group_logistics_ops"
_ALL_EDGES = (
    "correction",
    "unverified_linda_reply",
    "acceptance",
    "value_conflict",
    "out_of_sequence",
    "unit_mismatch",
    "evidence_unverified",
    "refusal_retry",
)


@tagged("post_install", "-at_install", "plasticos", "logistics", "export")
class TestLindaAuthorityByClass(_LindaCase):
    """DEC-011 OPT-A, fail-closed (TASK-061): who decides each held (command, edge case)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ops = cls._make_user("s11-logistics-ops", LOGISTICS_OPS)
        cls.rep = cls._make_user("s11-sales-rep", "plasticos_security_base.group_sales_rep")
        from odoo.addons.plasticos_logistics.models import linda_approval as module

        cls.module = module

    def _filed(self, command, edge_case, key):
        held = self.module.hold_for_approval(
            self.env(user=self.linda), command, edge_case, f"test {edge_case}", {"n": key}, key, self.company
        )
        self.assertEqual(held["status"], "pending", held)
        return self.env[APPROVAL].browse(held["approval_id"])

    def _open_activities(self, approval):
        return self.env["mail.activity"].search([("res_model", "=", APPROVAL), ("res_id", "=", approval.id)])

    def _activity_type(self, role):
        return self.env.ref(self.module.ROLE_ACTIVITY_TYPES[role])

    def test_the_authority_table_is_the_decided_one(self):
        expected = {
            ("schedule_load", "acceptance"),
            ("dispatch_load", "acceptance"),
            ("confirm_ready", "acceptance"),
            ("accept_appointment", "acceptance"),
            ("accept_shipment_event", "acceptance"),
            ("propose_shipment_event", "unverified_linda_reply"),
            ("record_gate_in", "evidence_unverified"),
            ("record_gate_in", "out_of_sequence"),
            ("record_departure", "evidence_unverified"),
            ("record_departure", "out_of_sequence"),
            ("record_actual_event", "evidence_unverified"),
            ("record_actual_event", "out_of_sequence"),
        }
        self.assertEqual(set(self.module.LOGISTICS_AUTHORITY), expected)
        roles = {value for value, _label in self.env[APPROVAL]._fields["routed_role"].selection}
        self.assertEqual(roles, {self.module.ROLE_LOGISTICS, self.module.ROLE_OPERATIONS})
        operations_only = {
            "correct_fact",
            "record_container_tare",
            "record_verified_gross_mass",
            "record_regulatory_parties",
        }
        forbidden_edges = {"correction", "value_conflict", "unit_mismatch", "refusal_retry"}
        for command, edge_case in expected:
            self.assertNotIn(command, operations_only)
            self.assertNotIn(edge_case, forbidden_edges)

    def test_every_command_and_edge_case_is_decided_server_side(self):
        """Positive and negative per (command, edge case): Logistics Ops only on its table, OM on all."""
        commands = [value for value, _label in self.env[APPROVAL]._fields["command"].selection]
        for command in commands:
            for edge_case in _ALL_EDGES:
                with self.subTest(command=command, edge_case=edge_case):
                    approval = self._filed(command, edge_case, f"auth:{command}:{edge_case}")
                    logistics = (command, edge_case) in self.module.LOGISTICS_AUTHORITY
                    self.assertEqual(approval.routed_role, "logistics_ops" if logistics else "operations_manager")
                    self.assertEqual(approval.with_user(self.manager)._require_approver(), "operations_manager")
                    if logistics:
                        self.assertEqual(approval.with_user(self.ops)._require_approver(), "logistics_ops")
                    else:
                        with self.assertRaises(AccessError):
                            approval.with_user(self.ops)._require_approver()
                        with self.assertRaises(AccessError):
                            approval.with_user(self.ops).action_approve()
                        with self.assertRaises(AccessError):
                            approval.with_user(self.ops).action_reject()
                    for user in (self.linda, self.logistics, self.rep):
                        with self.assertRaises(AccessError):
                            approval.with_user(user)._require_approver()
                    self.assertEqual(approval.state, "pending")

    def test_logistics_ops_rejects_its_class_and_the_activity_closes(self):
        approval = self._filed("schedule_load", "acceptance", "auth-reject")
        self.assertEqual(len(self._open_activities(approval)), 1)
        approval.with_user(self.ops).action_reject("wrong slot")
        self.assertEqual((approval.state, approval.decided_by), ("rejected", self.ops))
        self.assertFalse(self._open_activities(approval), "a decided approval keeps no open activity")

    def test_a_pending_approval_has_exactly_one_activity_for_its_owning_role(self):
        for command, edge_case, role in (
            ("confirm_ready", "acceptance", "logistics_ops"),
            ("correct_fact", "correction", "operations_manager"),
            ("record_gate_in", "value_conflict", "operations_manager"),
        ):
            with self.subTest(command=command, edge_case=edge_case):
                key = f"act:{command}"
                approval = self._filed(command, edge_case, key)
                self._filed(command, edge_case, key)  # the same hold again schedules nothing new
                activities = self._open_activities(approval)
                self.assertEqual(len(activities), 1)
                self.assertEqual(activities.activity_type_id, self._activity_type(role))
                group = self.module.ROLE_GROUPS["logistics_ops" if role == "logistics_ops" else "operations_manager"]
                self.assertTrue(activities.user_id.has_group(group), "assigned to the owning role")
                self.assertNotEqual(activities.user_id, self.linda)

    def test_logistics_approval_applies_a_routine_acceptance(self):
        load = self._load()
        load._transition("awaiting_ready")
        approval = self._held(load.with_user(self.linda).action_confirm_ready(), "acceptance", "confirm_ready")
        result = self._approve(approval, self.ops)
        self.assertEqual(result["status"], "applied", result)
        self.assertEqual(
            (approval.state, approval.decided_by, approval.routed_role), ("approved", self.ops, "logistics_ops")
        )
        self.assertTrue(load.ready_confirmed_at)
        self.assertEqual(load.ready_confirmed_by, self.linda.name, "the record keeps Linda as its author")
        self.assertFalse(self._open_activities(approval))
        again = self._approve(approval, self.ops)
        self.assertEqual(again["status"], "already_applied", "replay idempotency holds")

    def test_logistics_approval_accepts_a_shipment_event(self):
        _po, _tx, loads = self._five_container_order()
        proposed = (
            self.env[PROPOSAL]
            .with_user(self.logistics)
            .action_propose_shipment_event(self._loaded_values(loads[0]), "lca-1")
        )
        proposal = self.env[PROPOSAL].browse(proposed["record_id"])
        approval = self._held(proposal.with_user(self.linda).action_accept(), "acceptance", "accept_shipment_event")
        self.assertEqual(self._approve(approval, self.ops)["status"], "applied")
        proposal.invalidate_recordset()
        self.assertEqual(proposal.state, "accepted")

    def test_logistics_approval_confirms_an_unverified_reply_proposal(self):
        po, _tx, loads = self._five_container_order()
        reply = self._linda_reply(po, disposition="identity_unverified")
        held = self._linda(PROPOSAL).action_propose_shipment_event(self._loaded_values(loads[0], reply), "lcp-1")
        approval = self._held(held, "unverified_linda_reply", "propose_shipment_event")
        result = self._approve(approval, self.ops)
        self.assertEqual(result["status"], "applied", result)
        self.assertEqual(self.env[PROPOSAL].browse(result["record_id"]).create_uid, self.linda)

    def test_an_unverified_reply_approval_keeps_every_other_owner_guard(self):
        """CTO ANSWER 1: Logistics confirms the reply only; a failing evidence guard still blocks and re-routes."""
        po, _tx, loads = self._five_container_order()
        reply = self._linda_reply(po, disposition="identity_unverified")
        values = self._loaded_values(loads[0], reply)
        held = self._linda(PROPOSAL).action_propose_shipment_event(values, "lcp-guard")
        approval = self._held(held, "unverified_linda_reply", "propose_shipment_event")
        # The original leaves the load after the hold, so the proposal's evidence guard refuses at replay.
        evidence = self.env["ir.attachment"].browse(values["evidence_attachment_id"])
        evidence.sudo().write({"res_id": loads[1].id})  # sudo: fixture moves the original to another load
        result = self._approve(approval, self.ops)
        self.assertEqual((result["status"], result.get("rerouted_to")), ("blocked", "operations_manager"), result)
        self.assertEqual(
            (approval.state, approval.routed_role, approval.result_status), ("pending", "operations_manager", "blocked")
        )
        self.assertFalse(self.env[PROPOSAL].search([("operation_key", "=", "lcp-guard")]), "nothing is applied")

    def test_a_still_failing_guard_blocks_and_reroutes_to_operations(self):
        """Out of sequence, still unresolved: nothing applied, blocked, one Operations Manager activity."""
        journey = self._journey("S11-L-REROUTE")
        doc = self._attach(journey, "sailed.pdf")
        held = self._linda().action_record_departure(journey.id, self._ago(2), "MSC Aurora", "A1", doc.id, "lcr1")
        approval = self._held(held, "out_of_sequence", "record_departure")
        self.assertEqual(approval.routed_role, "logistics_ops")
        result = self._approve(approval, self.ops)
        self.assertEqual((result["status"], result["rerouted_to"]), ("blocked", "operations_manager"), result)
        self.assertEqual(
            (approval.state, approval.routed_role, approval.result_status, approval.rerouted_by),
            ("pending", "operations_manager", "blocked", self.ops),
        )
        self.assertFalse(approval.decided_by, "a re-route is not a decision")
        self.assertFalse(self.env[FACT].search([("journey_id", "=", journey.id)]), "nothing is applied")
        activities = self._open_activities(approval)
        self.assertEqual(activities.activity_type_id, self._activity_type("operations_manager"))
        self.assertEqual(len(activities), 1)
        with self.assertRaises(AccessError):
            approval.with_user(self.ops).action_approve()
        manager = self._approve(approval)
        self.assertEqual(manager["status"], "blocked", "Operations Manager keeps today's semantics")
        self.assertEqual((approval.state, approval.decided_by), ("approved", self.manager))
        self.assertFalse(self._open_activities(approval))

    def test_a_resolved_sequence_applies_on_logistics_approval(self):
        journey = self._journey("S11-L-RESOLVED")
        doc = self._attach(journey, "sailed.pdf")
        held = self._linda().action_record_departure(journey.id, self._ago(2), "MSC Aurora", "A1", doc.id, "lcs1")
        approval = self._held(held, "out_of_sequence", "record_departure")
        self._gate_in(journey, hours=6, key="lcs-gate")
        result = self._approve(approval, self.ops)
        self.assertEqual(result["status"], "applied", result)
        self.assertEqual(journey.current_fact("departure").recorded_by, self.linda)

    def test_unverified_evidence_stays_blocked_for_logistics(self):
        journey = self._journey("S11-L-EVID-OPS")
        elsewhere = self._attach(self._load(), "unrelated.pdf")
        held = self._linda().action_record_gate_in(journey.id, self._ago(5), self.terminal.id, elsewhere.id, "lce1")
        approval = self._held(held, "evidence_unverified", "record_gate_in")
        result = self._approve(approval, self.ops)
        self.assertEqual(result.get("rerouted_to"), "operations_manager", result)
        self.assertFalse(self.env[FACT].search([("journey_id", "=", journey.id)]))

    def test_an_owner_guard_refusal_on_a_consequential_command_reroutes(self):
        """Dispatch of a load that is not scheduled: the owner guard refuses; Logistics cannot push it through."""
        load = self._load()
        held = load.with_user(self.linda).action_dispatch()
        approval = self._held(held, "acceptance", "dispatch_load")
        result = self._approve(approval, self.ops)
        self.assertEqual(result.get("rerouted_to"), "operations_manager", result)
        self.assertNotEqual(load.state, "dispatched")
        self.assertEqual((approval.state, approval.routed_role), ("pending", "operations_manager"))

    def test_kill_switch_refuses_a_logistics_approval_and_writes_nothing(self):
        load = self._load()
        load._transition("awaiting_ready")
        approval = self._held(load.with_user(self.linda).action_confirm_ready(), "acceptance", "confirm_ready")
        self.linda.active = False
        try:
            with self.assertRaises(UserError):
                approval.with_user(self.ops).action_approve()
        finally:
            self.linda.active = True
        self.assertEqual((approval.state, approval.routed_role), ("pending", "logistics_ops"))
        self.assertFalse(load.ready_confirmed_at)

    def test_no_logistics_user_is_made_an_operations_manager(self):
        self.assertFalse(self.ops.has_group(MANAGER))
        self.assertFalse(self.linda.has_group(MANAGER))
