import logging

from odoo import api, models

_logger = logging.getLogger(__name__)


class PlasticosAuditCron(models.Model):
    _name = "plasticos.audit.cron"
    _description = "Plasticos Monthly Audit Cron"

    @api.model
    def run_monthly_audit(self):
        tx_model = self.env["plasticos.transaction"]
        self.env.cr.execute(
            "SELECT pg_try_advisory_lock(hashtext(%s))", ["plasticos_transaction.cron_plasticos_monthly_audit"]
        )
        locked = self.env.cr.fetchone()[0]
        if not locked:
            _logger.info("Skipping monthly audit cron: lock is already held.")
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
                names = ", ".join(violations[:10].mapped("name"))
                _logger.warning(
                    "Monthly audit: %d violation(s) in closed transactions: %s%s",
                    len(violations),
                    names,
                    "..." if len(violations) > 10 else "",
                )
            else:
                _logger.info("Monthly audit: no violations found.")
        finally:
            self.env.cr.execute(
                "SELECT pg_advisory_unlock(hashtext(%s))", ["plasticos_transaction.cron_plasticos_monthly_audit"]
            )
