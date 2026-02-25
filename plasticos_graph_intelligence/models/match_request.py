from odoo import fields, models


class MatchRequest(models.Model):
    _name = "plasticos.match.request"
    _description = "Graph Match Request"
    _order = "create_date desc"

    intake_id = fields.Many2one(
        "plasticos.intake",
        required=True,
        index=True,
        ondelete="cascade",
    )

    mode = fields.Selection(
        [("strict", "Strict"), ("relaxed", "Relaxed")],
        default="strict",
        required=True,
    )

    requested_by = fields.Many2one(
        "res.users",
        default=lambda self: self.env.user,
        required=True,
    )

    state = fields.Selection(
        [
            ("pending", "Pending"),
            ("completed", "Completed"),
            ("failed", "Failed"),
        ],
        default="pending",
        index=True,
    )

    result_ids = fields.One2many(
        "plasticos.match.result",
        "match_request_id",
        string="Results",
    )

    error_message = fields.Text()
