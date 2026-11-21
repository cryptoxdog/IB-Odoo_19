"""Review surface and Return to Logistics on the DEC-012 exception activity itself.

The fields below are non-stored presentation computes read as the acting user: an original or
record the user cannot read shows UNKNOWN, never a value read through sudo. Candidate facts are
labelled as candidates; nothing here marks evidence verified, posts a bill or associates a file.
The only write is ``action_plasticos_return_to_logistics``, which reassigns the one existing
activity through the DEC-010 router and never creates a second one.
"""

import logging

from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

_logger = logging.getLogger(__name__)

UNKNOWN = "UNKNOWN"
OPERATIONS_GROUP_XMLID = "plasticos_security_base.group_operations_manager"


def _router_api():
    """The plasticos_documents exception router. Cross-addon imports stay in functions."""
    from odoo.addons.plasticos_documents.models import exception_router

    return exception_router


class PlasticosMailActivityReview(models.Model):
    _inherit = "mail.activity"

    plasticos_original_attachment_id = fields.Many2one(
        "ir.attachment",
        string="Original",
        compute="_compute_plasticos_review",
        ondelete="set null",
        help="The original file of the record under review, when the reviewer can read it.",
    )
    plasticos_candidate_facts = fields.Text(
        string="Candidate Facts",
        compute="_compute_plasticos_review",
        help="Extracted or classified candidates. They are not verified evidence; UNKNOWN stays UNKNOWN.",
    )
    plasticos_record_values = fields.Text(
        string="Current Record Values",
        compute="_compute_plasticos_review",
        help="The exact linked record and its current values, read with the reviewer's own access.",
    )
    plasticos_can_return_to_logistics = fields.Boolean(
        string="Can Return to Logistics",
        compute="_compute_plasticos_review",
        help="True for shipping-document exception classes that Logistics may own (DEC-010).",
    )

    @api.model
    def _plasticos_returnable_type_ids(self):
        router = _router_api()
        ids = []
        for spec in router.EXCEPTION_CLASSES.values():
            if spec["ops_only"]:
                continue
            activity_type = self.env.ref(spec["type"], raise_if_not_found=False)
            if activity_type:
                ids.append(activity_type.id)
        return ids

    def _plasticos_record(self):
        """The linked record as the acting user may read it, or None."""
        self.ensure_one()
        if not self.res_model or self.res_model not in self.env or not self.res_id:
            return None
        record = self.env[self.res_model].browse(self.res_id).exists()
        if not record or not record.has_access("read"):
            return None
        return record

    @api.depends("res_model", "res_id", "activity_type_id")
    def _compute_plasticos_review(self):
        returnable = set(self._plasticos_returnable_type_ids())
        for activity in self:
            activity.plasticos_can_return_to_logistics = activity.activity_type_id.id in returnable
            record = activity._plasticos_record()
            if record is None:
                activity.plasticos_original_attachment_id = False
                activity.plasticos_candidate_facts = UNKNOWN
                activity.plasticos_record_values = f"{UNKNOWN}: the record is missing or not readable."
                continue
            activity.plasticos_original_attachment_id = activity._plasticos_original(record)
            activity.plasticos_candidate_facts = activity._plasticos_facts(record)
            activity.plasticos_record_values = activity._plasticos_values(record)

    @staticmethod
    def _plasticos_original(record):
        for fname in ("attachment_id", "message_main_attachment_id"):
            if fname in record._fields and record[fname]:
                return record[fname]
        return False

    @staticmethod
    def _plasticos_facts(record):
        if record._name == "account.move":
            total = record.plasticos_document_total if "plasticos_document_total" in record._fields else 0.0
            extracted = f"{total:.2f}" if total else UNKNOWN
            return f"Candidate (extracted, not verified) document total: {extracted}."
        if record._name == "documents.document":
            doc_type = record.doc_type if "doc_type" in record._fields and record.doc_type else UNKNOWN
            subject = UNKNOWN
            if "association_subject_model" in record._fields and record.association_subject_model:
                subject = f"{record.association_subject_model} {record.association_subject_id}"
            return (
                f"Classification: {doc_type} (a candidate until a person confirms it). "
                f"Candidate record: {subject} (not an accepted association)."
            )
        return UNKNOWN

    @staticmethod
    def _plasticos_values(record):
        parts = [f"{record._description}: {record.display_name}"]
        for fname, label in (
            ("state", "State"),
            ("partner_id", "Partner"),
            ("ref", "Reference"),
            ("amount_total", "Total"),
            ("folder_id", "Folder"),
            ("transaction_id", "Transaction"),
        ):
            if fname not in record._fields:
                continue
            value = record[fname]
            if isinstance(value, models.BaseModel):
                value = value.display_name or UNKNOWN
            parts.append(f"{label}: {value if value not in (False, None, '') else UNKNOWN}")
        return "\n".join(parts)

    def action_plasticos_return_to_logistics(self):
        """Hand a shipping-document exception back to Logistics: the same activity, a new owner.

        Server-side: only an Operations Manager; only classes Logistics may own (DEC-010); the owner
        comes from the plasticos_base resolver inside the record's company. No activity is created.
        """
        if not self.env.user.has_group(OPERATIONS_GROUP_XMLID):
            raise AccessError(_("Only an Operations Manager can return an exception to Logistics."))
        router_api = _router_api()
        router = self.env["plasticos.exception.router"]
        returnable = set(self._plasticos_returnable_type_ids())
        type_classes = {
            self.env.ref(spec["type"]).id: exception_class
            for exception_class, spec in router_api.EXCEPTION_CLASSES.items()
            if self.env.ref(spec["type"], raise_if_not_found=False)
        }
        for activity in self:
            if activity.activity_type_id.id not in returnable:
                raise UserError(
                    _("%s is Operations Manager work and cannot be returned to Logistics.", activity.summary)
                )
            record = activity._plasticos_record()
            company = record.company_id if record is not None and "company_id" in record._fields else None
            if company is not None and len(company) != 1:
                company = None
            purpose = router_api.Purpose(router_api.LOGISTICS, True, "Returned to Logistics by the Operations Manager.")
            route = router.route(purpose, type_classes[activity.activity_type_id.id])
            owner = router.owner(route, company or None)
            if not owner:
                raise UserError(_("No active Logistics owner exists in the record's company."))
            activity.write(
                {
                    "user_id": owner.id,
                    "note": (activity.note or Markup())
                    + Markup("<p>Returned to Logistics by %s.</p>") % self.env.user.name,
                }
            )
        return True
