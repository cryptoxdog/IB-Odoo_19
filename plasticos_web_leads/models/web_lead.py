# ═══════════════════════════════════════════════════════════
# Model : plasticos.web.lead
# Purpose: Web lead ingestion with AI-powered triage pipeline:
#          1. Receive raw Cognito payload OR pre-processed agent payload
#          2. AI normalization (1 LLM call)
#          3. Image analysis (1 Vision call per image)
#          4. Deterministic HOT/COLD classification
#          5. HOT → partner + intake + attachments
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

PLASTICOS_WEB_LEAD_CONFIG = "plasticos.web.lead.config"
OP_ILIKE = "=ilike"
WEB_LEAD_FORM = "Web Lead Form"
UTM_SOURCE = "utm.source"
PLASTICOS_INTAKE = "plasticos.intake"
RES_PARTNER = "res.partner"
_logger = logging.getLogger(__name__)

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


def _safe_int(val: Any, default: int = 0) -> int:
    """Coerce to int, returning default on failure."""
    if val is None:
        return default
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return default


class PlasticosWebLead(models.Model):
    """Stores every inbound web lead from Cognito forms or external agents.

    HOT leads automatically generate a plasticos.intake record and
    (optionally) a res.partner. COLD leads are stored for reference
    but do not create downstream records.
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
    source = fields.Char(
        default="cognito_form",
        help="Origin system identifier.",
    )
    lead_source_id = fields.Many2one(
        UTM_SOURCE,
        string="Lead Source",
        index=True,
        tracking=True,
        help="How this lead was originally acquired (SICCODE, referral, web form, etc.).",
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

    company_name = fields.Char()
    contact_name = fields.Char()
    contact_email = fields.Char()
    contact_phone = fields.Char()
    material_description = fields.Text()
    quantity_text = fields.Char(
        help="Raw quantity text from the form.",
    )
    estimated_lbs_per_load = fields.Integer()
    estimated_loads_per_month = fields.Integer()
    frequency = fields.Char()
    has_contaminants = fields.Boolean()
    contaminant_notes = fields.Text()

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
    error_message = fields.Text(
        readonly=True,
    )

    # ═══════════════════════════════════════════════════════════
    # Links
    # ═══════════════════════════════════════════════════════════

    partner_id = fields.Many2one(
        RES_PARTNER,
        string="Created/Linked Partner",
        index=True,
        ondelete="set null",
    )
    intake_id = fields.Many2one(
        PLASTICOS_INTAKE,
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
        """Guard against modifying processed leads (except state changes)."""
        if "state" not in vals:
            for rec in self:
                if rec.state == "intake_created":
                    raise UserError(
                        f"Cannot modify lead '{rec.lead_id}' after intake was created. Edit the intake record directly."
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
        """Ingest a raw Cognito form submission directly.

        The entire triage pipeline runs inside Odoo:
          1. Parse raw Cognito fields
          2. Generate unique lead_id
          3. Create web.lead record (state=received)
          4. Run AI normalization
          5. Run image analysis
          6. Deterministic classification
          7. HOT → partner + intake + attachments
        """
        lead_id = raw_payload.get("EntryId") or raw_payload.get("entry_id") or f"CG-{uuid.uuid4().hex[:12]}"

        existing = self.search([("lead_id", "=", str(lead_id))], limit=1)
        if existing:
            _logger.info("Duplicate Cognito submission %s — returning existing.", lead_id)
            return existing

        company = (raw_payload.get("YourBusinessCompanyName", "") or raw_payload.get("CompanyName", "") or "").strip()
        contact = (raw_payload.get("YourName", "") or raw_payload.get("Name", "") or "").strip()
        email = (raw_payload.get("Email", "") or raw_payload.get("EmailAddress", "") or "").strip()
        phone = (raw_payload.get("Phone", "") or raw_payload.get("PhoneNumber", "") or "").strip()
        material_desc = (
            raw_payload.get("DescribeYourMaterial", "") or raw_payload.get("WhatTypeOfPlastic", "") or ""
        ).strip()
        quantity_text = (raw_payload.get("WhatIsTheQuantity", "") or "").strip()
        contaminants = (raw_payload.get("AreThereAnyContaminants", "") or "").strip()

        image_urls = self._extract_image_urls(raw_payload)

        # Look up web_lead source
        web_lead_source = self.env[UTM_SOURCE].search([("name", "=", WEB_LEAD_FORM)], limit=1)

        vals = {
            "lead_id": str(lead_id),
            "source": "cognito_form",
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
    # Entry Point 2: Pre-Processed Agent Payload (Legacy)
    # ═══════════════════════════════════════════════════════════

    @api.model
    def create_from_agent(self, payload: dict[str, Any]) -> PlasticosWebLead:
        """Create a web lead from a pre-processed agent payload.

        Expected payload structure::

            {
                "lead_id": "WL123",
                "source": "cognito_form",
                "decision": "Hot",
                "decision_reasons": ["monthly_lbs >= 10000", ...],
                "raw_payload": { ... Cognito form fields ... },
                "ai_analysis": { ... }
            }

        Returns the created web.lead record.
        """
        lead_id = payload.get("lead_id")
        if not lead_id:
            raise UserError("Missing required field: lead_id")

        existing = self.search([("lead_id", "=", lead_id)], limit=1)
        if existing:
            _logger.info("Web lead %s already exists, returning existing.", lead_id)
            return existing

        raw = payload.get("raw_payload", {})
        ai = payload.get("ai_analysis", {})
        ai_qty = ai.get("quantity", {})
        ai_freq = ai.get("frequency", {})
        decision_raw = (payload.get("decision") or "cold").lower()

        company = raw.get("YourBusinessCompanyName", "").strip()
        contact = raw.get("YourName", "").strip()
        email = raw.get("Email", "").strip()
        phone = raw.get("Phone", "").strip()
        qty_text = raw.get("WhatIsTheQuantity", "")
        contaminants = raw.get("AreThereAnyContaminants", "")
        material_desc = raw.get("DescribeYourMaterial", "") or raw.get("WhatTypeOfPlastic", "")

        # Look up web_lead source
        web_lead_source = self.env[UTM_SOURCE].search([("name", "=", WEB_LEAD_FORM)], limit=1)

        vals = {
            "lead_id": lead_id,
            "source": payload.get("source", "cognito_form"),
            "lead_source_id": web_lead_source.id if web_lead_source else False,
            "decision": "hot" if decision_raw == "hot" else "cold",
            "decision_reasons": payload.get("decision_reasons"),
            "raw_payload": raw,
            "ai_analysis": ai,
            "company_name": company or "Unknown",
            "contact_name": contact,
            "contact_email": email,
            "contact_phone": phone,
            "material_description": material_desc,
            "quantity_text": qty_text,
            "estimated_lbs_per_load": _safe_int(ai_qty.get("per_load_lbs")),
            "estimated_loads_per_month": _safe_int(ai_qty.get("loads_per_month")),
            "frequency": ai_freq.get("frequency", ""),
            "has_contaminants": bool(contaminants),
            "contaminant_notes": contaminants or False,
        }

        lead = self.create(vals)
        _logger.info("Web lead %s created (decision=%s).", lead_id, lead.decision)

        if lead.decision == "hot":
            lead._process_hot_lead_simple()
        else:
            lead.write({"state": "skipped"})

        return lead

    # ═══════════════════════════════════════════════════════════
    # AI Triage Pipeline
    # ═══════════════════════════════════════════════════════════

    def _run_triage_pipeline(self):
        """Execute the full AI triage pipeline on this web lead.

        Steps:
          1. AI normalization (if enabled)
          2. Image analysis (if enabled and images present)
          3. Deterministic classification
          4. Process result (HOT → intake, COLD → archive)
        """
        self.ensure_one()
        config = self.env[PLASTICOS_WEB_LEAD_CONFIG].sudo().get_config()
        log_lines: list[str] = []
        urls = self.image_urls or []

        try:
            ai_data = self._run_ai_normalization_step(config, log_lines)
            vision_results = self._run_image_analysis_step(config, urls, log_lines)

            # Step 3: Merge AI + Vision data
            merged = self._merge_ai_and_vision(ai_data, vision_results)
            log_lines.append(
                f"Step 3: Merged data — polymer={merged.get('polymer')}, "
                f"form={merged.get('form')}, lbs={merged.get('estimated_lbs')}"
            )

            # Step 4: Deterministic Classification
            log_lines.append("Step 4: Running deterministic classification...")
            result = classify_lead(
                polymer=merged.get("polymer"),
                material_description=self.material_description,
                estimated_lbs=merged.get("estimated_lbs", 0),
                source_description=merged.get("source_description", ""),
                source_type=merged.get("source_type"),
                reject_materials=config.get_reject_materials(),
                reject_sources=config.get_reject_sources(),
                hot_min_lbs=config.hot_min_lbs or 10000,
                cold_max_lbs=config.cold_max_lbs or 8000,
            )
            log_lines.append(f"  Decision: {result.decision.upper()}")
            for reason in result.reasons:
                log_lines.append(f"  Reason: {reason}")

            self._write_classification_result(result, merged, config, log_lines)

            # Step 7: Fetch and attach images
            if urls:
                log_lines.append(f"Step 6: Fetching {len(urls)} image(s) as attachments...")
                self._fetch_and_attach_images(urls)
                log_lines.append("  Done: images attached.")

        except Exception as exc:
            _logger.exception("Triage pipeline error for lead %s", self.lead_id)
            log_lines.append(f"ERROR: {exc}")
            self.write(
                {
                    "state": "error",
                    "error_message": str(exc),
                }
            )

        self.write({"triage_log": "\n".join(log_lines)})

    def _run_ai_normalization_step(self, config, log_lines: list) -> dict:
        """Run Step 1 — AI normalization; return ai_data dict (empty if skipped/disabled)."""
        ai_data: dict[str, Any] = {}
        if config.ai_enabled and config.openai_api_key:
            log_lines.append("Step 1: Running AI normalization...")
            ai_data = ai_normalizer.normalize_with_llm(
                raw_payload=self.raw_payload or {},
                api_key=config.openai_api_key,
                model=config.openai_model or "gpt-4.1-mini",
            )
            self.write({"ai_normalized": ai_data})
            if ai_data.get("error"):
                log_lines.append(f"  WARNING: AI error — {ai_data['error']}")
            else:
                log_lines.append(
                    f"  OK: polymer={ai_data.get('polymer')}, "
                    f"form={ai_data.get('form')}, "
                    f"lbs={ai_data.get('estimated_lbs_per_load')}"
                )
        else:
            log_lines.append("Step 1: AI normalization SKIPPED (disabled or no key).")
        return ai_data

    def _run_image_analysis_step(self, config, urls: list, log_lines: list) -> list:
        """Run Step 2 — image vision analysis; return list of vision result dicts."""
        vision_results: list[dict[str, Any]] = []
        if config.vision_enabled and config.openai_api_key and urls:
            log_lines.append(f"Step 2: Analyzing {len(urls)} image(s)...")
            vision_results = image_analyzer.analyze_multiple_images(
                image_urls=urls,
                api_key=config.openai_api_key,
                model=config.openai_vision_model or "gpt-4.1-mini",
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
            log_lines.append("Step 2: Image analysis SKIPPED.")
        return vision_results

    def _write_classification_result(self, result, merged: dict, config, log_lines: list):
        """Persist classification result and route HOT/COLD processing (Steps 5–6)."""
        self.write({
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
        })
        if result.decision == "hot":
            log_lines.append("Step 5: Processing HOT lead → partner + intake...")
            self._process_hot_lead_triage(merged, config)
            log_lines.append("  Done: intake created.")
        else:
            log_lines.append("Step 5: COLD lead — archived.")
            self.write({"state": "skipped"})

    # ═══════════════════════════════════════════════════════════
    # Merge AI + Vision
    # ═══════════════════════════════════════════════════════════

    def _merge_ai_and_vision(
        self,
        ai_data: dict[str, Any],
        vision_results: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Merge text-based AI normalization with vision analysis.

        Text AI is authoritative for polymer, weight, source.
        Vision is authoritative for form, color, contamination.
        """
        merged = self._build_ai_merged_fields(ai_data)
        self._apply_best_vision(merged, vision_results)
        return merged

    def _build_ai_merged_fields(self, ai_data: dict[str, Any]) -> dict[str, Any]:
        """Build the merged dict from text-based AI normalization output."""
        polymer_raw = (ai_data.get("polymer") or "").lower().strip()
        raw = self.raw_payload or {}
        return {
            "polymer": _POLYMER_NORMALIZE.get(polymer_raw, polymer_raw or None),
            "form": _FORM_NORMALIZE.get((ai_data.get("form") or "").lower().strip(), None),
            "color": (ai_data.get("color") or "").lower().strip() or None,
            "source_type": _SOURCE_NORMALIZE.get((ai_data.get("source_type") or "").lower().strip(), None),
            "estimated_lbs": _safe_int(ai_data.get("estimated_lbs_per_load"), 0),
            "loads_per_month": _safe_int(ai_data.get("loads_per_month"), 0),
            "is_plastic": ai_data.get("is_plastic", True),
            "is_commercial_source": ai_data.get("is_commercial_source", False),
            "material_summary": ai_data.get("material_summary", ""),
            "contaminants_noted": ai_data.get("contaminants_noted"),
            "confidence": ai_data.get("confidence", 0.5),
            "frequency": (ai_data.get("frequency") or "").lower().strip(),
            "source_description": raw.get("WhatIsTheSourceOfThisMaterial", "") or raw.get("Source", "") or "",
        }

    def _apply_best_vision(self, merged: dict[str, Any], vision_results: list[dict[str, Any]]) -> None:
        """Overlay the highest-confidence vision result onto the merged dict in-place."""
        if not vision_results:
            return
        best_vision = max(
            [v for v in vision_results if not v.get("error")],
            key=lambda v: v.get("confidence", 0),
            default={},
        )
        if not best_vision:
            return
        v_form = _FORM_NORMALIZE.get((best_vision.get("observed_form") or "").lower().strip())
        if v_form and not merged.get("form"):
            merged["form"] = v_form
        v_color = (best_vision.get("observed_color") or "").lower().strip()
        if v_color and not merged.get("color"):
            merged["color"] = v_color
        if best_vision.get("contamination_visible"):
            merged["contamination_visible"] = True
            merged["contamination_notes"] = best_vision.get("contamination_notes")
        merged["vision_summary"] = best_vision.get("visual_summary", "")

    # ═══════════════════════════════════════════════════════════
    # HOT Lead Processing (Triage Pipeline)
    # ═══════════════════════════════════════════════════════════

    def _process_hot_lead_triage(self, merged: dict[str, Any], config: Any):
        """Create intake from HOT lead and notify admin for review.

        NEW FLOW (2026-02-23):
        - Creates intake WITHOUT partner (partner created only when buyer-matching)
        - Stores company name as pending_company_name on intake
        - Notifies admin to review the intake
        - Partner + material profile created only if admin decides to buyer-match
        """
        self.ensure_one()

        intake = self._create_intake_triage(merged, config)
        self.write(
            {
                "intake_id": intake.id,
                "state": "intake_created",
            }
        )

        # Notify admin to review
        self._notify_admin_hot_intake(intake, config)

        _logger.info(
            "HOT lead %s → intake %s (pending review, no partner yet)",
            self.lead_id,
            intake.id,
        )

    def _create_intake_triage(self, merged: dict[str, Any], config: Any):
        """Create intake record WITHOUT partner (deferred until buyer-match).

        Looks up polymer_id, form_id, source_type_id from master registries
        by code. Falls back to 'other' record if code not found.
        """
        polymer_code = merged.get("polymer") or "other"
        form_code = merged.get("form") or "other"
        source_type_code = merged.get("source_type") or config.default_source_type or "post_consumer"
        qty_per_load = max(merged.get("estimated_lbs", 0), 1)
        loads_per_month = max(merged.get("loads_per_month", 0), 0)

        freq_raw = merged.get("frequency", "")
        deal_type = _FREQ_TO_DEAL.get(freq_raw, "spot")

        # Look up Many2one records by code (BUG-073 fix)
        Polymer = self.env["plasticos.polymer"]
        Form = self.env["plasticos.material.form"]
        SourceType = self.env["plasticos.source.type"]

        polymer_rec = Polymer.search([("code", OP_ILIKE, polymer_code)], limit=1)
        if not polymer_rec:
            polymer_rec = Polymer.search([("code", OP_ILIKE, "other")], limit=1)

        form_rec = Form.search([("code", OP_ILIKE, form_code)], limit=1)
        if not form_rec:
            form_rec = Form.search([("code", OP_ILIKE, "other")], limit=1)

        source_type_rec = SourceType.search([("code", OP_ILIKE, source_type_code)], limit=1)
        if not source_type_rec:
            source_type_rec = SourceType.search([("code", OP_ILIKE, "post_consumer")], limit=1)

        # Look up web_lead source for intake
        web_lead_source = self.env[UTM_SOURCE].search([("name", "=", WEB_LEAD_FORM)], limit=1)

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
            "contamination_notes": merged.get("contaminants_noted") or self.contaminant_notes or False,
        }

        Intake = self.env[PLASTICOS_INTAKE]
        intake = Intake.create(intake_vals)

        # Link this lead to the intake for reference (Many2one on web_lead side)
        self.intake_id = intake.id

        return intake

    def _notify_admin_hot_intake(self, intake, config):
        """Create activity for admin to review HOT intake.

        Assigns to configured reviewer or falls back to current user.
        """
        reviewer_id = self.env.user.id

        # Check if there's a configured reviewer (could add to config model)
        if hasattr(config, "intake_reviewer_id") and config.intake_reviewer_id:
            reviewer_id = config.intake_reviewer_id.id

        # Build material description from Many2one fields
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
                f"<p><b>Action:</b> Click 'Match to Buyers' to create partner and run matching, "
                f"or delete/archive if not a valid lead.</p>"
            ),
        )

    # ═══════════════════════════════════════════════════════════
    # HOT Lead Processing (Simple/Legacy)
    # ═══════════════════════════════════════════════════════════

    def _process_hot_lead_simple(self):
        """Create intake from HOT lead and notify admin (simple/legacy flow).

        Same new flow as triage: no partner until buyer-match.
        """
        self.ensure_one()
        config = self.env[PLASTICOS_WEB_LEAD_CONFIG].get_config()

        try:
            intake = self._create_intake_simple(config)
            self.write(
                {
                    "intake_id": intake.id,
                    "state": "intake_created",
                }
            )

            # Notify admin to review
            self._notify_admin_hot_intake(intake, config)

            _logger.info(
                "HOT lead %s → intake %s (pending review, no partner yet)",
                self.lead_id,
                intake.id,
            )

        except Exception as exc:
            _logger.exception("Error processing HOT lead %s", self.lead_id)
            self.write(
                {
                    "state": "error",
                    "error_message": str(exc),
                }
            )

    def _extract_ai_material_params(self):
        """Extract and normalize material/qty/freq codes from ai_analysis payload."""
        ai = self.ai_analysis or {}
        ai_qty = ai.get("quantity", {})
        ai_freq = ai.get("frequency", {})
        ai_material = ai.get("material", {})

        polymer_raw = (ai_material.get("polymer", "") or ai_material.get("resin_type", "") or "").lower().strip()
        polymer_code = _POLYMER_NORMALIZE.get(polymer_raw, "other")

        form_raw = (ai_material.get("form", "") or ai_material.get("material_form", "") or "").lower().strip()
        form_code = _FORM_NORMALIZE.get(form_raw, "other")

        freq_raw = (ai_freq.get("frequency") or "").lower()
        deal_type = _FREQ_TO_DEAL.get(freq_raw, "spot")

        qty_per_load = _safe_int(ai_qty.get("per_load_lbs"), 40000)
        loads_per_month = _safe_int(ai_qty.get("loads_per_month"), 1)

        return polymer_code, form_code, deal_type, qty_per_load, loads_per_month

    def _lookup_intake_material_records(self, polymer_code, form_code, source_type_code):
        """Resolve polymer, form, source_type ORM records by code with 'other' fallback."""
        Polymer = self.env["plasticos.polymer"]
        Form = self.env["plasticos.material.form"]
        SourceType = self.env["plasticos.source.type"]

        polymer_rec = Polymer.search([("code", OP_ILIKE, polymer_code)], limit=1) if polymer_code else False
        if polymer_code and not polymer_rec:
            polymer_rec = Polymer.search([("code", OP_ILIKE, "other")], limit=1)

        form_rec = Form.search([("code", OP_ILIKE, form_code)], limit=1) if form_code else False
        if form_code and not form_rec:
            form_rec = Form.search([("code", OP_ILIKE, "other")], limit=1)

        source_type_rec = SourceType.search([("code", OP_ILIKE, source_type_code)], limit=1)
        if not source_type_rec:
            source_type_rec = SourceType.search([("code", OP_ILIKE, "post_consumer")], limit=1)

        return polymer_rec, form_rec, source_type_rec

    def _create_intake_simple(self, config: Any):
        """Create intake WITHOUT partner from pre-processed agent payload.

        Looks up polymer_id, form_id, source_type_id from master registries
        by normalized code. Falls back to 'other' record if code not found.
        """
        source_type_code = config.default_source_type or "post_consumer"
        polymer_code, form_code, deal_type, qty_per_load, loads_per_month = self._extract_ai_material_params()
        polymer_rec, form_rec, source_type_rec = self._lookup_intake_material_records(
            polymer_code, form_code, source_type_code
        )

        # Look up web_lead source for intake
        web_lead_source = self.env[UTM_SOURCE].search([("name", "=", WEB_LEAD_FORM)], limit=1)

        intake_vals = {
            "pending_company_name": self.company_name or "Unknown",
            "source_lead_id": self.id,
            "source_type_id": source_type_rec.id if source_type_rec else False,
            "lead_source_id": web_lead_source.id if web_lead_source else False,
            "quantity_per_load_lbs": max(qty_per_load, 1),
            "loads_per_month": max(loads_per_month, 0),
            "deal_type": deal_type,
            "contamination_notes": self.contaminant_notes or False,
        }

        if polymer_rec:
            intake_vals["polymer_id"] = polymer_rec.id
        if form_rec:
            intake_vals["form_id"] = form_rec.id

        Intake = self.env[PLASTICOS_INTAKE]
        intake = Intake.create(intake_vals)

        # Link this lead to the intake for reference (Many2one on web_lead side)
        self.intake_id = intake.id

        return intake

    # ═══════════════════════════════════════════════════════════
    # Partner Handling
    # ═══════════════════════════════════════════════════════════

    def _find_or_create_partner(self):
        """Find existing partner by company name or create a new one.

        DEPRECATED (2026-02-23): No longer called by main flows.
        Partner creation now happens in intake.action_match_to_buyers().
        Kept for manual/utility use.
        """
        Partner = self.env[RES_PARTNER]
        name = self.company_name or "Unknown Web Lead"

        partner = Partner.search([("name", OP_ILIKE, name)], limit=1)
        if partner:
            return partner

        config = self.env[PLASTICOS_WEB_LEAD_CONFIG].sudo().get_config()
        if not config.auto_create_partner:
            raise UserError(f"No partner found for '{name}' and auto-create is disabled.")

        partner_vals = {
            "name": name,
            "is_company": True,
            "comment": f"Auto-created from web lead {self.lead_id}",
        }
        if self.contact_email:
            partner_vals["email"] = self.contact_email
        if self.contact_phone:
            partner_vals["phone"] = self.contact_phone

        partner = Partner.create(partner_vals)
        _logger.info("Auto-created partner '%s' (id=%s).", name, partner.id)

        if self.contact_name:
            Partner.create(
                {
                    "name": self.contact_name,
                    "parent_id": partner.id,
                    "email": self.contact_email or False,
                    "phone": self.contact_phone or False,
                    "type": "contact",
                }
            )

        return partner

    # ═══════════════════════════════════════════════════════════
    # Image Handling
    # ═══════════════════════════════════════════════════════════

    def _extract_image_urls(self, raw_payload: dict[str, Any]) -> list[str]:
        """Extract image URLs from a Cognito form payload."""
        urls: list[str] = []
        for key, val in raw_payload.items():
            if isinstance(val, str) and self._looks_like_image_url(val):
                urls.append(val)
            elif isinstance(val, list):
                for item in val:
                    if isinstance(item, str) and self._looks_like_image_url(item):
                        urls.append(item)
                    elif isinstance(item, dict) and item.get("url"):
                        url = item["url"]
                        if self._looks_like_image_url(url):
                            urls.append(url)
            elif isinstance(val, dict) and val.get("url"):
                url = val["url"]
                if self._looks_like_image_url(url):
                    urls.append(url)
        return urls

    @staticmethod
    def _looks_like_image_url(url: str) -> bool:
        """Heuristic: does this URL look like an image?"""
        lower = url.lower()
        return lower.startswith("http") and any(
            ext in lower for ext in (".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".heic")
        )

    @staticmethod
    def _resolve_image_extension(content_type: str) -> str:
        """Determine file extension from HTTP Content-Type header."""
        if "png" in content_type:
            return ".png"
        if "webp" in content_type:
            return ".webp"
        if "gif" in content_type:
            return ".gif"
        return ".jpg"

    @staticmethod
    def _build_image_attachment_vals(
        fname: str, content: bytes, content_type: str,
        res_model: str, res_id: int,
    ) -> dict:
        """Build ir.attachment create-vals for a binary image."""
        return {
            "name": fname,
            "type": "binary",
            "datas": base64.b64encode(content).decode("ascii"),
            "res_model": res_model,
            "res_id": res_id,
            "mimetype": content_type,
        }

    def _fetch_and_attach_images(self, urls: list[str]):
        """Download images from URLs and create ir.attachment records."""
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
                ext = self._resolve_image_extension(content_type)
                fname = f"web_lead_{self.lead_id}_img_{i + 1}{ext}"

                Attachment.create(
                    self._build_image_attachment_vals(fname, content, content_type, "plasticos.web.lead", self.id)
                )

                if self.intake_id:
                    Attachment.create(
                        self._build_image_attachment_vals(
                            fname, content, content_type,
                            PLASTICOS_INTAKE, self.intake_id.id,
                        )
                    )

                _logger.info("Attached image %s to web lead %s.", fname, self.lead_id)

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

    def action_retry_processing(self):
        """Retry processing a lead that errored (legacy flow)."""
        for rec in self:
            if rec.state != "error":
                raise UserError("Only errored leads can be retried.")
            if rec.decision == "hot":
                rec._process_hot_lead_simple()

    def action_force_create_intake(self):
        """Force-create an intake from a COLD lead (manual override)."""
        for rec in self:
            if rec.intake_id:
                raise UserError("Intake already exists for this lead.")
            rec._process_hot_lead_simple()

    def action_retry_triage(self):
        """Re-run the AI triage pipeline on an errored or cold lead."""
        for rec in self:
            if rec.state not in ("error", "skipped", "received"):
                raise UserError("Only errored, skipped, or received leads can be re-triaged.")
            rec._run_triage_pipeline()

    def action_force_hot(self):
        """Manually override a COLD lead to HOT and create intake."""
        for rec in self:
            if rec.intake_id:
                raise UserError("Intake already exists for this lead.")
            config = rec.env[PLASTICOS_WEB_LEAD_CONFIG].sudo().get_config()
            merged = rec.ai_normalized or rec.ai_analysis or {}
            rec.write(
                {
                    "decision": "hot",
                    "decision_reasons": {"reasons": ["Manual override by user"]},
                }
            )
            rec._process_hot_lead_triage(merged, config)

    # ═════════════════════════════════════════════════════════
    # Action Methods (for UX smart buttons)
    # ═════════════════════════════════════════════════════════

    def action_view_intake(self):
        """Open the linked intake form."""
        self.ensure_one()
        if not self.intake_id:
            return False
        return {
            "type": "ir.actions.act_window",
            "res_model": PLASTICOS_INTAKE,
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
            "res_model": RES_PARTNER,
            "res_id": self.partner_id.id,
            "view_mode": "form",
            "target": "current",
        }
