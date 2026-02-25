from odoo import models


class AnomalyStreamHook(models.AbstractModel):
    _name = "plasticos.graph.anomaly.stream"

    def on_event(self, tenant_code, event):
        if event.get("volume", 0) > 100000:
            self.env["plasticos.graph.anomaly.detector"].detect_transaction_spike(tenant_code)
