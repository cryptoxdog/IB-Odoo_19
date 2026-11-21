"""Responsibility-based exception routing (DEC-010) carried by mail.activity (DEC-012).

One routing function decides who owns a document exception: ``route(purpose, exception_class)``
returns the owner role, the owner group, the module-owned activity type and the reason.

The confirmed business purpose comes from the association and the obligation (the associated
model, the obligation's document type code, the native classification a human set, an
``account.move`` ``move_type``). A file name, a tag on its own or an AI guess never decides it.

* A confidently attributed shipping-document exception (BOL, packing list, scale ticket, CST,
  loading/delivery photo, receiving report, delivery order, carrier certification, PO/SO shipping
  paperwork) is owned by Logistics.
* Everything else is owned by the Operations Manager: unclassified or conflicting
  classification, unknown or conflicting references, ambiguous association, wrong or conflicting
  company, financial (AP/AR) discrepancies, duplicate and blocked bills, transaction-level and
  cross-department exceptions. An uncertain classification goes to Operations even when one
  candidate is a logistics type.

Every writer schedules through ``schedule``: it searches the record's open activity for the
obligation first (Odoo never deduplicates ``activity_schedule``), retypes or reassigns it when
the routing changed, creates it only when it is absent, and ``resolve`` closes it with
``action_feedback``. The owner comes from the ``plasticos_base`` resolver, which never returns
the cron user or the superuser; Linda, a service user, is excluded as well.
"""

import logging
from collections import namedtuple

from odoo import api, fields, models
from odoo.addons.plasticos_base.models.res_users import EXCLUDE_CONTEXT_KEY
from odoo.tools import html2plaintext

_logger = logging.getLogger(__name__)

LOGISTICS = "logistics"
OPERATIONS = "operations"
OWNER_GROUPS = {
    LOGISTICS: "plasticos_security_base.group_logistics_ops",
    OPERATIONS: "plasticos_security_base.group_operations_manager",
}
LINDA_USER_XMLID = "plasticos_logistics.user_linda"

# Exception classes. ``ops_only`` classes are Operations Manager work whatever the document is.
EXC_MISSING_DOCUMENTS = "missing_documents"
EXC_MISSING_SCALE_TICKET = "missing_scale_ticket"
EXC_ASSOCIATION_REVIEW = "association_review"
EXC_CLASSIFICATION_REVIEW = "classification_review"
EXC_EVIDENCE_GAP = "evidence_gap"
EXC_SPLIT_REVIEW = "split_review"
EXC_DUPLICATE_CANDIDATE = "duplicate_candidate"
EXC_BLOCKED_BILL = "blocked_bill"

EXCEPTION_CLASSES = {
    EXC_MISSING_DOCUMENTS: {"type": "plasticos_documents.activity_type_missing_documents", "ops_only": False},
    EXC_MISSING_SCALE_TICKET: {"type": "plasticos_documents.activity_type_missing_scale_ticket", "ops_only": False},
    EXC_ASSOCIATION_REVIEW: {"type": "plasticos_documents.activity_type_association_review", "ops_only": False},
    EXC_CLASSIFICATION_REVIEW: {"type": "plasticos_documents.activity_type_classification_review", "ops_only": True},
    EXC_EVIDENCE_GAP: {"type": "plasticos_documents.activity_type_evidence_gap", "ops_only": False},
    EXC_SPLIT_REVIEW: {"type": "plasticos_documents.activity_type_split_review", "ops_only": False},
    EXC_DUPLICATE_CANDIDATE: {"type": "plasticos_documents.activity_type_duplicate_candidate", "ops_only": True},
    EXC_BLOCKED_BILL: {"type": "plasticos_documents.activity_type_blocked_bill", "ops_only": True},
}

# plasticos.document.tag codes of shipping paperwork (DEC-010 Logistics column). ``PO`` and
# ``CARRIER_CERT`` are seeded by TASK-069 (DEC-014); they route as soon as they exist. ``CO`` is
# the customer (sales) order. ``INV``, ``CERT``, ``CONTRACT``, ``PERMIT``, ``LAB``, ``CORR``,
# ``CLAIM_PHOTO`` and ``OTHER`` are not shipping paperwork.
LOGISTICS_TAG_CODES = frozenset(
    {"BOL", "PACKING", "SCALE", "CST", "PHOTO", "RECEIVING", "DO", "CO", "PO", "CARRIER_CERT"}
)

