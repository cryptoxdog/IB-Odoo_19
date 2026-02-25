from odoo import models


class GraphEventMixin(models.AbstractModel):
    _name = "graph.event.mixin"
    _description = "Graph Sync Event Mixin"

    def _enqueue_graph_event(self, event_type):
        for record in self:
            self.env["plasticos.graph.outbox"].create(
                {
                    "model_name": record._name,
                    "res_id": record.id,
                    "event_type": event_type,
                }
            )
