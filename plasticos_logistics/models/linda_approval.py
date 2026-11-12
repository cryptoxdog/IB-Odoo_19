"""Operations Manager approval of Linda's edge cases (S11, OP11-E02, coordinator C12-SCOPE-2).

Linda is ``plasticos_logistics.user_linda``, a service user with the Logistics
group only. When she runs a gated command, a straight-through outcome applies at
once. An edge case is held here instead, pending until an Operations Manager
approves or rejects it:

* any journey-fact correction;
* a shipment event proposal citing a Linda reply whose disposition is
  ``identity_unverified`` or ``unresolved``;
* accepting a shipment event proposal;
* recording a journey fact whose value conflicts with the current revision, that
  is out of sequence, whose weight unit is wrong, or whose evidence is missing or
  unverified;
* retrying a command that was refused or rejected under the same operation key.

Neither Linda nor a Logistics user without Operations Manager rights can approve.
Approval runs the held command as Linda, so the fact or proposal keeps her as its
author, under a context token that RPC cannot forge. Human actors are never
held: they need no second approver (operator decision 2026-11-12). No cron is
reassigned; today no automated path calls a gated command (EVIDENCE/S11).
"""

import json
from datetime import date, datetime

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

from .iso_journey import _lock, _normalize_text

LINDA_XMLID = "plasticos_logistics.user_linda"
MANAGER_GROUP = "plasticos_security_base.group_operations_manager"
FACT = "plasticos.iso.journey.fact"
PROPOSAL = "plasticos.shipment.event.proposal"
APPROVAL = "plasticos.linda.approval"
# Set only by action_approve: an object, so no RPC context can carry it.
_APPROVED_RUN = "plasticos_linda_approved_run"
_APPROVED_TOKEN = object()
_DECISION_WRITE = "plasticos_linda_approval_decision"
_DECISION_TOKEN = object()
RECORD_COMMANDS = (
    "record_gate_in",
    "record_departure",
    "record_regulatory_parties",
    "record_container_tare",
    "record_verified_gross_mass",
)


def linda_user(env):
    """The Linda service user, or an empty recordset when her record is absent."""
    return env.ref(LINDA_XMLID, raise_if_not_found=False) or env["res.users"]


def linda_acting(env):
    """True when Linda runs a gated command that is not an approved replay."""
    linda = linda_user(env)
    if not linda or env.uid != linda.id:
        return False
    return env.context.get(_APPROVED_RUN) is not _APPROVED_TOKEN


def _json_default(value):
    if isinstance(value, datetime):
        return fields.Datetime.to_string(value)
    if isinstance(value, date):
        return fields.Date.to_string(value)
    raise TypeError(f"cannot hold {type(value).__name__} for approval")


def prior_refusal(env, command, operation_key, company):
    """Whether Linda's ``command`` under this key was already refused or rejected."""
    return bool(
        env[APPROVAL]
        .sudo()  # sudo: Linda reads her own approval history; she holds no write on it
        .search_count(
            [
                ("company_id", "=", company.id),
                ("command", "=", command),
                ("operation_key", "=", operation_key),
                "|",
                ("state", "=", "rejected"),
                ("result_status", "in", ["blocked", "not_available", "rejected"]),
            ],
            limit=1,
        )
    )


