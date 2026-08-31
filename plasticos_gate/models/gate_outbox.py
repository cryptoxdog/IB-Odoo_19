"""Transactional outbox for authoritative Odoo -> Graph projections.

Why an outbox and not a direct call: the Odoo business write and the Graph
projection must not be two independent network commitments. A row is created in
the *same* PostgreSQL transaction as the business write, so either both survive
or neither does. Delivery is then at-least-once and idempotent — never a
distributed transaction, and never a claim of exactly-once.

Graph is a derived read model. Graph being unreachable must never roll back a
valid Odoo enrichment, so a failed send parks here with a retry budget instead
of raising into the business transaction.
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

OUTBOX_WORKER_LOCK = "gate.outbox.drain"

#: A row still 'sending' after this many minutes lost its worker (process kill,
#: container replacement) and is returned to the retry pool.
SENDING_STALE_MINUTES = 30


class PlasticosGateOutbox(models.Model):
    _name = "plasticos.gate.outbox"
    _description = "Gate Projection Outbox"
    _order = "id"

    semantic_key = fields.Char(
        required=True,
        index=True,
        readonly=True,
        help="Dedupe identity for one logical projection: entity type, identity, and content hash.",
    )
    action = fields.Char(
        required=True,
        readonly=True,
        help="Gate action used to publish this projection (e.g. sync).",
    )
    payload_json = fields.Json(
        required=True,
        readonly=True,
        help="Validated, allowlisted projection payload as sent to Gate.",
    )
    state = fields.Selection(
        [
            ("pending", "Pending"),
            ("sending", "Sending"),
            ("retry", "Retry"),
            ("done", "Done"),
            ("failed", "Failed"),
        ],
        default="pending",
        index=True,
        readonly=True,
        help="pending/retry are claimable; done and failed are terminal.",
    )
    attempt_count = fields.Integer(default=0, readonly=True, help="Delivery attempts already made.")
    next_attempt_at = fields.Datetime(
        index=True,
        readonly=True,
        help="Earliest time this row may be claimed again. Empty means immediately.",
    )
    last_attempt_at = fields.Datetime(readonly=True)
    last_error = fields.Text(readonly=True, help="Classified failure from the most recent attempt.")
    failure_class = fields.Char(readonly=True, help="retryable / permanent / unknown.")
    gate_packet_id = fields.Char(readonly=True, help="Gate response TransportPacket id for audit.")
    completed_at = fields.Datetime(readonly=True)

    _unique_semantic_key = models.Constraint(
        "unique(semantic_key)",
        "A projection with this semantic key is already queued or delivered.",
    )

    # ── Enqueue (same transaction as the business write) ──────────

    @api.model
    def enqueue_projection(self, *, semantic_key, action, payload):
        """Create (or reuse) the outbox row for one projection.

        Called inside the business transaction that performed the authoritative
        Odoo write. Returns the record. An identical projection that is already
        queued or delivered is a no-op: the semantic key carries a content hash,
        so an unchanged projection cannot enqueue twice, while a changed one gets
        its own row.
        """
        if not semantic_key or not action or not payload:
            raise ValueError("enqueue_projection requires semantic_key, action, and payload")
        existing = self.sudo().search([("semantic_key", "=", semantic_key)], limit=1)
        if existing:
            return existing
        return self.sudo().create(
            {
                "semantic_key": semantic_key,
                "action": action,
                "payload_json": payload,
                "state": "pending",
            }
        )

    # ── Delivery ──────────────────────────────────────────────────

    def _mark_delivered(self, packet_id):
        self.ensure_one()
        self.sudo().write(
            {
                "state": "done",
                "gate_packet_id": packet_id or False,
                "last_error": False,
                "failure_class": False,
                "completed_at": fields.Datetime.now(),
            }
        )

    def _mark_failed_attempt(self, failure_class, message):
        """Schedule the next attempt, or fail terminally when the budget is spent."""
        from odoo.addons.plasticos_gate.services.gate_retry import attempts_exhausted, next_attempt_at

        self.ensure_one()
        attempts = (self.attempt_count or 0) + 1
        now = fields.Datetime.now()
        vals = {
            "attempt_count": attempts,
            "last_attempt_at": now,
            "last_error": message,
            "failure_class": failure_class,
        }
        if failure_class == "permanent" or attempts_exhausted(attempts):
            vals["state"] = "failed"
            vals["next_attempt_at"] = False
        else:
            vals["state"] = "retry"
            vals["next_attempt_at"] = next_attempt_at(attempts, now=now)
        self.sudo().write(vals)

    def _deliver_one(self):
        """Send one row to Gate. Never raises: outcomes are recorded on the row."""
        from odoo.addons.plasticos_gate.services.gate_client import (
            classify_transport_failure,
            send_graph_sync_action,
        )
        from odoo.addons.plasticos_gate.services.gate_config import GateIntegrationError
        from odoo.addons.plasticos_gate.services.gate_mappers import extract_audit_metadata

        self.ensure_one()
        try:
            result = send_graph_sync_action(
                self.env,
                payload=self.payload_json,
                correlation_id=self.semantic_key,
            )
        except GateIntegrationError as exc:
            failure = getattr(exc, "failure_class", None) or classify_transport_failure(exc).value
            self._mark_failed_attempt(failure, str(exc))
            return False
        except Exception as exc:  # noqa: BLE001 — boundary: classify, never escape the worker
            failure = classify_transport_failure(exc).value
            _logger.exception("Gate projection delivery failed for outbox %s", self.id)
            self._mark_failed_attempt(failure, str(exc))
            return False

        audit = extract_audit_metadata(result["packet"])
        self._mark_delivered(audit.get("gate_packet_id"))
        return True

    # ── Worker ────────────────────────────────────────────────────

    @api.model
    def _requeue_stale_sending(self):
        """Return rows abandoned mid-send by a dead worker to the retry pool."""
        cutoff = fields.Datetime.subtract(fields.Datetime.now(), minutes=SENDING_STALE_MINUTES)
        stale = self.sudo().search([("state", "=", "sending"), ("last_attempt_at", "<", cutoff)])
        if stale:
            _logger.warning("Requeuing %s outbox row(s) abandoned mid-send.", len(stale))
            stale.write({"state": "retry", "next_attempt_at": False})
        return len(stale)

    @api.model
    def _claim_batch(self, limit):
        """Claim up to ``limit`` due rows, marking them 'sending' before delivery."""
        now = fields.Datetime.now()
        due = self.sudo().search(
            [
                ("state", "in", ["pending", "retry"]),
                "|",
                ("next_attempt_at", "=", False),
                ("next_attempt_at", "<=", now),
            ],
            order="id",
            limit=limit,
        )
        if due:
            due.write({"state": "sending", "last_attempt_at": now})
        return due

    @api.model
    def action_cron_drain_outbox(self, limit=100):
        """Drain due projections to Gate. Safe to run on an empty or disabled queue."""
        from odoo.addons.plasticos_gate.services.gate_config import graph_outbox_worker_enabled
        from odoo.addons.plasticos_gate.services.gate_locks import worker_lock

        if not graph_outbox_worker_enabled(self.env):
            _logger.info(
                "Gate outbox worker disabled (plasticos.gate.graph_outbox_worker_enabled=0); pending rows stay queued."
            )
            return 0

        delivered = 0
        with worker_lock(self.env.cr, OUTBOX_WORKER_LOCK) as acquired:
            if not acquired:
                return 0
            self._requeue_stale_sending()
            self.env.cr.commit()  # release the claim of the requeue before sending
            batch = self._claim_batch(limit)
            self.env.cr.commit()  # claim is durable before any network call
            for row in batch:
                if row._deliver_one():
                    delivered += 1
                # One row's outcome must never be rolled back by the next row's failure.
                self.env.cr.commit()
        _logger.info("Gate outbox drain delivered %s of %s claimed row(s).", delivered, len(batch))
        return delivered

    # ── Operator actions ──────────────────────────────────────────

    def action_retry_now(self):
        """Operator retry for a failed projection: reset the budget and requeue."""
        for rec in self:
            if rec.state not in ("failed", "retry", "sending"):
                raise UserError(_("Outbox row %s is not in a retryable state.") % rec.id)
        self.sudo().write(
            {
                "state": "pending",
                "attempt_count": 0,
                "next_attempt_at": False,
                "last_error": False,
                "failure_class": False,
            }
        )
        return True

    def unlink(self):
        """Never delete undelivered projection work."""
        for rec in self:
            if rec.state not in ("done", "failed"):
                raise UserError(_("Outbox row %s is still undelivered. Let it retry or fail it explicitly.") % rec.id)
        return super().unlink()
