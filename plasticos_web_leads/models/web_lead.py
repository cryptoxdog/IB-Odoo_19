import logging
import json

from odoo import models, fields, api
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════
# Mapping helpers — translate lead_intake agent output
# to plasticos.intake field values.
# ═══════════════════════════════════════════════════════════

_POLYMER_MAP = {
    "hdpe": "hdpe",
    "ldpe": "ldpe",
    "lldpe": "lldpe",
    "pp": "pp",
    "pet": "pet",
    "ps": "ps",
    "pvc": "pvc",
    "abs": "abs",
    "pc": "pc",
    "pa": "pa",
    "nylon": "pa",
    "tpe": "tpe",
    "tpu": "tpu",
    "pmma": "pmma",
    "acetal": "pom",
    "pom": "pom",
}

_FORM_MAP = {
    "regrind": "regrind",
    "pellet": "pellet",
    "pellets": "pellet",
    "bale": "bale",
    "baled": "bale",
    "film": "film",
    "bottle": "bottle",
    "bottles": "bottle",
    "flake": "flake",
    "flakes": "flake",
    "purge": "purge",
    "lump": "lump",
    "lumps": "lump",
    "roll": "roll",
    "rolls": "roll",
    "sheet": "sheet",
    "part": "part",
    "parts": "part",
}

_FREQUENCY_MAP = {
    "ongoing": "ongoing",
    "one_time": "spot",
    "spot": "spot",
    "unclear": "spot",
}


def _safe_int(val, default=0):
    """Coerce to int, returning default on failure."""
    if val is None:
        return default
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return default


