"""Correct Classification: a reasoned human correction of a native document (DEC-015, TASK-070).

The correction is recorded by mail tracking (``doc_type``, ``folder_id``) plus one reason message
with a module-owned subtype. The original file is never touched. The pending business shell is
re-classified while it is still pending, and the review activity is re-routed through the
TASK-060 router by the ordinary sync.
"""

import logging

from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

_logger = logging.getLogger(__name__)

DOCUMENTS_DOCUMENT = "documents.document"
# Enterprise documents.document ``type`` value of a folder.
FOLDER_TYPE = "folder"
REASON_SUBTYPE = "plasticos_documents_native.mt_classification_correction"


class PlasticosDocumentClassificationCorrection(models.TransientModel):
    _name = "plasticos.document.classification.correction"
    _description = "Correct the classification of a native document"

    @api.model
    def _doc_type_selection(self):
        return self.env[DOCUMENTS_DOCUMENT]._fields["doc_type"].selection

    document_id = fields.Many2one(DOCUMENTS_DOCUMENT, required=True, ondelete="cascade", readonly=True)
    doc_type = fields.Selection(selection="_doc_type_selection", string="Document Type", required=True)
    folder_id = fields.Many2one(
        DOCUMENTS_DOCUMENT,
        string="Folder",
        required=True,
        ondelete="cascade",
        domain=[("type", "=", FOLDER_TYPE), ("shortcut_document_id", "=", False)],
        help="An existing folder the corrected document belongs in.",
    )
    reason = fields.Text(required=True, help="Why the classification is corrected. Kept on the document.")

    def action_apply(self):
        self.ensure_one()
        reason = (self.reason or "").strip()
        if not reason:
            raise UserError(_("A correction needs a reason."))
        document = self.document_id
        # Authority is the acting user's own write access, never a button.
        document.check_access("write")
        if self.folder_id.type != FOLDER_TYPE:
            raise UserError(_("The target must be an existing folder."))
        try:
            self.folder_id.check_access("read")
        except AccessError:
            raise UserError(_("You cannot move the document into that folder.")) from None

        previous = dict(document._fields["doc_type"].selection).get(document.doc_type, _("none"))
        document.write({"doc_type": self.doc_type, "folder_id": self.folder_id.id})
        self._reclassify_pending_shell(document)
        document.message_post(
            body=Markup("<p>%s</p><p>%s</p>") % (_("Classification corrected from %s.", previous), reason),
            subtype_xmlid=REASON_SUBTYPE,
        )
        service = self.env["plasticos.document.sync"]
        if document.plasticos_doc_id:
            service.sync_native_to_legacy(document)
        return {"type": "ir.actions.act_window_close"}

    def _reclassify_pending_shell(self, document):
        """A pending shell follows the corrected type; accepted or verified evidence keeps its own."""
        shell = document.plasticos_doc_id
        if not shell:
            return
        if shell.verified or shell.override or shell.association_state == "accepted":
            document.message_post(
                body=_("The accepted business evidence keeps its classification; re-associate it if it changed."),
                subtype_xmlid=REASON_SUBTYPE,
            )
            return
        service = self.env["plasticos.document.sync"]
        code = service.DOC_TYPE_TAG_MAP.get(document.doc_type, "OTHER")
        tag = self.env["plasticos.document.tag"].search([("code", "=", code)], limit=1)
        if tag and tag != shell.tag_id:
            shell.tag_id = tag
