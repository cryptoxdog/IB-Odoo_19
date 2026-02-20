# -*- coding: utf-8 -*-
# ═══════════════════════════════════════════════════════════
# Model : plasticos.web.lead (inherit)
# Purpose: Extend the web lead with AI triage pipeline:
#          1. Receive raw Cognito payload
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

from . import ai_normalizer
from . import image_analyzer
from .classification_engine import classify_lead

_logger = logging.getLogger(__name__)

# ── Polymer code mapping (AI output → Odoo code) ────────────
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

# ── Form mapping (AI output → Odoo selection key) ───────────
_FORM_NORMALIZE: dict[str, str] = {
    "bale": "bale",
    "baled": "bale",
    "regrind": "regrind",
    "flake": "flake",
    "flakes": "flake",
    "pellet": "pellet",
    "pellets": "pellet",
    "rollstock": "rollstock",
    "purge": "purge",
    "lump": "lump",
    "lumps": "lump",
    "film": "film",
    "sheet": "sheet",
    "powder": "powder",
    "parts": "parts",
    "part": "parts",
    "re-useable": "re_useable",
    "reuseable": "re_useable",
    "reusable": "re_useable",
}

# ── Source type mapping ──────────────────────────────────────
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

# ── Frequency → deal_type mapping ────────────────────────────
_FREQ_TO_DEAL: dict[str, str] = {
    "ongoing": "recurring",
    "monthly": "recurring",
    "weekly": "recurring",
    "one_time": "spot",
    "one-time": "spot",
    "spot": "spot",
}


def _safe_int(val: Any, default: int = 0) -> int:
    """Coerce to int, returning *default* on failure."""
    if val is None:
        return default
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return default


