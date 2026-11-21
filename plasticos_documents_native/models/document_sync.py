"""Bidirectional sync between native ``documents.document`` and legacy
``plasticos.document``.

When a native document gets plastics-specific fields populated (polymer,
load, transaction, doc_type), this service ensures a corresponding
``plasticos.document`` record exists for backward compatibility with the
compliance service and existing document rules.

The sync is **one-way primary**: native → legacy.  The legacy record is
a mirror that the compliance engine can query without knowing about the
Enterprise module.
"""

import logging

from odoo import api, models

from .account_move import BILL_REVIEW_SUMMARY
from .reference_match import extract_tokens, number_pattern, split_email_body

_logger = logging.getLogger(__name__)


def _router_api():
    """The plasticos_documents exception router's constants (DEC-010). Imported here, not at module
    scope: cross-addon imports stay inside functions (AGENTS.md)."""
    from odoo.addons.plasticos_documents.models import exception_router

    return exception_router


DOCUMENT_REVIEW_SUMMARY = "Document association needs review"
# (model, ir.sequence code). The format itself is read from the sequence row.
REFERENCE_SEQUENCE_CODES = (
    ("plasticos.transaction", "plasticos.transaction"),
    ("plasticos.load", "plasticos.load"),
    ("sale.order", "sale.order"),
    ("purchase.order", "purchase.order"),
)


