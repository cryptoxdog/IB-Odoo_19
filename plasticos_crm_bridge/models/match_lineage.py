"""Opportunity → Lot → Run → Result → Offer lineage, owned by CRM Bridge.

Matching does not depend on CRM Bridge, so the lineage fields live here:
``plasticos.match.run.opportunity_id`` / ``approval_id`` and
``plasticos.offer.match_result_id``. Offer acceptance records one explicit
commercial winner per opportunity and hands a draft native sale order to the
existing transaction compiler.
"""

from __future__ import annotations

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

# Lineage columns the orchestrator must carry onto a durable failure receipt.
LINEAGE_RUN_FIELDS = ("opportunity_id", "approval_id")


class PlasticosMatchRunOpportunity(models.Model):
    _inherit = "plasticos.match.run"

    opportunity_id = fields.Many2one(
        "crm.lead",
        string="Opportunity",
        index=True,
        ondelete="restrict",
        help="Native CRM opportunity this Gate run matches for. Historical intake runs have none.",
    )
    approval_id = fields.Many2one(
        "plasticos.opportunity.approval",
        string="Approved Lot",
        index=True,
        ondelete="restrict",
        help="Frozen lot the Gate request was built from.",
    )

    @api.constrains("opportunity_id", "approval_id")
    def _check_lot_opportunity(self):
        for rec in self:
            if rec.approval_id and rec.opportunity_id and rec.approval_id.opportunity_id != rec.opportunity_id:
                raise ValidationError(_("The approved lot belongs to a different opportunity."))

    @api.depends("opportunity_id")
    def _compute_display_name(self):
        super()._compute_display_name()
        for rec in self.filtered(lambda run: not run.intake_id and run.opportunity_id):
            rec.display_name = f"Match run {rec.id or 'new'} [{rec.state}] / {rec.opportunity_id.name}"

    def _plasticos_durable_lineage_fields(self):
        return tuple(super()._plasticos_durable_lineage_fields()) + LINEAGE_RUN_FIELDS

    def _plasticos_lot_retry_subject(self):
        """Retry a lot run from its frozen approval, never from the live profile."""
        self.ensure_one()
        approval = self.approval_id
        if not approval:
            return super()._plasticos_lot_retry_subject()
        return {
            "supplier_partner_id": approval.partner_id.id,
            "snapshot": dict(approval.snapshot or {}),
            "run_vals": {"opportunity_id": approval.opportunity_id.id, "approval_id": approval.id},
            "intake": approval.source_intake_id or None,
        }


class PlasticosOfferMatchLineage(models.Model):
    _inherit = "plasticos.offer"

    match_result_id = fields.Many2one(
        "plasticos.match.result",
        string="Match Result",
        index=True,
        ondelete="restrict",
        help="Reviewed Gate match result this offer was created from.",
    )

    # One unsent draft per reviewed result: a second creation call finds the
    # existing offer. Historical offers without a result are unaffected.
    _unique_offer_per_match_result = models.UniqueIndex("(match_result_id) WHERE match_result_id IS NOT NULL")

    def _plasticos_opportunity(self):
        self.ensure_one()
        return self.match_result_id.match_run_id.opportunity_id

    def _plasticos_approval(self):
        self.ensure_one()
        return self.match_result_id.match_run_id.approval_id

    @api.constrains("match_result_id", "buyer_id", "supplier_id")
    def _check_result_parties(self):
        for rec in self.filtered("match_result_id"):
            result = rec.match_result_id
            if result.buyer_partner_id != rec.buyer_id:
                raise ValidationError(_("Offer buyer must be the matched buyer of its Gate result."))
            run = result.match_run_id
            if run and run.supplier_partner_id != rec.supplier_id:
                raise ValidationError(_("Offer supplier must be the supplier of its Gate match run."))

    def action_accept(self):
        """Accept: one explicit commercial winner per opportunity, then one draft native sale order."""
        for rec in self:
            opportunity = rec._plasticos_opportunity()
            if not opportunity:
                continue
            others = self.search(
                [
                    ("id", "!=", rec.id),
                    ("state", "=", "accepted"),
                    ("match_result_id.match_run_id.opportunity_id", "=", opportunity.id),
                ],
                limit=1,
            )
            if others:
                raise UserError(
                    _("Opportunity %(opp)s already has a commercial winner (%(offer)s).")
                    % {"opp": opportunity.name, "offer": others.name}
                )
        res = super().action_accept()
        for rec in self:
            opportunity = rec._plasticos_opportunity()
            if not opportunity:
                continue
            approval = rec._plasticos_approval()
            order = self.env["sale.order"]._plasticos_draft_order_for_offer(
                rec, opportunity.id, approval.material_profile_id
            )
            opportunity.message_post(
                body=_(
                    "Commercial winner recorded: offer %(offer)s to %(buyer)s. Draft sale order %(order)s awaits "
                    "confirmation; confirmation compiles the transaction.",
                    offer=rec.name,
                    buyer=rec.buyer_id.name,
                    order=order.name,
                ),
                message_type="notification",
                subtype_xmlid="mail.mt_note",
            )
        return res