class PlasticosWebLead(models.Model):
    """Stores every inbound web lead from the lead_intake agent.

    HOT leads automatically generate a plasticos.intake record and
    (optionally) a res.partner. COLD leads are stored for reference
    but do not create downstream records.
    """

    _name = "plasticos.web.lead"
    _description = "Web Lead"
    _inherit = ["mail.thread"]
    _order = "create_date desc"
    _rec_name = "lead_id"

    # ═════════════════════════════════════════════════════════
    # Identity
    # ═════════════════════════════════════════════════════════

    lead_id = fields.Char(
        required=True,
        index=True,
        tracking=True,
        help="Unique lead identifier from the agent (e.g. WL123).",
    )
    source = fields.Char(
        default="cognito_form",
        help="Origin system identifier.",
    )

    # ═════════════════════════════════════════════════════════
    # Raw Data (immutable after creation)
    # ═════════════════════════════════════════════════════════

    raw_payload = fields.Json(
        readonly=True,
        help="Complete raw form submission from Cognito.",
    )
    ai_analysis = fields.Json(
        readonly=True,
        help="AI analysis output from the lead_intake agent.",
    )

    # ═════════════════════════════════════════════════════════
    # Classification
    # ═════════════════════════════════════════════════════════

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

    # ═════════════════════════════════════════════════════════
    # Extracted Fields (denormalized for display)
    # ═════════════════════════════════════════════════════════

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

    # ═════════════════════════════════════════════════════════
    # Processing State
    # ═════════════════════════════════════════════════════════

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

    # ═════════════════════════════════════════════════════════
    # Links
    # ═════════════════════════════════════════════════════════

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

    # ═════════════════════════════════════════════════════════
    # Constraints
    # ═════════════════════════════════════════════════════════

    _check_unique_lead = models.Constraint(
        "unique(lead_id)",
        "A web lead with this ID already exists (idempotency guard).",
    )

    # ═════════════════════════════════════════════════════════
    # Core Logic — Create from Agent Payload
    # ═════════════════════════════════════════════════════════

    @api.model
    def create_from_agent(self, payload):
        """Create a web lead record from the lead_intake agent's output.

        Expected payload structure::

            {
                "lead_id": "WL123",
                "source": "cognito_form",
                "decision": "Hot",
                "decision_reasons": ["monthly_lbs >= 10000", ...],
                "raw_payload": { ... Cognito form fields ... },
                "ai_analysis": {
                    "quantity": {
                        "per_load_lbs": 40000,
                        "loads_per_month": 2,
                        "confidence": 0.85
                    },
                    "frequency": {
                        "frequency": "ongoing",
                        "confidence": 0.7
                    },
                    "material": { ... },
                    "observations": [ ... ]
                }
            }

        Returns the created web.lead record.
        """
        lead_id = payload.get("lead_id")
        if not lead_id:
            raise UserError("Missing required field: lead_id")

        # Idempotency: if already exists, return existing
        existing = self.search([("lead_id", "=", lead_id)], limit=1)
        if existing:
            _logger.info("Web lead %s already exists, returning existing.", lead_id)
            return existing

        raw = payload.get("raw_payload", {})
        ai = payload.get("ai_analysis", {})
        ai_qty = ai.get("quantity", {})
        ai_freq = ai.get("frequency", {})
        ai_material = ai.get("material", {})
        decision_raw = (payload.get("decision") or "cold").lower()

        # Extract contact fields from Cognito form
        company = raw.get("YourBusinessCompanyName", "").strip()
        contact = raw.get("YourName", "").strip()
        email = raw.get("Email", "").strip()
        phone = raw.get("Phone", "").strip()
        qty_text = raw.get("WhatIsTheQuantity", "")
        contaminants = raw.get("AreThereAnyContaminants", "")
        material_desc = raw.get("DescribeYourMaterial", "") or raw.get(
            "WhatTypeOfPlastic", ""
        )

        vals = {
            "lead_id": lead_id,
            "source": payload.get("source", "cognito_form"),
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

        # Process HOT leads immediately
        if lead.decision == "hot":
            lead._process_hot_lead()
        else:
            lead.write({"state": "skipped"})

        return lead

    def _process_hot_lead(self):
        """Convert a HOT web lead into a partner + intake record."""
        self.ensure_one()
        config = self.env["plasticos.web.lead.config"].get_config()

        try:
            # 1. Find or create partner
            partner = self._find_or_create_partner(config)
            self.write({"partner_id": partner.id})

            # 2. Create intake
            intake = self._create_intake(partner, config)
            self.write({
                "intake_id": intake.id,
                "state": "intake_created",
            })

            _logger.info(
                "HOT lead %s → partner %s, intake %s",
                self.lead_id, partner.id, intake.id,
            )

        except Exception as exc:
            _logger.exception("Error processing HOT lead %s", self.lead_id)
            self.write({
                "state": "error",
                "error_message": str(exc),
            })

    def _find_or_create_partner(self, config):
        """Find existing partner by company name or create a new one."""
        Partner = self.env["res.partner"]
        name = self.company_name or "Unknown Web Lead"

        # Try exact match first
        partner = Partner.search([("name", "=ilike", name)], limit=1)
        if partner:
            return partner

        if not config.auto_create_partner:
            raise UserError(
                f"No partner found for '{name}' and auto-create is disabled."
            )

        # Create new partner
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
        _logger.info("Auto-created partner '%s' (id=%s) from web lead.", name, partner.id)

        # Create contact under company if we have a contact name
        if self.contact_name:
            Partner.create({
                "name": self.contact_name,
                "parent_id": partner.id,
                "email": self.contact_email or False,
                "phone": self.contact_phone or False,
                "type": "contact",
            })

        return partner

    def _create_intake(self, partner, config):
        """Create a plasticos.intake record from this web lead."""
        ai = self.ai_analysis or {}
        ai_qty = ai.get("quantity", {})
        ai_freq = ai.get("frequency", {})
        ai_material = ai.get("material", {})

        # Map polymer from AI analysis
        polymer_raw = (
            ai_material.get("polymer", "")
            or ai_material.get("resin_type", "")
            or ""
        ).lower().strip()
        polymer = _POLYMER_MAP.get(polymer_raw, False)

        # Map form from AI analysis
        form_raw = (
            ai_material.get("form", "")
            or ai_material.get("material_form", "")
            or ""
        ).lower().strip()
        form = _FORM_MAP.get(form_raw, False)

        # Map frequency to deal_type
        freq_raw = (ai_freq.get("frequency") or "").lower()
        deal_type = _FREQUENCY_MAP.get(freq_raw, "spot")

        # Quantity — use AI output, fall back to 0 (will fail constraint)
        qty_per_load = _safe_int(ai_qty.get("per_load_lbs"), 40000)
        loads_per_month = _safe_int(ai_qty.get("loads_per_month"), 1)

        intake_vals = {
            "name": f"WEB-{self.lead_id}",
            "partner_id": partner.id,
            "source_type": config.default_source_type or "post_consumer",
            "quantity_per_load_lbs": max(qty_per_load, 1),
            "loads_per_month": max(loads_per_month, 0),
            "deal_type": deal_type,
            "contamination_notes": self.contaminant_notes or False,
            "match_status": "pending",
        }

        # Only set polymer/form if we have valid mapped values
        if polymer:
            intake_vals["polymer"] = polymer
        if form:
            intake_vals["form"] = form

        Intake = self.env["plasticos.intake"]
        intake = Intake.create(intake_vals)
        return intake

    # ═════════════════════════════════════════════════════════
    # Manual Actions
    # ═════════════════════════════════════════════════════════

    def action_retry_processing(self):
        """Retry processing a lead that errored."""
        for rec in self:
            if rec.state != "error":
                raise UserError("Only errored leads can be retried.")
            if rec.decision == "hot":
                rec._process_hot_lead()

    def action_force_create_intake(self):
        """Force-create an intake from a COLD lead (manual override)."""
        for rec in self:
            if rec.intake_id:
                raise UserError("Intake already exists for this lead.")
            config = self.env["plasticos.web.lead.config"].get_config()
            rec._process_hot_lead()
