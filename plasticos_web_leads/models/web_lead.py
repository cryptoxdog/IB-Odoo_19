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

from . import ai_normalizer, image_analyzer
from .classification_engine import classify_lead

_logger = logging.getLogger(__name__)

# ── Pallet weight assumption when no lbs given ───────────────────────────────
_LBS_PER_PALLET_ASSUMPTION = 1_500  # conservative: typical plastic pallet

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
        _STATE_ONLY_FIELDS = frozenset({"state", "error_message", "triage_log"})
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
        """Ingest a raw Cognito form submission and run full triage pipeline.

        Steps:
          1. Extract Cognito entry ID and deduplicate
          2. Generate sequence-based lead_id
          3. Parse all form fields (name, email, phone, material, quantity)
          4. Create web.lead record (decision=cold, state=received)
          5. _run_triage_pipeline() — AI + vision + classify + intake
        """
        _entry = raw_payload.get("Entry") or {}
        _raw_id = (
            raw_payload.get("Id")
            or str(_entry.get("Number") or "")
            or raw_payload.get("EntryId")
            or raw_payload.get("entry_id")
            or ""
        )

        # Deduplication — CG-{_raw_id} is the canonical ID for Cognito submissions.
        # Assign it immediately so the stored lead_id matches the dedup search key,
        # ensuring idempotency works on repeat submissions.
        if _raw_id:
            lead_id = f"CG-{_raw_id}"
            existing = self.search([("lead_id", "=", lead_id)], limit=1)
            if existing:
                _logger.info(
                    "Duplicate Cognito submission (source id=%s) — returning existing %s.",
                    _raw_id,
                    existing.lead_id,
                )
                return existing
        else:
            lead_id = self.env["ir.sequence"].next_by_code("plasticos.web.lead") or f"WL-{uuid.uuid4().hex[:5].upper()}"

        company = (raw_payload.get("YourBusinessCompanyName", "") or raw_payload.get("CompanyName", "") or "").strip()

        contact = _extract_cognito_name(raw_payload)
        email = (raw_payload.get("Email", "") or raw_payload.get("EmailAddress", "") or "").strip()
        phone = (raw_payload.get("Phone", "") or raw_payload.get("PhoneNumber", "") or "").strip()
        material_desc = (
            raw_payload.get("WhatIsIt", "")
            or raw_payload.get("DescribeYourMaterial", "")
            or raw_payload.get("WhatTypeOfPlastic", "")
            or ""
        ).strip()

        # FIX: quantity_text — prefer numeric WeightPerLoad; fall back to
        # WhatIsTheQuantity (unit count). WeightPerLoad="unknown" was silently
        # winning and causing 0-lbs COLD misclassification.
        _wpl = (raw_payload.get("WeightPerLoad") or "").strip()
        _qty = (raw_payload.get("WhatIsTheQuantity") or "").strip()
        quantity_text = (_wpl if _safe_int(_wpl) > 0 else _qty) or _wpl or _qty

        contaminants = (raw_payload.get("AreThereAnyContaminants", "") or "").strip()

        # Extract image URLs from known Cognito upload field names first,
        # then fall back to general extraction for flexibility.
        image_urls = self._extract_image_urls(raw_payload)

        web_lead_source = self.env["utm.source"].search([("name", "=", "Web Lead Form")], limit=1)

        vals = {
            "lead_id": str(lead_id),
            "source": "web_lead",
            "lead_source_id": web_lead_source.id if web_lead_source else False,
            "decision": "cold",
            "raw_payload": raw_payload,
            "company_name": company or "Unknown",
            "contact_name": contact,
            "contact_email": email,
            "contact_phone": phone,
            "material_description": material_desc,
            "quantity_text": quantity_text,
            "has_contaminants": bool(contaminants),
            "contaminant_notes": contaminants or False,
            "image_urls": image_urls,
            "state": "received",
        }
        lead = self.create(vals)
        _logger.info("Web lead %s created from Cognito form.", lead_id)

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
        if lead_id:
            existing = self.search([("lead_id", "=", lead_id)], limit=1)
            if existing:
                _logger.info("Web lead %s already exists, returning existing.", lead_id)
                return existing
        else:
            lead_id = self.env["ir.sequence"].next_by_code("plasticos.web.lead") or f"WL-{uuid.uuid4().hex[:5].upper()}"

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
        log_lines: list[str] = []

        try:
            # ── Step 1: AI Normalization ───────────────────────────────
            ai_data: dict[str, Any] = {}
            providers = config.get_llm_providers_ordered() if config.ai_enabled else []
            if providers:
                log_lines.append("[AI] Running normalization...")
                ai_data = ai_normalizer.normalize_with_fallback(
                    raw_payload=self.raw_payload or {},
                    providers=providers,
                )
                provider_used = ai_data.pop("_provider_used", "unknown")
                self.write({"ai_normalized": ai_data})
                if ai_data.get("error"):
                    log_lines.append(f"  WARNING: AI error — {ai_data['error']}")
                else:
                    log_lines.append(
                        f"  OK ({provider_used}): polymer={ai_data.get('polymer')}, "
                        f"form={ai_data.get('form')}, "
                        f"lbs={ai_data.get('estimated_lbs_per_load')}"
                    )
            else:
                log_lines.append("[AI] SKIPPED (disabled or no API keys).")

            # ── Step 2: Image Analysis ─────────────────────────────────
            vision_results: list[dict[str, Any]] = []
            urls = self.image_urls or []
            vision_prov = config.get_vision_provider() if config.vision_enabled else None
            if vision_prov and urls:
                log_lines.append(f"[VISION] Analyzing {len(urls)} image(s) via {vision_prov['provider']}...")
                vision_results = image_analyzer.analyze_multiple_images(
                    image_urls=urls,
                    api_key=vision_prov["api_key"],
                    model=vision_prov["model"],
                    base_url=vision_prov.get("base_url"),
                )
                self.write({"ai_vision_results": vision_results})
                for i, vr in enumerate(vision_results):
                    if vr.get("error"):
                        log_lines.append(f"  Image {i + 1}: ERROR — {vr['error']}")
                    else:
                        log_lines.append(
                            f"  Image {i + 1}: form={vr.get('observed_form')}, "
                            f"color={vr.get('observed_color')}, "
                            f"confidence={vr.get('confidence', 0):.2f}"
                        )
            else:
                log_lines.append("[VISION] SKIPPED.")

            # ── Step 3: Merge AI + Vision (weight fallback cascade here) ──
            merged = self._merge_ai_and_vision(ai_data, vision_results)
            log_lines.append(
                f"[MERGE] polymer={merged.get('polymer')}, "
                f"form={merged.get('form')}, "
                f"lbs={merged.get('estimated_lbs')} "
                f"(source: {merged.get('lbs_source', 'unknown')})"
            )

            # ── Step 4: Deterministic Classification ───────────────────
            log_lines.append("[CLASS] Running classification...")
            result = classify_lead(
                polymer=merged.get("polymer"),
                material_description=self.material_description,
                estimated_lbs=merged.get("estimated_lbs", 0),
                source_description=merged.get("source_description", ""),
                source_type=merged.get("source_type"),
                reject_materials=config.get_reject_materials(),
                reject_sources=config.get_reject_sources(),
                hot_min_lbs=config.hot_min_lbs or 10_000,
                cold_max_lbs=config.cold_max_lbs or 8_000,
            )
            log_lines.append(f"  → {result.decision.upper()}")
            for reason in result.reasons:
                log_lines.append(f"  Reason: {reason}")

            # ── Step 5: Persist classification result ──────────────────
            self.write(
                {
                    "decision": result.decision,
                    "decision_reasons": {
                        "reasons": result.reasons,
                        "cold_gates": result.cold_gates_triggered,
                        "hot_qualifiers": result.hot_qualifiers_met,
                    },
                    "ai_analysis": merged,
                    "estimated_lbs_per_load": merged.get("estimated_lbs", 0),
                    "estimated_loads_per_month": merged.get("loads_per_month", 0),
                    "frequency": merged.get("frequency", ""),
                }
            )

            # ── Step 6: HOT → intake / COLD → archive ──────────────────
            if result.decision == "hot":
                log_lines.append("[HOT] Creating intake + scheduling review activity...")
                self._process_hot_lead_triage(merged, config)
                log_lines.append("  Done: intake created.")
            else:
                log_lines.append("[COLD] Archiving lead.")
                self.write({"state": "skipped"})

            # ── Step 7: Attach images (HOT only — avoid blocking on COLD) ──
            if urls and result.decision == "hot":
                log_lines.append(f"[IMG] Fetching {len(urls)} image(s)...")
                self._fetch_and_attach_images(urls)
                log_lines.append("  Done: images attached.")
            elif urls:
                log_lines.append("[IMG] SKIPPED (COLD lead — images not downloaded).")

        except Exception as exc:
            _logger.exception("Triage pipeline error for lead %s", self.lead_id)
            log_lines.append(f"[ERROR] {exc}")
            self.write({"state": "error", "error_message": str(exc)})

        self.write({"triage_log": "\n".join(log_lines)})

    # ═══════════════════════════════════════════════════════════
    # Merge AI + Vision
    # ═══════════════════════════════════════════════════════════

    def _merge_ai_and_vision(
        self,
        ai_data: dict[str, Any],
        vision_results: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Merge text AI normalization with vision analysis.

        Authority rules:
        - Text AI: polymer, weight, source (form data knows the business context)
        - Vision: form, color, contamination (eyes on the material)

        Weight fallback cascade (FIX — resolves WeightPerLoad="unknown" bug):
          1. AI estimated_lbs_per_load (most reliable when AI ran)
          2. Vision estimated_lbs (any image gave a weight estimate)
          3. WhatIsTheQuantity × _LBS_PER_PALLET_ASSUMPTION (unit count fallback)
          4. 0 (classification will gate on cold_max_lbs)

        lbs_source is logged so triage_log shows which path fired.
        """
        merged: dict[str, Any] = {}

        polymer_raw = (ai_data.get("polymer") or "").lower().strip()
        merged["polymer"] = _POLYMER_NORMALIZE.get(polymer_raw, polymer_raw or None)
        merged["form"] = _FORM_NORMALIZE.get((ai_data.get("form") or "").lower().strip(), None)
        merged["color"] = (ai_data.get("color") or "").lower().strip() or None
        merged["source_type"] = _SOURCE_NORMALIZE.get((ai_data.get("source_type") or "").lower().strip(), None)
        merged["loads_per_month"] = _safe_int(ai_data.get("loads_per_month"), 0)
        merged["is_plastic"] = ai_data.get("is_plastic", True)
        merged["is_commercial_source"] = ai_data.get("is_commercial_source", False)
        merged["material_summary"] = ai_data.get("material_summary", "")
        merged["contaminants_noted"] = ai_data.get("contaminants_noted")
        merged["confidence"] = ai_data.get("confidence", 0.5)
        merged["frequency"] = (ai_data.get("frequency") or "").lower().strip()

        raw = self.raw_payload or {}
        merged["source_description"] = raw.get("WhatIsTheSourceOfThisMaterial", "") or raw.get("Source", "") or ""

        # ── Weight fallback cascade ────────────────────────────────────
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
        intake = self._create_intake(merged, config)
        # FIX: removed duplicate self.intake_id = intake.id inside _create_intake;
        # single authoritative write here.
        self.write({"intake_id": intake.id, "state": "intake_created"})
        self._notify_admin_hot_intake(intake, config)
        _logger.info(
            "HOT lead %s → intake %s (pending review, no partner yet)",
            self.lead_id,
            intake.id,
        )

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
                    "Failed to fetch image %s for lead %s: %s",
                    url[:80],
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
            merged = rec.ai_normalized or rec.ai_analysis or {}
            rec._process_hot_lead_triage(merged, config)

    def action_force_hot(self):
        """Manually override a COLD lead to HOT and create intake."""
        for rec in self:
            if rec.intake_id:
                raise UserError("Intake already exists for this lead.")
            config = rec.env["plasticos.web.lead.config"].sudo().get_config()
            merged = rec.ai_normalized or rec.ai_analysis or {}
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
