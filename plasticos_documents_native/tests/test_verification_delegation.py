"""Native verification delegates. Sync and historical disagreements do not author a decision."""

import base64
import importlib.util

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.addons.plasticos_documents_native.models.document_native import NATIVE_HISTORY_KEY
from odoo.exceptions import AccessError, UserError
from odoo.modules.module import get_module_path
from odoo.tests.common import tagged


def _migration():
    path = get_module_path("plasticos_documents_native") + "/migrations/19.0.1.2.6/pre-migrate.py"
    spec = importlib.util.spec_from_file_location("plasticos_documents_native_pre_1926", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.migrate


@tagged("post_install", "-at_install", "documents", "verification")
class TestNativeVerificationDelegation(PlasticosTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if "documents.document" not in cls.env:
            raise AssertionError("BLOCKED: Enterprise documents.document is not installed")
        cls.partner = cls.env["res.partner"].create(
            {"name": "Native Docs Partner", "is_company": True, "customer_rank": 1, "supplier_rank": 1}
        )
        internal = cls.env.ref("base.group_user")
        manager = cls.env.ref("plasticos_documents.group_documents_manager")
        cls.manager = cls.env["res.users"].create(
            {
                "name": "Native Docs Manager",
                "login": "phase_a_native_manager",
                "group_ids": [(6, 0, [internal.id, manager.id])],
            }
        )
        cls.internal = cls.env["res.users"].create(
            {
                "name": "Native Base Internal",
                "login": "phase_a_native_internal",
                "group_ids": [(6, 0, [internal.id])],
            }
        )
        cls.folder = cls.env.ref("plasticos_documents_native.folder_plasticos_inbox")
        cls.tx = cls.env["plasticos.transaction"].create(
            {"supplier_id": cls.partner.id, "buyer_id": cls.partner.id, "quantity": 1000}
        )

    def _native(self, name="bol.pdf"):
        return self.env["documents.document"].create(
            {
                "name": name,
                "folder_id": self.folder.id,
                "datas": base64.b64encode(b"%PDF-1.4 phase-a"),
                "doc_type": "bol",
                "transaction_id": self.tx.id,
            }
        )

    def test_native_verify_delegates_once_and_projects_the_domain_decision(self):
        native = self._native()
        legacy = self.env["plasticos.document.sync"].sync_native_to_legacy(native)
        self.assertTrue(legacy)
        self.assertFalse(legacy.verified)
        self.assertEqual(legacy.res_model, "documents.document")
        self.assertFalse(legacy.transaction_id)
        self.assertEqual(native.transaction_id, self.tx)
        row = native.with_user(self.manager).action_associate_exact(
            "plasticos.transaction",
            self.tx.id,
            source_reference="desk request",
        )
        self.assertEqual(row.association_state, "accepted")
        self.assertFalse(row.verified)
        self.assertFalse(native.verified)
        native.with_user(self.manager).action_verify()
        legacy.invalidate_recordset()
        native.invalidate_recordset()
        row.invalidate_recordset()
        self.assertTrue(row.verified)
        self.assertEqual(legacy.verified_by, self.manager)
        self.assertEqual(native.verified_by, legacy.verified_by)
        self.assertEqual(native.verified_at, legacy.verified_at)
        self.assertTrue(native.verified)
        stamp = legacy.verified_at
        native.with_user(self.manager).action_verify()
        self.assertEqual(legacy.verified_at, stamp)
        again = self.env["plasticos.document.sync"].sync_native_to_legacy(native)
        self.assertEqual(again, legacy)
        self.assertEqual(legacy.verified_at, stamp)
        self.assertEqual(
            self.env["plasticos.document"].search_count([("attachment_id", "=", native.attachment_id.id)]), 1
        )

    def test_base_user_cannot_write_or_call_native_verification(self):
        native = self._native("blocked.pdf")
        legacy = self.env["plasticos.document.sync"].sync_native_to_legacy(native)
        with self.assertRaises(AccessError):
            native.with_user(self.internal).action_verify()
        with self.assertRaises(AccessError):
            native.with_user(self.internal).write({"verified": True, "override": True, "override_reason": "forged"})
        forged = {NATIVE_HISTORY_KEY: {"uid": self.internal.id}}
        with self.assertRaises(AccessError):
            native.with_user(self.internal).with_context(**forged).write({"verification_review_required": False})
        self.assertFalse(legacy.verified)
        self.assertFalse(legacy.override)

    def test_sync_cannot_promote_native_verification_and_is_idempotent(self):
        native = self._native("sync.pdf")
        native.with_user(self.manager).preserve_historical_native_verification(
            {"verified": True, "verified_by": self.manager.id, "override": False}
        )
        self.assertTrue(native.verification_review_required)
        legacy = self.env["plasticos.document.sync"].sync_native_to_legacy(native)
        again = self.env["plasticos.document.sync"].sync_native_to_legacy(native)
        self.assertEqual(again, legacy)
        self.assertFalse(legacy.verified)
        self.assertFalse(legacy.override)
        self.assertFalse(legacy.verified_by)
        self.assertFalse(native.verified)

    def test_historical_disagreement_is_review_and_migration_is_idempotent(self):
        native = self._native("conflict.pdf")
        legacy = self.env["plasticos.document.sync"].sync_native_to_legacy(native)
        self.assertFalse(legacy.verified)
        native.with_user(self.manager).preserve_historical_native_verification(
            {
                "verified": True,
                "verified_by": self.manager.id,
                "override": False,
                "override_reason": False,
            }
        )
        snapshot = native.verification_conflict_snapshot
        self.assertTrue(native.verification_review_required)
        self.assertIn('"verified": true', snapshot)
        self.assertFalse(legacy.verified)
        self.assertFalse(native.verified)
        self.assertEqual(native.verification_binding(), "conflict")
        again = native.with_user(self.manager).preserve_historical_native_verification({"verified": False})
        self.assertFalse(again)
        self.assertEqual(native.verification_conflict_snapshot, snapshot)
        self.assertFalse(legacy.verified)

        self.env.cr.execute(
            """
            SELECT 1
              FROM information_schema.columns
             WHERE table_name = 'documents_document'
               AND column_name = 'verified'
            """
        )
        if self.env.cr.fetchone():
            self.env.cr.execute(
                """
                UPDATE documents_document
                   SET verified = true,
                       verification_snapshot_captured = false
                 WHERE id = %s
                """,
                (native.id,),
            )
        migrate = _migration()
        migrate(self.env.cr, "19.0.1.2.5")
        migrate(self.env.cr, "19.0.1.2.5")
        native.invalidate_recordset()
        legacy.invalidate_recordset()
        self.assertTrue(native.verification_snapshot_captured)
        self.assertFalse(legacy.verified)
        self.assertFalse(native.verified)

    def test_ambiguous_native_file_stays_pending(self):
        native = self._native("ambiguous.pdf")
        self.env["plasticos.document.sync"].sync_native_to_legacy(native)
        load_a = self.env["plasticos.load"].create({})
        load_b = self.env["plasticos.load"].create({})
        first = native.with_user(self.manager).action_associate_exact(
            "plasticos.load", load_a.id, source_reference="load a"
        )
        second = native.with_user(self.manager).action_associate_exact(
            "plasticos.load", load_b.id, source_reference="load b"
        )
        native.invalidate_recordset()
        self.assertEqual(native.verification_binding(), "ambiguous")
        self.assertFalse(native.verified)
        with self.assertRaisesRegex(UserError, "UNRESOLVED"):
            native.with_user(self.manager).action_verify()
        self.assertFalse(first.verified)
        self.assertFalse(second.verified)
        self.assertEqual(first.attachment_id, second.attachment_id)
