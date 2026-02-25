from odoo import models


class PlasticosAuditCron(models.Model):
    _name = "plasticos.audit.cron"
    _description = "Plasticos Monthly Audit Cron"

    def run_monthly_audit(self):
        tx_model = self.env["plasticos.transaction"]
        self.env.cr.execute(
            "SELECT pg_try_advisory_lock(hashtext(%s))", ["plasticos_transaction.cron_plasticos_monthly_audit"]
        )
        locked = self.env.cr.fetchone()[0]
        if not locked:
            return

        try:
            violations = tx_model.search(
                [
                    ("state", "=", "closed"),
                    "|",
                    ("gross_margin", "<", 0),
                    ("commission_locked", "=", False),
                ],
                order="write_date ASC, id ASC",
                limit=500,
            )
            if violations:
                raise Exception("Audit violations detected in closed transactions.")
        finally:
            self.env.cr.execute(
                "SELECT pg_advisory_unlock(hashtext(%s))", ["plasticos_transaction.cron_plasticos_monthly_audit"]
            )
