from odoo import models


class Intake(models.Model):
    _inherit = ["plasticos.intake", "graph.event.mixin"]

    def write(self, vals):
        res = super().write(vals)
        self._enqueue_graph_event("upsert")
        return res

    def create(self, vals_list):
        records = super().create(vals_list)
        records._enqueue_graph_event("upsert")
        return records
