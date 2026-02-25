from odoo import fields, models


class EmergentGrade(models.Model):
    _name = "plasticos.graph.emergent.grade"
    _description = "Proposed Emergent Grade"
    _order = "create_date desc"

    cluster_id = fields.Many2one(
        "plasticos.graph.emergent.cluster",
        required=True,
        ondelete="cascade",
    )

    proposed_grade_code = fields.Char(required=True)
    proposed_spec = fields.Json(required=True)
    similarity_centroid = fields.Json()
    approval_status = fields.Selection(
        [
            ("pending", "Pending"),
            ("approved", "Approved"),
            ("rejected", "Rejected"),
        ],
        default="pending",
    )