def hold_for_approval(env, command, edge_case, reason, arguments, operation_key, company, subject=None):
    """Hold Linda's edge case pending Operations Manager approval. Idempotent per key."""
    approvals = env[APPROVAL].sudo()  # sudo: Linda files her own request; she cannot write or approve it
    key = _normalize_text(operation_key)
    pending = approvals.search(
        [
            ("company_id", "=", company.id),
            ("command", "=", command),
            ("operation_key", "=", key),
            ("state", "=", "pending"),
        ],
        limit=1,
    )
    if not pending:
        pending = approvals.with_context(**{_DECISION_WRITE: _DECISION_TOKEN}).create(
            {
                "company_id": company.id,
                "command": command,
                "edge_case": edge_case,
                "edge_reason": reason,
                "arguments": json.dumps(arguments, default=_json_default, sort_keys=True),
                "operation_key": key,
                "subject_model": subject._name if subject else False,
                "subject_id": subject.id if subject else False,
                "requested_by": env.uid,
                "requested_at": fields.Datetime.now(),
            }
        )
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
        ],
        required=True,
        readonly=True,
    )
    edge_case = fields.Selection(
        [
            ("correction", "Fact Correction"),
            ("unverified_linda_reply", "Unverified Linda Reply"),
            ("acceptance", "Proposal Acceptance"),
            ("value_conflict", "Conflicts With Current Fact"),
            ("out_of_sequence", "Out of Sequence"),
            ("unit_mismatch", "Unit Mismatch"),
            ("evidence_unverified", "Missing or Unverified Evidence"),
            ("refusal_retry", "Retry After Refusal"),
        ],
        required=True,
        readonly=True,
    )
    edge_reason = fields.Text(readonly=True, help="Why the command was held.")
    arguments = fields.Text(readonly=True, help="The held command's arguments, as Linda sent them (JSON).")
    operation_key = fields.Char(required=True, readonly=True, index=True)
    subject_model = fields.Char(readonly=True)
    subject_id = fields.Integer(readonly=True)
    state = fields.Selection(
        [("pending", "Pending"), ("approved", "Approved"), ("rejected", "Rejected")],
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
        help="The held command's answer once approved.",
    )
    result_record_id = fields.Integer(readonly=True)
    result_reason = fields.Text(readonly=True)

    _one_pending_per_key = models.UniqueIndex(
        "(company_id, command, operation_key) WHERE state = 'pending'",
        "Linda already has this command pending approval under that operation key.",
    )
    _decided_has_actor = models.Constraint(
        "CHECK(state = 'pending' OR (decided_by IS NOT NULL AND decided_at IS NOT NULL))",
        "A decided approval names who decided it and when.",
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

    def _require_approver(self):
        linda = linda_user(self.env)
        if linda and self.env.uid == linda.id:
            raise AccessError("Linda cannot approve her own edge cases.")
        if not self.env.user.has_group(MANAGER_GROUP):
            raise AccessError("Only an Operations Manager can approve or reject a Linda edge case.")

    def _locked_pending(self):
        self.ensure_one()
        self.check_access("read")
        # justification: serialize concurrent decisions on the approval row; the ORM has no SELECT FOR UPDATE.
        self.env.cr.execute("SELECT id FROM plasticos_linda_approval WHERE id = %s FOR UPDATE", [self.id])
        self.invalidate_recordset()
        return self.state == "pending"

    def action_approve(self, note=None):
        """Run the held command as Linda and record its answer. Returns that answer."""
        self._require_approver()
        results = []
        for rec in self:
            if not rec._locked_pending():
                results.append({"status": "already_applied", "approval_id": rec.id, "reason": f"already {rec.state}"})
                continue
            result = rec._execute()
            rec.sudo().with_context(
                **{_DECISION_WRITE: _DECISION_TOKEN}
            ).write(  # sudo: the manager decides; rows stay read-only
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
        return results[0] if len(results) == 1 else results

    def action_reject(self, note=None):
        self._require_approver()
        for rec in self:
            if not rec._locked_pending():
                continue
            rec.sudo().with_context(
                **{_DECISION_WRITE: _DECISION_TOKEN}
            ).write(  # sudo: the manager decides; rows stay read-only
                {
                    "state": "rejected",
                    "decided_by": self.env.uid,
                    "decided_at": fields.Datetime.now(),
                    "decision_note": _normalize_text(note),
                }
            )
        return True

    def _execute(self):
        """The held command, run as Linda under the approval token. Never raises a refusal."""
        self.ensure_one()
        linda = linda_user(self.env)
        if not linda:
            return {"status": "not_available", "reason": "the Linda user no longer exists"}
        env = self.env(user=linda.id, su=False, context={**self.env.context, _APPROVED_RUN: _APPROVED_TOKEN})
        arguments = json.loads(self.arguments or "{}")
        try:
            with self.env.cr.savepoint():
                return self._dispatch(env, arguments)
        except (UserError, ValidationError, AccessError) as error:
            return {"status": "blocked", "reason": str(error.args[0] if error.args else error)}

    def _dispatch(self, env, arguments):
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
        if self.edge_case == "value_conflict":
            return self._apply_conflict_as_correction(env, arguments)
        return getattr(facts, f"action_{command}")(**arguments)

    def _apply_conflict_as_correction(self, env, arguments):
        """An approved conflicting record supersedes the current revision of that fact."""
        kind = self.command.removeprefix("record_")
        journey = env["plasticos.iso.journey"].browse(int(arguments.get("journey_id") or 0)).exists()
        if not journey:
            return {"status": "not_available", "reason": "container journey not found"}
        _lock(env, "plasticos_iso_journey", [journey.id])
        current = journey.current_fact(kind)
        if not current:
            return getattr(env[FACT], f"action_{self.command}")(**arguments)
        values = {name: value for name, value in arguments.items() if name not in ("journey_id", "operation_key")}
        reason = (
            f"Linda reported a different {kind.replace('_', ' ')}; approved by {self.env.user.name}"
            f" (Linda approval {self.id})"
        )
        return env[FACT].action_correct_fact(current.id, values, reason, f"linda-approval:{self.id}")
