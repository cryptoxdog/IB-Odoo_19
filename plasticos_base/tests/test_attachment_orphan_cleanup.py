"""The filestore orphan cleanup deletes only provable orphans and fails closed otherwise."""

import os
import tempfile
from unittest.mock import patch

from odoo.tests import TransactionCase, tagged

CURSOR_PARAM = "plasticos_base.attachment_orphan_cleanup_cursor"


@tagged("post_install", "-at_install", "plasticos", "cron")
class TestAttachmentOrphanCleanup(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Attachment = cls.env["ir.attachment"]
        cls.params = cls.env["ir.config_parameter"].sudo()

    def _attachments(self, count, **values):
        records = self.Attachment.create(
            [
                {"name": f"orphan-cleanup-{index}.bin", "raw": os.urandom(32), "type": "binary", **values}
                for index in range(count)
            ]
        )
        self.assertTrue(all(records.mapped("store_fname")), "attachments must be stored in the filestore")
        return records

    def _start_before(self, attachments):
        """Scan only this test's rows: the fixture's own attachments are not under test."""
        self.params.set_param(CURSOR_PARAM, str(min(attachments.ids) - 1))

    def _drop_blob(self, attachment):
        os.unlink(self.Attachment._full_path(attachment.store_fname))

    def _run(self):
        return self.Attachment._cron_cleanup_missing_filestore_orphans()

    def test_single_orphan_among_healthy_rows_is_removed(self):
        records = self._attachments(8)
        self._start_before(records)
        self._drop_blob(records[2])

        self.assertEqual(self._run(), 1)

        self.assertEqual(records.exists(), records - records[2])
        self.assertEqual(self.params.get_param(CURSOR_PARAM), "0", "a short page ends the cycle")

    def test_cursor_advances_page_by_page_and_wraps_on_a_short_page(self):
        """Rows already examined are revisited: the cycle wraps even when a page is never empty."""
        records = self._attachments(10)
        self._start_before(records)
        with patch("odoo.addons.plasticos_base.models.ir_attachment.PAGE_SIZE", 4):
            self.assertEqual(self._run(), 0)
            self.assertEqual(self.params.get_param(CURSOR_PARAM), str(records[3].id))
            self.assertEqual(self._run(), 0)
            self.assertEqual(self.params.get_param(CURSOR_PARAM), str(records[7].id))
            # Two rows remain: a short, non-empty page still ends the cycle.
            self.assertEqual(self._run(), 0)
            self.assertEqual(self.params.get_param(CURSOR_PARAM), "0")

            # A blob lost after its row was examined is found on the next cycle.
            self._drop_blob(records[1])
            self._start_before(records)
            self.assertEqual(self._run(), 1)
        self.assertEqual(records.exists(), records - records[1])

    def test_unreachable_filestore_root_deletes_nothing(self):
        records = self._attachments(8)
        self._start_before(records)
        gone = os.path.join(tempfile.gettempdir(), "plasticos-no-such-filestore", "db")
        with patch.object(type(self.Attachment), "_filestore", lambda _self: gone):
            self.assertEqual(self._run(), 0)
        self.assertEqual(records.exists(), records)
        self.assertEqual(self.params.get_param(CURSOR_PARAM), str(min(records.ids) - 1), "cursor must not advance")

    def test_empty_filestore_root_deletes_nothing(self):
        """An unmounted volume is an existing, empty directory: every blob looks missing."""
        records = self._attachments(8)
        self._start_before(records)
        with (
            tempfile.TemporaryDirectory() as empty,
            patch.object(type(self.Attachment), "_filestore", lambda _self: empty),
        ):
            self.assertEqual(self._run(), 0)
        self.assertEqual(records.exists(), records)

    def test_implausible_missing_share_deletes_nothing(self):
        records = self._attachments(8)
        self._start_before(records)
        for attachment in records[:4]:
            self._drop_blob(attachment)

        self.assertEqual(self._run(), 0)

        self.assertEqual(records.exists(), records)
        self.assertEqual(self.params.get_param(CURSOR_PARAM), str(min(records.ids) - 1), "cursor must not advance")

    def test_io_error_is_not_treated_as_missing(self):
        records = self._attachments(8)
        self._start_before(records)
        broken = self.Attachment._full_path(records[1].store_fname)
        real_stat = os.stat

        def failing_stat(path, *args, **kwargs):
            if path == broken:
                raise OSError(5, "Input/output error")
            return real_stat(path, *args, **kwargs)

        with patch("odoo.addons.plasticos_base.models.ir_attachment.os.stat", failing_stat):
            self.assertEqual(self._run(), 0)
        self.assertEqual(records.exists(), records)

    def test_business_document_attachment_is_kept_and_plain_orphan_is_not(self):
        healthy = self._attachments(8)
        protected = self._attachments(1, res_model="account.move", res_id=0)
        plain = self._attachments(1)
        self._start_before(healthy)
        self._drop_blob(protected)
        self._drop_blob(plain)

        self.assertEqual(self._run(), 1)

        self.assertTrue(protected.exists(), "an account.move attachment is never removed by maintenance")
        self.assertFalse(plain.exists())
        self.assertEqual(healthy.exists(), healthy)

    def test_attachment_referenced_by_a_protected_model_column_is_kept(self):
        """Reference protection is generic: any stored ir.attachment link of a protected model counts."""
        partner = self.env["res.partner"].create({"name": "Orphan Cleanup Probe", "is_company": True})
        link = partner._fields["message_main_attachment_id"]
        self.assertEqual((link.comodel_name, link.store), ("ir.attachment", True))
        healthy = self._attachments(8)
        referenced = self._attachments(1)
        partner.message_main_attachment_id = referenced
        self.env.flush_all()
        self._start_before(healthy)
        self._drop_blob(referenced)
        module = "odoo.addons.plasticos_base.models.ir_attachment"

        with patch(f"{module}.PROTECTED_MODELS", ("res.partner",)):
            self.assertEqual(self._run(), 0)
        self.assertTrue(referenced.exists())

        # Falsifying: without the protection the same row is an ordinary orphan.
        self._start_before(healthy)
        with patch(f"{module}.PROTECTED_MODELS", ()):
            self.assertEqual(self._run(), 1)
        self.assertFalse(referenced.exists())
