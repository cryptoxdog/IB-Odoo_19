"""Kafka-backed graph event dispatcher.

Overrides the HTTP-based dispatcher to publish events to Kafka instead.
"""

from datetime import datetime, timezone

from odoo import api, models


class GraphEventDispatcherKafka(models.AbstractModel):
    _inherit = "plasticos.graph.event.dispatcher"

    @api.model
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
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "data": record.read()[0],
            }

            producer.publish("graph_events", payload)
            event.mark_processed()
