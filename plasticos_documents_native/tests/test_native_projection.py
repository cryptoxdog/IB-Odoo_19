"""Native documents.document helpers for this addon's tests.

The Enterprise model string lives in one place so callers never hardcode it.
The sales-dashboard native branch in plasticos_commission calls these helpers
and does not name the model.
"""

from __future__ import annotations

import base64

from odoo.tests import TransactionCase, tagged

NATIVE_MODEL = "documents.document"


def native_model_name() -> str:
    """The Enterprise document model, owned by this module's tests."""
    return NATIVE_MODEL


def native_model_installed(env) -> bool:
    """True when the Enterprise documents.document model is registered."""
    return native_model_name() in env


def create_native_document(env, *, name: str, folder, datas: bytes, doc_type: str, transaction=None):
    """Create one documents.document through its owning module."""
    vals = {
        "name": name,
        "folder_id": folder.id,
        "datas": datas,
        "doc_type": doc_type,
    }
    if transaction is not None:
        vals["transaction_id"] = transaction.id
    return env[native_model_name()].create(vals)


@tagged("post_install", "-at_install")
class TestNativeProjectionHelpers(TransactionCase):
    def test_helper_creates_a_native_document_in_the_inbox(self):
        if not native_model_installed(self.env):
            raise AssertionError("BLOCKED: Enterprise documents.document is not installed")
        folder = self.env.ref("plasticos_documents_native.folder_plasticos_inbox")
        doc = create_native_document(
            self.env,
            name="helper-native.pdf",
            folder=folder,
            datas=base64.b64encode(b"%PDF-1.4 helper"),
            doc_type="bol",
        )
        self.assertEqual(doc.folder_id, folder)
        self.assertEqual(doc.doc_type, "bol")
