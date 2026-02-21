from odoo import models


class PlasticosAuditCron(models.Model):
    _name = "plasticos.audit.cron"
    _description = "Plasticos Monthly Audit Cron"

    def run_monthly_audit(self):
        tx_model = self.env["plasticos.transaction"]
        violations = tx_model.search(
            [
                ("state", "=", "closed"),
                "|",
                ("gross_margin", "<", 0),
                ("commission_locked", "=", False),
            ]
        )
        if violations:
            raise Exception("Audit violations detected in closed transactions.")
