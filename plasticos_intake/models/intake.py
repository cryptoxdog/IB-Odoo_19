# plasticos_intake/models/intake.py
# TIER-2 WIRING (2026-04-01):
# TODO #1 — action_match_to_buyers() wired to plasticos.buyer.matcher
# TODO #3 — action_send_offers() creates plasticos.offer per selected line
# TODO #4 — action_view_offers() + action_view_matches() + offer_count
#
# pipeline_v2.py is NOT imported. External API bridge is deferred.

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class PlasticosIntake(models.Model):
    _name = "plasticos.intake"
    _description = "Material Intake"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc, id desc"

    name = fields.Char(
        string="Reference", required=True, copy=False,
        readonly=True, default=lambda self: _("New"), tracking=True,
    )
    partner_id = fields.Many2one(
        "res.partner", string="Company", index=True, tracking=True,
        domain="[('is_company', '=', True)]",
    )
    pending_company_name = fields.Char(string="Pending Company Name")
    material_profile_id = fields.Many2one(
        "plasticos.material.profile", string="Material Profile",
        tracking=True, index=True,
    )
    facility_profile_id = fields.Many2one(
        "plasticos.facility.profile", string="Facility", tracking=True,
    )
    quantity_lbs = fields.Float(string="Quantity (lbs)", digits=(12, 2))
    asking_price = fields.Float(string="Asking Price ($/lb)", digits=(10, 4))

    status = fields.Selection(
        selection=[
            ("new", "New"),
            ("matched", "Matched"),
            ("offer_sent", "Offers Sent"),
            ("transacted", "Transacted"),
            ("archived", "Archived"),
        ],
        string="Status", default="new", required=True,
        tracking=True, index=True,
    )

    match_line_ids = fields.One2many(
        "plasticos.intake.match", "intake_id",
        string="Buyer Matches", copy=False,
    )

    match_count = fields.Integer(
        string="Match Count", compute="_compute_match_count",
        store=True, compute_sudo=True,
    )

    # TODO #4: offer_count computed field
    offer_count = fields.Integer(
        string="Offer Count", compute="_compute_offer_count",
        store=True, compute_sudo=True,
        help="Number of plasticos.offer records created from this intake.",
    )

    @api.depends("match_line_ids")
    def _compute_match_count(self):
        for rec in self:
            rec.match_count = len(rec.match_line_ids)

    @api.depends("match_line_ids.offer_id")
    def _compute_offer_count(self):
        for rec in self:
            rec.offer_count = len(
                rec.match_line_ids.filtered(lambda l: l.offer_id).mapped("offer_id")
            )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", _("New")) == _("New"):
                vals["name"] = (
                    self.env["ir.sequence"].next_by_code("plasticos.intake")
                    or _("New")
                )
        return super().create(vals_list)

    # ── TODO #1: action_match_to_buyers ──────────────────────────────────
    def action_match_to_buyers(self):
        """
        Run buyer matching via plasticos.buyer.matcher.
        Idempotent: stale match_line_ids unlinked before re-run.
        """
        self.ensure_one()

        if not self.partner_id and self.pending_company_name:
            self._create_partner_from_pending()
        if not self.partner_id:
            raise UserError(
                _("Cannot match buyers without a company.\n\n"
                  "Please set a Company or enter a Pending Company Name.")
            )
        if not self.material_profile_id:
            raise UserError(
                _(
                    "Cannot match buyers: Intake '%(name)s' has no material profile.\n\n"
                    "Please link a Material Profile (polymer + form) before running matching.",
                ) % {"name": self.name}
            )

        # Idempotent reset
        if self.match_line_ids:
            self.match_line_ids.unlink()

        results = self.env["plasticos.buyer.matcher"].find_matches_for_supplier(
            supplier_partner_id=self.partner_id.id,
            intake_id=self.id,
            mode="strict",
        )

        if not results:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("No Matches Found"),
                    "message": _(
                        "No buyers matched for %s. "
                        "Try relaxed mode or check facility profiles."
                    ) % self.display_name,
                    "type": "warning",
                    "sticky": False,
                },
            }

        IntakeMatch = self.env["plasticos.intake.match"]
        for r in results:
            failed = ", ".join(r.get("gates_failed") or []) or _("none")
            IntakeMatch.create({
                "intake_id": self.id,
                "buyer_id": r["buyer_id"],
                "match_score": round(r.get("total_score", 0.0) * 100, 1),
                "typical_price": r.get("typical_price") or 0.0,
                "match_reason": _("Gates passed: %s/%s. Failed: %s") % (
                    r.get("gates_passed", 0),
                    r.get("gates_total", 12),
                    failed,
                ),
                "selected": False,
            })

        self.status = "matched"
        self.message_post(
            body=_("Buyer matching complete: %d candidate(s) found (top score: %.1f%%).") % (
                len(results),
                round(results[0].get("total_score", 0.0) * 100, 1),
            ),
            message_type="notification",
            subtype_xmlid="mail.mt_note",
        )

        return {
            "type": "ir.actions.act_window",
            "name": _("Matches — %s") % self.display_name,
            "res_model": "plasticos.intake.match",
            "view_mode": "list,form",
            "domain": [("intake_id", "=", self.id)],
            "context": {"default_intake_id": self.id},
            "target": "current",
        }

    # ── TODO #3: action_send_offers ──────────────────────────────────────
    def action_send_offers(self):
        """
        Create plasticos.offer per selected match line.
        Idempotent: skips lines where offer_id already set.
        """
        self.ensure_one()

        selected = self.match_line_ids.filtered(lambda l: l.selected)
        if not selected:
            raise UserError(
                _("No buyers selected.\n\n"
                  "Check 'Send Offer?' on at least one match line.")
            )

        pending = selected.filtered(lambda l: not l.offer_id)
        if not pending:
            raise UserError(
                _("All selected lines already have offers. No new offers to send.")
            )

        Offer = self.env["plasticos.offer"]
        created_ids = []

        for line in pending:
            # sudo() justified: offer creation crosses group boundaries
            # (broker vs intake user). Audited via message_post below.
            offer = Offer.sudo().create({
                "intake_id": self.id,
                "buyer_id": line.buyer_id.id,
                "supplier_id": self.partner_id.id,
                "price_per_lb": line.typical_price or self.asking_price or 0.0,
                "quantity_lbs": self.quantity_lbs or 0.0,
                "state": "draft",
            })
            line.offer_id = offer.id
            created_ids.append(offer.id)

        self.status = "offer_sent"
        self.message_post(
            body=_("%d offer(s) created and dispatched to buyers.") % len(created_ids),
            message_type="notification",
            subtype_xmlid="mail.mt_note",
        )

        return {
            "type": "ir.actions.act_window",
            "name": _("Offers — %s") % self.display_name,
            "res_model": "plasticos.offer",
            "view_mode": "list,form",
            "domain": [("intake_id", "=", self.id)],
            "context": {"default_intake_id": self.id},
            "target": "current",
        }

    # ── TODO #4: action_view_offers + action_view_matches ────────────────
    def action_view_offers(self):
        self.ensure_one()
        offer_ids = (
            self.match_line_ids.filtered(lambda l: l.offer_id)
            .mapped("offer_id").ids
        )
        return {
            "type": "ir.actions.act_window",
            "name": _("Offers — %s") % self.display_name,
            "res_model": "plasticos.offer",
            "view_mode": "list,form",
            "domain": [("id", "in", offer_ids)],
            "context": {"default_intake_id": self.id},
            "target": "current",
        }

    def action_view_matches(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Matches — %s") % self.display_name,
            "res_model": "plasticos.intake.match",
            "view_mode": "list,form",
            "domain": [("intake_id", "=", self.id)],
            "context": {"default_intake_id": self.id},
            "target": "current",
        }

    # ── Internal helpers ─────────────────────────────────────────────────
    def _create_partner_from_pending(self):
        self.ensure_one()
        if not self.pending_company_name:
            return
        partner = self.env["res.partner"].create({
            "name": self.pending_company_name,
            "is_company": True,
            "supplier_rank": 1,
        })
        self.partner_id = partner.id
        self.message_post(
            body=_("Auto-created partner: %s") % partner.name,
            message_type="notification",
            subtype_xmlid="mail.mt_note",
        )

