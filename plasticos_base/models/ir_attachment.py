import logging
import os

from odoo import api, models
from odoo.tools import SQL, config

_logger = logging.getLogger(__name__)

IR_ATTACHMENT = "ir.attachment"
CLEANUP_LOCK = "plasticos_base.ir_cron_cleanup_attachment_orphans"
# Last attachment id the cleanup examined; the next run continues after it.
CURSOR_PARAM = "plasticos_base.attachment_orphan_cleanup_cursor"
PAGE_SIZE = 2000
# A page where more than this share of blobs is missing is not a page of
# orphans: it is an unavailable or wrong filestore. Nothing is deleted then.
MAX_MISSING_RATIO = 0.25
# Business documents are never removed by maintenance, with or without a blob.
# Named, not imported: plasticos_base gains no dependency on these models.
PROTECTED_MODELS = ("plasticos.document", "documents.document", "account.move")


class IrAttachment(models.Model):
    _inherit = IR_ATTACHMENT

    @api.model
    def _cron_cleanup_missing_filestore_orphans(self):
        """Delete binary attachment rows whose filestore blob is missing.

        Fail-closed: the run deletes nothing when the filestore cannot be
        proven available (unreachable or empty root, an I/O error, no blob of
        the page present, or an implausible share missing). Rows that belong
        to or are referenced by a protected business model are always kept.
        Each run examines the page after the stored cursor and wraps at the end.
        """
        self.env.cr.execute("SELECT pg_try_advisory_lock(hashtext(%s))", [CLEANUP_LOCK])
        locked = self.env.cr.fetchone()[0]
        if not locked:
            _logger.info("Skipping attachment orphan cleanup: lock is already held.")
            return 0

        try:
            return self._cleanup_missing_filestore_page()
        finally:
            self.env.cr.execute("SELECT pg_advisory_unlock(hashtext(%s))", [CLEANUP_LOCK])

    @api.model
    def _orphan_cleanup_filestore_root(self):
        """The database filestore directory, or ``None`` when it is not provably available."""
        if not config.get("data_dir"):
            _logger.warning("Attachment orphan cleanup skipped: missing data_dir config")
            return None
        root = self._filestore()
        try:
            with os.scandir(root) as entries:
                populated = any(True for _entry in entries)
        except OSError as error:
            _logger.error("Attachment orphan cleanup aborted: filestore root %s is unreachable (%s)", root, error)
            return None
        if not populated:
            _logger.error("Attachment orphan cleanup aborted: filestore root %s is empty (unmounted?)", root)
            return None
        return root

    @api.model
    def _orphan_cleanup_cursor(self):
        params = self.env["ir.config_parameter"].sudo()  # cron-sudo-justification: maintenance cursor is system state
        value = params.get_param(CURSOR_PARAM, "0")
        return int(value) if str(value).isdigit() else 0

    @api.model
    def _orphan_cleanup_set_cursor(self, attachment_id):
        params = self.env["ir.config_parameter"].sudo()  # cron-sudo-justification: maintenance cursor is system state
        params.set_param(CURSOR_PARAM, str(int(attachment_id)))

    @api.model
    def _orphan_cleanup_protected_ids(self, attachments):
        """Ids among ``attachments`` owned or referenced by a protected business model."""
        protected = set(attachments.filtered(lambda attachment: attachment.res_model in PROTECTED_MODELS).ids)
        ids = attachments.ids
        if not ids:
            return protected
        cr = self.env.cr
        for model_name in PROTECTED_MODELS:
            if model_name not in self.env:
                continue
            model = self.env[model_name]
            for field in model._fields.values():
                if field.comodel_name != IR_ATTACHMENT or not field.store:
                    continue
                if field.type == "many2one":
                    column, table = field.name, model._table
                elif field.type == "many2many":
                    column, table = field.column2, field.relation
                else:
                    continue
                cr.execute(
                    SQL(
                        "SELECT %s FROM %s WHERE %s = ANY(%s)",
                        SQL.identifier(column),
                        SQL.identifier(table),
                        SQL.identifier(column),
                        ids,
                    )
                )
                protected.update(row[0] for row in cr.fetchall())
        # Chatter attachments of a protected record (mail is optional for this module).
        if "mail.message" in self.env:
            cr.execute(
                """
                SELECT rel.attachment_id
                  FROM message_attachment_rel rel
                  JOIN mail_message message ON message.id = rel.message_id
                 WHERE rel.attachment_id = ANY(%s) AND message.model = ANY(%s)
                """,
                [ids, list(PROTECTED_MODELS)],
            )
            protected.update(row[0] for row in cr.fetchall())
        return protected

    @api.model
    def _cleanup_missing_filestore_page(self):
        filestore_root = self._orphan_cleanup_filestore_root()
        if filestore_root is None:
            return 0

        cursor = self._orphan_cleanup_cursor()
        domain = [("type", "=", "binary"), ("store_fname", "!=", False), ("id", ">", cursor)]
        candidates = self.sudo().search(  # cron-sudo-justification: bypass ACLs for orphan purge
            domain, order="id ASC", limit=PAGE_SIZE
        )
        if not candidates:
            if cursor:
                self._orphan_cleanup_set_cursor(0)
            _logger.info("Attachment orphan cleanup: end of attachments reached; cursor reset")
            return 0

        missing_ids = []
        for attachment in candidates:
            full_path = os.path.join(filestore_root, attachment.store_fname)
            if os.path.exists(full_path):
                continue
            # exists() is False for any failure; only a clean "no such file" is an orphan.
            try:
                os.stat(full_path)
            except FileNotFoundError:
                missing_ids.append(attachment.id)
                continue
            except OSError as error:
                # Not "missing": the store itself is failing. Decide nothing from it.
                _logger.error("Attachment orphan cleanup aborted: cannot stat %s (%s)", full_path, error)
                return 0

        checked = len(candidates)
        if missing_ids and (len(missing_ids) == checked or len(missing_ids) > MAX_MISSING_RATIO * checked):
            _logger.error(
                "Attachment orphan cleanup aborted: %s of %s blobs missing after id %s is implausible for "
                "orphans; filestore %s is treated as unavailable and nothing was deleted",
                len(missing_ids),
                checked,
                cursor,
                filestore_root,
            )
            return 0

        missing = self.browse(missing_ids).sudo()  # cron-sudo-justification: unlink orphans
        protected_ids = self._orphan_cleanup_protected_ids(missing)
        if protected_ids:
            _logger.error(
                "Attachment orphan cleanup kept %s business-document attachment rows whose blob is missing: %s",
                len(protected_ids),
                sorted(protected_ids),
            )
        orphans = missing.filtered(lambda attachment: attachment.id not in protected_ids)
        count = len(orphans)
        if orphans:
            orphans.unlink()
            _logger.warning("Attachment orphan cleanup removed %s orphan rows (missing filestore blobs)", count)
        else:
            _logger.info("Attachment orphan cleanup: no removable orphan in batch (%s checked)", checked)
        self._orphan_cleanup_set_cursor(candidates[-1].id)
        return count