# Native ``documents.document`` doc_type values (set by a person or by the TASK-070 tag bridge,
# never by a file name) and their owning family (AI_PROMPT_INVENTORY taxonomy.type_families).
LOGISTICS_DOC_TYPES = frozenset(
    {
        "bol",
        "scale_ticket",
        "certified_scale_ticket",
        "loading_pic",
        "unloading_pic",
        "delivery_photo",
        "photo",
        "customer_order",
        "purchase_order",
        "order_confirmation",
        "packing_list",
        "receiving_report",
        "delivery_order",
        "delivery_receipt",
        "carrier_certification",
    }
)
OPERATIONS_DOC_TYPES = frozenset(
    {
        "invoice",
        "customer_invoice",
        "financial_document",
        "carrier_invoice",
        "credit_note",
        "debit_note",
        "statement",
        "payment_confirmation",
        "contract",
        "certification",
        "material_certification",
        "technical_specification",
        "permit",
        "lab_report",
        "correspondence",
        "damage_photo",
    }
)

# Native review-signal tags (DEC-014, DEC-019), keyed by tag name. TASK-069 seeds them.
SIGNAL_NEEDS_REVIEW = "Needs Review"
SIGNAL_TO_SPLIT = "To Split"
SIGNAL_EVIDENCE_GAP = "Evidence Gap"
SIGNAL_DUPLICATE_CANDIDATE = "Duplicate Candidate"
SIGNAL_SUPPORTING_EVIDENCE = "Includes Supporting Evidence"
SIGNAL_CLASSES = {
    SIGNAL_NEEDS_REVIEW: EXC_CLASSIFICATION_REVIEW,
    SIGNAL_DUPLICATE_CANDIDATE: EXC_DUPLICATE_CANDIDATE,
    SIGNAL_EVIDENCE_GAP: EXC_EVIDENCE_GAP,
    SIGNAL_TO_SPLIT: EXC_SPLIT_REVIEW,
    SIGNAL_SUPPORTING_EVIDENCE: None,  # informational: no activity
}

# Purpose: ``family`` is LOGISTICS, OPERATIONS or None (unknown); ``confident`` is True only when
# the classification and the attribution are both settled; ``reason`` says why in plain words.
Purpose = namedtuple("Purpose", ["family", "confident", "reason"])
Route = namedtuple("Route", ["role", "group_xmlid", "activity_type_xmlid", "reason"])
# One exception obligation on one record. ``summary`` is the obligation's identity on the record.
Obligation = namedtuple("Obligation", ["summary", "purpose", "exception_class", "note"])
# A reroute run: owner counts by role before and after, and how many activities changed.
RerouteResult = namedtuple("RerouteResult", ["before", "after", "rerouted"])


