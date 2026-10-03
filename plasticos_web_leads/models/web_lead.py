# ═══════════════════════════════════════════════════════════
# Model : plasticos.web.lead
# Purpose: Web lead ingestion with AI-powered triage pipeline:
#          1. Receive a provider packet through the inbound adapter port
#          2. AI normalization (1 LLM call)
#          3. Image analysis (1 Vision call per image)
#          4. Deterministic HOT/COLD classification
#          5. HOT → intake (partner deferred to buyer-match)
# ═══════════════════════════════════════════════════════════
from __future__ import annotations

import logging
import uuid
from collections.abc import Mapping
from typing import Any

import psycopg2
import psycopg2.errorcodes

from odoo import api, fields, models
from odoo.exceptions import ConcurrencyError, UserError

from ..adapters.base import (
    EVENT_SUBMITTED,
    PACKET_SCHEMA_VERSION,
    InboundEvent,
    WebLeadPacket,
    acquisition_rows,
    packet_to_dict,
)
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


def _is_lead_identity_collision(exc: Exception) -> bool:
    """True for a PostgreSQL unique violation on the web-lead identity constraint."""
    if not isinstance(exc, psycopg2.IntegrityError):
        return False
    if getattr(exc, "pgcode", None) != psycopg2.errorcodes.UNIQUE_VIOLATION:
        return False
    constraint = str(getattr(getattr(exc, "diag", None), "constraint_name", "") or "")
    return "lead_id" in constraint


