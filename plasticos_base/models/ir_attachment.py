import logging
import os

from odoo import api, models
from odoo.tools import config

_logger = logging.getLogger(__name__)


class IrAttachment(models.Model):
    _inherit = "ir.attachment"

    @api.model
    def _cron_cleanup_missing_filestore_orphans(self):
        """Delete binary attachment rows whose filestore blob is missing."""
        self.env.cr.execute("SELECT pg_try_advisory_lock(hashtext(%s))", ["plasticos_base.ir_cron_cleanup_attachment_orphans"])
        locked = self.env.cr.fetchone()[0]
        if not locked:
            _logger.info("Skipping attachment orphan cleanup: lock is already held.")
            return 0

        try:
            data_dir = config.get("data_dir")
            if not data_dir:
                _logger.warning("Attachment orphan cleanup skipped: missing data_dir config")
                return 0

            filestore_root = os.path.join(data_dir, "filestore", self.env.cr.dbname)
            candidates = self.sudo().search(  # cron-sudo-justification: attachment cleanup must bypass attachment ACLs for orphan purge
                [("type", "=", "binary"), ("store_fname", "!=", False)],
                order="id ASC",
                limit=2000,
            )

            missing_ids = []
            for attachment in candidates:
                full_path = os.path.join(filestore_root, attachment.store_fname)
                if not os.path.exists(full_path):
                    missing_ids.append(attachment.id)

            if not missing_ids:
                _logger.info(
                    "Attachment orphan cleanup: no missing filestore blobs in batch (%s checked)",
                    len(candidates),
                )
                return 0

            missing = self.browse(missing_ids).sudo()  # cron-sudo-justification: purge requires unlink rights across orphaned attachments
            count = len(missing)
            missing.unlink()
            _logger.warning(
                "Attachment orphan cleanup removed %s orphan rows (missing filestore blobs)",
                count,
            )
            return count
        finally:
            self.env.cr.execute("SELECT pg_advisory_unlock(hashtext(%s))", ["plasticos_base.ir_cron_cleanup_attachment_orphans"])
