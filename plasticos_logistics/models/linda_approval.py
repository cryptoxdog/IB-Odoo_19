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

Neither Linda nor a Logistics user without Operations Manager rights can approve.
Approval runs the held command as Linda, in the approval's company only, under a
context token that RPC cannot forge, so the owner guards still run and the record
keeps Linda as its author. Human actors are never held: they need no second
approver (operator decision 2026-11-12). No cron is reassigned; today no automated
path calls a gated command (EVIDENCE/S11).
"""

import json
from datetime import date, datetime

import psycopg2.errors

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

from .iso_journey import _lock, _normalize_text

LINDA_XMLID = "plasticos_logistics.user_linda"
MANAGER_GROUP = "plasticos_security_base.group_operations_manager"
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


def linda_user(env):
    """The Linda service user, or an empty recordset when her record is absent."""
    return env.ref(LINDA_XMLID, raise_if_not_found=False) or env["res.users"]


def is_linda(env):
    """True when the acting user is Linda, approved replay or not."""
    linda = linda_user(env)
    return bool(linda) and env.uid == linda.id


def linda_acting(env):
    """True when Linda runs a gated command that is not an approved replay."""
    return is_linda(env) and env.context.get(_APPROVED_RUN) is not _APPROVED_TOKEN


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
    """Hold Linda's edge case pending Operations Manager approval.

    Idempotent per company, command and key: the same arguments answer the same
    pending approval, different arguments under that key are refused, and a
    concurrent filing that loses the pending index answers the winning row.
    """
    approvals = _ledger(env)
    key = _normalize_text(operation_key)
    if not key:
        return {"status": "blocked", "reason": "operation_key is required"}
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
    return {
        "status": "pending",
        "approval_id": pending.id,
        "reason": f"held for Operations Manager approval ({pending.edge_case}): {pending.edge_reason}",
    }


class PlasticosLindaApproval(models.Model):
    _name = "plasticos.linda.approval"
    _description = "Plasticos Linda Edge-Case Approval"
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

    def _require_approver(self):
        if is_linda(self.env):
            raise AccessError("Linda cannot approve her own edge cases.")
        if not self.env.user.has_group(MANAGER_GROUP):
            raise AccessError("Only an Operations Manager can approve or reject a Linda edge case.")

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
        self._require_approver()
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
            result = rec._execute()
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
        if command in ("confirm_ready", "record_actual_event"):
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
