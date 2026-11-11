"""Non-authoritative, source-traceable broker knowledge with human admission."""

import re

from psycopg2 import IntegrityError

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_RISKY = frozenset({"numeric_spec", "buyer_spec", "commercial_policy", "regulatory", "procedure", "pricing"})
# Reviewer attestation is about a specific saved meaning, scope and evidence.
# Changing any of those invalidates the prior attestation before admission.
_REVIEW_INPUTS = frozenset(
    {
        "name",
        "meaning",
        "topic_tags",
        "applies_to",
        "category",
        "company_id",
        "proposed_owner",
        "evidence_class",
        "prerequisite_keys",
        "review_class",
        "reviewed_meaning",
        "workflow_scope",
        "evidence_requirements",
        "review_rationale",
        "review_evidence_ref",
        "authoritative_evidence_ref",
        "evidence_attachment_id",
        "review_evidence_file",
        "review_evidence_filename",
    }
)


class BrokerKnowledge(models.Model):
    _name = "plasticos.broker.knowledge"
    _description = "Broker Knowledge Candidate and Approved Revision"
    _order = "stable_key, version desc, id desc"

    stable_key = fields.Char(required=True, index=True, copy=False)
    version = fields.Integer(required=True, default=1, readonly=True, copy=False)
    name = fields.Char(required=True)
    meaning = fields.Text(help="Candidate guidance; this text is not approved until reviewer admission.")
    topic_tags = fields.Char(help="Comma-delimited contextual keywords for retrieval, never proof.")
    applies_to = fields.Selection(
        [
            ("all", "All Advisory Contexts"),
            ("intake", "Intake"),
            ("web_lead", "Web Lead"),
            ("offer", "Offer"),
            ("match_result", "Match Result"),
        ],
        required=True,
        default="all",
    )
    category = fields.Selection(
        [
            ("capability", "Capability"),
            ("rejection", "Rejection Meaning"),
            ("inspection", "Material Inspection"),
            ("coaching", "Coaching"),
            ("sequence", "Proposed Sequence"),
            ("technical", "Technical Reference"),
            ("operator", "Operator Knowledge"),
        ],
        required=True,
        default="operator",
    )
    company_id = fields.Many2one(
        "res.company",
        index=True,
        ondelete="restrict",
        help="Empty is shared reference knowledge; never a foreign company's private fact.",
    )
    proposed_owner = fields.Char(required=True, help="Current Odoo owner or justified local advisory owner.")
    evidence_class = fields.Selection(
        [
            ("source_assertion", "Unverified Source Assertion"),
            ("synthetic", "Synthetic Example"),
            ("expert_unverified", "Unverified Expert Guidance"),
            ("technical_candidate", "Technical Candidate"),
            ("proposed_sequence", "Proposed Sequence"),
            ("verified_reference", "Verified Reference"),
            ("approved_procedure", "Approved Procedure"),
        ],
        required=True,
        default="source_assertion",
    )
    source_file = fields.Char(required=True, copy=False)
    source_sha256 = fields.Char(required=True, copy=False)
    source_selector = fields.Char(required=True, copy=False)
    source_candidate_id = fields.Char(copy=False)
    prerequisite_keys = fields.Char(help="Comma-delimited structured Odoo fact keys required before using this advice.")
    review_class = fields.Selection(
        [
            ("ordinary", "Ordinary Advisory"),
            ("numeric_spec", "Numeric/Technical Threshold"),
            ("buyer_spec", "Buyer Specification"),
            ("commercial_policy", "Commercial Policy"),
            ("regulatory", "Regulatory Assertion"),
            ("procedure", "Claimed SOP"),
            ("pricing", "Price/Market Claim"),
        ],
        required=True,
        default="ordinary",
    )
    reviewed_meaning = fields.Text(help="Human reviewed, bounded semantic meaning, not an inferred source fact.")
    workflow_scope = fields.Char(help="Material/workflow applicability and exclusions.")
    evidence_requirements = fields.Text(help="Prerequisites and observations the broker must verify.")
    review_rationale = fields.Text()
    review_evidence_ref = fields.Char(help="Exact reference to separately inspected supporting evidence.")
    authoritative_evidence_ref = fields.Char(
        help="Reference supporting regulated, numeric, buyer, pricing or SOP claims."
    )
    evidence_attachment_id = fields.Many2one(
        "ir.attachment",
        ondelete="restrict",
        help="Existing supporting evidence bound to this exact knowledge revision.",
    )
    review_evidence_file = fields.Binary(
        string="Upload Supporting Evidence",
        attachment=True,
        copy=False,
        help="Native Odoo attachment owned by the current knowledge revision.",
    )
    review_evidence_filename = fields.Char(copy=False)
    reviewer_attested = fields.Boolean(default=False, help="Reviewer confirms they inspected the support and scope.")
    audit_event_ids = fields.One2many("plasticos.broker.review.event", "knowledge_id", readonly=True)
    reviewer_id = fields.Many2one("res.users", readonly=True, copy=False)
    reviewed_at = fields.Datetime(readonly=True, copy=False)
    retirement_reason = fields.Text()
    state = fields.Selection(
        [("draft", "Draft"), ("approved", "Approved"), ("retired", "Retired")],
        required=True,
        default="draft",
        readonly=True,
        index=True,
        copy=False,
    )

    # Odoo 19 native indexes; NULL companies are normalized to a single shared scope.
    _unique_candidate_revision = models.UniqueIndex("(stable_key, version, COALESCE(company_id, 0))")
    _unique_active_advice = models.UniqueIndex("(stable_key, COALESCE(company_id, 0)) WHERE state = 'approved'")
    _valid_version = models.Constraint("CHECK (version >= 1)", "Knowledge version must be positive.")

    def _require_reviewer(self):
        if not (self.env.su or self.env.user.has_group("plasticos_broker_intelligence.group_broker_reviewer")):
            raise AccessError("Only an authorized Broker Knowledge Reviewer can change or admit knowledge.")

    @api.model_create_multi
    def create(self, vals_list):
        self._require_reviewer()
        for vals in vals_list:
            if vals.get("state", "draft") != "draft" or vals.get("reviewer_id") or vals.get("reviewed_at"):
                raise UserError("Knowledge must enter as a draft; reviewer admission is a separate action.")
            if not vals.get("stable_key") or not vals.get("source_file") or not vals.get("source_selector"):
                raise ValidationError("Candidate identity and source provenance are required.")
            if not _SHA256.fullmatch(str(vals.get("source_sha256") or "")):
                raise ValidationError("Source must carry its real lowercase SHA-256 digest.")
        return super().create(vals_list)

    def write(self, vals):
        self._require_reviewer()
        protected = {
            "state",
            "stable_key",
            "version",
            "source_file",
            "source_sha256",
            "source_selector",
            "source_candidate_id",
            "reviewer_id",
            "reviewed_at",
        }
        if protected.intersection(vals):
            raise UserError(
                "Knowledge state, source identity and revision are changed only through controlled actions."
            )
        if any(item.state != "draft" for item in self):
            raise UserError("Approved/retired knowledge is immutable. Create a new draft revision.")
        if _REVIEW_INPUTS.intersection(vals):
            if vals.get("reviewer_attested"):
                raise UserError("Save revised knowledge and evidence before attesting in a separate action.")
            vals = dict(vals, reviewer_attested=False)
        return super().write(vals)

    def unlink(self):
        raise UserError("Broker knowledge retains its approval and retirement history; deletion is prohibited.")

    def _check_admission(self):
        self.ensure_one()
        if self.state != "draft":
            raise UserError("Only draft knowledge may be admitted.")
        required = (
            "source_file",
            "source_sha256",
            "source_selector",
            "source_candidate_id",
            "proposed_owner",
            "reviewed_meaning",
            "workflow_scope",
            "evidence_requirements",
            "review_rationale",
            "review_evidence_ref",
        )
        missing = [field for field in required if not str(self[field] or "").strip()]
        if not _SHA256.fullmatch(str(self.source_sha256 or "")):
            missing.append("valid SHA-256")
        if missing:
            raise UserError(f"Cannot approve: missing verified review inputs: {', '.join(missing)}.")
        if not self.reviewer_attested:
            raise UserError("Reviewer must attest to the supporting evidence and bounded meaning.")
        # Supporting evidence may be uploaded using native Odoo Binary attachment
        # storage, or linked as an existing attachment of this exact revision.
        attachment = self.evidence_attachment_id
        if not attachment:
            # A binary-field read would decode the entire file just to check
            # presence. Locate its native Odoo attachment instead.
            attachment = self.env["ir.attachment"].search(
                [
                    ("res_model", "=", self._name),
                    ("res_id", "=", self.id),
                    ("res_field", "=", "review_evidence_file"),
                ],
                limit=1,
            )
        if not attachment:
            raise UserError("Admission requires a readable Odoo attachment bound to this exact revision.")
        if (
            self.review_class in _RISKY
            or self.evidence_class in {"synthetic", "proposed_sequence", "technical_candidate"}
        ) and not self.authoritative_evidence_ref:
            raise UserError("High-risk candidate also requires an authoritative evidence reference.")
        attachment.check_access("read")
        if attachment.res_model != self._name or attachment.res_id != self.id:
            raise UserError("Supporting evidence must be attached to this exact knowledge revision.")
        if not attachment.file_size:
            raise UserError("An empty supporting attachment cannot establish review evidence.")

    def action_approve(self):
        self._require_reviewer()
        for item in self:
            # The partial unique index is the final concurrent-approval guard.
            self.env.cr.execute("SELECT id FROM plasticos_broker_knowledge WHERE id = %s FOR UPDATE", [item.id])
            item.invalidate_recordset(["state"])
            item._check_admission()
            existing = self.search(
                [
                    ("stable_key", "=", item.stable_key),
                    ("state", "=", "approved"),
                    ("company_id", "=", item.company_id.id or False),
                ],
                limit=1,
            )
            if existing:
                raise UserError("Retire the currently approved revision before approving its successor.")
            now = fields.Datetime.now()
            try:
                with self.env.cr.savepoint():
                    super(BrokerKnowledge, item).write(
                        {"state": "approved", "reviewer_id": self.env.user.id, "reviewed_at": now}
                    )
            except IntegrityError as exc:
                raise UserError("Another reviewer admitted an active revision concurrently.") from exc
            self.env["plasticos.broker.review.event"]._append_from_knowledge(
                knowledge=item, event="approved", reason=item.review_rationale
            )
        return True

    def action_retire(self):
        self.ensure_one()
        self._require_reviewer()
        if self.state != "approved":
            raise UserError("Only approved knowledge can be retired.")
        return {
            "type": "ir.actions.act_window",
            "name": "Retire Knowledge",
            "res_model": "plasticos.broker.retire.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_knowledge_id": self.id},
        }

    def _retire_with_reason(self, reason):
        self.ensure_one()
        self._require_reviewer()
        reason = str(reason or "").strip()
        if not reason:
            raise UserError("Retirement requires a reviewer rationale.")
        self.env.cr.execute("SELECT id FROM plasticos_broker_knowledge WHERE id = %s FOR UPDATE", [self.id])
        self.invalidate_recordset(["state"])
        if self.state != "approved":
            raise UserError("Only an active, approved revision may be retired.")
        super().write({"state": "retired", "retirement_reason": reason})
        self.env["plasticos.broker.review.event"]._append_from_knowledge(knowledge=self, event="retired", reason=reason)
        return True

    def action_new_revision(self):
        self.ensure_one()
        self._require_reviewer()
        if self.state == "draft":
            raise UserError("Complete or retire this draft before creating a successor.")
        versions = self.search(
            [("stable_key", "=", self.stable_key), ("company_id", "=", self.company_id.id or False)]
        ).mapped("version")
        draft = self.copy(
            {
                "version": max(versions or [0]) + 1,
                "state": "draft",
                "stable_key": self.stable_key,
                "source_file": self.source_file,
                "source_sha256": self.source_sha256,
                "source_selector": self.source_selector,
                "source_candidate_id": self.source_candidate_id,
                "reviewer_id": False,
                "reviewed_at": False,
                "reviewed_meaning": False,
                "review_rationale": False,
                "review_evidence_ref": False,
                "authoritative_evidence_ref": False,
                "evidence_attachment_id": False,
                "review_evidence_filename": False,
                "reviewer_attested": False,
                "retirement_reason": False,
            }
        )
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": draft.id,
            "view_mode": "form",
            "target": "current",
        }
