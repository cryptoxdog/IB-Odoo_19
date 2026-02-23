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

_logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════
# Mapping helpers — translate AI output to Odoo field values
# ═══════════════════════════════════════════════════════════

_POLYMER_NORMALIZE: dict[str, str] = {
    "hdpe": "hdpe",
    "ldpe": "ldpe",
    "lldpe": "lldpe",
    "pp": "pp",
    "pet": "pet",
    "rpet": "rpet",
    "ps": "ps",
    "hips": "hips",
    "pvc": "pvc",
    "eva": "eva",
    "abs": "abs",
    "nylon": "nylon",
    "pa": "nylon",
    "pc": "pc",
    "pbt": "pbt",
    "pom": "pom",
    "acetal": "pom",
    "pmma": "pmma",
    "ppo": "ppo",
    "tpe": "tpe",
    "tpu": "tpu",
    "pla": "pla",
    "e-waste": "ewaste",
    "ewaste": "ewaste",
}

_FORM_NORMALIZE: dict[str, str] = {
    "bale": "bales",
    "baled": "bales",
    "bales": "bales",
    "regrind": "regrind",
    "flake": "flake",
    "flakes": "flake",
    "pellet": "pellet",
    "pellets": "pellet",
    "rollstock": "rollstock",
    "purge": "purge",
    "lump": "lump",
    "lumps": "lump",
    "film": "rollstock",
    "sheet": "sheet",
    "powder": "powder",
    "parts": "parts",
    "part": "parts",
    "re-useable": "re_useable",
    "reuseable": "re_useable",
    "reusable": "re_useable",
    "bottle": "bottle",
    "bottles": "bottle",
    "roll": "roll",
    "rolls": "roll",
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
    lead_source = fields.Selection(
        [
            ("web_lead", "Web Lead (Marketing)"),
            ("sales_manual", "Sales Manual Entry"),
            ("linkedin_ai", "LinkedIn AI Prospecting"),
            ("referral", "Referral"),
            ("trade_show", "Trade Show"),
            ("other", "Other"),
        ],
        string="Lead Source",
        default="web_lead",
        index=True,
        tracking=True,
        help="How this lead was acquired. Critical for marketing vs. sales attribution.",
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

    _check_unique_lead = models.Constraint(
        "unique(lead_id)",
        "A web lead with this ID already exists (idempotency guard).",
    )

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

        vals = {
            "lead_id": str(lead_id),
            "source": "cognito_form",
            "lead_source": "web_lead",
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

        vals = {
            "lead_id": lead_id,
            "source": payload.get("source", "cognito_form"),
            "lead_source": "web_lead",
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
        config = self.env["plasticos.web.lead.config"].sudo().get_config()
        log_lines: list[str] = []

        try:
            # Step 1: AI Normalization
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

            # Step 2: Image Analysis
            vision_results: list[dict[str, Any]] = []
            urls = self.image_urls or []
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
                        log_lines.append(f"  Image {i+1}: ERROR — {vr['error']}")
                    else:
                        log_lines.append(
                            f"  Image {i+1}: form={vr.get('observed_form')}, "
                            f"color={vr.get('observed_color')}, "
                            f"confidence={vr.get('confidence', 0):.2f}"
                        )
            else:
                log_lines.append("Step 2: Image analysis SKIPPED.")

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

            # Step 5: Write classification result
            write_vals: dict[str, Any] = {
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
            self.write(write_vals)

            # Step 6: Process HOT leads
            if result.decision == "hot":
                log_lines.append("Step 5: Processing HOT lead → partner + intake...")
                self._process_hot_lead_triage(merged, config)
                log_lines.append("  Done: intake created.")
            else:
                log_lines.append("Step 5: COLD lead — archived.")
                self.write({"state": "skipped"})

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
        merged: dict[str, Any] = {}

        polymer_raw = (ai_data.get("polymer") or "").lower().strip()
        merged["polymer"] = _POLYMER_NORMALIZE.get(polymer_raw, polymer_raw or None)
        merged["form"] = _FORM_NORMALIZE.get((ai_data.get("form") or "").lower().strip(), None)
        merged["color"] = (ai_data.get("color") or "").lower().strip() or None
        merged["source_type"] = _SOURCE_NORMALIZE.get((ai_data.get("source_type") or "").lower().strip(), None)
        merged["estimated_lbs"] = _safe_int(ai_data.get("estimated_lbs_per_load"), 0)
        merged["loads_per_month"] = _safe_int(ai_data.get("loads_per_month"), 0)
        merged["is_plastic"] = ai_data.get("is_plastic", True)
        merged["is_commercial_source"] = ai_data.get("is_commercial_source", False)
        merged["material_summary"] = ai_data.get("material_summary", "")
        merged["contaminants_noted"] = ai_data.get("contaminants_noted")
        merged["confidence"] = ai_data.get("confidence", 0.5)
        merged["frequency"] = (ai_data.get("frequency") or "").lower().strip()

        raw = self.raw_payload or {}
        merged["source_description"] = raw.get("WhatIsTheSourceOfThisMaterial", "") or raw.get("Source", "") or ""

        if vision_results:
            best_vision = max(
                [v for v in vision_results if not v.get("error")],
                key=lambda v: v.get("confidence", 0),
                default={},
            )
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
        """Create intake record WITHOUT partner (deferred until buyer-match)."""
        polymer = merged.get("polymer") or "other"
        form = merged.get("form") or "other"
        source_type = merged.get("source_type") or config.default_source_type or "post_consumer"
        qty_per_load = max(merged.get("estimated_lbs", 0), 1)
        loads_per_month = max(merged.get("loads_per_month", 0), 0)

        freq_raw = merged.get("frequency", "")
        deal_type = _FREQ_TO_DEAL.get(freq_raw, "spot")

        intake_vals = {
            "pending_company_name": self.company_name or "Unknown",
            "source_lead_id": self.id,
            "polymer": polymer,
            "form": form,
            "source_type": source_type,
            "quantity_per_load_lbs": qty_per_load,
            "loads_per_month": loads_per_month,
            "deal_type": deal_type,
            "contamination_notes": merged.get("contaminants_noted") or self.contaminant_notes or False,
        }

        Intake = self.env["plasticos.intake"]
        intake = Intake.create(intake_vals)
        return intake

    def _notify_admin_hot_intake(self, intake, config):
        """Create activity for admin to review HOT intake.

        Assigns to configured reviewer or falls back to current user.
        """
        reviewer_id = self.env.user.id

        # Check if there's a configured reviewer (could add to config model)
        if hasattr(config, "intake_reviewer_id") and config.intake_reviewer_id:
            reviewer_id = config.intake_reviewer_id.id

        intake.activity_schedule(
            "mail.mail_activity_data_todo",
            user_id=reviewer_id,
            summary=f"Review HOT Web Lead: {self.company_name or 'Unknown'}",
            note=(
                f"<p>New HOT lead from web form requires review:</p>"
                f"<ul>"
                f"<li><b>Company:</b> {self.company_name or 'Unknown'}</li>"
                f"<li><b>Material:</b> {intake.polymer} / {intake.form}</li>"
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
        config = self.env["plasticos.web.lead.config"].get_config()

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

    def _create_intake_simple(self, config: Any):
        """Create intake WITHOUT partner from pre-processed agent payload."""
        ai = self.ai_analysis or {}
        ai_qty = ai.get("quantity", {})
        ai_freq = ai.get("frequency", {})
        ai_material = ai.get("material", {})

        polymer_raw = (ai_material.get("polymer", "") or ai_material.get("resin_type", "") or "").lower().strip()
        polymer = _POLYMER_NORMALIZE.get(polymer_raw, False)

        form_raw = (ai_material.get("form", "") or ai_material.get("material_form", "") or "").lower().strip()
        form = _FORM_NORMALIZE.get(form_raw, False)

        freq_raw = (ai_freq.get("frequency") or "").lower()
        deal_type = _FREQ_TO_DEAL.get(freq_raw, "spot")

        qty_per_load = _safe_int(ai_qty.get("per_load_lbs"), 40000)
        loads_per_month = _safe_int(ai_qty.get("loads_per_month"), 1)

        intake_vals = {
            "pending_company_name": self.company_name or "Unknown",
            "source_lead_id": self.id,
            "source_type": config.default_source_type or "post_consumer",
            "quantity_per_load_lbs": max(qty_per_load, 1),
            "loads_per_month": max(loads_per_month, 0),
            "deal_type": deal_type,
            "contamination_notes": self.contaminant_notes or False,
        }

        if polymer:
            intake_vals["polymer"] = polymer
        if form:
            intake_vals["form"] = form

        Intake = self.env["plasticos.intake"]
        intake = Intake.create(intake_vals)
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
        Partner = self.env["res.partner"]
        name = self.company_name or "Unknown Web Lead"

        partner = Partner.search([("name", "=ilike", name)], limit=1)
        if partner:
            return partner

        config = self.env["plasticos.web.lead.config"].sudo().get_config()
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

                fname = f"web_lead_{self.lead_id}_img_{i+1}"
                content_type = resp.headers.get("Content-Type", "image/jpeg")
                ext = ".jpg"
                if "png" in content_type:
                    ext = ".png"
                elif "webp" in content_type:
                    ext = ".webp"
                elif "gif" in content_type:
                    ext = ".gif"
                fname += ext

                att_vals = {
                    "name": fname,
                    "type": "binary",
                    "datas": base64.b64encode(content).decode("ascii"),
                    "res_model": "plasticos.web.lead",
                    "res_id": self.id,
                    "mimetype": content_type,
                }
                Attachment.create(att_vals)

                if self.intake_id:
                    Attachment.create(
                        {
                            "name": fname,
                            "type": "binary",
                            "datas": base64.b64encode(content).decode("ascii"),
                            "res_model": "plasticos.intake",
                            "res_id": self.intake_id.id,
                            "mimetype": content_type,
                        }
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
            config = rec.env["plasticos.web.lead.config"].sudo().get_config()
            merged = rec.ai_normalized or rec.ai_analysis or {}
            rec.write(
                {
                    "decision": "hot",
                    "decision_reasons": {"reasons": ["Manual override by user"]},
                }
            )
            rec._process_hot_lead_triage(merged, config)
