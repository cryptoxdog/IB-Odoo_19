import json
import logging
import uuid

from odoo import api, fields, models
from odoo.exceptions import UserError

from .normalizer_config import FALLBACK_POLYMERS, PACKET_SCHEMA_VERSION

_logger = logging.getLogger(__name__)


class PlasticosIntakeNormalizer(models.Model):
    """Extends plasticos.intake with schema-driven normalization.

    The normalizer validates an intake record against the canonical
    schema (DevKit PlastOS v6.0), assembles a JSON packet containing
    all fields the L9 adapter needs, and stores it on the record.

    Design rules:
      - Pure _inherit, no _name redefinition.
      - No write() override.
      - No state mutation on other models.
      - All cron methods use @api.model.
    """

    _inherit = "plasticos.intake"

    # ── Fields written by normalizer (must exist for view and .write()) ────────
    normalized = fields.Boolean(
        string="Normalized",
        default=False,
        help="True after successful normalization (packet assembled).",
    )
    match_status = fields.Selection(
        selection=[
            ("pending", "Pending"),
            ("normalized", "Normalized"),
            ("error", "Error"),
        ],
        string="Match Status",
        default="pending",
    )
    last_packet_id = fields.Char(string="Last Packet ID", readonly=True)
    last_packet_version = fields.Char(string="Last Packet Version", readonly=True)
    last_packet_ts = fields.Datetime(string="Last Packet At", readonly=True)
    last_packet_payload = fields.Json(string="Last Packet Payload", readonly=True)

    # ── Additional fields for normalization audit ────────
    normalization_errors = fields.Json(
        string="Normalization Errors",
        help="JSON array of validation errors from the last normalization attempt.",
        readonly=True,
    )
    normalization_warnings = fields.Json(
        string="Normalization Warnings",
        help="JSON array of non-blocking warnings from the last normalization attempt.",
        readonly=True,
    )
    normalization_ts = fields.Datetime(
        string="Last Normalization",
        readonly=True,
    )

    # ═════════════════════════════════════════════════════
    # PUBLIC ACTIONS
    # ═════════════════════════════════════════════════════

    def action_normalize(self):
        """Validate and normalize a single intake (button action)."""
        self.ensure_one()
        # sudo: config may not be readable by all users
        config = self.env["plasticos.normalizer.config"].sudo().get_config()
        errors, warnings = self._validate_for_normalization(config)

        if errors:
            self.write(
                {
                    "normalization_errors": errors,
                    "normalization_warnings": warnings,
                    "normalization_ts": fields.Datetime.now(),
                    "match_status": "error",
                    "normalized": False,
                }
            )
            self._log_normalization("error", errors)
            raise UserError(
                f"Normalization failed with {len(errors)} error(s):\n\n"
                + "\n".join(f"• {e['field']}: {e['message']}" for e in errors)
            )

        packet = self._assemble_packet()
        packet_id = f"PKT-{uuid.uuid4().hex[:12].upper()}"

        self.write(
            {
                "normalized": True,
                "match_status": "normalized",
                "normalization_errors": None,
                "normalization_warnings": warnings or None,
                "normalization_ts": fields.Datetime.now(),
                "last_packet_id": packet_id,
                "last_packet_version": PACKET_SCHEMA_VERSION,
                "last_packet_payload": packet,
                "last_packet_ts": fields.Datetime.now(),
            }
        )
        self._log_normalization("normalized", None)

        # Geocode facility if not already populated
        self._ensure_facility_geocoded()

        _logger.info(
            "Intake %s normalized → packet %s (v%s)",
            self.name,
            packet_id,
            PACKET_SCHEMA_VERSION,
        )

    def action_mark_normalized(self):
        """Override the stub from plasticos_intake — route through normalizer."""
        for rec in self:
            rec.action_normalize()

    def _ensure_facility_geocoded(self):
        """Geocode facility/partner if coordinates not already populated.

        Called during normalization to ensure geo data is available for matching.
        Uses Odoo's native geo_localize() from base_geolocalize module.
        Falls back silently if geocoding fails (nightly cron will retry).
        """
        # Check facility first, then partner
        target = self.facility_id or self.partner_id
        if not target:
            return

        # Skip if already geocoded
        if target.partner_latitude and target.partner_latitude != 0.0:
            _logger.debug("Facility %s already geocoded (lat=%s)", target.name, target.partner_latitude)
            return

        # Skip if no address to geocode
        if not target.street and not target.city:
            _logger.debug("Facility %s has no address to geocode", target.name)
            return

        try:
            target.geo_localize()
            if target.partner_latitude and target.partner_latitude != 0.0:
                _logger.info(
                    "Geocoded facility %s during normalization: lat=%s, lon=%s",
                    target.name,
                    target.partner_latitude,
                    target.partner_longitude,
                )
        except Exception:
            _logger.warning(
                "Failed to geocode facility %s during normalization (will retry in nightly cron)",
                target.name,
                exc_info=True,
            )

    # ═════════════════════════════════════════════════════
    # BATCH CRON
    # ═════════════════════════════════════════════════════

    @api.model
    def cron_batch_normalize(self):
        """Normalize all pending intakes in batch.

        Called by ir.cron. Processes up to config.batch_limit records
        per run. Errors are stored per-record, not raised.
        """
        self.env.cr.execute(
            "SELECT pg_try_advisory_lock(hashtext(%s))", ["plasticos_intake_normalizer.cron_batch_normalize_intakes"]
        )
        locked = self.env.cr.fetchone()[0]
        if not locked:
            _logger.info("Skipping batch normalize cron: lock is already held.")
            return

        try:
            config = self.env["plasticos.normalizer.config"].sudo().get_config()  # cron-sudo-justification: config read
            limit = config.batch_limit or 200

            pending = self.search(
                [("normalized", "=", False), ("match_status", "=", "pending")],
                limit=limit,
                order="create_date ASC, id ASC",
            )

            _logger.info("Batch normalize: %d intakes to process.", len(pending))

            success_count = 0
            error_count = 0

            for rec in pending:
                try:
                    errors, warnings = rec._validate_for_normalization(config)

                    if errors:
                        rec.write(
                            {
                                "normalization_errors": errors,
                                "normalization_warnings": warnings,
                                "normalization_ts": fields.Datetime.now(),
                                "match_status": "error",
                                "normalized": False,
                            }
                        )
                        rec._log_normalization("error", errors)
                        error_count += 1
                        continue

                    packet = rec._assemble_packet()
                    packet_id = f"PKT-{uuid.uuid4().hex[:12].upper()}"

                    rec.write(
                        {
                            "normalized": True,
                            "match_status": "normalized",
                            "normalization_errors": None,
                            "normalization_warnings": warnings or None,
                            "normalization_ts": fields.Datetime.now(),
                            "last_packet_id": packet_id,
                            "last_packet_version": PACKET_SCHEMA_VERSION,
                            "last_packet_payload": packet,
                            "last_packet_ts": fields.Datetime.now(),
                        }
                    )
                    rec._log_normalization("normalized", None)
                    success_count += 1

                except Exception as exc:
                    _logger.exception(
                        "Unexpected error normalizing intake %s",
                        rec.name,
                    )
                    rec.write(
                        {
                            "normalization_errors": [{"field": "_system", "message": str(exc)}],
                            "normalization_ts": fields.Datetime.now(),
                            "match_status": "error",
                            "normalized": False,
                        }
                    )
                    error_count += 1

            _logger.info(
                "Batch normalize complete: %d success, %d errors out of %d.",
                success_count,
                error_count,
                len(pending),
            )
        finally:
            self.env.cr.execute(
                "SELECT pg_advisory_unlock(hashtext(%s))", ["plasticos_intake_normalizer.cron_batch_normalize_intakes"]
            )

    # ═════════════════════════════════════════════════════
    # VALIDATION ENGINE
    # ═════════════════════════════════════════════════════

    def _validate_for_normalization(self, config):
        """Validate this intake against the canonical schema.

        Returns (errors: list[dict], warnings: list[dict]).
        Each dict has keys: field, message, code.
        """
        self.ensure_one()
        errors = []
        warnings = []

        # ── Required fields ──────────────────────────────
        if not self.polymer_id:
            errors.append(
                {
                    "field": "polymer_id",
                    "message": "Polymer is required.",
                    "code": "INT-003",
                }
            )
        elif config.require_polymer_in_canonical:
            polymer_code = (self.polymer_id.code or "").strip().upper()
            canonical_polymers = self._get_canonical_polymers()
            if polymer_code not in canonical_polymers:
                errors.append(
                    {
                        "field": "polymer_id",
                        "message": f"Polymer '{self.polymer_id.name}' is not in the canonical "
                        f"polymer list. Accepted: {sorted(canonical_polymers)}",
                        "code": "INT-003",
                    }
                )

        if not self.form_id:
            errors.append(
                {
                    "field": "form_id",
                    "message": "Form is required.",
                    "code": "INT-007",
                }
            )

        if config.require_positive_quantity:
            if not self.quantity_per_load_lbs or self.quantity_per_load_lbs <= 0:
                errors.append(
                    {
                        "field": "quantity_per_load_lbs",
                        "message": "Quantity per load must be positive.",
                        "code": "INT-005",
                    }
                )

        if config.require_partner and not self.partner_id:
            errors.append(
                {
                    "field": "partner_id",
                    "message": "Partner is required.",
                    "code": "INT-004",
                }
            )

        # ── Range validations (non-blocking if field empty) ──
        if config.validate_density_range and self.density_value:
            density_min = config.density_min or 0.0
            density_max = config.density_max or 0.0
            if self.density_value <= 0:
                errors.append(
                    {
                        "field": "density_value",
                        "message": f"Density {self.density_value} must be greater than 0.",
                        "code": "INT-007",
                    }
                )
            elif density_max > 0 and not (density_min <= self.density_value <= density_max):
                errors.append(
                    {
                        "field": "density_value",
                        "message": f"Density {self.density_value} outside configured range "
                        f"{density_min}–{density_max} g/cm³.",
                        "code": "INT-007",
                    }
                )

        if config.validate_mfi_positive and self.mfi_value:
            if self.mfi_value < 0:
                errors.append(
                    {
                        "field": "mfi_value",
                        "message": f"MFI value {self.mfi_value} cannot be negative.",
                        "code": "INT-007",
                    }
                )

        # ── Warnings (non-blocking) ─────────────────────
        if not self.color_id:
            warnings.append(
                {
                    "field": "color_id",
                    "message": "Color not specified — matching may be less precise.",
                    "code": "WARN-001",
                }
            )

        if not self.loads_per_month:
            warnings.append(
                {
                    "field": "loads_per_month",
                    "message": "Loads per month not specified — defaults to 1.",
                    "code": "WARN-002",
                }
            )

        if not self.lat and not self.lon:
            warnings.append(
                {
                    "field": "geo",
                    "message": "No coordinates — geo-matching disabled for this intake.",
                    "code": "WARN-003",
                }
            )

        if not self.source_type_id:
            warnings.append(
                {
                    "field": "source_type_id",
                    "message": "Source type not specified — defaults to 'unknown'.",
                    "code": "WARN-004",
                }
            )

        # ── Material profile cross-check ─────────────────
        if hasattr(self, "material_profile_id") and self.material_profile_id:
            mp = self.material_profile_id
            if hasattr(mp, "polymer_id") and mp.polymer_id and self.polymer_id:
                mp_polymer = (mp.polymer_id.code or "").strip().upper()
                intake_polymer = (self.polymer_id.code or "").strip().upper()
                if mp_polymer and intake_polymer and mp_polymer != intake_polymer:
                    warnings.append(
                        {
                            "field": "polymer_id",
                            "message": f"Intake polymer '{self.polymer_id.name}' differs from "
                            f"material profile polymer '{mp.polymer_id.name}'. "
                            f"Verify alignment.",
                            "code": "WARN-005",
                        }
                    )

        return errors, warnings

    # ═════════════════════════════════════════════════════
    # PACKET ASSEMBLY
    # ═════════════════════════════════════════════════════

    def _assemble_packet(self):
        """Assemble the canonical L9-ready JSON packet.

        The packet structure is defined by the DevKit PlastOS v6.0
        intake_schema + schema_crosswalk. It contains everything
        the L9 adapter needs to run buyer matching.

        Returns a Python dict (stored as Json field).
        """
        self.ensure_one()

        packet = {
            "schema_version": PACKET_SCHEMA_VERSION,
            "intake_id": self.name,
            "odoo_record_id": self.id,
            # ── Identity ─────────────────────────────────
            "partner": self._assemble_partner_block(),
            # ── Quality Specs ────────────────────────────
            "quality": {
                "mfi_value": self.mfi_value or None,
                "density_value": self.density_value or None,
                "moisture_pct": self.moisture_pct or None,
                "contamination_pct": self.contamination_pct or None,
                "has_residue": self.has_residue,
                "attributes": self.material_attribute_ids.mapped("code"),
                "filler_type": self.filler_type_id.code if self.filler_type_id else None,
                "filler_pct": self.filler_pct or None,
                "contamination_notes": self.contamination_notes or None,
            },
            # ── Origin Intelligence ──────────────────────
            "origin": {
                "application": self.origin_application or None,
                "sector": self.origin_sector or None,
                "process_type": self.origin_process_type or None,
            },
            # ── Frequency (commercial terms) ─────────────
            "frequency": {
                "quantity_per_load_lbs": self.quantity_per_load_lbs,
                "loads_per_month": self.loads_per_month or 1,
                "deal_type": self.deal_type or "spot",
                "contract_duration_months": self.contract_duration_months or None,
            },
            # ── Geo ──────────────────────────────────────
            "geo": self._assemble_geo_block(),
            # ── Material Profile Enrichment ──────────────
            "material_profile": self._assemble_material_profile_block(),
            # ── Facility Capability Enrichment ───────────
            "facility_capability": self._assemble_facility_block(),
        }

        return packet

    def _assemble_partner_block(self):
        """Build the partner identity sub-block."""
        self.ensure_one()
        if not self.partner_id:
            return None

        partner = self.partner_id
        return {
            "id": partner.id,
            "name": partner.name,
            "email": partner.email or None,
            "phone": partner.phone or None,
            "city": partner.city or None,
            "state": partner.state_id.code if partner.state_id else None,
            "country": partner.country_id.code if partner.country_id else None,
        }

    def _assemble_geo_block(self):
        """Build the geo sub-block from intake coords + partner address."""
        self.ensure_one()
        geo = {
            "lat": self.lat or None,
            "lon": self.lon or None,
            "pickup_city": None,
            "pickup_state": None,
        }

        # Try facility first, then partner
        source = self.facility_id or self.partner_id
        if source:
            geo["pickup_city"] = source.city or None
            geo["pickup_state"] = source.state_id.code if source.state_id else None

        return geo

    def _assemble_material_profile_block(self):
        """Build the material profile enrichment sub-block.

        Only populated if material_profile_id is set (from PR #7).
        Uses hasattr for backward compatibility with repos that
        haven't merged the intake refactor yet.
        """
        self.ensure_one()
        if not hasattr(self, "material_profile_id") or not self.material_profile_id:
            return None

        mp = self.material_profile_id
        block = {
            "id": mp.id,
            "name": mp.name,
        }

        # polymer_id is from PR #6 (material profile unification)
        if hasattr(mp, "polymer_id") and mp.polymer_id:
            block["polymer_code"] = mp.polymer_id.code
            block["polymer_name"] = mp.polymer_id.name

        # Standard fields that exist on the base material_profile
        for fld in ("form", "color", "source_type", "grade"):
            if hasattr(mp, fld):
                block[fld] = getattr(mp, fld) or None

        return block

    def _assemble_facility_block(self):
        """Build the facility capability sub-block.

        Pulls from plasticos.facility.profile linked to the
        partner or facility. Uses hasattr for backward compat.
        """
        self.ensure_one()
        target = self.facility_id or self.partner_id
        if not target:
            return None

        # facility_profile is linked via partner
        if "plasticos.facility.profile" not in self.env:
            return None
        FP = self.env["plasticos.facility.profile"]

        profile = FP.search(
            [("partner_id", "=", target.id)],
            limit=1,
        )
        if not profile:
            return None

        block = {
            "id": profile.id,
            "partner_id": target.id,
            "partner_name": target.name,
        }

        # Capability fields from PR #5
        if hasattr(profile, "process_type"):
            block["process_type"] = profile.process_type or None
        if hasattr(profile, "feedstock_type"):
            block["feedstock_type"] = profile.feedstock_type or None
        if hasattr(profile, "capacity_lbs_month"):
            block["capacity_lbs_month"] = profile.capacity_lbs_month or None
        if hasattr(profile, "contamination_tolerance_pct"):
            block["contamination_tolerance_pct"] = profile.contamination_tolerance_pct or None

        # Accepted polymers (M2M from PR #5)
        if hasattr(profile, "accepted_polymer_ids") and profile.accepted_polymer_ids:
            block["accepted_polymers"] = [
                {"id": p.id, "code": p.code, "name": p.name} for p in profile.accepted_polymer_ids
            ]
        else:
            block["accepted_polymers"] = []

        return block

    # ═════════════════════════════════════════════════════
    # REFERENCE TABLE HELPERS
    # ═════════════════════════════════════════════════════

    def _get_canonical_polymers(self):
        """Get canonical polymer codes from plasticos.polymer table.

        Falls back to hardcoded list if table not available.
        Returns a frozenset of uppercase codes.
        """
        if "plasticos.polymer" not in self.env:
            return FALLBACK_POLYMERS
        Polymer = self.env["plasticos.polymer"]

        polymers = Polymer.search([("active", "=", True)])
        if not polymers:
            return FALLBACK_POLYMERS

        return frozenset(p.code.upper() for p in polymers if p.code)

    # ═════════════════════════════════════════════════════
    # LOGGING
    # ═════════════════════════════════════════════════════

    def _log_normalization(self, action, errors):
        """Write to plasticos.automation.log if the model exists."""
        self.ensure_one()
        if "plasticos.automation.log" not in self.env:
            return
        AutoLog = self.env["plasticos.automation.log"]

        detail = ""
        if errors:
            detail = json.dumps(errors, indent=2)

        try:
            # sudo: create audit log regardless of user permissions
            AutoLog.sudo().create(
                {
                    "model_name": "plasticos.intake",
                    "record_id": self.id,
                    "action_type": f"normalize_{action}",
                    "detail": detail or f"Packet {self.last_packet_id or 'N/A'}",
                }
            )
        except Exception:
            _logger.debug(
                "Could not write automation log for intake %s",
                self.name,
                exc_info=True,
            )