class DocumentSyncService(models.AbstractModel):
    """Service that synchronises native Enterprise documents with the legacy
    ``plasticos.document`` model used by the compliance engine."""

    _name = "plasticos.document.sync"
    _description = "Native ↔ Legacy Document Sync Service"

    # ── Tag Mapping ──────────────────────────────────────────
    # Maps doc_type selection values to plasticos.document.tag codes.
    # Aligned with plasticos_documents/data/document_tags_data.xml
    DOC_TYPE_TAG_MAP = {
        "bol": "BOL",
        "invoice": "INV",
        "scale_ticket": "SCALE",
        "loading_pic": "PHOTO",
        "customer_order": "CO",
        "contract": "CONTRACT",
        "certification": "CERT",
        "permit": "PERMIT",
        "lab_report": "LAB",
        "photo": "PHOTO",
        "correspondence": "CORR",
        "other": "OTHER",
        # DEC-014 OPT-A (TASK-069). Review-signal tags carry no doc_type and have no entry.
        "purchase_order": "PO",
        "packing_list": "PACKING",
        "receiving_report": "RECEIVING",
        "certified_scale_ticket": "CST",
        "delivery_order": "DO",
        "delivery_receipt": "DO",
        "carrier_certification": "CARRIER_CERT",
        "customer_invoice": "INV",
        "financial_document": "INV",
        "carrier_invoice": "INV",
        "credit_note": "INV",
        "debit_note": "INV",
        "statement": "INV",
        "payment_confirmation": "INV",
        "order_confirmation": "CO",
        "material_certification": "CERT",
        "technical_specification": "OTHER",
        "unloading_pic": "PHOTO",
        "delivery_photo": "PHOTO",
        "damage_photo": "CLAIM_PHOTO",
    }

    @api.model
    def sync_native_to_legacy(self, native_doc):
        """Create or update a ``plasticos.document`` record from a native
        ``documents.document`` record.

        Parameters
        ----------
        native_doc : recordset
            A single ``documents.document`` record with plastics fields.

        Returns
        -------
        recordset
            The created or updated ``plasticos.document`` record.
        """
        PlasticosDoc = self.env["plasticos.document"]

        # Skip if no attachment (empty/url-only documents)
        if not native_doc.attachment_id:
            return PlasticosDoc

        # Already linked? Do not retarget that pointer or erase other evidence rows.
        if native_doc.plasticos_doc_id:
            legacy = self._update_legacy(native_doc)
        else:
            legacy = self._create_pending_shell(native_doc)
        if legacy and legacy.association_state != "accepted":
            self._apply_reference_match(native_doc, legacy)
            self._schedule_review_once(native_doc)
        elif legacy:
            self.env["plasticos.exception.router"].resolve(
                native_doc, DOCUMENT_REVIEW_SUMMARY, "The original was associated by the association command."
            )
        if legacy:
            self._schedule_review_signals(native_doc)
        return legacy

    @api.model
    def _create_pending_shell(self, native_doc):
        """Unassigned classification. Native navigation is not copied as evidence."""
        PlasticosDoc = self.env["plasticos.document"]
        PlasticosTag = self.env["plasticos.document.tag"]
        tag_code = self.DOC_TYPE_TAG_MAP.get(native_doc.doc_type, "OTHER")
        tag = PlasticosTag.search([("code", "=", tag_code)], limit=1)
        if not tag:
            tag = PlasticosTag.search([("code", "=", "OTHER")], limit=1)
        if not tag:
            _logger.warning(
                "No plasticos.document.tag found for code '%s'; skipping sync for document %s",
                tag_code,
                native_doc.id,
            )
            return PlasticosDoc
        existing = PlasticosDoc.search(
            [
                ("attachment_id", "=", native_doc.attachment_id.id),
                ("res_model", "=", "documents.document"),
                ("res_id", "=", native_doc.id),
                ("association_state", "=", "pending"),
            ],
            limit=1,
        )
        if existing:
            native_doc.write({"plasticos_doc_id": existing.id})
            return existing
        legacy_doc = PlasticosDoc.create(
            {
                "name": native_doc.name or "Untitled",
                "res_model": "documents.document",
                "res_id": native_doc.id,
                "attachment_id": native_doc.attachment_id.id,
                "tag_id": tag.id,
                "association_state": "pending",
                "candidate_partner_id": native_doc.partner_id.id,
                "pending_reason": self._navigation_reason(native_doc),
            }
        )
        native_doc.write({"plasticos_doc_id": legacy_doc.id})
        _logger.info(
            "Held native document %s as unverified pending plasticos.document %s",
            native_doc.id,
            legacy_doc.id,
        )
        return legacy_doc

    @api.model
    def _navigation_reason(self, native_doc):
        if native_doc.transaction_id and native_doc.load_id:
            return "Native transaction and load were not accepted; they disagree as evidence."
        if native_doc.transaction_id or native_doc.load_id or native_doc.intake_id or native_doc.partner_id:
            return "Native navigation was not accepted as evidence."
        return "Original is unassigned."

    @api.model
    def _report_no_reviewer(self, record, subject):
        """No eligible owner is an error on the record, never a silent skip."""
        _logger.error(
            "No eligible owner can review %s %s (%s).",
            record._name,
            record.id,
            subject,
        )
        marker = "No Operations Manager is available to review this record."
        notes = record.sudo().message_ids  # sudo: the record's own notes, to keep this note single
        if any(marker in (message.body or "") for message in notes):
            return
        record.message_post(
            body=f"{marker} {subject}",
            message_type="notification",
            subtype_xmlid="mail.mt_note",
        )

    @api.model
    def _schedule_routed_activity(self, record, obligation, company):
        """One open activity for ``obligation`` with its DEC-010 owner; no owner is reported."""
        router = self.env["plasticos.exception.router"]
        route = router.route(obligation.purpose, obligation.exception_class)
        owner = router.owner(route, company or None)
        activity = router.upsert(record, obligation, route, owner, company or None)
        if not activity:
            self._report_no_reviewer(record, obligation.summary)
        return activity

    @api.model
    def _schedule_manager_activity(self, record, summary, note):
        """Hold-review entry point for a digitized vendor bill (account_move.py): Operations Manager.

        Kept as the bill guard's call site. The owner, the activity type and the idempotency come
        from the DEC-010 router; a blocked bill is never Logistics work.
        """
        router = self.env["plasticos.exception.router"]
        purpose = (
            router.purpose_from_move(record) if record._name == "account.move" else router.purpose_from_tag_codes(())
        )
        company = record.company_id if "company_id" in record._fields else self.env["res.company"]
        api_ = _router_api()
        obligation = api_.Obligation(summary, purpose, api_.EXC_BLOCKED_BILL, note)
        return self._schedule_routed_activity(record, obligation, company)

    @api.model
    def _review_purpose(self, native_doc):
        """Confirmed purpose of a held original: its doc_type plus whether one record was resolved.

        A classification without a single resolved subject (no reference, conflicting references,
        a sender who is not a party) is not attributed: Operations Manager owns it (DEC-010).
        """
        shell = native_doc.plasticos_doc_id
        attributed = bool(shell.association_subject_model and shell.association_subject_id)
        reason = shell.pending_reason or self._navigation_reason(native_doc)
        return self.env["plasticos.exception.router"].purpose_from_doc_type(native_doc.doc_type, attributed, reason)

    @api.model
    def _schedule_review_once(self, native_doc):
        """One association-review activity on the original, owned per DEC-010, never by the uploader."""
        note = native_doc.plasticos_doc_id.pending_reason or self._navigation_reason(native_doc)
        api_ = _router_api()
        obligation = api_.Obligation(
            DOCUMENT_REVIEW_SUMMARY, self._review_purpose(native_doc), api_.EXC_ASSOCIATION_REVIEW, note
        )
        return self._schedule_routed_activity(native_doc, obligation, native_doc.company_id)

    @api.model
    def _schedule_review_signals(self, native_doc):
        """One activity per DEC-019 review signal tag on the original; a removed signal is closed."""
        names = native_doc.tag_ids.mapped("name") if "tag_ids" in native_doc._fields else []
        return self.env["plasticos.exception.router"].schedule_signals(
            native_doc, names, self._review_purpose(native_doc), native_doc.company_id or None
        )

    @api.model
    def reroute_open_reviews(self):
        """Move open association reviews and bill holds to their DEC-010 owner. Repeatable.

        Returns a ``RerouteResult``: owner counts by role before and after, and the changed count.
        """
        reroute = self.env["plasticos.escalation.reroute"]
        activities = self.env["mail.activity"].search(
            [
                "|",
                "&",
                ("res_model", "=", "documents.document"),
                ("summary", "=", DOCUMENT_REVIEW_SUMMARY),
                "&",
                ("res_model", "=", "account.move"),
                ("summary", "=", BILL_REVIEW_SUMMARY),
            ],
            order="id ASC",
        )
        before = reroute._owner_roles(activities)
        rerouted = 0
        for activity in activities:
            if not activity.exists():
                continue
            snapshot = (activity.user_id.id, activity.activity_type_id.id)
            record = self.env[activity.res_model].browse(activity.res_id).exists()
            if not record:
                continue
            if record._name == "documents.document":
                if record.plasticos_doc_id.association_state == "accepted":
                    continue  # accepted: the next sync closes it; a migration does not decide that
                kept = self._schedule_review_once(record)
            else:
                kept = self._schedule_manager_activity(record, BILL_REVIEW_SUMMARY, reroute._base_note(activity))
            if kept and (kept.user_id.id, kept.activity_type_id.id) != snapshot:
                rerouted += 1
        after = reroute._owner_roles(activities)
        _logger.info("Rerouted %d review activities: before %s, after %s", rerouted, before, after)
        return _router_api().RerouteResult(before, after, rerouted)

    # ── Deterministic reference matching (email subject, body, filename, bill reference) ──
    @api.model
    def _reference_company(self, company):
        """The company a reference is resolved in. Unknown in a multi-company database."""
        if company:
            return company
        companies = self.env["res.company"].sudo().search([], limit=2)  # sudo: count legal companies only
        return companies.sudo(False) if len(companies) == 1 else self.env["res.company"]

    @api.model
    def _reference_patterns(self, company):
        """``(model, pattern)`` built from the live sequence definitions. No format is assumed."""
        patterns = []
        sequence = self.env["ir.sequence"].sudo()  # sudo: number formats only
        for model, code in REFERENCE_SEQUENCE_CODES:
            if model not in self.env:
                continue
            for row in sequence.search([("code", "=", code), ("company_id", "in", [company.id, False])]):
                pattern = number_pattern(row.prefix, row.suffix, row.padding)
                if pattern:
                    patterns.append((model, pattern))
        if "stock.picking.type" in self.env:
            types = (
                self.env["stock.picking.type"]
                .sudo()  # sudo: number formats only
                .search([("code", "=", "outgoing"), ("company_id", "=", company.id)])
            )
            for row in types.mapped("sequence_id"):
                pattern = number_pattern(row.prefix, row.suffix, row.padding)
                if pattern:
                    patterns.append(("stock.picking", pattern))
        return patterns

    @api.model
    def _reference_records(self, model, token, company):
        """Exact name equality inside one company. Another company's record is not a match."""
        if model not in self.env:
            return self.env["res.partner"].browse()
        # Identity lookup for a pending hint. Nothing is accepted or disclosed beyond the number.
        found = self.env[model].sudo().search([("name", "=", token)])  # sudo: exact-name identity lookup
        if model == "plasticos.transaction":

            def owned(tx):
                companies = tx.sale_order_id.company_id | tx.purchase_order_ids.mapped("company_id")
                return not companies or company in companies

            return found.filtered(owned)
        return found.filtered(lambda row: not row.company_id or row.company_id == company)

    @api.model
    def _reference_transactions(self, record):
        Transaction = self.env["plasticos.transaction"].sudo()  # sudo: identity lookup only
        if record._name == "plasticos.transaction":
            return record
        if record._name == "sale.order":
            return Transaction.search([("sale_order_id", "=", record.id)])
        if record._name == "purchase.order":
            return Transaction.search([("purchase_order_ids", "in", record.ids)])
        if record._name == "plasticos.load":
            return record.transaction_id
        if record._name == "stock.picking":
            return Transaction.search([("delivery_order_id", "=", record.id)])
        return Transaction.browse()

    @api.model
    def _reference_parties(self, subject):
        """Commercial partners on the vendor side of a resolved record.

        The transaction supplier and carrier, purchase order vendors, and the
        carrier of every load of the transaction or of its sale order. A buyer
        is not a party here: this is asked for a vendor's bill or paperwork.
        """
        partners = self.env["res.partner"].sudo()  # sudo: party identity only
        if subject is None:
            return partners
        subject = subject.sudo()  # sudo: party identity only
        sale_orders = self.env["sale.order"].sudo()  # sudo: party identity only
        if subject._name == "plasticos.transaction":
            partners |= subject.supplier_id | subject.carrier_id | subject.purchase_order_ids.mapped("partner_id")
            if "load_ids" in subject._fields:
                partners |= subject.load_ids.mapped("carrier_id")
            sale_orders = subject.sale_order_id
        elif subject._name == "purchase.order":
            partners |= subject.partner_id
        elif subject._name == "plasticos.load":
            partners |= subject.carrier_id
        elif subject._name == "sale.order":
            sale_orders = subject
        if sale_orders and "plasticos.load" in self.env:
            load_model = self.env["plasticos.load"].sudo()  # sudo: carrier identity only
            partners |= load_model.search([("sale_order_id", "in", sale_orders.ids)]).mapped("carrier_id")
        return partners.mapped("commercial_partner_id")

    @api.model
    def resolve_references(self, company, sources, quoted=None):
        """Resolve reference numbers to one transaction, a conflict, or nothing.

        ``sources`` is an ordered list of ``(label, text)``. ``quoted`` is the
        replied-to or forwarded part of the email: it is read only when the
        fresh sources carry no reference at all, so an older quoted number
        cannot contradict the one the sender wrote.

        Returns a dict: ``status`` (``one`` / ``conflicting`` / ``none``),
        ``matches`` (``(label, model, token, record)``), ``subject`` (the single
        agreed record: the transaction when the matches have one, else the one
        matched record) and ``detail`` (a sentence naming tokens and records).
        Nothing is written.
        """
        result = {"status": "none", "matches": [], "subject": None, "detail": ""}
        company = self._reference_company(company)
        if not company:
            result["detail"] = "The company is unknown, so no reference was resolved."
            return result
        patterns = self._reference_patterns(company)
        if not patterns:
            return result
        groups = [list(sources or [])]
        if quoted:
            groups.append([("quoted text", quoted)])
        for group in groups:
            matches = []
            seen = set()
            for label, text in group:
                for model, token in extract_tokens(text or "", patterns):
                    for record in self._reference_records(model, token, company):
                        if (record._name, record.id) in seen:
                            continue
                        seen.add((record._name, record.id))
                        matches.append((label, model, token, record))
            if matches:
                break
        if not matches:
            return result
        keys = {}
        for _label, _model, _token, record in matches:
            transactions = self._reference_transactions(record)
            for target in transactions or record:
                keys[(target._name, target.id)] = target
        named = ", ".join(
            f"{token} in the {label} ({record._name} {record.id})" for label, _m, token, record in matches
        )
        result["matches"] = matches
        if len(keys) == 1:
            result["status"] = "one"
            result["subject"] = next(iter(keys.values()))
            result["detail"] = f"Reference {named}."
        else:
            result["status"] = "conflicting"
            result["detail"] = f"References disagree: {named}."
        return result

    @api.model
    def _origin_email(self, record):
        """The oldest inbound email on the record, or an empty recordset."""
        return (
            self.env["mail.message"]
            .sudo()  # sudo: the record's own inbound email; internal notes are not read
            .search(
                [("model", "=", record._name), ("res_id", "=", record.id), ("message_type", "=", "email")],
                order="id ASC",
                limit=1,
            )
        )

    @api.model
    def _email_sources(self, email, filename=None):
        """``(sources, quoted)`` for :meth:`resolve_references`."""
        sources = []
        quoted = ""
        if email:
            fresh, quoted = split_email_body(email.body or "")
            sources.append(("email subject", email.subject or ""))
            sources.append(("email body", fresh))
        if filename:
            sources.append(("file name", filename))
        return sources, quoted

    @api.model
    def _apply_reference_match(self, native_doc, shell):
        """Pre-fill the pending shell's candidate subject from the originating email.

        Exactly one: the draft subject and draft source reference are filled when
        they are empty. Conflict: the pending reason states it. None: unchanged.
        The row stays pending; the association command remains the only acceptance.
        """
        if not shell or shell.association_state != "pending":
            return
        email = self._origin_email(native_doc)
        if not email:
            return
        sources, quoted = self._email_sources(email, native_doc.attachment_id.name or native_doc.name)
        company = native_doc.company_id or shell.subject_company_id
        found = self.resolve_references(company, sources, quoted)
        if found["status"] == "conflicting":
            reason = f"Email references conflict; nothing was pre-filled. {found['detail']}"
            if shell.pending_reason != reason:
                shell.write({"pending_reason": reason})
            return
        if found["status"] != "one":
            return
        subject = found["subject"]
        sender = email.author_id.commercial_partner_id
        if sender and sender not in self._reference_parties(subject):
            reason = (
                f"{found['detail']} Nothing was pre-filled: the sender ({sender.display_name}) is not its "
                "supplier, purchase order vendor or load carrier."
            )
            if shell.pending_reason != reason:
                shell.write({"pending_reason": reason})
            return
        if not sender:
            reason = f"{found['detail']} The sender is unknown, so it was not checked as a party of that record."
            if shell.pending_reason != reason:
                shell.write({"pending_reason": reason})
        reference = f"email {email.message_id or email.id}: {found['detail']}"
        vals = {
            "association_subject_model": subject._name,
            "association_subject_id": subject.id,
            "association_source_reference": reference,
        }
        for target in (shell, native_doc):
            if not target.association_subject_model and not target.association_subject_id:
                target.write(vals)

    @api.model
    def _update_legacy(self, native_doc):
        """Return the linked business document without writing verification.

        Repeated sync is idempotent. A native flag, tag change, or auto-sort
        cannot accept evidence or revive a stale approval.
        """
        legacy = native_doc.plasticos_doc_id
        if not legacy:
            return self.env["plasticos.document"]
        return legacy

    @api.model
    def _resolve_business_link(self, native_doc):
        """Native attributes are not an accepted association.

        Transaction, load, intake, and partner stay navigation. The pending
        shell points at the native original itself.
        """
        return "documents.document", native_doc.id

    @api.model
    def batch_sync_unlinked(self):
        """Cron-callable method: find all native documents with plastics
        fields populated but no legacy link, and sync them.

        Not scheduled. The create and write hook on ``documents.document``
        holds a classified original as it arrives; this is the operator
        backfill for originals classified before that hook existed.
        """
        NativeDoc = self.env["documents.document"]
        domain = [
            ("plasticos_doc_id", "=", False),
            ("doc_type", "!=", False),
            ("attachment_id", "!=", False),
        ]
        last_id = 0
        seen = 0
        synced = 0
        while True:
            batch = NativeDoc.search(
                [*domain, ("id", ">", last_id)],
                order="id ASC",
                limit=200,
            )
            if not batch:
                break
            last_id = batch[-1].id
            seen += len(batch)
            for doc in batch:
                # A savepoint per document: a failure rolls back only that
                # document's partial work (e.g. a legacy row created before
                # the link is written), so it stays unlinked for a later run
                # without a duplicate, and later documents still sync.
                try:
                    with self.env.cr.savepoint():
                        legacy = self.sync_native_to_legacy(doc)
                except Exception:
                    _logger.exception(
                        "Failed to sync native document %s to legacy",
                        doc.id,
                    )
                    continue
                # An empty result (no matching tag) links nothing.
                if legacy:
                    synced += 1
        _logger.info(
            "Batch sync complete: %d of %d documents synced",
            synced,
            seen,
        )
        return synced