class PlasticosWebLead(models.Model):
    """Stores every inbound web lead admitted through the provider port.

    HOT leads automatically generate a plasticos.intake record.
    COLD leads are stored for reference but do not create downstream records.

    Pipeline (admit_inbound → create_from_packet):
      1. Project the provider payload into a provider-neutral packet
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
    mack_review_state = fields.Selection(
        [
            ("not_queued", "Not Queued"),
            ("queued", "Queued for Internal Review"),
            ("blocked", "Blocked: Reviewer Not Configured"),
        ],
        string="Mack Review Handoff",
        default="not_queued",
        readonly=True,
        tracking=True,
        index=True,
        help=(
            "Internal human-review handoff state for a HOT intake. 'Blocked' is a "
            "durable, visible state meaning no eligible reviewer is configured; the "
            "handoff is never silently assigned to the ingestion worker. This field "
            "does not call Mack, matching, Gate, or any commercial operation."
        ),
    )
    mack_review_reason = fields.Text(
        string="Mack Review Handoff Note",
        readonly=True,
        help="Administrative reason for a queued or blocked internal review handoff.",
    )

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
                "mack_review_state",
                "mack_review_reason",
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
    # Inbound port admission
    # ═══════════════════════════════════════════════════════════

    @api.model
    def admit_inbound(self, provider_key: str, body: Mapping[str, Any]) -> tuple[InboundEvent, PlasticosWebLead]:
        """Classify one provider payload and admit it only when it is a submission.

        Non-submission events return an empty recordset and must not create or
        mutate a lead. Adapter validation failures surface as ``UserError``.
        """
        try:
            adapter = get_adapter(provider_key)
            event = adapter.classify_event(body)
        except ValueError as exc:
            raise UserError(str(exc)) from exc
        if event.kind != EVENT_SUBMITTED:
            return event, self.browse()
        try:
            packet = adapter.to_packet(body)
        except ValueError as exc:
            raise UserError(str(exc)) from exc
        return event, self.create_from_packet(packet)

    @api.model
    def record_rejected_inbound(self, provider_key: str, body: Mapping[str, Any], reason: str) -> PlasticosWebLead:
        """Store a permanently rejected submission without running triage."""
        lead = self.create(
            {
                "lead_id": self._next_lead_identity(),
                "source": "web_lead",
                "provider_key": provider_key,
                "raw_payload": dict(body),
                "decision": "cold",
                "state": "error",
                "error_message": reason,
            }
        )
        _logger.info("Web lead %s stored as a rejected inbound from provider %s.", lead.lead_id, provider_key)
        return lead

    @api.model
    def create_from_cognito(self, raw_payload: dict[str, Any]) -> PlasticosWebLead:
        """Compatibility shim. Cognito submissions enter through the inbound port."""
        return self.admit_inbound("cognito", raw_payload)[1]

    # ═══════════════════════════════════════════════════════════
    # Identity and idempotent admission
    # ═══════════════════════════════════════════════════════════

    @api.model
    def _next_lead_identity(self) -> str:
        """Server-generated identity for submissions that carry none."""
        return self.env["ir.sequence"].next_by_code("plasticos.web.lead") or f"WL-{uuid.uuid4().hex[:5].upper()}"

    @api.model
    def _find_existing_lead(self, lead_id: str) -> PlasticosWebLead:
        """Locate a prior admission by identity (a separate method so tests can race it)."""
        return self.search([("lead_id", "=", lead_id)], limit=1)

    @api.model
    def _assert_equivalent_packet_replay(self, existing: PlasticosWebLead, packet: WebLeadPacket) -> None:
        """A replay must describe the same provider submission as the prior receipt."""
        if existing.provider_key and existing.provider_key != packet.provider:
            raise UserError(
                f"Web lead {existing.lead_id} was admitted from provider {existing.provider_key!r}; "
                f"a {packet.provider!r} submission cannot reuse that identity."
            )
        if (
            existing.provider_external_id
            and packet.provider_external_id
            and existing.provider_external_id != packet.provider_external_id
        ):
            raise UserError(
                f"Web lead {existing.lead_id} is bound to provider submission "
                f"{existing.provider_external_id!r}, not {packet.provider_external_id!r}."
            )

    @api.model
    def _create_or_replay(self, vals: dict[str, Any]) -> tuple[PlasticosWebLead, bool]:
        """Create inside a savepoint; a unique collision on ``lead_id`` is a concurrent replay.

        Two retries of the same provider submission can both miss the pre-check
        search. The loser then hits the ``unique(lead_id)`` constraint at flush.
        That is not a failure of admission: the savepoint is rolled back and the
        committed winner is re-queried so the caller returns that prior receipt.

        Odoo cursors run at REPEATABLE READ, so when this transaction's snapshot
        predates the winner's commit the winner is invisible here and no query in
        this transaction can ever return it. The only correct recovery is a fresh
        transaction: ``ConcurrencyError`` is the contract the HTTP and RPC
        dispatchers honour (``odoo.service.model.retrying`` rolls back and replays
        the request), and the replayed admission finds the winner in its
        pre-check and returns the prior receipt.
        """
        try:
            with self.env.cr.savepoint():
                return self.create(vals), True
        except psycopg2.IntegrityError as exc:
            if not _is_lead_identity_collision(exc):
                raise
        existing = self._find_existing_lead(str(vals["lead_id"]))
        if not existing:
            raise ConcurrencyError(
                f"Web lead {vals['lead_id']!r} was admitted by a concurrent transaction that is not visible "
                "in this snapshot; replay the admission in a fresh transaction."
            )
        _logger.info("Concurrent replay for web lead %s; returning the prior receipt.", existing.lead_id)
        return existing, False

    @api.model
    def create_from_packet(self, packet: WebLeadPacket) -> PlasticosWebLead:
        """Create a durable web lead from a validated provider-neutral packet.

        Admission is idempotent on the packet's idempotency key, including under
        concurrent retries: a replay returns the prior lead without re-running
        triage. Signed attachment URLs travel only on the in-memory ``packet``;
        the stored canonical payload never retains them.
        """
        if packet.schema_version != PACKET_SCHEMA_VERSION:
            raise UserError(f"Unsupported web-lead packet version: {packet.schema_version!r}")

        lead_id = packet.idempotency_key
        if lead_id:
            existing = self._find_existing_lead(lead_id)
            if existing:
                self._assert_equivalent_packet_replay(existing, packet)
                _logger.info(
                    "Duplicate packet submission for provider=%s external_id=%s.",
                    packet.provider,
                    packet.provider_external_id,
                )
                return existing
        else:
            lead_id = self._next_lead_identity()

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
        lead, created = self._create_or_replay(vals)
        if not created:
            self._assert_equivalent_packet_replay(lead, packet)
            return lead
        _logger.info("Web lead %s created from provider packet %s.", lead.lead_id, packet.provider)
        lead._run_triage_pipeline(packet=packet)
        return lead

    # ═══════════════════════════════════════════════════════════
    # AI Triage Pipeline
    # ═══════════════════════════════════════════════════════════

    def _attachment_allowed_hosts(self, config: Any) -> tuple[str, ...]:
        """Provider destination policy for this lead: adapter default plus operator additions."""
        provider_key = self.provider_key or (config.inbound_default_provider_key if config else "") or ""
        try:
            provider_hosts = tuple(getattr(get_adapter(provider_key), "attachment_allowed_hosts", ()))
        except ValueError:
            provider_hosts = ()
        return config.get_attachment_allowed_hosts(provider_hosts)

    def _run_triage_pipeline(self, packet: WebLeadPacket | None = None):
        """Execute the full AI triage pipeline on this web lead.

        Steps:
          [AI]     1. AI normalization (if enabled)
          [VISION] 2. Image analysis (if enabled + images present)
          [MERGE]  3. Merge AI + Vision → weight fallback cascade
          [CLASS]  4. Deterministic HOT/COLD classification
          [WRITE]  5. Persist classification result
          [HOT]    6. Create intake + notify admin
          [IMG]    7. Attach images (HOT only — skip blocking download for COLD)

        ``packet`` is the in-memory admission packet and the only carrier of
        signed attachment URLs. A later re-triage has no packet: it reuses prior
        successful acquisitions and records the rest as unavailable.
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
                packet_attachments = (
                    acquisition_rows(packet) if packet is not None else list(triage_input.get("attachments") or [])
                )
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
                    allowed_hosts=self._attachment_allowed_hosts(config),
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

    @staticmethod
    def _eligible_reviewer(config):
        """The configured reviewer, only while an active internal user; otherwise empty."""
        reviewer = getattr(config, "hot_intake_reviewer_id", None)
        if not reviewer or not reviewer.exists() or not reviewer.active or reviewer.share:
            return None
        return reviewer

    def _notify_admin_hot_intake(self, intake, config):
        """Create one internal Odoo review activity or record a durable blocked handoff.

        This is an Odoo-native human handoff only. The reviewer is exclusively
        the explicitly configured internal user: the webhook worker / current
        user is never an implicit fallback (it runs under sudo after token
        auth, so it is a technical actor, not a broker). It never calls Mack,
        matching, email, or any commercial operation.
        """
        self.ensure_one()
        reviewer = self._eligible_reviewer(config)
        if reviewer is None:
            self.write(
                {
                    "mack_review_state": "blocked",
                    "mack_review_reason": "HOT Intake Reviewer is not configured.",
                }
            )
            self.message_post(
                body=(
                    "HOT lead intake was created, but the internal review handoff is blocked: "
                    "configure a HOT Intake Reviewer in Web Lead Settings, then use Route Review."
                )
            )
            _logger.warning("HOT lead %s has no configured internal reviewer.", self.lead_id)
            return

        summary = f"Review HOT Web Lead: {self.lead_id}"
        existing = self.env["mail.activity"].search_count(
            [
                ("res_model", "=", "plasticos.intake"),
                ("res_id", "=", intake.id),
                ("user_id", "=", reviewer.id),
                ("summary", "=", summary),
            ]
        )
        if existing:
            self.write(
                {
                    "mack_review_state": "queued",
                    "mack_review_reason": f"Internal review is assigned to {reviewer.name}.",
                }
            )
            return

        polymer_name = intake.polymer_id.name if intake.polymer_id else "Unknown"
        form_name = intake.form_id.name if intake.form_id else "Unknown"

        intake.activity_schedule(
            "mail.mail_activity_data_todo",
            user_id=reviewer.id,
            summary=summary,
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
        self.write(
            {
                "mack_review_state": "queued",
                "mack_review_reason": f"Internal review is assigned to {reviewer.name}.",
            }
        )

    def action_route_hot_review(self):
        """Re-attempt a blocked human handoff after a reviewer has been configured."""
        config = self.env["plasticos.web.lead.config"].sudo().get_config()
        for rec in self:
            if not rec.intake_id:
                raise UserError("Only a lead with an intake has a review handoff to route.")
            rec._notify_admin_hot_intake(rec.intake_id, config)
        return True

    def action_approve_for_commercial_preparation(self):
        """Record a broker approval as an immutable server-derived snapshot.

        The snapshot model's ``_record_broker_approval`` is the only path that
        can mint a snapshot: it derives approver, time, revision, lead/intake
        binding, payload and hash itself, so no caller can supply provenance.
        """
        self.ensure_one()
        if self.review_status == "approved" and self.review_snapshot_ids:
            return self.action_view_review_snapshots()

        snapshot = self.env["plasticos.web.lead.review.snapshot"]._record_broker_approval(self)
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
