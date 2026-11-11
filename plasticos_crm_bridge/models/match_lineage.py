"""Opportunity → Lot → Run → Result → Offer lineage, owned by CRM Bridge.

Matching does not depend on CRM Bridge, so the lineage fields live here:
``plasticos.match.run.opportunity_id`` / ``approval_id`` and
``plasticos.offer.match_result_id``. Offer acceptance records one explicit
commercial winner per opportunity and marks that opportunity Won. It creates
no purchase order, sale order, or transaction.

``plasticos.offer.opportunity_id`` is one stored relation for both routes:
a Gate offer takes it from its result's run; a manual offer (buyers selected
by the broker, no Gate result) is linked directly and names the
opportunity-owned material row it was drafted from.
"""

from __future__ import annotations

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

# Lineage columns the orchestrator must carry onto a durable failure receipt.
LINEAGE_RUN_FIELDS = ("opportunity_id", "approval_id")

# Specification of an opportunity material row that an accepted offer is bound
# to. Quantity and price are the offer's own terms and are not part of it.
MATERIAL_SPEC_FIELDS = (
    "polymer_id",
    "material_grade_id",
    "form_id",
    "color_id",
    "packaging_type_id",
    "source_type_id",
    "filler_type_id",
)


def material_spec_key(material):
    """Stable text key of a material row's specification (record ids, attributes sorted)."""
    if not material:
        return ""
    parts = [f"{name}={material[name].id or 0}" for name in MATERIAL_SPEC_FIELDS]
    parts.append("attributes=" + ",".join(str(i) for i in sorted(material.material_attribute_ids.ids)))
    return ";".join(parts)


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

    # Same column as the former stored related field: historical Gate offers keep
    # their value. New Gate offers are filled from their result in ``create``.
    opportunity_id = fields.Many2one(
        "crm.lead",
        string="Opportunity",
        index=True,
        ondelete="restrict",
        tracking=True,
        help="Native CRM opportunity this offer pursues: from the Gate result lineage, or set directly "
        "when the broker selected the buyer manually.",
    )
    material_source_id = fields.Many2one(
        "plasticos.opportunity.material",
        string="Opportunity Material",
        index=True,
        ondelete="restrict",
        help="Opportunity-owned material row a manual offer was drafted from.",
    )
    material_spec_key = fields.Char(
        string="Sent Material Specification",
        readonly=True,
        copy=False,
        help="Specification of the material row when the offer was sent. Release refuses a drifted material.",
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
    # One active manual draft per opportunity and buyer company. Gate offers keep
    # their own one-per-result rule; sent and closed offers are history.
    _unique_manual_draft_per_buyer = models.UniqueIndex(
        "(opportunity_id, buyer_id) WHERE state = 'draft' AND match_result_id IS NULL AND opportunity_id IS NOT NULL"
    )

    @api.model_create_multi
    def create(self, vals_list):
        Result = self.env["plasticos.match.result"]
        for vals in vals_list:
            if vals.get("match_result_id") and not vals.get("opportunity_id"):
                opportunity = Result.browse(vals["match_result_id"]).match_run_id.opportunity_id
                if opportunity:
                    vals["opportunity_id"] = opportunity.id
        return super().create(vals_list)

    def _plasticos_term_fields(self):
        return tuple(super()._plasticos_term_fields()) + ("opportunity_id", "material_source_id")

    def _plasticos_opportunity(self):
        self.ensure_one()
        return self.opportunity_id

    def _plasticos_approval(self):
        self.ensure_one()
        return self.match_result_id.match_run_id.approval_id

    @api.constrains("match_result_id", "opportunity_id", "material_source_id")
    def _check_opportunity_lineage(self):
        for rec in self:
            if rec.match_result_id:
                run_opportunity = rec.match_result_id.match_run_id.opportunity_id
                if rec.opportunity_id != run_opportunity:
                    raise ValidationError(_("A Gate offer belongs to the opportunity of its match run."))
            if rec.material_source_id and rec.material_source_id.opportunity_id != rec.opportunity_id:
                raise ValidationError(_("The offer material must belong to the offer's opportunity."))

    def _plasticos_send_blockers(self):
        blockers = super()._plasticos_send_blockers()
        if not self.match_result_id and self.opportunity_id:
            opportunity = self.opportunity_id
            if not opportunity.active or opportunity.stage_id.is_won:
                blockers.append(_("Opportunity %s is no longer open.") % opportunity.name)
            if not self.material_source_id or self.material_source_id.opportunity_id != opportunity:
                blockers.append(_("The offer is not linked to its opportunity's material sheet."))
        return blockers

    def _plasticos_freeze_on_send_vals(self):
        vals = super()._plasticos_freeze_on_send_vals()
        if self.material_source_id:
            vals["material_spec_key"] = material_spec_key(self.material_source_id)
        return vals

    def _plasticos_check_release_material(self, material):
        """Release sells the material the accepted offer was sent for, or nothing."""
        self.ensure_one()
        if self.material_source_id and material != self.material_source_id:
            raise UserError(
                _("Offer %s was sent for a different material row than the opportunity holds now.") % self.name
            )
        if self.material_spec_key and material_spec_key(material) != self.material_spec_key:
            raise UserError(
                _(
                    "The opportunity material changed after offer %s was sent (polymer, type, form, color, "
                    "packaging, source, filler or attributes). Release stopped: restore the sent specification "
                    "or send a new offer.",
                    self.name,
                )
            )

    def _plasticos_is_manual_offer(self):
        """Drafted from buyers the broker selected on an opportunity, not from a Gate result."""
        self.ensure_one()
        return bool(self.opportunity_id and not self.match_result_id)

    def _plasticos_send_evidence_fields(self):
        # The material specification frozen at send is what release compares against.
        return tuple(super()._plasticos_send_evidence_fields()) + ("material_spec_key",)

    def _plasticos_requires_send_evidence(self):
        return super()._plasticos_requires_send_evidence() or self._plasticos_is_manual_offer()

    def _plasticos_keeps_sent_history(self):
        # An emailed manual offer is communicated history: a revised proposal is a new offer.
        return super()._plasticos_keeps_sent_history() or (
            self._plasticos_is_manual_offer() and bool(self.sent_message_id)
        )

    def action_reset_to_draft(self):
        """An emailed manual offer never returns to Draft; an unsent one may not become a second draft."""
        for rec in self:
            # Same refusal as the write guard, raised before any other check.
            rec._plasticos_check_state_transition({"state": "draft"})
        manual = self.filtered(lambda offer: offer.opportunity_id and not offer.match_result_id)
        if manual:
            # One query for the whole batch; pairs are compared in memory.
            drafts = self.search(
                [
                    ("id", "not in", manual.ids),
                    ("opportunity_id", "in", manual.opportunity_id.ids),
                    ("buyer_id", "in", manual.buyer_id.ids),
                    ("match_result_id", "=", False),
                    ("state", "=", "draft"),
                ]
            )
            taken = {(draft.opportunity_id.id, draft.buyer_id.id) for draft in drafts}
            for rec in manual:
                if (rec.opportunity_id.id, rec.buyer_id.id) in taken:
                    raise UserError(
                        _("%(buyer)s already has a draft offer on this opportunity. Edit that draft instead.")
                        % {"buyer": rec.buyer_id.display_name}
                    )
        return super().action_reset_to_draft()

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
