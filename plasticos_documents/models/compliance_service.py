from odoo import models
from odoo.exceptions import AccessError
from odoo.tools.float_utils import float_compare

# Buyer Receiving is the only quantity-scoped invoice evidence. Aggregation of
# partial receipts is not an admitted rule, so one row must cover the subject.
RECEIVING_TAG_CODE = "RECEIVING"
LEGACY_OBLIGATION = "legacy"


class PlasticosComplianceService(models.AbstractModel):
    """Document compliance checking service.

    NOTE: AbstractModel = no database table, no ACL needed.
    This is a service class, not a data model. Audit tools may flag
    "MISSING_ACL" but this is a false positive for AbstractModel classes.
    """

    _name = "plasticos.compliance.service"
    _description = "Compliance Service"

    # Gates name the rule flag that scopes them: a rule required for close only must
    # not block invoice posting (plasticos.document.rule required_for_*).
    _PURPOSE_FLAGS = {"invoice": "required_for_invoice", "close": "required_for_close"}

    def get_missing_documents(self, res_model, res_id, purpose=None):
        domain = [("res_model", "=", res_model), ("active", "=", True)]
        if purpose is not None:
            domain.append((self._PURPOSE_FLAGS[purpose], "=", True))
        rules = self.env["plasticos.document.rule"].search(domain)

        missing = []

        # Batch query: fetch all documents for this record with any of the rule tags
        tag_ids = rules.mapped("tag_id").ids
        all_docs = (
            self.env["plasticos.document"].search(
                [
                    ("res_model", "=", res_model),
                    ("res_id", "=", res_id),
                    ("tag_id", "in", tag_ids),
                    ("association_state", "=", "accepted"),
                    # Invoice, close and transaction display read legacy rows only.
                    # An operation-scoped row never satisfies or blocks them.
                    *self.env["plasticos.document"]._legacy_obligation_domain(),
                    "|",
                    ("verified", "=", True),
                    ("override", "=", True),
                ]
            )
            if tag_ids
            else self.env["plasticos.document"]
        )

        # Group docs by tag_id
        docs_by_tag = {}
        for doc in all_docs:
            if doc.tag_id.id not in docs_by_tag:
                docs_by_tag[doc.tag_id.id] = self.env["plasticos.document"]
            docs_by_tag[doc.tag_id.id] |= doc

        for rule in rules:
            docs = docs_by_tag.get(rule.tag_id.id, self.env["plasticos.document"])
            # Historical approval is not current eligibility. Expired, inactive,
            # superseded, replaced, or unbound evidence stays on the record and
            # does not satisfy the rule.
            valid_docs = docs.filtered(
                lambda d, rule=rule: (
                    d._currently_eligible() and self._quantity_covers_subject(d, rule, res_model, res_id)
                )
            )

            if not valid_docs:
                missing.append(rule.tag_id.code)

        return missing

    def _quantity_covers_subject(self, doc, rule, res_model, res_id):
        """One Receiving row covers a transaction only when its own quantity does.

        Partial rows are not summed. An unknown quantity fails closed. Other tags
        are not quantity evidence.
        """
        if not rule.tag_id or rule.tag_id.code != RECEIVING_TAG_CODE:
            return True
        if res_model != "plasticos.transaction":
            return False
        transaction = self.env["plasticos.transaction"].browse(res_id).exists()
        if not transaction or not transaction.quantity or not doc.covered_quantity:
            return False
        return float_compare(doc.covered_quantity, transaction.quantity, precision_digits=2) >= 0

    def is_compliant(self, res_model, res_id, purpose=None):
        """Live eligibility. This read does not store, recompute, or post."""
        return not self.get_missing_documents(res_model, res_id, purpose=purpose)

    # ── Operation-scope verdict (frozen facade: plasticos.document.get_scoped_evidence_verdict) ──

    def _scoped_subject(self, company_id, subject_kind, subject_id):
        """Resolve the exact subject and its company. Returns ``(subject, verdict)``.

        A subject the caller cannot read, or one in a company the caller does
        not work in, answers exactly like a missing one, so the verdict is not
        an oracle for other companies' records. Company refusals carry no
        record id.
        """
        document = self.env["plasticos.document"]
        not_found = {"status": "not_available", "reason": "subject not found"}
        if subject_kind not in document._scoped_subject_models() or subject_kind not in self.env:
            return None, {"status": "not_available", "reason": f"unknown subject kind {subject_kind!r}"}
        try:
            subject = self.env[subject_kind].browse(int(subject_id)).exists()
        except (TypeError, ValueError):
            subject = None
        if not subject:
            return None, dict(not_found)
        try:
            subject.check_access("read")
        except AccessError:
            return None, dict(not_found)
        companies, requires_company = document._subject_company_candidates(subject)
        if not self.env.su and companies - self.env.user.company_ids:
            return None, dict(not_found)
        company = self.env["res.company"].browse(int(company_id or 0)).exists()
        if not company or (not self.env.su and company not in self.env.user.company_ids):
            return None, {"status": "not_available", "reason": "company not found"}
        if len(companies) > 1:
            return None, {"status": "ambiguous", "reason": "the subject companies conflict"}
        if requires_company and not companies:
            return None, {"status": "not_available", "reason": "the subject company is not established"}
        if companies and companies != company:
            return None, {"status": "blocked", "reason": "the subject belongs to another company"}
        return subject, None

    def scoped_evidence_verdict(self, company_id, subject_kind, subject_id, obligation_kind, source_revision_key):
        """Exact company, subject, obligation and operation revision. Live read; writes nothing.

        Reuses ``_currently_eligible`` for the original, version and decision.
        Partial rows are not summed. An unknown obligation, subject or company
        is ``not_available``; zero declared rules never yield ``applied``.
        """
        document = self.env["plasticos.document"]
        kind = (obligation_kind or "").strip()
        revision = (source_revision_key or "").strip()
        if not kind or kind == LEGACY_OBLIGATION or kind not in document._scoped_obligation_kinds():
            return {"status": "not_available", "reason": f"unknown obligation {obligation_kind!r}"}
        if not revision:
            return {"status": "not_available", "reason": "operation revision is required"}
        subject, verdict = self._scoped_subject(company_id, subject_kind, subject_id)
        if verdict:
            return verdict
        scope = [
            ("res_model", "=", subject_kind),
            ("res_id", "=", subject.id),
            ("obligation_kind", "=", kind),
            ("association_state", "=", "accepted"),
            ("subject_company_id", "=", int(company_id)),
        ]
        rows = document.search([*scope, ("operation_revision_key", "=", revision)], order="id ASC")
        eligible = rows.filtered(lambda row: row._currently_eligible())
        if eligible:
            by_coverage = {}
            for row in eligible:
                by_coverage.setdefault(row.coverage_key, set()).add(row.attachment_id.id)
            conflicting = sorted(key for key, originals in by_coverage.items() if len(originals) > 1)
            if conflicting:
                return {
                    "status": "ambiguous",
                    "record_id": eligible[0].id,
                    "reason": f"conflicting originals for coverage {', '.join(conflicting)}",
                }
            return {"status": "applied", "record_id": eligible[0].id}
        if rows.filtered(lambda row: row.verified or row.override):
            return {
                "status": "stale",
                "record_id": rows[0].id,
                "reason": "the accepted evidence is expired, superseded, replaced or conflicting",
            }
        if rows:
            return {"status": "blocked", "record_id": rows[0].id, "reason": "evidence awaits verification"}
        if document.search_count([*scope, ("operation_revision_key", "!=", revision)], limit=1):
            return {"status": "stale", "reason": "evidence exists only for another operation revision"}
        return {"status": "blocked", "reason": "evidence is missing"}