class PlasticosExceptionRouter(models.AbstractModel):
    _name = "plasticos.exception.router"
    _description = "PlasticOS document exception router (DEC-010)"

    # ── Purpose (decided by association and obligation, never by file name) ──
    @api.model
    def purpose_from_tag_codes(self, codes, attributed=True):
        """Purpose of the obligations named by plasticos.document.tag codes.

        All shipping paperwork on an attributed record is Logistics. Any non-shipping code makes
        the obligation financial or cross-department, which is Operations. No code is unknown.
        """
        codes = {code for code in (codes or ()) if code}
        if not codes:
            return Purpose(None, False, "No document obligation is identified.")
        if not attributed:
            return Purpose(None, False, "The record the documents belong to is not settled.")
        if codes <= LOGISTICS_TAG_CODES:
            return Purpose(LOGISTICS, True, f"Shipping paperwork ({', '.join(sorted(codes))}).")
        if codes & LOGISTICS_TAG_CODES:
            return Purpose(
                OPERATIONS,
                True,
                f"Cross-department obligations ({', '.join(sorted(codes))}).",
            )
        return Purpose(OPERATIONS, True, f"Non-shipping obligations ({', '.join(sorted(codes))}).")

    @api.model
    def purpose_from_doc_type(self, doc_type, attributed, attribution_reason=""):
        """Purpose of a native original from its confirmed doc_type and its association state."""
        if not doc_type or doc_type == "other":
            return Purpose(None, False, "The original is unclassified.")
        if doc_type in LOGISTICS_DOC_TYPES:
            family = LOGISTICS
        elif doc_type in OPERATIONS_DOC_TYPES:
            family = OPERATIONS
        else:
            return Purpose(None, False, f"The classification '{doc_type}' has no owner.")
        if not attributed:
            return Purpose(family, False, attribution_reason or "The association is not settled.")
        return Purpose(family, True, f"Classified as '{doc_type}' and attributed to one record.")

    @api.model
    def purpose_from_move(self, move):
        """A vendor bill or customer invoice is financial: Operations Manager (DEC-010)."""
        side = "vendor bill" if move.move_type in ("in_invoice", "in_refund") else "customer invoice"
        return Purpose(OPERATIONS, True, f"Accounting {side}.")

    # ── The routing function ──
    @api.model
    def route(self, purpose, exception_class):
        """Return the ``Route`` (owner role, group, activity type, reason) for one exception."""
        spec = EXCEPTION_CLASSES[exception_class]
        if spec["ops_only"]:
            role, reason = OPERATIONS, f"{exception_class} is an Operations Manager exception."
        elif purpose.family == LOGISTICS and purpose.confident:
            role, reason = LOGISTICS, purpose.reason
        elif purpose.family == LOGISTICS:
            role, reason = OPERATIONS, f"Uncertain: {purpose.reason} A logistics candidate is not enough."
        else:
            role, reason = OPERATIONS, purpose.reason
        return Route(role, OWNER_GROUPS[role], spec["type"], reason)

    # ── Owners ──
    @api.model
    def _service_user_ids(self):
        linda = self.env.ref(LINDA_USER_XMLID, raise_if_not_found=False)
        return [linda.id] if linda else []

    @api.model
    def _excluded_ids(self, role):
        """Users who may not own ``role`` work: Linda always; Operations Managers for Logistics work."""
        excluded = self._service_user_ids()
        if role == LOGISTICS:
            group = self.env.ref(OWNER_GROUPS[OPERATIONS], raise_if_not_found=False)
            if group:
                excluded += group.sudo().all_user_ids.ids  # sudo: membership ids only, to keep roles apart
        return excluded

    @api.model
    def owner(self, route, company=None, group=None):
        """The one eligible owner of ``route`` in ``company``, or an empty recordset.

        ``group`` overrides the route's group (a caller's test seam); the exclusions stay. With no
        eligible owner nothing is substituted: the caller notes the record and logs an error.
        """
        users = self.env["res.users"]
        if company and len(company) > 1:
            return users  # conflicting companies: nobody can own it (POS-INV-05)
        if group is None:
            group = self.env.ref(route.group_xmlid, raise_if_not_found=False)
        found = users.with_context(
            **{EXCLUDE_CONTEXT_KEY: self._excluded_ids(route.role)}
        )._plasticos_escalation_manager_in_group(group, company)
        return users.browse(found.ids)

    @api.model
    def owner_is_valid(self, user, route, company=None, group=None):
        """Whether ``user`` may keep an open activity of ``route`` (an older routing may not)."""
        if not user or user.id in self._excluded_ids(route.role) or (company and len(company) > 1):
            return False
        if group is None:
            group = self.env.ref(route.group_xmlid, raise_if_not_found=False)
        if not group:
            return False
        users = self.env["res.users"].with_context(**{EXCLUDE_CONTEXT_KEY: self._excluded_ids(route.role)})
        domain = [("id", "=", user.id), *users._plasticos_escalation_domain(group, company or None)]
        return bool(users.sudo().search_count(domain, limit=1))  # sudo: read-only membership check

    # ── Activities ──
    @api.model
    def _open_activities(self, record, summary):
        """The record's open activities for one obligation, of any type (older routing included)."""
        return self.env["mail.activity"].search(
            [("res_model", "=", record._name), ("res_id", "=", record.id), ("summary", "=", summary)],
            order="id ASC",
        )

    @api.model
    def upsert(self, record, obligation, route, owner, company=None, group=None, existing=None):
        """Keep exactly one open activity for ``obligation`` on ``record``.

        Existing: retyped when the class's type differs, reassigned only when its owner is no
        longer valid for ``route``, its note follows the reason. Absent: created for ``owner``.
        Returns the activity; empty when it is absent and ``owner`` is empty (caller reports it).
        ``existing`` is the caller's preloaded open activities of this obligation (a batched page
        searches once); None searches here.
        """
        activity_type = self.env.ref(route.activity_type_xmlid, raise_if_not_found=False)
        if not activity_type:
            # Module data is missing: fail closed and visible; the caller notes the record unrouted.
            _logger.error("Activity type %s is missing; %s is not routed.", route.activity_type_xmlid, record)
            return self.env["mail.activity"]
        note =f"{obligation.note} Routed to {route.role}: {route.reason}".strip()
        if existing is None:
            existing = self._open_activities(record, obligation.summary)
        else:
            existing = existing.exists().filtered("active").sorted("id")
        if existing:
            keep, extra = existing[:1], existing[1:]
            if extra:
                # A duplicate left by an older writer is the same obligation: close it, keep one.
                extra.action_feedback(feedback="Duplicate of the obligation's open activity.")
            vals = {}
            if keep.activity_type_id != activity_type:
                vals["activity_type_id"] = activity_type.id
            if owner and keep.user_id != owner and not self.owner_is_valid(keep.user_id, route, company, group):
                vals["user_id"] = owner.id
            if html2plaintext(keep.note or "").strip() != note:
                vals["note"] = note
            if vals:
                keep.write(vals)
            return keep
        if not owner:
            return self.env["mail.activity"]
        return (
            self.env["mail.activity"]
            .with_context(mail_activity_quick_update=True)
            .create(
                {
                    "res_model_id": self.env["ir.model"]._get_id(record._name),
                    "res_id": record.id,
                    "activity_type_id": activity_type.id,
                    "summary": obligation.summary,
                    "note": note,
                    "user_id": owner.id,
                    "automated": True,
                    "date_deadline": fields.Date.context_today(record),
                }
            )
        )

    @api.model
    def schedule(self, record, obligation, company=None):
        """Route ``obligation`` and keep its one open activity. No owner: noted once and logged."""
        route = self.route(obligation.purpose, obligation.exception_class)
        owner = self.owner(route, company)
        activity = self.upsert(record, obligation, route, owner, company)
        if not activity:
            self.env["res.users"]._plasticos_note_unrouted_escalation(
                record,
                obligation.summary,
                f"No active {route.role} owner exists in the record's company. Assign it manually.",
            )
        return activity

    @api.model
    def resolve(self, record, summary, feedback, existing=None):
        """Close the obligation's open activities with feedback. Other obligations stay open.

        ``existing`` is the caller's preloaded open activities of this obligation; None searches.
        """
        if existing is None:
            activities = self._open_activities(record, summary)
        else:
            activities = existing.exists().filtered("active")
        if activities:
            activities.action_feedback(feedback=feedback)
        return activities

    @api.model
    def schedule_signals(self, record, signal_names, primary_purpose, company=None):
        """One activity per review signal present (DEC-019); a signal no longer present is closed.

        Needs Review and Duplicate Candidate go to Operations; Evidence Gap to the owner of the type
        family; To Split to the owner of the primary type; Includes Supporting Evidence to nobody.
        """
        present = set(signal_names or ())
        # A signal on an identified document belongs to its type family whatever the attribution:
        # an Evidence Gap on a recognised BOL is Logistics work, never escalated to Operations.
        family_purpose = Purpose(primary_purpose.family, primary_purpose.family is not None, primary_purpose.reason)
        scheduled = self.env["mail.activity"]
        for signal, exception_class in SIGNAL_CLASSES.items():
            if not exception_class:
                continue
            summary = f"Review signal: {signal}"
            if signal in present:
                obligation = Obligation(summary, family_purpose, exception_class, f"Tagged {signal}.")
                scheduled |= self.schedule(record, obligation, company)
            else:
                self.resolve(record, summary, f"{signal} was removed.")
        return scheduled
