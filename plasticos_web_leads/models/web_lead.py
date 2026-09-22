# ═══════════════════════════════════════════════════════════
# Model : plasticos.web.lead
# Purpose: Web lead ingestion with AI-powered triage pipeline:
#          1. Receive raw Cognito payload OR pre-processed agent payload
#          2. AI normalization (1 LLM call)
#          3. Image analysis (1 Vision call per image)
#          4. Deterministic HOT/COLD classification
#          5. HOT → intake (partner deferred to buyer-match)
# ═══════════════════════════════════════════════════════════
from __future__ import annotations

import base64
import logging
import uuid
from typing import Any

import requests as http_requests

from odoo import api, fields, models
from odoo.exceptions import UserError

from ..adapters.base import PACKET_SCHEMA_VERSION, WebLeadPacket, packet_to_dict
from ..adapters.registry import get_adapter
from . import ai_normalizer, image_analyzer
from .attachment_processor import copy_successful_attachments_to_intake, process_attachments
from .classification_engine import classify_lead
from .economic_evaluator import evaluate_economic_opportunity
from .economic_policy import evaluate_economic_eligibility
from .evidence_keys import (
    ASSESSMENT_STATUS_ASSESSED,
    KEY_ASSESSMENT,
    KEY_DECISION,
    KEY_ECONOMIC_ASSESSMENT,
    KEY_ECONOMIC_ELIGIBILITY,
    KEY_HOT_QUALIFIERS,
    KEY_REASONS,
    KEY_REVIEW_REASONS,
    KEY_REVIEW_REQUIRED,
    KEY_STATUS,
)
from .evidence_reconciler import reconcile_evidence
from .inference_provider import InferenceProvider
from .quantity_normalizer import QuantityEvidence, normalize_quantity_evidence
from .review_snapshot import build_snapshot_payload, snapshot_content_hash

_logger = logging.getLogger(__name__)

# ── Pallet weight assumption when no lbs given ───────────────────────────────
_LBS_PER_PALLET_ASSUMPTION = 1_500  # conservative: typical plastic pallet
_FORM_TERM_CRATE = "crate"

# ═══════════════════════════════════════════════════════════
# Mapping helpers — translate AI output to Odoo field values
# ═══════════════════════════════════════════════════════════

_POLYMER_NORMALIZE: dict[str, str] = {
    "hdpe": "HDPE",
    "ldpe": "LDPE",
    "lldpe": "LLDPE",
    "pp": "PP",
    "pet": "PET",
    "rpet": "PET",
    "ps": "PS",
    "hips": "HIPS",
    "pvc": "PVC",
    "eva": "EVA",
    "abs": "ABS",
    "nylon": "NYLON",
    "pa": "NYLON",
    "pc": "PC",
    "pbt": "PBT",
    "pom": "POM",
    "acetal": "POM",
    "pmma": "PMMA",
    "ppo": "PPO",
    "tpe": "TPE",
    "tpu": "TPE",
    "pla": "PET",
    "e-waste": "EWASTE",
    "ewaste": "EWASTE",
}

_FORM_NORMALIZE: dict[str, str] = {
    "bale": "BALES",
    "baled": "BALES",
    "bales": "BALES",
    "regrind": "REGRIND",
    "flake": "FLAKE",
    "flakes": "FLAKE",
    "pellet": "PELLETS",
    "pellets": "PELLETS",
    "rollstock": "ROLLSTOCK",
    "purge": "PURGE",
    "lump": "OTHER",
    "lumps": "OTHER",
    "film": "ROLLSTOCK",
    "sheet": "SHEET",
    "powder": "POWDER",
    "parts": "PARTS",
    "part": "PARTS",
    "pallet": "PALLETS",
    "pallets": "PALLETS",
    "tote": "TOTES",
    "totes": "TOTES",
    _FORM_TERM_CRATE: "CRATES",
    "crates": "CRATES",
    "re-useable": "OTHER",
    "reuseable": "OTHER",
    "reusable": "OTHER",
    "bottle": "BOTTLES",
    "bottles": "BOTTLES",
    "roll": "ROLLSTOCK",
    "rolls": "ROLLSTOCK",
}

_SOURCE_NORMALIZE: dict[str, str] = {
    "post_industrial": "post_industrial",
    "post-industrial": "post_industrial",
    "post_consumer": "post_consumer",
    "post-consumer": "post_consumer",
    "post_commercial": "post_commercial",
    "post-commercial": "post_commercial",
    "agricultural": "agricultural",
    "prime": "prime",
    "virgin": "prime",
    "wide_spec": "wide_spec",
    "wide spec": "wide_spec",
    "off_spec": "off_spec",
    "off spec": "off_spec",
    "ocean_recovered": "ocean_recovered",
    "ocean": "ocean_recovered",
}

_FREQ_TO_DEAL: dict[str, str] = {
    "ongoing": "recurring",
    "monthly": "recurring",
    "weekly": "recurring",
    "one_time": "spot",
    "one-time": "spot",
    "spot": "spot",
    "unclear": "spot",
}

# Non-numeric strings that _safe_int should silently ignore
_NON_NUMERIC_WORDS = frozenset({"unknown", "n/a", "unclear", "tbd", "na", "none", ""})


def _safe_int(val: Any, default: int = 0) -> int:
    """Coerce to int, returning default on failure.

    Handles:
    - None → default
    - "30,000" → 30000 (comma-formatted)
    - "unknown" / "n/a" / "unclear" → default (silently)
    - float strings → truncated int
    """
    if val is None:
        return default
    s = str(val).replace(",", "").strip()
    if s.lower() in _NON_NUMERIC_WORDS:
        return default
    try:
        result = int(float(s))
        return result
    except (ValueError, TypeError):
        _logger.debug("_safe_int: non-numeric value %r → %d", val, default)
        return default


def _extract_cognito_name(raw_payload: dict[str, Any]) -> str:
    """Extract contact name from Cognito payload.

    Cognito sends Name as a dict: {"First": ..., "Last": ..., "FirstAndLast": ...}
    Handles dict, plain string, and legacy YourName field.
    """
    _name_val = raw_payload.get("Name")
    if isinstance(_name_val, dict):
        return (
            (_name_val.get("FirstAndLast") or "").strip()
            or f"{(_name_val.get('First') or '').strip()} {(_name_val.get('Last') or '').strip()}".strip()
            or ""
        )
    if isinstance(_name_val, str):
        return _name_val.strip()
    return (raw_payload.get("YourName") or "").strip()


