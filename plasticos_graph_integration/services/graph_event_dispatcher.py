import requests

from odoo import api, models


class GraphEventDispatcher(models.AbstractModel):
    _name = "plasticos.graph.event.dispatcher"

    @api.model
    def dispatch_pending(self):
        outbox = self.env["plasticos.graph.outbox"].search([("status", "=", "pending")], limit=100)
        builder = self.env["plasticos.graph.payload.builder"]

        for event in outbox:
            try:
                record = self.env[event.model_name].browse(event.res_id)
                if not record.exists():
                    event.mark_processed()
                    continue

                payload_method = getattr(builder, f"build_{event.model_name.split('.')[-1]}", None)
                if not payload_method:
                    event.mark_processed()
                    continue

                payload = payload_method(record)
                requests.post(
                    "http://graph-service:8000/sync",
                    json={"model": event.model_name, "event": event.event_type, "payload": payload},
                    timeout=5,
                )

                event.mark_processed()

            except Exception as e:
                event.mark_failed(e)
