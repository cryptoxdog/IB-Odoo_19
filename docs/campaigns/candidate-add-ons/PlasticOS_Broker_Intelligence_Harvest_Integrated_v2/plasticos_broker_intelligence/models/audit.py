"""Append-only, source-bound approval events created only by the knowledge owner."""
from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError


class BrokerReviewEvent(models.Model):
    _name = "plasticos.broker.review.event"
    _description = "Broker Knowledge Review Audit Event"
    _order = "id desc"

    knowledge_id = fields.Many2one("plasticos.broker.knowledge", required=True, ondelete="restrict", readonly=True)
    event = fields.Selection([("approved", "Approved"), ("retired", "Retired")], required=True, readonly=True)
    actor_id = fields.Many2one("res.users", required=True, ondelete="restrict", readonly=True)
    company_id = fields.Many2one("res.company", required=True, ondelete="restrict", readonly=True)
    reason = fields.Text(required=True, readonly=True)
    source_snapshot = fields.Text(required=True, readonly=True)
    support_snapshot = fields.Text(readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        raise AccessError("Review events cannot be created directly; use knowledge approval or retirement.")

    @api.model
    def _append_from_knowledge(self, *, knowledge, event, reason):
        """Private, audited write seam. Odoo RPC cannot invoke underscore methods."""
        knowledge.ensure_one()
        knowledge._require_reviewer()
        if event not in ("approved", "retired") or knowledge.state != event:
            raise UserError("Review event must reflect an actual knowledge lifecycle transition.")
        if not str(reason or "").strip():
            raise UserError("Review event requires its actual lifecycle rationale.")
        values = {
            "knowledge_id": knowledge.id, "event": event,
            "actor_id": self.env.user.id,
            "company_id": knowledge.company_id.id or self.env.company.id,
            "reason": reason,
            "source_snapshot": "%s:%s#%s" % (knowledge.source_file, knowledge.source_sha256,
                                            knowledge.source_selector),
            "support_snapshot": knowledge.review_evidence_ref,
        }
        # Only this owner may bypass the direct-create guard; the original actor
        # is captured before sudo and is never supplied by an untrusted caller.
        return super(BrokerReviewEvent, self.sudo()).create([values])

    def write(self, vals):
        raise UserError("Review events are immutable.")

    def unlink(self):
        raise UserError("Review events cannot be deleted.")