class PlasticosWebLead(models.Model):
    """Stores every inbound web lead from Cognito forms or external agents.

    HOT leads automatically generate a plasticos.intake record.
    COLD leads are stored for reference but do not create downstream records.

    Pipeline (create_from_cognito):
      1. Parse + normalise Cognito fields
      2. Create web.lead record (decision=cold, state=received)
      3. _run_triage_pipeline():
           a. AI normalization (LLM)
           b. Image analysis (Vision)
           c. _merge_ai_and_vision() — weight fallback cascade here
           d. classify_lead() — deterministic HOT/COLD
           e. HOT → _create_intake() + notify admin
           f. Attach images (async-safe: skip on COLD to avoid blocking)
    """

    _name = "plasticos.web.lead"
    _description = "Web Lead"
    _inherit = ["mail.thread"]
    _order = "create_date desc"
    _rec_name = "lead_id"

    # ═══════════════════════════════════════════════════════════
    # Identity
    # ═══════════════════════════════════════════════════════════

    lead_id = fields.Char(
        required=True,
        index=True,
        tracking=True,
        help="Unique lead identifier (e.g. WL123 or CG-abc123).",
    )
    source = fields.Selection(
        [
            ("web_lead", "Web Lead"),
            ("cognito_form", "Cognito Form"),
            ("n8n", "n8n Webhook"),
            ("api", "External API"),
            ("manual", "Manual Entry"),
        ],
        string="Source",
        default="web_lead",
        tracking=True,
        help="Channel through which this lead was received.",
    )
    lead_source_id = fields.Many2one(
        "utm.source",
        string="Lead Source",
        index=True,
        tracking=True,
        help="How this lead was originally acquired (SICCODE, referral, web form, etc.).",
        ondelete="restrict",
    )

    # ═══════════════════════════════════════════════════════════
    # Raw Data (immutable after creation)
    # ═══════════════════════════════════════════════════════════

    raw_payload = fields.Json(
        readonly=True,
        help="Complete raw form submission from Cognito.",
    )
    provider_key = fields.Char(
        readonly=True,
        index=True,
        help="Inbound provider key used to construct this lead's canonical packet.",
    )
    provider_external_id = fields.Char(
        readonly=True,
        index=True,
        help="Stable provider submission identity used alongside the historical lead ID.",
    )
    canonical_payload = fields.Json(
        readonly=True,
        help="Versioned provider-neutral seller evidence retained for packet-backed retries.",
    )
    evidence_bundle = fields.Json(
        readonly=True,
        help="Versioned deterministic, AI, and attachment evidence produced during triage.",
    )
    review_status = fields.Selection(
        [
            ("pending", "Broker Review Pending"),
            ("clarification_required", "Clarification Required"),
            ("approved", "Broker Approved"),
            ("rejected", "Broker Rejected"),
        ],
        default="pending",
        tracking=True,
        index=True,
        help="Human disposition of HOT triage evidence. HOT is eligibility, not commercial readiness.",
    )
    review_notes = fields.Text(
        string="Broker Review Notes",
        help="Broker rationale for an approved, rejected, or clarification-required disposition.",
    )
    review_required_reason = fields.Text(
        string="Review Requirements",
        readonly=True,
        help="Concise evidence conflicts and missing facts that require broker attention.",
    )
    review_snapshot_ids = fields.One2many(
        "plasticos.web.lead.review.snapshot",
        "web_lead_id",
        string="Broker-Approved Snapshots",
    )
    review_snapshot_count = fields.Integer(compute="_compute_review_snapshot_count")
    ai_analysis = fields.Json(
        readonly=True,
        help="AI analysis output (merged from LLM + Vision).",
    )

    # ═══════════════════════════════════════════════════════════
    # Classification
    # ═══════════════════════════════════════════════════════════

    decision = fields.Selection(
        [
            ("hot", "HOT"),
            ("cold", "COLD"),
        ],
        required=True,
        default="cold",  # FIX: explicit default — no missing-required crash
        index=True,
        tracking=True,
    )
    decision_reasons = fields.Json(
        readonly=True,
        help="Reasons for the HOT/COLD classification.",
    )

    # ═══════════════════════════════════════════════════════════
    # Extracted Fields (denormalized for display)
    # ═══════════════════════════════════════════════════════════

    company_name = fields.Char(string="Company")
    contact_name = fields.Char(string="Contact Name")
    contact_email = fields.Char(string="Contact Email")
    contact_phone = fields.Char(string="Contact Phone")
    material_description = fields.Text(string="Material Description")
    quantity_text = fields.Char(
        string="Quantity (Form Input)",
        help="Raw quantity text from the form — unprocessed, for display only.",
    )
    estimated_lbs_per_load = fields.Integer(string="Est. Lbs/Load")
    estimated_loads_per_month = fields.Integer(string="Est. Loads/Month")
    frequency = fields.Char(string="Frequency")
    has_contaminants = fields.Boolean(string="Has Contaminants")
    contaminant_notes = fields.Text(string="Contaminant Notes")

    # ═══════════════════════════════════════════════════════════
    # AI Triage Fields
    # ═══════════════════════════════════════════════════════════

    ai_normalized = fields.Json(
        string="AI Normalized Data",
        readonly=True,
        help="Structured output from the LLM normalization call.",
    )
    ai_vision_results = fields.Json(
        string="AI Vision Results",
        readonly=True,
        help="Structured output from Vision API image analysis.",
    )
    triage_log = fields.Text(
        string="Triage Audit Log",
        readonly=True,
        help="Step-by-step log of the triage pipeline execution.",
    )
    image_urls = fields.Json(
        string="Image URLs",
        readonly=True,
        help="URLs of images submitted with the form.",
    )

    # ═══════════════════════════════════════════════════════════
    # Processing State
    # ═══════════════════════════════════════════════════════════

    state = fields.Selection(
        [
            ("received", "Received"),
            ("intake_created", "Intake Created"),
            ("skipped", "Skipped (Cold)"),
            ("error", "Error"),
        ],
        default="received",
        tracking=True,
        index=True,
    )
    error_message = fields.Text(readonly=True)

    # ═══════════════════════════════════════════════════════════
    # Links
    # ═══════════════════════════════════════════════════════════

    partner_id = fields.Many2one(
        "res.partner",
        string="Created/Linked Partner",
        index=True,
        ondelete="set null",
    )
    intake_id = fields.Many2one(
        "plasticos.intake",
        string="Created Intake",
        index=True,
        ondelete="set null",
    )

    @api.depends("review_snapshot_ids")
    def _compute_review_snapshot_count(self):
        for record in self:
            record.review_snapshot_count = len(record.review_snapshot_ids)

    # ═══════════════════════════════════════════════════════════
    # Constraints
    # ═══════════════════════════════════════════════════════════

    _unique_lead_id = models.Constraint(
        "unique(lead_id)",
        "A web lead with this ID already exists (idempotency guard).",
    )

    # ═══════════════════════════════════════════════════════════
    # CRUD Guards
    # ═══════════════════════════════════════════════════════════

    def write(self, vals):
        """Guard against modifying processed leads.

        FIX: previous guard was bypassable by including 'state' alongside other
        fields. Now only pure state/log/error transitions are allowed on
        intake_created leads — all other field modifications are blocked.
        """
        _STATE_ONLY_FIELDS = frozenset(
            {
                "state",
                "error_message",
                "triage_log",
                "review_status",
                "review_notes",
                "review_required_reason",
                "review_snapshot_ids",
                "crm_lead_id",
            }
        )
        non_state_fields = set(vals.keys()) - _STATE_ONLY_FIELDS
        if non_state_fields:
            for rec in self:
                if rec.state == "intake_created":
                    raise UserError(
                        f"Cannot modify lead '{rec.lead_id}' after intake was created. "
                        f"Edit the intake record directly. (Attempted: {sorted(non_state_fields)})"
                    )
        return super().write(vals)

    def unlink(self):
        """Prevent deletion of processed leads."""
        for rec in self:
            if rec.state == "intake_created":
                raise UserError(
                    f"Cannot delete lead '{rec.lead_id}' after intake was created. "
                    "The lead record is preserved for audit trail."
                )
        return super().unlink()

    # ═══════════════════════════════════════════════════════════
    # Entry Point 1: Direct Cognito Ingestion (AI Triage)
    # ═══════════════════════════════════════════════════════════

    @api.model
    def create_from_cognito(self, raw_payload: dict[str, Any]) -> PlasticosWebLead:
        """Keep the public Cognito entrypoint while routing to the internal adapter."""
        try:
            return self.create_from_packet(get_adapter("cognito").to_packet(raw_payload))
        except ValueError as exc:
            raise UserError(str(exc)) from exc

    @api.model
    def create_from_packet(self, packet: WebLeadPacket) -> PlasticosWebLead:
        """Create a durable web lead from a validated provider-neutral packet."""
        if packet.schema_version != PACKET_SCHEMA_VERSION:
            raise UserError(f"Unsupported web-lead packet version: {packet.schema_version!r}")

        lead_id = packet.idempotency_key
        if lead_id:
            existing = self.search([("lead_id", "=", lead_id)], limit=1)
            if existing:
                _logger.info(
                    "Duplicate packet submission for provider=%s external_id=%s.",
                    packet.provider,
                    packet.provider_external_id,
                )
                return existing
        else:
            lead_id = self.env["ir.sequence"].next_by_code("plasticos.web.lead") or f"WL-{uuid.uuid4().hex[:5].upper()}"

        web_lead_source = self.env["utm.source"].search([("name", "=", "Web Lead Form")], limit=1)
        image_urls = [item.source_url for item in packet.attachments if item.content_type.startswith("image/")]
        contaminants = packet.contaminants_text.strip()
        negative_contaminant_values = {"", "no", "none", "n/a", "na", "clean"}
        vals = {
            "lead_id": str(lead_id),
            "source": "web_lead",
            "lead_source_id": web_lead_source.id if web_lead_source else False,
            "decision": "cold",
            "raw_payload": dict(packet.raw_payload),
            "provider_key": packet.provider,
            "provider_external_id": packet.provider_external_id or False,
            "canonical_payload": packet_to_dict(packet, omit_raw_payload=True),
            "company_name": packet.company_name or "Unknown",
            "contact_name": packet.contact_name,
            "contact_email": packet.contact_email,
            "contact_phone": packet.contact_phone,
            "material_description": packet.material_description,
            "quantity_text": packet.weight_per_load_text or packet.quantity_text,
            "has_contaminants": contaminants.lower() not in negative_contaminant_values,
            "contaminant_notes": contaminants or False,
            "image_urls": image_urls,
            "state": "received",
        }
        lead = self.create(vals)
        _logger.info("Web lead %s created from provider packet %s.", lead.lead_id, packet.provider)
        lead._run_triage_pipeline()
        return lead

    # ═══════════════════════════════════════════════════════════
    # Entry Point 2: Pre-Processed Agent Payload (Legacy / n8n)
    # ═══════════════════════════════════════════════════════════

    @api.model
    def create_from_agent(self, payload: dict[str, Any]) -> PlasticosWebLead:
        """Create a web lead from a pre-processed agent payload (n8n legacy).

        Expected payload structure::

            {
                "lead_id": "WL123",
                "source": "cognito_form",
                "decision": "Hot",
                "decision_reasons": [...],
                "raw_payload": { ... Cognito form fields ... },
                "ai_analysis": { ... }
            }

        NOTE: Odoo re-runs its own classification — the agent's decision is
        stored as external_decision for audit but does not bypass Odoo triage.
        """
        lead_id = payload.get("lead_id")
        if not lead_id:
            raise UserError("Missing required field: lead_id")
        existing = self.search([("lead_id", "=", lead_id)], limit=1)
        if existing:
            _logger.info("Web lead %s already exists, returning existing.", lead_id)
            return existing

        raw = payload.get("raw_payload") or {}

        # FIX: use same name extraction as create_from_cognito — handles dict Name
        contact = _extract_cognito_name(raw) or raw.get("YourName", "").strip()
        company = (raw.get("YourBusinessCompanyName", "") or raw.get("CompanyName", "") or "").strip()
        email = (raw.get("Email", "") or raw.get("EmailAddress", "") or "").strip()
        phone = (raw.get("Phone", "") or raw.get("PhoneNumber", "") or "").strip()
        qty_text = (raw.get("WhatIsTheQuantity") or raw.get("WeightPerLoad") or "").strip()
        contaminants = (raw.get("AreThereAnyContaminants", "") or "").strip()
        material_desc = (
            raw.get("WhatIsIt", "") or raw.get("DescribeYourMaterial", "") or raw.get("WhatTypeOfPlastic", "") or ""
        ).strip()

        image_urls = self._extract_image_urls(raw)
        web_lead_source = self.env["utm.source"].search([("name", "=", "Web Lead Form")], limit=1)

        # Store agent's pre-classified decision for audit; Odoo will re-classify
        external_decision = (payload.get("decision") or "cold").lower()

        vals = {
            "lead_id": lead_id,
            "source": payload.get("source", "api"),
            "lead_source_id": web_lead_source.id if web_lead_source else False,
            "decision": "cold",  # always start cold; triage will update
            "decision_reasons": payload.get("decision_reasons"),
            "raw_payload": raw,
            "ai_analysis": payload.get("ai_analysis"),  # store for reference
            "company_name": company or "Unknown",
            "contact_name": contact,
            "contact_email": email,
            "contact_phone": phone,
            "material_description": material_desc,
            "quantity_text": qty_text,
            "has_contaminants": bool(contaminants),
            "contaminant_notes": contaminants or False,
            "image_urls": image_urls,
            "state": "received",
        }

        lead = self.create(vals)
        _logger.info(
            "Web lead %s created from agent (external_decision=%s). Running Odoo triage.",
            lead_id,
            external_decision,
        )

        # Always run Odoo's own triage — never blindly trust external decision
        lead._run_triage_pipeline()
        return lead

    # ═══════════════════════════════════════════════════════════
    # AI Triage Pipeline
    # ═══════════════════════════════════════════════════════════

    def _run_triage_pipeline(self):
        """Execute the full AI triage pipeline on this web lead.

        Steps:
          [AI]     1. AI normalization (if enabled)
          [VISION] 2. Image analysis (if enabled + images present)
          [MERGE]  3. Merge AI + Vision → weight fallback cascade
          [CLASS]  4. Deterministic HOT/COLD classification
          [WRITE]  5. Persist classification result
          [HOT]    6. Create intake + notify admin
          [IMG]    7. Attach images (HOT only — skip blocking download for COLD)
        """
        self.ensure_one()
        config = self.env["plasticos.web.lead.config"].sudo().get_config()
        run_id = uuid.uuid4().hex
        log_lines = [f"[RUN] {run_id} started"]

        try:
            canonical_payload = self.canonical_payload or {}
            is_packet_path = bool(canonical_payload)
            triage_input = canonical_payload if is_packet_path else self.raw_payload or {}
            quantity_evidence: QuantityEvidence | None = None
            attachment_evidence: list[dict[str, Any]] = []

            if is_packet_path:
                quantity_evidence = normalize_quantity_evidence(
                    quantity_text=triage_input.get("quantity_text"),
                    weight_per_load_text=triage_input.get("weight_per_load_text"),
                    frequency_text=triage_input.get("frequency_text"),
                )
                log_lines.append(
                    f"[QUANTITY] weight={quantity_evidence.load_weight_lbs} "
                    f"source={quantity_evidence.weight_source} cadence={quantity_evidence.loads_per_month}"
                )

            ai_data: dict[str, Any] = {}
            text_provider_spec = config.get_inference_provider("text_normalization") if config.ai_enabled else None
            if text_provider_spec:
                log_lines.append("[AI] Running normalization.")
                text_provider = InferenceProvider(**text_provider_spec)
                ai_data = ai_normalizer.normalize_with_provider(
                    raw_payload=triage_input,
                    quantity_evidence=quantity_evidence,
                    provider=text_provider,
                )
                provider_used = ai_data.pop("_provider_used", "unknown")
                log_lines.append(f"[AI] provider={provider_used}:{text_provider.model}")
            else:
                log_lines.append("[AI] SKIPPED (disabled or no API keys).")

            vision_results: list[dict[str, Any]] = []
            vision_provider_spec = config.get_inference_provider("vision_analysis") if config.vision_enabled else None
            if is_packet_path:
                packet_attachments = triage_input.get("attachments") or []
                analyzer = None
                if vision_provider_spec:
                    vision_provider = InferenceProvider(**vision_provider_spec)
                    analyzer = lambda content, mimetype: image_analyzer.analyze_image_with_provider(
                        content,
                        content_type=mimetype,
                        provider=vision_provider,
                    )
                    log_lines.append(f"[VISION] provider={vision_provider.provider}:{vision_provider.model}")

                log_lines.append(f"[ATTACHMENTS] processing={len(packet_attachments)}")
                attachment_evidence = process_attachments(
                    lead=self,
                    attachments=packet_attachments,
                    analyzer=analyzer,
                    evidence_bundle=self.evidence_bundle,
                )
                vision_results = [
                    row["analysis"]
                    for row in attachment_evidence
                    if row.get("analysis_type") == "image"
                    and row.get("analysis_status") == "success"
                    and row.get("analysis")
                ]
            else:
                urls = self.image_urls or []
                if urls:
                    log_lines.append(
                        "[VISION] SKIPPED legacy URL path; only admitted attachment bytes are sent to providers."
                    )
                else:
                    log_lines.append("[VISION] SKIPPED.")

            merged = self._merge_ai_and_vision(ai_data, vision_results, quantity_evidence=quantity_evidence)
            evidence_bundle = None
            if is_packet_path and quantity_evidence is not None:
                evidence_bundle = reconcile_evidence(
                    canonical_payload=canonical_payload,
                    quantity=quantity_evidence,
                    ai_normalized=ai_data,
                    attachments=attachment_evidence,
                    run_id=run_id,
                )
                log_lines.append(f"[RECONCILE] conflicts={len(evidence_bundle['conflicts'])}")

            economic_eligibility = evaluate_economic_eligibility(
                estimated_lbs=float(merged.get("estimated_lbs") or 0),
                standard_hot_min_lbs=config.hot_min_lbs or 10_000,
                reusable_item_hot_min_lbs=config.reusable_item_hot_min_lbs or 8_000,
                polymer_code=merged.get("polymer"),
                form_code=merged.get("form"),
                reusable_item_policy_codes=config.get_reusable_item_policy_codes(),
            )
            log_lines.append(
                f"[POLICY] class={economic_eligibility.opportunity_class} "
                f"threshold={economic_eligibility.applicable_hot_min_lbs:,.0f}lbs"
            )

            log_lines.append("[CLASS] Running deterministic classification.")
            result = classify_lead(
                polymer=merged.get("polymer"),
                material_description=self.material_description,
                estimated_lbs=merged.get("estimated_lbs", 0),
                source_description=merged.get("source_description", ""),
                source_type=merged.get("source_type"),
                is_plastic_hint=merged.get("is_plastic"),
                is_commercial_hint=merged.get("is_commercial_source"),
                weight_source=merged.get("lbs_source", "none"),
                reject_materials=config.get_reject_materials(),
                reject_sources=config.get_reject_sources(),
                hot_min_lbs=economic_eligibility.applicable_hot_min_lbs,
                cold_max_lbs=config.cold_max_lbs or 8_000,
                economic_eligible=economic_eligibility.eligible,
                economic_policy_reasons=list(economic_eligibility.reasons),
            )
            log_lines.append(f"[CLASS] decision={result.decision}")

            review_reasons = list(result.review_reasons) if result.decision == "hot" else []
            economic_assessment = None
            if evidence_bundle is not None:
                economic_provider_spec = (
                    config.get_inference_provider("economic_evaluation") if config.ai_enabled else None
                )
                economic_provider = InferenceProvider(**economic_provider_spec) if economic_provider_spec else None
                economic_assessment = evaluate_economic_opportunity(
                    provider=economic_provider,
                    canonical_payload=canonical_payload,
                    evidence_bundle=evidence_bundle,
                    classification={
                        KEY_DECISION: result.decision,
                        KEY_REASONS: result.reasons,
                        KEY_HOT_QUALIFIERS: result.hot_qualifiers_met,
                    },
                    eligibility=economic_eligibility.to_dict(),
                )
                evidence_bundle[KEY_ECONOMIC_ASSESSMENT] = economic_assessment
                if result.decision == "hot":
                    review_reasons.extend(evidence_bundle.get("clarification_requests", []))
                    review_reasons.extend(
                        f"Evidence conflict: {item.get('field', 'unknown')}"
                        for item in evidence_bundle.get("conflicts", [])
                    )
                    review_reasons.extend(economic_assessment.get(KEY_ASSESSMENT, {}).get("clarifications", []))
                    if economic_assessment.get(KEY_STATUS) != ASSESSMENT_STATUS_ASSESSED:
                        review_reasons.append(
                            "Economic assessment is unavailable; broker review is required before commercial work."
                        )
                log_lines.append(f"[ECONOMIC] status={economic_assessment.get(KEY_STATUS)}")

            values = {
                "decision": result.decision,
                "decision_reasons": {
                    KEY_REASONS: result.reasons,
                    "cold_gates": result.cold_gates_triggered,
                    KEY_HOT_QUALIFIERS: result.hot_qualifiers_met,
                    KEY_ECONOMIC_ELIGIBILITY: economic_eligibility.to_dict(),
                    KEY_REVIEW_REQUIRED: bool(review_reasons),
                    KEY_REVIEW_REASONS: review_reasons,
                },
                "ai_normalized": ai_data,
                "ai_vision_results": vision_results,
                "ai_analysis": merged,
                "estimated_lbs_per_load": int(merged.get("estimated_lbs") or 0),
                "estimated_loads_per_month": int(merged.get("loads_per_month") or 0),
                "frequency": merged.get("frequency", ""),
                "review_status": "clarification_required" if review_reasons else "pending",
                "review_required_reason": "\n".join(sorted(set(review_reasons))) or False,
            }
            if evidence_bundle is not None:
                values["evidence_bundle"] = evidence_bundle
            self.write(values)

            if result.decision == "hot":
                log_lines.append("[HOT] Creating intake and scheduling human review.")
                self._process_hot_lead_triage(merged, config)
                if evidence_bundle is not None:
                    copy_successful_attachments_to_intake(
                        lead=self, intake=self.intake_id, evidence_bundle=evidence_bundle
                    )
                elif self.image_urls:
                    # Legacy agent leads do not have packet attachment evidence.
                    # Preserve their established HOT-only URL attachment handoff.
                    log_lines.append(f"[IMG] Fetching {len(self.image_urls)} legacy image(s).")
                    self._fetch_and_attach_images(self.image_urls)
                crm_lead = getattr(self, "crm_lead_id", None)
                synchronize_images = getattr(crm_lead, "_propagate_available_commercial_images", None)
                if callable(synchronize_images):
                    synchronize_images()
            else:
                log_lines.append("[COLD] Archiving lead.")
                self.write({"state": "skipped"})
                if not is_packet_path and self.image_urls:
                    log_lines.append("[IMG] SKIPPED legacy image download for COLD lead.")

        except Exception as exc:
            _logger.exception("Triage pipeline error for lead %s", self.lead_id)
            log_lines.append(f"[ERROR] {exc}")
            self.write({"state": "error", "error_message": str(exc)})

        log_lines.append(f"[RUN] {run_id} finished")
        self.write({"triage_log": "\n".join(log_lines)})

    # ═══════════════════════════════════════════════════════════
    # Merge AI + Vision
    # ═══════════════════════════════════════════════════════════

    def _merge_ai_and_vision(
        self,
        ai_data: dict[str, Any],
        vision_results: list[dict[str, Any]],
        *,
        quantity_evidence: QuantityEvidence | None = None,
    ) -> dict[str, Any]:
        """Merge text AI normalization with vision analysis.

        Authority rules:
        - Text AI: polymer, weight, source (form data knows the business context)
        - Vision: form, color, contamination (eyes on the material)

        Legacy-path weight fallback cascade (FIX — resolves WeightPerLoad="unknown" bug):
          1. AI estimated_lbs_per_load (most reliable when AI ran)
          2. Vision estimated_lbs (any image gave a weight estimate)
          3. WhatIsTheQuantity × _LBS_PER_PALLET_ASSUMPTION (unit count fallback)
          4. 0 (classification will gate on cold_max_lbs)

        Canonical Packet path uses deterministic QuantityEvidence first, permits an
        explicit AI per-load mass only as fallback, and never turns a unit count
        into pounds.
        """
        merged: dict[str, Any] = {}

        polymer_raw = (ai_data.get("polymer") or "").lower().strip()
        merged["polymer"] = _POLYMER_NORMALIZE.get(polymer_raw, polymer_raw or None)
        merged["form"] = _FORM_NORMALIZE.get((ai_data.get("form") or "").lower().strip(), None)
        merged["color"] = (ai_data.get("color") or "").lower().strip() or None
        merged["source_type"] = _SOURCE_NORMALIZE.get((ai_data.get("source_type") or "").lower().strip(), None)
        merged["loads_per_month"] = _safe_int(ai_data.get("loads_per_month"), 0)
        # Missing AI output is unknown evidence, never a negative fact. The
        # classifier owns the distinct treatment of None versus explicit False.
        merged["is_plastic"] = ai_data.get("is_plastic")
        merged["is_commercial_source"] = ai_data.get("is_commercial_source")
        merged["material_summary"] = ai_data.get("material_summary", "")
        merged["contaminants_noted"] = ai_data.get("contaminants_noted")
        merged["confidence"] = ai_data.get("confidence", 0.5)
        merged["frequency"] = (ai_data.get("frequency") or "").lower().strip()

        raw = self.raw_payload or {}
        canonical = self.canonical_payload or {}
        merged["source_description"] = (
            canonical.get("source_description")
            if quantity_evidence is not None
            else raw.get("WhatIsTheSourceOfThisMaterial", "") or raw.get("Source", "") or ""
        ) or ""

        # Explicit form words in a seller submission are deterministic material
        # hints. They permit the reusable-item policy to recognize pallets,
        # totes, or crates; polymer identity alone never changes the threshold.
        if not merged["form"]:
            declared_material = " ".join(
                str(value or "")
                for value in (
                    canonical.get("material_description"),
                    canonical.get("material_composition_text"),
                    raw.get("DescribeYourMaterial"),
                    raw.get("WhatIsIt"),
                )
            ).lower()
            for term, form_code in (("pallet", "PALLETS"), ("tote", "TOTES"), ("crate", "CRATES")):
                if term in declared_material:
                    merged["form"] = form_code
                    break

        # ── Weight fallback cascade ────────────────────────────────────
        if quantity_evidence is not None:
            lbs = quantity_evidence.load_weight_lbs or 0
            lbs_source = quantity_evidence.weight_source
            if not lbs:
                ai_lbs = _safe_int(ai_data.get("estimated_lbs_per_load"), 0)
                if ai_lbs > 0:
                    lbs = ai_lbs
                    lbs_source = "ai_text"
            merged["loads_per_month"] = (
                quantity_evidence.loads_per_month
                if quantity_evidence.loads_per_month is not None
                else _safe_int(ai_data.get("loads_per_month"), 0)
            )
            merged["frequency"] = quantity_evidence.supply_mode
        else:
            lbs = _safe_int(ai_data.get("estimated_lbs_per_load"), 0)
            lbs_source = "ai_text"

            if not lbs and vision_results:
                for vr in vision_results:
                    v_lbs = _safe_int(vr.get("estimated_lbs"), 0)
                    if v_lbs > 0:
                        lbs = v_lbs
                        lbs_source = "vision"
                        break

            if not lbs:
                qty_count = _safe_int(raw.get("WhatIsTheQuantity"), 0)
                if qty_count > 0:
                    lbs = qty_count * _LBS_PER_PALLET_ASSUMPTION
                    lbs_source = f"pallet_count({qty_count}×{_LBS_PER_PALLET_ASSUMPTION})"

        merged["estimated_lbs"] = lbs
        merged["lbs_source"] = lbs_source

        # ── Vision overrides for form/color/contamination ──────────────
        if vision_results:
            valid_vision = [v for v in vision_results if not v.get("error")]
            best_vision = max(valid_vision, key=lambda v: v.get("confidence", 0), default={})
            if best_vision:
                v_form = _FORM_NORMALIZE.get((best_vision.get("observed_form") or "").lower().strip())
                if v_form and not merged["form"]:
                    merged["form"] = v_form
                v_color = (best_vision.get("observed_color") or "").lower().strip()
                if v_color and not merged["color"]:
                    merged["color"] = v_color
                if best_vision.get("contamination_visible"):
                    merged["contamination_visible"] = True
                    merged["contamination_notes"] = best_vision.get("contamination_notes")
                merged["vision_summary"] = best_vision.get("visual_summary", "")

        return merged

    # ═══════════════════════════════════════════════════════════
    # HOT Lead Processing
    # ═══════════════════════════════════════════════════════════

    def _process_hot_lead_triage(self, merged: dict[str, Any], config: Any):
        """Create intake from HOT lead and notify admin for review.

        Flow (2026-02-23+):
        - Creates intake WITHOUT partner (deferred to buyer-matching)
        - Stores company name as pending_company_name on intake
        - Schedules activity for admin to review
        """
        self.ensure_one()
        intake = self.intake_id or self._create_intake(merged, config)
        if not self.intake_id:
            self.write({"intake_id": intake.id, "state": "intake_created"})
            self._notify_admin_hot_intake(intake, config)
        self._ensure_crm_lead_for_hot_intake()
        _logger.info(
            "HOT lead %s → intake %s (CRM tracking ensured; broker review pending)",
            self.lead_id,
            intake.id,
        )

    def _ensure_crm_lead_for_hot_intake(self):
        """Ensure the optional CRM bridge creates one traceable lead for this HOT intake.

        The CRM bridge owns CRM fields and stage policy. This module deliberately
        calls only its retry-safe bridge method when that extension is installed.
        """
        self.ensure_one()
        create_crm_lead = getattr(self, "_create_crm_lead", None)
        existing_crm_lead = getattr(self, "crm_lead_id", None)
        if callable(create_crm_lead) and not existing_crm_lead:
            create_crm_lead()

    def _create_intake(self, merged: dict[str, Any], config: Any):
        """Create intake record WITHOUT partner from merged AI data.

        Unified replacement for _create_intake_triage + _create_intake_simple.
        Looks up polymer_id, form_id, source_type_id from master registries by
        code. Falls back to 'other' / 'post_consumer' records if code not found.

        FIX: removed inconsistent qty_per_load defaults (1 vs 40000).
        0-lbs fallback is 1 (meaningful minimum) so the field doesn't explode.
        """
        polymer_code = (merged.get("polymer") or "other").lower()
        form_code = (merged.get("form") or "other").lower()
        source_type_code = merged.get("source_type") or getattr(config, "default_source_type", None) or "post_consumer"
        qty_per_load = max(merged.get("estimated_lbs", 0), 1)
        loads_per_month = max(merged.get("loads_per_month", 0), 0)
        deal_type = _FREQ_TO_DEAL.get(merged.get("frequency", ""), "spot")

        def _lookup(Model, code, fallback_code):
            rec = Model.search([("code", "=ilike", code)], limit=1)
            if not rec and fallback_code and code != fallback_code:
                rec = Model.search([("code", "=ilike", fallback_code)], limit=1)
            return rec

        Polymer = self.env["plasticos.polymer"]
        Form = self.env["plasticos.material.form"]
        SourceType = self.env["plasticos.source.type"]

        polymer_rec = _lookup(Polymer, polymer_code, "other")
        form_rec = _lookup(Form, form_code, "other")
        source_type_rec = _lookup(SourceType, source_type_code, "post_consumer")

        web_lead_source = self.env["utm.source"].search([("name", "=", "Web Lead Form")], limit=1)

        intake_vals = {
            "pending_company_name": self.company_name or "Unknown",
            "source_lead_id": self.id,
            "polymer_id": polymer_rec.id if polymer_rec else False,
            "form_id": form_rec.id if form_rec else False,
            "source_type_id": source_type_rec.id if source_type_rec else False,
            "lead_source_id": web_lead_source.id if web_lead_source else False,
            "quantity_per_load_lbs": qty_per_load,
            "loads_per_month": loads_per_month,
            "deal_type": deal_type,
            "contamination_notes": (
                merged.get("contaminants_noted") or merged.get("contamination_notes") or self.contaminant_notes or False
            ),
        }

        return self.env["plasticos.intake"].create(intake_vals)

    def _notify_admin_hot_intake(self, intake, config):
        """Schedule review activity on the intake for the configured reviewer."""
        reviewer_id = self.env.user.id
        if hasattr(config, "intake_reviewer_id") and config.intake_reviewer_id:
            reviewer_id = config.intake_reviewer_id.id

        polymer_name = intake.polymer_id.name if intake.polymer_id else "Unknown"
        form_name = intake.form_id.name if intake.form_id else "Unknown"

        intake.activity_schedule(
            "mail.mail_activity_data_todo",
            user_id=reviewer_id,
            summary=f"Review HOT Web Lead: {self.company_name or 'Unknown'}",
            note=(
                f"<p>New HOT lead from web form requires review:</p>"
                f"<ul>"
                f"<li><b>Company:</b> {self.company_name or 'Unknown'}</li>"
                f"<li><b>Material:</b> {polymer_name} / {form_name}</li>"
                f"<li><b>Quantity:</b> {intake.quantity_per_load_lbs:,.0f} lbs/load</li>"
                f"<li><b>Lead ID:</b> {self.lead_id}</li>"
                f"</ul>"
                f"<p><b>Action:</b> Click 'Match to Buyers' to create partner and run "
                f"matching, or delete/archive if not a valid lead.</p>"
            ),
        )

    def action_approve_for_commercial_preparation(self):
        """Create an immutable broker-approved snapshot for later commercial work."""
        self.ensure_one()
        if self.decision != "hot" or not self.intake_id:
            raise UserError("Only a HOT lead with an intake can be approved for commercial preparation.")
        assessment = (self.evidence_bundle or {}).get(KEY_ECONOMIC_ASSESSMENT) or {}
        if assessment.get(KEY_STATUS) != ASSESSMENT_STATUS_ASSESSED:
            raise UserError(
                "A completed economic-opportunity assessment is required before broker approval. "
                "Configure the selected economic evaluation provider and re-run triage."
            )
        if self.review_status == "approved" and self.review_snapshot_ids:
            return self.action_view_review_snapshots()

        next_revision = max(self.review_snapshot_ids.mapped("revision"), default=0) + 1
        payload = build_snapshot_payload(lead=self, intake=self.intake_id, review_notes=self.review_notes)
        snapshot = self.env["plasticos.web.lead.review.snapshot"].create(
            {
                "name": f"{self.lead_id} / Broker Snapshot v{next_revision}",
                "web_lead_id": self.id,
                "intake_id": self.intake_id.id,
                "revision": next_revision,
                "approved_by_id": self.env.user.id,
                "snapshot_payload": payload,
                "content_hash": snapshot_content_hash(payload),
            }
        )
        self.write({"review_status": "approved"})
        self.message_post(
            body=(
                f"Broker-approved snapshot <b>{snapshot.name}</b> created by {self.env.user.display_name}. "
                "Downstream matching or commercial preparation must use this snapshot."
            )
        )
        return {
            "type": "ir.actions.act_window",
            "name": snapshot.name,
            "res_model": "plasticos.web.lead.review.snapshot",
            "res_id": snapshot.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_request_clarification(self):
        """Record that evidence requires seller/broker clarification before approval."""
        self.ensure_one()
        self.write({"review_status": "clarification_required"})
        self.message_post(body="Broker marked this lead as requiring clarification before commercial preparation.")
        return True

    def action_reject_after_review(self):
        """Record a broker-reviewed rejection without deleting source evidence."""
        self.ensure_one()
        self.write({"review_status": "rejected"})
        self.message_post(body="Broker rejected this lead after review; intake and evidence remain retained for audit.")
        return True

    def action_view_review_snapshots(self):
        """Open immutable broker-approved snapshots for this lead."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": f"Broker Snapshots — {self.lead_id}",
            "res_model": "plasticos.web.lead.review.snapshot",
            "view_mode": "list,form",
            "domain": [("web_lead_id", "=", self.id)],
            "context": {"default_web_lead_id": self.id, "default_intake_id": self.intake_id.id},
        }

    # ═══════════════════════════════════════════════════════════
    # Image Handling
    # ═══════════════════════════════════════════════════════════

    def _extract_image_urls(self, raw_payload: dict[str, Any]) -> list[str]:
        """Extract image URLs from a Cognito form payload.

        Strategy:
          1. Check known Cognito upload field names explicitly (fast, reliable)
          2. Fall back to general dict crawl for unknown field names

        Cognito tokenized URLs have no file extension — the cognitoforms.com
        domain check handles these.
        """
        urls: list[str] = []
        seen: set[str] = set()

        def _add(url: str) -> None:
            if url and url not in seen and url.startswith("http"):
                seen.add(url)
                urls.append(url)

        # Pass 1: known Cognito upload field names
        _COGNITO_UPLOAD_FIELDS = [
            "UploadPhotosOfYourScrapUpTo10",
            "UploadPhotos",
            "Photos",
            "Attachments",
            "Files",
        ]
        for field_name in _COGNITO_UPLOAD_FIELDS:
            items = raw_payload.get(field_name)
            if isinstance(items, list):
                for item in items:
                    if isinstance(item, dict):
                        url = item.get("File") or item.get("url") or item.get("Url") or ""
                        if url and ("cognitoforms.com" in url or self._looks_like_image_url(url)):
                            _add(url)
                    elif isinstance(item, str):
                        _add(item)

        # Pass 2: general crawl for any remaining upload-like fields
        for key, val in raw_payload.items():
            if key in _COGNITO_UPLOAD_FIELDS:
                continue  # already handled
            if isinstance(val, str) and self._looks_like_image_url(val):
                _add(val)
            elif isinstance(val, list):
                for item in val:
                    if isinstance(item, str) and self._looks_like_image_url(item):
                        _add(item)
                    elif isinstance(item, dict):
                        url = item.get("File") or item.get("url") or item.get("Url") or ""
                        if url and (self._looks_like_image_url(url) or "cognitoforms.com" in url):
                            _add(url)

        return urls

    @staticmethod
    def _looks_like_image_url(url: str) -> bool:
        """Heuristic: does this URL look like an image?"""
        lower = url.lower()
        return lower.startswith("http") and any(
            ext in lower for ext in (".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".heic")
        )

    def _fetch_and_attach_images(self, urls: list[str]):
        """Download images from URLs and create ir.attachment records.

        FIX: images are encoded once and reused for both web.lead and intake
        attachments, halving memory usage for large image sets.

        NOTE: this method is synchronous and blocks the Odoo worker thread.
        For future improvement: enqueue via queue_job or ir.actions.server.
        Currently only called for HOT leads to limit blast radius.
        """
        self.ensure_one()
        Attachment = self.env["ir.attachment"]

        for i, url in enumerate(urls[:10]):
            try:
                resp = http_requests.get(url, timeout=30, stream=True)
                resp.raise_for_status()
                content = resp.content
                if not content:
                    continue

                content_type = resp.headers.get("Content-Type", "image/jpeg")
                ext_map = {"png": ".png", "webp": ".webp", "gif": ".gif"}
                ext = next((v for k, v in ext_map.items() if k in content_type), ".jpg")
                fname = f"web_lead_{self.lead_id}_img_{i + 1}{ext}"
                datas = base64.b64encode(content).decode("ascii")  # encode once

                Attachment.create(
                    {
                        "name": fname,
                        "type": "binary",
                        "datas": datas,
                        "res_model": "plasticos.web.lead",
                        "res_id": self.id,
                        "mimetype": content_type,
                    }
                )

                if self.intake_id:
                    Attachment.create(
                        {
                            "name": fname,
                            "type": "binary",
                            "datas": datas,  # reuse — no second encode
                            "res_model": "plasticos.intake",
                            "res_id": self.intake_id.id,
                            "mimetype": content_type,
                        }
                    )

                _logger.info("Attached %s to web lead %s.", fname, self.lead_id)

            except Exception as exc:
                _logger.warning(
                    "Failed to fetch an image for lead %s: %s",
                    self.lead_id,
                    exc,
                )

    # ═══════════════════════════════════════════════════════════
    # Manual Actions
    # ═══════════════════════════════════════════════════════════

    def action_retry_triage(self):
        """Re-run the full AI triage pipeline."""
        for rec in self:
            if rec.state not in ("error", "skipped", "received"):
                raise UserError("Only errored, skipped, or received leads can be re-triaged.")
            rec._run_triage_pipeline()

    def action_retry_processing(self):
        """Retry processing a lead that errored.

        FIX: previously a COLD errored lead was a silent no-op here.
        Now always re-runs full triage regardless of decision.
        """
        for rec in self:
            if rec.state != "error":
                raise UserError("Only errored leads can be retried.")
            rec._run_triage_pipeline()

    def action_force_create_intake(self):
        """Force-create an intake from a COLD lead (manual override)."""
        for rec in self:
            if rec.intake_id:
                raise UserError("Intake already exists for this lead.")
            config = rec.env["plasticos.web.lead.config"].sudo().get_config()
            merged = rec.ai_analysis or rec.ai_normalized or {}
            rec._process_hot_lead_triage(merged, config)

    def action_force_hot(self):
        """Manually override a COLD lead to HOT and create intake."""
        for rec in self:
            if rec.intake_id:
                raise UserError("Intake already exists for this lead.")
            config = rec.env["plasticos.web.lead.config"].sudo().get_config()
            merged = rec.ai_analysis or rec.ai_normalized or {}
            rec.write(
                {
                    "decision": "hot",
                    "decision_reasons": {"reasons": ["Manual override by user"]},
                }
            )
            rec._process_hot_lead_triage(merged, config)

    # ═══════════════════════════════════════════════════════════
    # UX Smart Button Actions
    # ═══════════════════════════════════════════════════════════

    def action_view_intake(self):
        """Open the linked intake form."""
        self.ensure_one()
        if not self.intake_id:
            return False
        return {
            "type": "ir.actions.act_window",
            "res_model": "plasticos.intake",
            "res_id": self.intake_id.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_view_partner(self):
        """Open the linked partner form."""
        self.ensure_one()
        if not self.partner_id:
            return False
        return {
            "type": "ir.actions.act_window",
            "res_model": "res.partner",
            "res_id": self.partner_id.id,
            "view_mode": "form",
            "target": "current",
        }
