"""Operations Manager approval of Linda's edge cases (S11, OP11-E02; C12-SCOPE-2 and SCOPE-3).

Linda is ``plasticos_logistics.user_linda``, a service user with the Logistics
group only. When she runs a gated command, a straight-through outcome applies at
once. An edge case is held here instead, pending until an Operations Manager
approves or rejects it:

* any journey-fact correction;
* a shipment event proposal citing a Linda reply whose disposition is
  ``identity_unverified`` or ``unresolved``;
* accepting a shipment event proposal, and the load owner commands a proposal
  maps to: ``plasticos.load.action_confirm_ready`` (always), and
  ``plasticos.load.action_record_actual_event`` when it would correct a recorded
  value, is out of sequence or lacks verified evidence;
* recording a journey fact whose value conflicts with the current revision, that
  is out of sequence, whose weight unit is wrong, or whose evidence is missing or
  unverified;
* any call after a refusal: when Linda's command is refused on a subject (a
  journey and fact kind, a proposal or a load), the refusal is recorded here, and
  her next call of the same command on the same subject, under any operation
  key, is held.

Who may decide a held command is a server-side table keyed on (command, edge case)
(DEC-011 OPT-A, fail-closed): Logistics Operations decides the routine operational
classes in ``LOGISTICS_AUTHORITY``; an Operations Manager decides every held command.
A Logistics approval first replays the command as Linda against the current state with
her own gate active and no approval token: when that replay would still hold anything
but a plain acceptance, or any owner guard refuses, nothing is applied, the result is
``blocked`` and the case is re-routed to Operations Manager. Linda and a plain Logistics
user never approve. Each pending approval has one open activity for its owning role.

The supported stop is to archive ``user_linda``, which pauses her: every gated
command she runs and every approval of her held commands is refused and writes
nothing, typed requests and the load-obligation sweep answer ``blocked``, and her
queued mail is withheld until she is reactivated. Her mode does not change, so
she keeps owning order issuance, obligations still queue and inbound replies are
still recorded. A module upgrade never reactivates her. Removing her Logistics
group is not a supported stop.
Approval runs the held command as Linda, in the approval's company only, under a
context token that RPC cannot forge, so the owner guards still run and the record
keeps Linda as its author. Human actors are never held: they need no second
approver (operator decision 2026-11-12). No cron is reassigned; today no automated
path calls a gated command (EVIDENCE/S11).
"""

import json
import logging
from datetime import date, datetime

import psycopg2.errors

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

from .iso_journey import _lock, _normalize_text

_logger = logging.getLogger(__name__)