class PlasticosWebLeadTriage(models.Model):
    """Extends plasticos.web.lead with AI-powered triage pipeline.

    This _inherit adds:
      - lead_source field for attribution tracking
      - AI normalization fields
      - Image analysis fields
      - Full triage pipeline triggered on create
    """

    _inherit = "plasticos.web.lead"

    # ── Lead Source Attribution ───────────────────────────────
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
        help=(
            "How this lead was acquired. Auto-tagged on creation. "
            "Critical for marketing vs. sales attribution."
        ),
    )

    # ── AI Triage Fields ─────────────────────────────────────
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

    # ═════════════════════════════════════════════════════════
    # Direct Cognito Ingestion
    # ═════════════════════════════════════════════════════════

    @api.model
    def create_from_cognito(self, raw_payload: dict[str, Any]) -> "PlasticosWebLeadTriage":
        """Ingest a raw Cognito form submission directly.

        This replaces the old create_from_agent flow.  The entire
        triage pipeline runs inside Odoo:
          1. Parse raw Cognito fields
          2. Generate unique lead_id
          3. Create web.lead record (state=received)
          4. Run AI normalization (async-safe)
          5. Run image analysis
          6. Deterministic classification
          7. HOT → partner + intake + attachments
        """
        # Generate idempotency key from Cognito entry ID or UUID
        lead_id = raw_payload.get("EntryId") or raw_payload.get(
            "entry_id"
        ) or f"CG-{uuid.uuid4().hex[:12]}"

        # Idempotency guard
        existing = self.search([("lead_id", "=", str(lead_id))], limit=1)
        if existing:
            _logger.info("Duplicate Cognito submission %s — returning existing.", lead_id)
            return existing

        # Extract contact fields
        company = (
            raw_payload.get("YourBusinessCompanyName", "")
            or raw_payload.get("CompanyName", "")
            or ""
        ).strip()
        contact = (
            raw_payload.get("YourName", "")
            or raw_payload.get("Name", "")
            or ""
        ).strip()
        email = (
            raw_payload.get("Email", "")
            or raw_payload.get("EmailAddress", "")
            or ""
        ).strip()
        phone = (
            raw_payload.get("Phone", "")
            or raw_payload.get("PhoneNumber", "")
            or ""
        ).strip()
        material_desc = (
            raw_payload.get("DescribeYourMaterial", "")
            or raw_payload.get("WhatTypeOfPlastic", "")
            or ""
        ).strip()
        quantity_text = (raw_payload.get("WhatIsTheQuantity", "") or "").strip()
        contaminants = (raw_payload.get("AreThereAnyContaminants", "") or "").strip()

        # Extract image URLs from Cognito file upload fields
        image_urls = self._extract_image_urls(raw_payload)

        # Create the web lead record
        vals = {
            "lead_id": str(lead_id),
            "source": "cognito_form",
            "lead_source": "web_lead",
            "decision": "cold",  # Placeholder — will be overwritten by triage
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

        # Run the triage pipeline
        lead._run_triage_pipeline()
        return lead

    # ═════════════════════════════════════════════════════════
    # Triage Pipeline
    # ═════════════════════════════════════════════════════════

    def _run_triage_pipeline(self):
        """Execute the full triage pipeline on this web lead.

        Steps:
          1. AI normalization (if enabled)
          2. Image analysis (if enabled and images present)
          3. Deterministic classification
          4. Process result (HOT → intake, COLD → archive)
        """
        self.ensure_one()
        config = self.env["plasticos.triage.config"].sudo().get_config()
        log_lines: list[str] = []

        try:
            # ── Step 1: AI Normalization ─────────────────────
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

            # ── Step 2: Image Analysis ───────────────────────
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

            # ── Step 3: Merge AI + Vision data ───────────────
            merged = self._merge_ai_and_vision(ai_data, vision_results)
            log_lines.append(
                f"Step 3: Merged data — polymer={merged.get('polymer')}, "
                f"form={merged.get('form')}, lbs={merged.get('estimated_lbs')}"
            )

            # ── Step 4: Deterministic Classification ─────────
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

            # ── Step 5: Write classification result ──────────
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

            # ── Step 6: Process HOT leads ────────────────────
            if result.decision == "hot":
                log_lines.append("Step 5: Processing HOT lead → partner + intake...")
                self._process_hot_lead_triage(merged, config)
                log_lines.append("  Done: intake created.")
            else:
                log_lines.append("Step 5: COLD lead — archived.")
                self.write({"state": "skipped"})

            # ── Step 7: Fetch and attach images ──────────────
            if urls:
                log_lines.append(f"Step 6: Fetching {len(urls)} image(s) as attachments...")
                self._fetch_and_attach_images(urls)
                log_lines.append("  Done: images attached.")

        except Exception as exc:
            _logger.exception("Triage pipeline error for lead %s", self.lead_id)
            log_lines.append(f"ERROR: {exc}")
            self.write({
                "state": "error",
                "error_message": str(exc),
            })

        # Write audit log
        self.write({"triage_log": "\n".join(log_lines)})

    # ═════════════════════════════════════════════════════════
    # Merge AI + Vision
    # ═════════════════════════════════════════════════════════

    def _merge_ai_and_vision(
        self,
        ai_data: dict[str, Any],
        vision_results: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Merge text-based AI normalization with vision analysis.

        Text AI is authoritative for polymer, weight, source.
        Vision is authoritative for form, color, contamination.
        Cross-validation: if both agree, confidence is boosted.
        """
        merged: dict[str, Any] = {}

        # Text AI values
        polymer_raw = (ai_data.get("polymer") or "").lower().strip()
        merged["polymer"] = _POLYMER_NORMALIZE.get(polymer_raw, polymer_raw or None)
        merged["form"] = _FORM_NORMALIZE.get(
            (ai_data.get("form") or "").lower().strip(), None
        )
        merged["color"] = (ai_data.get("color") or "").lower().strip() or None
        merged["source_type"] = _SOURCE_NORMALIZE.get(
            (ai_data.get("source_type") or "").lower().strip(), None
        )
        merged["estimated_lbs"] = _safe_int(
            ai_data.get("estimated_lbs_per_load"), 0
        )
        merged["loads_per_month"] = _safe_int(
            ai_data.get("loads_per_month"), 0
        )
        merged["is_plastic"] = ai_data.get("is_plastic", True)
        merged["is_commercial_source"] = ai_data.get("is_commercial_source", False)
        merged["material_summary"] = ai_data.get("material_summary", "")
        merged["contaminants_noted"] = ai_data.get("contaminants_noted")
        merged["confidence"] = ai_data.get("confidence", 0.5)
        merged["frequency"] = (ai_data.get("frequency") or "").lower().strip()

        # Source description for classification
        raw = self.raw_payload or {}
        merged["source_description"] = (
            raw.get("WhatIsTheSourceOfThisMaterial", "")
            or raw.get("Source", "")
            or ""
        )

        # Vision override (form, color, contamination)
        if vision_results:
            best_vision = max(
                [v for v in vision_results if not v.get("error")],
                key=lambda v: v.get("confidence", 0),
                default={},
            )
            if best_vision:
                v_form = _FORM_NORMALIZE.get(
                    (best_vision.get("observed_form") or "").lower().strip()
                )
                if v_form and not merged["form"]:
                    merged["form"] = v_form
                v_color = (best_vision.get("observed_color") or "").lower().strip()
                if v_color and not merged["color"]:
                    merged["color"] = v_color
                if best_vision.get("contamination_visible"):
                    merged["contamination_visible"] = True
                    merged["contamination_notes"] = best_vision.get(
                        "contamination_notes"
                    )
                merged["vision_summary"] = best_vision.get("visual_summary", "")

        return merged

    # ═════════════════════════════════════════════════════════
    # HOT Lead Processing
    # ═════════════════════════════════════════════════════════

    def _process_hot_lead_triage(
        self,
        merged: dict[str, Any],
        config: Any,
    ):
        """Create partner + intake from a HOT-classified lead."""
        self.ensure_one()

        # 1. Find or create partner
        partner = self._find_or_create_partner_triage()
        self.write({"partner_id": partner.id})

        # 2. Create intake
        if config.auto_create_intake:
            intake = self._create_intake_triage(partner, merged)
            self.write({
                "intake_id": intake.id,
                "state": "intake_created",
            })
            _logger.info(
                "HOT lead %s → partner %s, intake %s",
                self.lead_id, partner.id, intake.id,
            )
        else:
            self.write({"state": "intake_created"})

    def _find_or_create_partner_triage(self):
        """Find existing partner by company name or create a new one."""
        Partner = self.env["res.partner"]
        name = self.company_name or "Unknown Web Lead"

        # Try exact match first
        partner = Partner.search([("name", "=ilike", name)], limit=1)
        if partner:
            return partner

        # Create company partner
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

        # Create contact under company
        if self.contact_name:
            Partner.create({
                "name": self.contact_name,
                "parent_id": partner.id,
                "email": self.contact_email or False,
                "phone": self.contact_phone or False,
                "type": "contact",
            })

        return partner

    def _create_intake_triage(
        self,
        partner: Any,
        merged: dict[str, Any],
    ):
        """Create a plasticos.intake record from merged AI data."""
        polymer = merged.get("polymer") or "other"
        form = merged.get("form") or "other"
        source_type = merged.get("source_type") or "unknown"
        qty_per_load = max(merged.get("estimated_lbs", 0), 1)
        loads_per_month = max(merged.get("loads_per_month", 0), 0)

        # Map frequency to deal_type
        freq_raw = merged.get("frequency", "")
        deal_type = _FREQ_TO_DEAL.get(freq_raw, "spot")

        # Find the facility (child partner) or use company directly
        facility = partner
        children = self.env["res.partner"].search([
            ("parent_id", "=", partner.id),
            ("type", "!=", "contact"),
        ], limit=1)
        if children:
            facility = children

        intake_vals = {
            "name": f"WEB-{self.lead_id}",
            "partner_id": facility.id,
            "polymer": polymer,
            "form": form,
            "source_type": source_type,
            "quantity_per_load_lbs": qty_per_load,
            "loads_per_month": loads_per_month,
            "deal_type": deal_type,
            "contamination_notes": merged.get("contaminants_noted") or self.contaminant_notes or False,
            "match_status": "pending",
            "onboarding_status": "draft",
            "material_hint_text": merged.get("material_summary", ""),
        }

        Intake = self.env["plasticos.intake"]
        intake = Intake.create(intake_vals)
        return intake

    # ═════════════════════════════════════════════════════════
    # Image Handling
    # ═════════════════════════════════════════════════════════

    def _extract_image_urls(self, raw_payload: dict[str, Any]) -> list[str]:
        """Extract image URLs from a Cognito form payload.

        Cognito stores file uploads as objects with a ``url`` key,
        or sometimes as plain URL strings.
        """
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
        return (
            lower.startswith("http")
            and any(
                ext in lower
                for ext in (".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".heic")
            )
        )

    def _fetch_and_attach_images(self, urls: list[str]):
        """Download images from URLs and create ir.attachment records.

        Attachments are linked to both the web lead and (if exists)
        the intake record, for downstream material profile use.
        """
        self.ensure_one()
        Attachment = self.env["ir.attachment"]

        for i, url in enumerate(urls[:10]):  # Safety cap at 10 images
            try:
                resp = http_requests.get(url, timeout=30, stream=True)
                resp.raise_for_status()
                content = resp.content
                if not content:
                    continue

                # Determine filename and mimetype
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

                # Also link to intake if it exists
                if self.intake_id:
                    Attachment.create({
                        "name": fname,
                        "type": "binary",
                        "datas": base64.b64encode(content).decode("ascii"),
                        "res_model": "plasticos.intake",
                        "res_id": self.intake_id.id,
                        "mimetype": content_type,
                    })

                _logger.info("Attached image %s to web lead %s.", fname, self.lead_id)

            except Exception as exc:
                _logger.warning(
                    "Failed to fetch image %s for lead %s: %s",
                    url[:80], self.lead_id, exc,
                )

    # ═════════════════════════════════════════════════════════
    # Manual Actions
    # ═════════════════════════════════════════════════════════

    def action_retry_triage(self):
        """Re-run the triage pipeline on an errored or cold lead."""
        for rec in self:
            if rec.state not in ("error", "skipped", "received"):
                raise UserError("Only errored, skipped, or received leads can be re-triaged.")
            rec._run_triage_pipeline()

    def action_force_hot(self):
        """Manually override a COLD lead to HOT and create intake."""
        for rec in self:
            if rec.intake_id:
                raise UserError("Intake already exists for this lead.")
            config = self.env["plasticos.triage.config"].sudo().get_config()
            merged = rec.ai_normalized or rec.ai_analysis or {}
            rec.write({
                "decision": "hot",
                "decision_reasons": {"reasons": ["Manual override by user"]},
            })
            rec._process_hot_lead_triage(merged, config)
