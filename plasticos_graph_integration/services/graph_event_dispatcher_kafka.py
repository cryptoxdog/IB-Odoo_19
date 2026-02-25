from datetime import datetime

from odoo import models


class GraphEventDispatcher(models.AbstractModel):
    _inherit = "plasticos.graph.event.dispatcher"

    def dispatch_pending(self):
        outbox = self.env["plasticos.graph.outbox"].search([("status", "=", "pending")], limit=500)

        producer = self.env["plasticos.kafka.producer"]

        for event in outbox:
            record = self.env[event.model_name].browse(event.res_id)
            if not record.exists():
                event.mark_processed()
                continue

            payload = {
                "model": event.model_name,
                "event": event.event_type,
                "timestamp": datetime.utcnow().isoformat(),
                "data": record.read()[0],
            }

            producer.publish("graph_events", payload)
            event.mark_processed()