LINDA_XMLID = "plasticos_logistics.user_linda"
MANAGER_GROUP = "plasticos_security_base.group_operations_manager"
LOGISTICS_OPS_GROUP = "plasticos_security_base.group_logistics_ops"
ROLE_LOGISTICS = "logistics_ops"
ROLE_OPERATIONS = "operations_manager"
ROLE_GROUPS = {ROLE_LOGISTICS: LOGISTICS_OPS_GROUP, ROLE_OPERATIONS: MANAGER_GROUP}
ROLE_ACTIVITY_TYPES = {
    ROLE_LOGISTICS: "plasticos_logistics.mail_act_linda_approval_logistics",
    ROLE_OPERATIONS: "plasticos_logistics.mail_act_linda_approval_operations",
}
# DEC-011 OPT-A: the (command, edge case) pairs Logistics Operations may decide. Every
# pair a Linda gate can hold for these commands except correction, value_conflict,
# unit_mismatch and refusal_retry, which stay with Operations Manager like every other
# command (correct_fact, record_container_tare, record_verified_gross_mass,
# record_regulatory_parties). Anything absent from this table is Operations Manager's.
LOGISTICS_AUTHORITY = frozenset(
    {
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
)
# The only fresh classifications a Logistics replay may meet: a human confirmation, never a
# guard. An unverified Linda reply can never become verified (linda_response is append-only and
# has no verified disposition), so it is the human's confirmation that the reply is right, like an
# acceptance; the proposal's own guards still run on the replay.
_CLEAR_EDGES = frozenset({"acceptance", "unverified_linda_reply"})
FACT = "plasticos.iso.journey.fact"
PROPOSAL = "plasticos.shipment.event.proposal"
LOAD = "plasticos.load"
JOURNEY = "plasticos.iso.journey"
APPROVAL = "plasticos.linda.approval"
# Set only by action_approve: an object, so no RPC context can carry it.
_APPROVED_RUN = "plasticos_linda_approved_run"
_APPROVED_TOKEN = object()
_DECISION_WRITE = "plasticos_linda_approval_decision"
_DECISION_TOKEN = object()
REFUSAL_STATUSES = ("blocked", "not_available")


def owning_role(command, edge_case):
    """The role that decides a held (command, edge case): Logistics Operations or Operations Manager."""
    return ROLE_LOGISTICS if (command, edge_case) in LOGISTICS_AUTHORITY else ROLE_OPERATIONS


class _ReplayRollback(Exception):
    """Rolls back a probe or a refused Logistics replay and carries its answer."""

    def __init__(self, result):
        super().__init__("replay")
        self.result = result


def linda_user(env):
    """The Linda service user, or an empty recordset when her record is absent."""
    return env.ref(LINDA_XMLID, raise_if_not_found=False) or env["res.users"]


def is_linda(env):
    """True when the acting user is Linda, approved replay or not."""
    linda = linda_user(env)
    return bool(linda) and env.uid == linda.id


LINDA_STOPPED_REASON = "linda_stopped"


def linda_stopped(env):
    """True when the operator has archived Linda: the supported kill switch (C12 round 2, R3)."""
    linda = linda_user(env)
    return bool(linda) and not linda.sudo().active  # sudo: any caller may learn whether Linda is stopped


STOPPED_RESULT = {"status": "blocked", "reason": "Linda is archived (operator stop); nothing was recorded"}


def linda_stop(env):
    """The refusal of a Linda command while she is archived, or ``None``. Writes nothing."""
    if is_linda(env) and linda_stopped(env):
        return dict(STOPPED_RESULT)
    return None


def linda_acting(env):
    """True when Linda runs a gated command that is not an approved replay."""
    return is_linda(env) and env.context.get(_APPROVED_RUN) is not _APPROVED_TOKEN


def original_hidden(env, attachment):
    """Whether the acting user cannot see this original or the record it is attached to (round 3, R8).

    ``ir.attachment.check_access`` alone can pass for an attachment whose record the
    user cannot read (another company's load or journey). A caller that cannot see
    the record must not learn the attachment's name from a refusal either.
    """
    attachment = attachment.exists() if attachment else attachment
    if not attachment:
        return False
    try:
        attachment.check_access("read")
    except AccessError:
        return True
    if attachment.company_id and attachment.company_id not in env.user.company_ids:
        return True
    located = attachment.sudo()  # sudo: where the original sits, not what it says
    model, res_id = located.res_model, located.res_id
    if model and res_id and model in env:
        record = env[model].browse(res_id).exists()
        if record:
            try:
                record.check_access("read")
            except AccessError:
                return True
    return False


def as_approved(records):
    """``records`` with the approval token, for a gate's own probe or an approved run."""
    return records.with_context(**{_APPROVED_RUN: _APPROVED_TOKEN})


def _json_default(value):
    if isinstance(value, datetime):
        return fields.Datetime.to_string(value)
    if isinstance(value, date):
        return fields.Date.to_string(value)
    if isinstance(value, models.BaseModel):
        return value.ids
    raise TypeError(f"cannot hold {type(value).__name__} for approval")


def _dump(arguments):
    return json.dumps(arguments, default=_json_default, sort_keys=True)


def _ledger(env):
    return env[APPROVAL].sudo()  # sudo: Linda files and reads her own ledger rows; no role may write them


def prior_refusal(env, command, subject_key, company):
    """Whether Linda's last decided ``command`` on this subject was refused (C12-SCOPE-3 (2)).

    A refusal row, a rejected approval or an approved run that the owner refused
    all count, under any operation key. A later approval that applied clears it.
    """
    if not subject_key:
        return False
    last = _ledger(env).search(
        [
            ("company_id", "=", company.id),
            ("command", "=", command),
            ("subject_key", "=", subject_key),
            ("state", "in", ["refused", "rejected", "approved"]),
        ],
        order="id desc",
        limit=1,
    )
    if not last:
        return False
    return last.state in ("refused", "rejected") or last.result_status in REFUSAL_STATUSES


def record_refusal(env, command, subject_key, company, result, arguments, operation_key, subject=None):
    """Record Linda's refusal so her next call on the same subject is held. Returns ``result`` unchanged."""
    if not (linda_acting(env) and subject_key and company and result.get("status") in REFUSAL_STATUSES):
        return result
    _ledger(env).with_context(**{_DECISION_WRITE: _DECISION_TOKEN}).create(
        {
            "company_id": company.id,
            "command": command,
            "edge_case": "refusal",
            "edge_reason": result.get("reason") or result.get("status"),
            "arguments": _dump(arguments),
            "operation_key": _normalize_text(operation_key) or f"refused:{subject_key}",
            "subject_key": subject_key,
            "subject_model": subject._name if subject else False,
            "subject_id": subject.id if subject else False,
            "state": "refused",
            "requested_by": env.uid,
            "requested_at": fields.Datetime.now(),
            "result_status": result.get("status"),
            "result_reason": result.get("reason"),
        }
    )
    return result


def hold_for_approval(
    env, command, edge_case, reason, arguments, operation_key, company, subject=None, subject_key=None, extra=None
):
    """Hold Linda's edge case pending approval by its owning role (DEC-011).

    Idempotent per company, command and key: the same arguments answer the same
    pending approval, different arguments under that key are refused, and a
    concurrent filing that loses the pending index answers the winning row.
    """
    approvals = _ledger(env)
    key = _normalize_text(operation_key)
    if not key:
        return {"status": "blocked", "reason": "operation_key is required"}
    if not company:
        return {"status": "blocked", "reason": "the subject has no company to hold the approval in"}
    dumped = _dump(arguments)
    domain = [
        ("company_id", "=", company.id),
        ("command", "=", command),
        ("operation_key", "=", key),
        ("state", "=", "pending"),
    ]
    pending = approvals.search(domain, limit=1)
    if not pending:
        vals = {
            "company_id": company.id,
            "command": command,
            "edge_case": edge_case,
            "edge_reason": reason,
            "arguments": dumped,
            "operation_key": key,
            "subject_key": subject_key,
            "subject_model": subject._name if subject else False,
            "subject_id": subject.id if subject else False,
            "requested_by": env.uid,
            "requested_at": fields.Datetime.now(),
            **(extra or {}),
        }
        try:
            with env.cr.savepoint():
                pending = approvals.with_context(**{_DECISION_WRITE: _DECISION_TOKEN}).create(vals)
        except psycopg2.errors.UniqueViolation:
            # A concurrent filing of the same command and key won the pending index; answer with its row.
            env.invalidate_all()
            pending = approvals.search(domain, limit=1)
            if not pending:
                raise
    if pending.arguments != dumped:
        return {
            "status": "blocked",
            "approval_id": pending.id,
            "reason": "this operation key is already pending approval with different arguments",
        }
    pending._ensure_owner_activity()
    role = dict(pending._fields["routed_role"].selection)[pending.routed_role]
    return {
        "status": "pending",
        "approval_id": pending.id,
        "reason": f"held for {role} approval ({pending.edge_case}): {pending.edge_reason}",
    }


class PlasticosLindaApproval(models.Model):
    _name = "plasticos.linda.approval"
    _inherit = ["mail.activity.mixin"]
    _description = "Plasticos Linda Edge-Case Approval"
    # Readers of an approval may close its activity; deciding still goes through _require_approver.
    _mail_post_access = "read"
    _order = "state, requested_at desc, id desc"

    company_id = fields.Many2one("res.company", required=True, readonly=True, index=True, ondelete="restrict")
    command = fields.Selection(
        [
            ("correct_fact", "Correct Journey Fact"),
            ("propose_shipment_event", "Propose Shipment Event"),
            ("accept_shipment_event", "Accept Shipment Event"),
            ("record_gate_in", "Record Gate-In"),
            ("record_departure", "Record Departure"),
            ("record_regulatory_parties", "Record Filer/Delivery"),
            ("record_container_tare", "Record Container Tare"),
            ("record_verified_gross_mass", "Record VGM"),
            ("confirm_ready", "Confirm Load Ready"),
            ("record_actual_event", "Record Actual Pickup/Delivery"),
            ("schedule_load", "Schedule Load"),
            ("dispatch_load", "Dispatch Load"),
            ("accept_appointment", "Accept Appointment"),
        ],
        required=True,
        readonly=True,
    )
    edge_case = fields.Selection(
        [
            ("correction", "Correction"),
            ("unverified_linda_reply", "Unverified Linda Reply"),
            ("acceptance", "Acceptance"),
            ("value_conflict", "Conflicts With Current Fact"),
            ("out_of_sequence", "Out of Sequence"),
            ("unit_mismatch", "Unit Mismatch"),
            ("evidence_unverified", "Missing or Unverified Evidence"),
            ("refusal_retry", "Retry After Refusal"),
            ("refusal", "Refused (ledger)"),
        ],
        required=True,
        readonly=True,
    )
    edge_reason = fields.Text(readonly=True, help="Why the command was held or refused.")
    arguments = fields.Text(readonly=True, help="The command's arguments, as Linda sent them (JSON).")
    operation_key = fields.Char(required=True, readonly=True, index=True)
    subject_key = fields.Char(
        readonly=True, index=True, help="journey:<id>:<fact kind>, proposal:<id>, load:<id> or journey:<id>:<event>."
    )
    subject_model = fields.Char(readonly=True)
    subject_id = fields.Integer(readonly=True)
    conflict_fact_id = fields.Integer(
        readonly=True, help="The fact revision a held value conflict was measured against (soft reference)."
    )
    state = fields.Selection(
        [("pending", "Pending"), ("approved", "Approved"), ("rejected", "Rejected"), ("refused", "Refused")],
        required=True,
        readonly=True,
        default="pending",
        index=True,
    )
    requested_by = fields.Many2one("res.users", required=True, readonly=True, ondelete="restrict")
    requested_at = fields.Datetime(required=True, readonly=True)
    decided_by = fields.Many2one("res.users", readonly=True, ondelete="restrict")
    decided_at = fields.Datetime(readonly=True)
    decision_note = fields.Text(readonly=True)
    result_status = fields.Selection(
        [
            ("applied", "Applied"),
            ("already_applied", "Already Applied"),
            ("blocked", "Blocked"),
            ("not_available", "Not Available"),
            ("rejected", "Rejected"),
        ],
        readonly=True,
        help="The command's answer: once approved, or the refusal of a ledger row.",
    )
    result_record_id = fields.Integer(readonly=True)
    result_reason = fields.Text(readonly=True)
    routed_role = fields.Selection(
        # Literal values (== ROLE_LOGISTICS, ROLE_OPERATIONS) so static enum audits can read them.
        [("logistics_ops", "Logistics Operations"), ("operations_manager", "Operations Manager")],
        string="Owning Role",
        required=True,
        readonly=True,
        default=ROLE_OPERATIONS,
        index=True,
        help="Who decides this held command (DEC-011). A blocked Logistics approval re-routes it to Operations Manager.",
    )
    rerouted_by = fields.Many2one("res.users", readonly=True, ondelete="restrict")
    rerouted_at = fields.Datetime(readonly=True)

    # ── Case view (TASK-032): what the decider needs to resolve this in place ──
    affected_load_id = fields.Many2one(LOAD, compute="_compute_case", string="Affected Load")
    original_reply_id = fields.Many2one(
        "plasticos.logistics.response", compute="_compute_case", string="Original Linda Reply"
    )
    conflict_fact_ref_id = fields.Many2one(FACT, compute="_compute_case", string="Conflicting Fact")
    next_action = fields.Char(compute="_compute_case")
    can_decide = fields.Boolean(compute="_compute_case", help="Whether you may approve or reject this case now.")

    @api.depends_context("uid")
    @api.depends("state", "routed_role", "command", "edge_case", "subject_model", "subject_id", "arguments")
    def _compute_case(self):
        loads, responses, facts = self.env[LOAD], self.env["plasticos.logistics.response"], self.env[FACT]
        for rec in self:
            arguments = json.loads(rec.arguments or "{}")
            values = arguments.get("values") if isinstance(arguments.get("values"), dict) else {}
            subject = (
                self.env[rec.subject_model].browse(rec.subject_id).exists()
                if rec.subject_model in self.env and rec.subject_id
                else None
            )
            load = loads
            if subject is not None and subject._name == LOAD:
                load = subject
            elif subject is not None and "load_id" in subject._fields:
                load = subject.load_id
            if not load:
                load = loads.browse(int(arguments.get("load_id") or values.get("load_id") or 0)).exists()
            reply = responses.browse(int(values.get("linda_response_id") or 0)).exists()
            if not reply and subject is not None and "linda_response_id" in subject._fields:
                reply = subject.linda_response_id
            rec.affected_load_id = load
            rec.original_reply_id = reply
            rec.conflict_fact_ref_id = facts.browse(rec.conflict_fact_id).exists() if rec.conflict_fact_id else facts
            try:
                role = rec._require_approver() if rec.state == "pending" else None
            except AccessError:
                role = None
            rec.can_decide = bool(role)
            if rec.state != "pending":
                rec.next_action = "Decided; nothing to do."
            elif rec.result_status == "blocked" and rec.rerouted_at:
                rec.next_action = "A Logistics approval was blocked by a current guard: Operations Manager decides."
            elif rec.routed_role == ROLE_LOGISTICS:
                rec.next_action = "Logistics Operations approves or rejects; a guard that still refuses re-routes it."
            else:
                rec.next_action = "Operations Manager approves or rejects."

    _one_pending_per_key = models.UniqueIndex(
        "(company_id, command, operation_key) WHERE state = 'pending'",
        "Linda already has this command pending approval under that operation key.",
    )
    _decided_has_actor = models.Constraint(
        "CHECK(state IN ('pending', 'refused') OR (decided_by IS NOT NULL AND decided_at IS NOT NULL))",
        "A decided approval names who decided it and when.",
    )
    _refusal_is_ledger = models.Constraint(
        "CHECK((state = 'refused') = (edge_case = 'refusal'))",
        "A refused row records a refusal; a held row names its edge case.",
    )

    # ── Integrity: rows are filed by the gate and decided by a manager only ──

    def _is_decision(self):
        return self.env.context.get(_DECISION_WRITE) is _DECISION_TOKEN

    @api.model_create_multi
    def create(self, vals_list):
        if not self._is_decision():
            raise UserError("A Linda approval is filed only by a held Linda command.")
        for vals in vals_list:
            # The owning role always comes from the authority table, never from the caller.
            vals["routed_role"] = owning_role(vals.get("command"), vals.get("edge_case"))
        return super().create(vals_list)

    def write(self, vals):
        if not self._is_decision():
            raise UserError("A Linda approval is decided with Approve or Reject; it is never edited.")
        return super().write(vals)

    def unlink(self):
        raise UserError("A Linda approval is evidence and cannot be deleted.")

    # ── Decisions ─────────────────────────────────────────────────────

    def _decided(self):
        """The manager's decision write; approval rows are read-only to every role."""
        decider = self.sudo()  # sudo: the manager decides; approval rows grant no write to any role
        return decider.with_context(**{_DECISION_WRITE: _DECISION_TOKEN})

    def action_view_affected_load(self):
        """One click from the case to the exact load it concerns."""
        self.ensure_one()
        if not self.affected_load_id:
            return False
        return {
            "type": "ir.actions.act_window",
            "res_model": LOAD,
            "res_id": self.affected_load_id.id,
            "view_mode": "form",
            "target": "current",
        }

    def _require_approver(self):
        """The decider's role for every row of ``self``: ``ROLE_OPERATIONS`` or ``ROLE_LOGISTICS``.

        Server-side, per (command, edge case) and per row (DEC-011). Raises AccessError otherwise.
        """
        if is_linda(self.env):
            raise AccessError("Linda cannot approve her own edge cases.")
        user = self.env.user
        if user.has_group(MANAGER_GROUP):
            return ROLE_OPERATIONS
        if user.has_group(LOGISTICS_OPS_GROUP):
            outside = self.filtered(
                lambda rec: rec.routed_role != ROLE_LOGISTICS or (rec.command, rec.edge_case) not in LOGISTICS_AUTHORITY
            )
            if not outside:
                return ROLE_LOGISTICS
            raise AccessError(
                "Only an Operations Manager can decide this Linda edge case: "
                + ", ".join(sorted({f"{rec.command} ({rec.edge_case})" for rec in outside}))
            )
        raise AccessError("Only Logistics Operations or an Operations Manager can decide a Linda edge case.")

    # ── Owner activity (DEC-012: one open activity per pending approval) ──

    def _owner_for(self, role):
        users = self.env["res.users"].with_context(plasticos_escalation_exclude_user_ids=linda_user(self.env).ids)
        group = self.env.ref(ROLE_GROUPS[role], raise_if_not_found=False)
        return users._plasticos_escalation_manager_in_group(group, self.company_id)

    def _activity_doc(self):
        return self.sudo()  # sudo: activity bookkeeping on a read-only ledger row, never a decision

    def _close_owner_activities(self, feedback):
        for rec in self:
            rec._activity_doc().activity_feedback(list(ROLE_ACTIVITY_TYPES.values()), feedback=feedback)

    def _ensure_owner_activity(self):
        """Exactly one open activity for the owning role while pending; idempotent (searched before create)."""
        for rec in self:
            doc = rec._activity_doc()
            # activity_schedule never deduplicates: search-then-create runs under the approval row lock.
            # justification: serialize the owner activity on the approval row, as _locked_state does.
            self.env.cr.execute("SELECT id FROM plasticos_linda_approval WHERE id = %s FOR UPDATE", [rec.id])
            rec.invalidate_recordset(["state", "routed_role"])
            if rec.state != "pending":
                continue
            wanted = ROLE_ACTIVITY_TYPES[rec.routed_role]
            stale = [xmlid for role, xmlid in ROLE_ACTIVITY_TYPES.items() if role != rec.routed_role]
            if doc.activity_search(stale):
                doc.activity_feedback(stale, feedback="re-routed to Operations Manager")
            if doc.activity_search([wanted]):
                continue
            owner = rec._owner_for(rec.routed_role)
            if not owner and rec.routed_role == ROLE_LOGISTICS:
                owner = rec._owner_for(ROLE_OPERATIONS)
            if not owner:
                _logger.error(
                    "Linda approval %s (%s, %s) has no eligible %s in company %s; assign it manually.",
                    rec.id,
                    rec.command,
                    rec.edge_case,
                    rec.routed_role,
                    rec.company_id.id,
                )
                continue
            doc.activity_schedule(
                wanted,
                summary=f"Decide Linda's {rec.command.replace('_', ' ')} ({rec.edge_case.replace('_', ' ')})",
                note=rec.edge_reason or "",
                user_id=owner.id,
            )

    # ── Logistics replay (DEC-011 fail-closed) ─────────────────────────

    def _linda_env(self, approved):
        linda = linda_user(self.env)
        context = {**self.env.context, "allowed_company_ids": [self.company_id.id]}
        if approved:
            context[_APPROVED_RUN] = _APPROVED_TOKEN
        else:
            context.pop(_APPROVED_RUN, None)
        return self.env(user=linda.id, su=False, context=context)

    def _replay_clear(self):
        """Replay the command as Linda with her gate active and no approval token; never applies anything.

        Returns ``None`` when the replay would apply straight through or meet only a plain
        acceptance, else the refusal reason. The probe frees this row's pending key so the
        gate classifies the current state afresh; everything it writes is rolled back.
        """
        self.ensure_one()
        ledger = _ledger(self.env)
        floor = ledger.search([], order="id desc", limit=1).id or 0
        arguments = json.loads(self.arguments or "{}")
        try:
            with self.env.cr.savepoint():
                self._decided().write({"operation_key": f"{self.operation_key}:replay:{self.id}"})
                result = self._dispatch(self._linda_env(approved=False), arguments)
                fresh = ledger.search([("id", ">", floor)])
                raise _ReplayRollback(
                    {"result": result, "fresh": [(r.state, r.edge_case, r.edge_reason) for r in fresh]}
                )
        except _ReplayRollback as done:
            outcome = done.result
        except (UserError, ValidationError, AccessError) as error:
            outcome = {
                "result": {"status": "blocked", "reason": str(error.args[0] if error.args else error)},
                "fresh": [],
            }
        self.env.invalidate_all()
        result = outcome["result"]
        results = result if isinstance(result, list) else [result]
        for answer in results:
            if (answer or {}).get("status") in REFUSAL_STATUSES:
                return answer.get("reason") or answer.get("status")
        for state, edge_case, reason in outcome["fresh"]:
            if state != "pending" or edge_case not in _CLEAR_EDGES:
                return f"{edge_case}: {reason}" if reason else edge_case
        return None

    def _reroute_to_operations(self, reason):
        self.ensure_one()
        self._decided().write(
            {
                "routed_role": ROLE_OPERATIONS,
                "result_status": "blocked",
                "result_reason": reason,
                "rerouted_by": self.env.uid,
                "rerouted_at": fields.Datetime.now(),
            }
        )
        self._ensure_owner_activity()
        return {
            "status": "blocked",
            "approval_id": self.id,
            "rerouted_to": ROLE_OPERATIONS,
            "reason": f"not applied; re-routed to Operations Manager: {reason}",
        }

    def _approve_as_logistics(self):
        """Apply only when the replay passes every current guard; otherwise block and re-route."""
        self.ensure_one()
        refusal = self._replay_clear()
        if refusal:
            return self._reroute_to_operations(refusal)
        try:
            with self.env.cr.savepoint():
                result = self._execute()
                if result.get("status") in REFUSAL_STATUSES:
                    raise _ReplayRollback(result)
        except _ReplayRollback as done:
            self.env.invalidate_all()
            return self._reroute_to_operations(done.result.get("reason") or done.result.get("status"))
        return result

    def _locked_state(self):
        self.ensure_one()
        self.check_access("read")
        # justification: serialize concurrent decisions on the approval row; the ORM has no SELECT FOR UPDATE.
        self.env.cr.execute("SELECT id FROM plasticos_linda_approval WHERE id = %s FOR UPDATE", [self.id])
        self.invalidate_recordset()
        return self.state

    def action_approve(self, note=None):
        """Run the held command as Linda and record its answer. Returns that answer.

        An approval already decided answers its decision: ``already_applied`` with
        the recorded result when approved, ``rejected`` when rejected. A ledger
        refusal is not an approval and cannot be approved.
        """
        role = self._require_approver()
        if linda_stopped(self.env):
            raise UserError("Linda is archived (operator stop). Reactivate her before approving her held commands.")
        results = []
        for rec in self:
            state = rec._locked_state()
            if state == "approved":
                results.append(
                    {"status": "already_applied", "approval_id": rec.id, "reason": f"approved: {rec.result_status}"}
                )
                continue
            if state in ("rejected", "refused"):
                results.append({"status": "rejected", "approval_id": rec.id, "reason": f"this request is {state}"})
                continue
            if role == ROLE_LOGISTICS:
                # Re-checked under the row lock: a concurrent re-route moves the row to Operations Manager.
                rec._require_approver()
                result = rec._approve_as_logistics()
                if result.get("rerouted_to"):
                    results.append(result)
                    continue
            else:
                result = rec._execute()
            rec._close_owner_activities(f"approved: {result.get('status')}")
            rec._decided().write(
                {
                    "state": "approved",
                    "decided_by": self.env.uid,
                    "decided_at": fields.Datetime.now(),
                    "decision_note": _normalize_text(note),
                    "result_status": result.get("status"),
                    "result_record_id": result.get("record_id") or False,
                    "result_reason": result.get("reason"),
                }
            )
            results.append({**result, "approval_id": rec.id})
        if len(results) == 1:
            return results[0]
        return results

    def action_reject(self, note=None):
        self._require_approver()
        for rec in self:
            if rec._locked_state() != "pending":
                continue
            rec._require_approver()
            rec._close_owner_activities("rejected")
            rec._decided().write(
                {
                    "state": "rejected",
                    "decided_by": self.env.uid,
                    "decided_at": fields.Datetime.now(),
                    "decision_note": _normalize_text(note),
                }
            )
        return True

    def _execute(self):
        """The held command, run as Linda in this approval's company. Never raises a refusal."""
        self.ensure_one()
        linda = linda_user(self.env)
        if not linda:
            return {"status": "not_available", "reason": "the Linda user no longer exists"}
        context = {
            **self.env.context,
            "allowed_company_ids": [self.company_id.id],
            _APPROVED_RUN: _APPROVED_TOKEN,
        }
        env = self.env(user=linda.id, su=False, context=context)
        arguments = json.loads(self.arguments or "{}")
        try:
            with self.env.cr.savepoint():
                return self._dispatch(env, arguments)
        except (UserError, ValidationError, AccessError) as error:
            return {"status": "blocked", "reason": str(error.args[0] if error.args else error)}

    def _dispatch(self, env, arguments):
        """Explicit command table: no dynamic dispatch, so the gate-reach witness sees every call."""
        command = self.command
        facts = env[FACT]
        if command == "correct_fact":
            return facts.action_correct_fact(**arguments)
        if command == "propose_shipment_event":
            return env[PROPOSAL].action_propose_shipment_event(**arguments)
        if command == "accept_shipment_event":
            proposal = env[PROPOSAL].browse(int(arguments.get("proposal_id") or 0)).exists()
            if not proposal:
                return {"status": "not_available", "reason": "the shipment event proposal no longer exists"}
            proposal.action_accept(arguments.get("note"))
            proposal.invalidate_recordset()
            return {"status": proposal.command_status or "applied", "record_id": proposal.id}
        if command == "accept_appointment":
            appointment = env["plasticos.load.appointment"].browse(int(arguments.get("appointment_id") or 0)).exists()
            if not appointment:
                return {"status": "not_available", "reason": "the appointment no longer exists"}
            return appointment.action_accept_appointment()
        if command in ("confirm_ready", "record_actual_event", "schedule_load", "dispatch_load"):
            return self._dispatch_load(env, arguments)
        if self.edge_case == "value_conflict":
            return self._apply_conflict_as_correction(env, arguments)
        return self._record_fact(env, command, arguments)

    @staticmethod
    def _record_fact(env, command, arguments):
        facts = env[FACT]
        if command == "record_gate_in":
            return facts.action_record_gate_in(**arguments)
        if command == "record_departure":
            return facts.action_record_departure(**arguments)
        if command == "record_regulatory_parties":
            return facts.action_record_regulatory_parties(**arguments)
        if command == "record_container_tare":
            return facts.action_record_container_tare(**arguments)
        if command == "record_verified_gross_mass":
            return facts.action_record_verified_gross_mass(**arguments)
        return {"status": "not_available", "reason": f"unknown held command {command!r}"}

    def _dispatch_load(self, env, arguments):
        load = env[LOAD].browse(int(arguments.get("load_id") or 0)).exists()
        if not load:
            return {"status": "not_available", "reason": "the load no longer exists"}
        if self.command == "confirm_ready":
            load.action_confirm_ready()
            return {"status": "applied", "record_id": load.id}
        if self.command == "schedule_load":
            load.action_schedule(arguments.get("pickup_dt"), arguments.get("delivery_dt"))
            return {"status": "applied", "record_id": load.id}
        if self.command == "dispatch_load":
            load.action_dispatch()
            return {"status": "applied", "record_id": load.id}
        attachment = env["ir.attachment"].browse(int(arguments.get("attachment_id") or 0))
        return load.action_record_actual_event(
            arguments.get("event_kind"), arguments.get("occurred_at"), attachment, arguments.get("reason")
        )

    def _apply_conflict_as_correction(self, env, arguments):
        """An approved conflicting record supersedes the revision it conflicted with, if still current."""
        kind = self.command.removeprefix("record_")
        journey = env[JOURNEY].browse(int(arguments.get("journey_id") or 0)).exists()
        if not journey:
            return {"status": "not_available", "reason": "container journey not found"}
        _lock(env, "plasticos_iso_journey", [journey.id])
        current = journey.current_fact(kind)
        if not current or current.id != self.conflict_fact_id:
            # C12-SCOPE-3 (4): someone recorded or corrected this fact after Linda's conflict was held.
            return {
                "status": "blocked",
                "reason": "stale: the fact Linda's value conflicted with is no longer the current revision",
            }
        values = {name: value for name, value in arguments.items() if name not in ("journey_id", "operation_key")}
        reason = (
            f"Linda reported a different {kind.replace('_', ' ')}; approved by {self.env.user.name}"
            f" (Linda approval {self.id})"
        )
        return env[FACT].action_correct_fact(current.id, values, reason, f"linda-approval:{self.id}")
