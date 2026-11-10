"""Opportunity → Lot → Run → Result → Offer lineage, owned by CRM Bridge.

Matching does not depend on CRM Bridge, so the lineage fields live here:
``plasticos.match.run.opportunity_id`` / ``approval_id`` and
``plasticos.offer.match_result_id``. Offer acceptance records one explicit
commercial winner per opportunity and marks that opportunity Won. It creates
no purchase order, sale order, or transaction.
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

    opportunity_id = fields.Many2one(
        related="match_result_id.match_run_id.opportunity_id",
        store=True,
        index=True,
        readonly=True,
        string="Opportunity",
        help="Native CRM opportunity this offer pursues, denormalized from its Gate result lineage.",
    )

    # One unsent draft per reviewed result: a second creation call finds the
    # existing offer. Historical offers without a result are unaffected.
    _unique_offer_per_match_result = models.UniqueIndex("(match_result_id) WHERE match_result_id IS NOT NULL")
    # One commercial winner per opportunity, enforced by PostgreSQL: two
    # concurrent acceptances cannot both commit. The pre-write check in
    # ``action_accept`` only turns the common case into a readable message.
    _unique_winner_per_opportunity = models.UniqueIndex(
        "(opportunity_id) WHERE state = 'accepted' AND opportunity_id IS NOT NULL"
    )

    def _plasticos_opportunity(self):
        self.ensure_one()
        return self.opportunity_id

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
        """Accept: one explicit commercial winner per opportunity, then the native Won stage.

        No purchase order, sale order, or transaction is created here.
        """
        opportunity_by_offer = {rec.id: rec.opportunity_id for rec in self}
        opportunities = self.env["crm.lead"].union(*[opp for opp in opportunity_by_offer.values() if opp])
        if opportunities:
            # Readable pre-check for the common case; the partial unique index on
            # (opportunity_id) WHERE state = 'accepted' is the invariant under concurrency.
            winners = self.search(
                [("id", "not in", self.ids), ("state", "=", "accepted"), ("opportunity_id", "in", opportunities.ids)]
            )
            winner_by_opportunity = {offer.opportunity_id.id: offer for offer in winners}
            for rec in self:
                opportunity = opportunity_by_offer[rec.id]
                if not opportunity:
                    continue
                other = winner_by_opportunity.get(opportunity.id)
                if other:
                    raise UserError(
                        _("Opportunity %(opp)s already has a commercial winner (%(offer)s).")
                        % {"opp": opportunity.name, "offer": other.name}
                    )
                # Two offers accepted in one call for one opportunity is also two winners.
                winner_by_opportunity[opportunity.id] = rec
        res = super().action_accept()
        won = self.env["crm.lead"]
        for rec in self:
            opportunity = rec._plasticos_opportunity()
            if not opportunity:
                continue
            won |= opportunity
            opportunity.message_post(
                body=_(
                    "Commercial winner recorded: offer %(offer)s to %(buyer)s. The opportunity is Won and waiting "
                    "for admin submit. No order was created.",
                    offer=rec.name,
                    buyer=rec.buyer_id.name,
                ),
                message_type="notification",
                subtype_xmlid="mail.mt_note",
            )
        won._plasticos_mark_won()
        return res
