import hashlib
import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING

import requests as http_requests

from odoo import api, fields, models
from odoo.exceptions import UserError

if TYPE_CHECKING:
    from odoo.addons.plasticos_inference_engine import InferenceEngine

_logger = logging.getLogger(__name__)

# Inference engine singleton (loaded once per worker)
_inference_engine: "InferenceEngine | None" = None


def _get_inference_classes():
    """Lazy load inference engine classes to avoid import error at module load time."""
    from odoo.addons.plasticos_inference_engine import InferenceEngine, InferenceRequest

    return InferenceEngine, InferenceRequest


# ── Normalization Maps ──────────────────────────────────────────
# Deterministic, static. Map AI extraction tokens to actual
# fields on plasticos.material.profile.
# Values aligned to csv_schema_index.json taxonomy.

POLYMER_NORMALIZE = {
    "hdpe": "HDPE",
    "pe-hd": "HDPE",
    "high density polyethylene": "HDPE",
    "hmw hdpe": "HMW HDPE",
    "hmw": "HMW HDPE",
    "ldpe": "LDPE",
    "pe-ld": "LDPE",
    "low density polyethylene": "LDPE",
    "lldpe": "LDPE",
    "pp": "PP",
    "polypropylene": "PP",
    "bopp": "BOPP",
    "biaxially oriented polypropylene": "BOPP",
    "pet": "PET",
    "polyester": "PET",
    "polyethylene terephthalate": "PET",
    "eps": "EPS",
    "expanded polystyrene": "EPS",
    "ps": "PS",
    "gpps": "PS",
    "polystyrene": "PS",
    "hips": "HIPS",
    "high impact polystyrene": "HIPS",
    "abs": "ABS",
    "acrylonitrile butadiene styrene": "ABS",
    "pc": "PC",
    "polycarbonate": "PC",
    "pc-pmma": "PC-PMMA",
    "pc/pmma": "PC-PMMA",
    "pmma": "PMMA",
    "acrylic": "PMMA",
    "pa": "PA",
    "nylon": "PA",
    "polyamide": "PA",
    "pvc": "PVC",
    "polyvinyl chloride": "PVC",
    "tpo": "TPO",
    "thermoplastic olefin": "TPO",
    "pp-pe": "PP-PE",
    "occ": "OCC",
    "old corrugated containers": "OCC",
    "mixed": "Mixed",
}

FORM_NORMALIZE = {
    "bag": "BAG",
    "bags": "BAG",
    "bale": "BALE",
    "bales": "BALE",
    "baled": "BALE",
    "chop": "CHOP",
    "chopped": "CHOP",
    "densified": "DENS",
    "dens": "DENS",
    "film": "FILM",
    "films": "FILM",
    "flake": "FLAKE",
    "flakes": "FLAKE",
    "flaked": "FLAKE",
    "gaylord": "GAY",
    "gaylords": "GAY",
    "log": "LOG",
    "logs": "LOG",
    "loose": "LOOSE",
    "pallet": "PAL",
    "pallets": "PAL",
    "parts": "PART",
    "part": "PART",
    "patty": "PATTY",
    "patties": "PATTY",
    "pellet": "PELL",
    "pellets": "PELL",
    "pelletized": "PELL",
    "purge": "PURG",
    "purgings": "PURG",
    "regrind": "RG",
    "regrinds": "RG",
    "reground": "RG",
    "repro": "REPRO",
    "reprocessed": "REPRO",
    "roll": "ROLL",
    "rolls": "ROLL",
    "rollstock": "ROLL",
    "sheet": "SHEET",
    "sheets": "SHEET",
    "shred": "SHRED",
    "shredded": "SHRED",
    "sweep": "SWEEP",
    "sweepings": "SWEEP",
}

SOURCE_TYPE_NORMALIZE = {
    "clean": "CLEAN",
    "contaminated": "CONT",
    "mixed": "MIXED",
    "off-grade": "OFF",
    "off grade": "OFF",
    "offgrade": "OFF",
    "post-consumer": "PC",
    "post consumer": "PC",
    "pcr": "PC",
    "post-industrial": "PI",
    "post industrial": "PI",
    "pir": "PI",
    "reusable": "REUSE",
    "no-value": "No-Value",
}

PROCESS_TYPE_NORMALIZE = {
    "injection": "injection",
    "injection molding": "injection",
    "injection moulding": "injection",
    "extrusion": "extrusion",
    "extruded": "extrusion",
    "blow molding": "blow_molding",
    "blow moulding": "blow_molding",
    "blow mold": "blow_molding",
    "thermoforming": "thermoforming",
    "thermoformed": "thermoforming",
    "rotomolding": "rotomolding",
    "rotational molding": "rotomolding",
    "film": "film",
    "blown film": "film",
    "cast film": "film",
    "compounding": "compounding",
    "compounded": "compounding",
}

# Map normalized process_type to plasticos.material.profile origin_process_type Selection
PROCESS_TYPE_TO_PROFILE = {
    "injection": "injection",
    "extrusion": "extrusion",
    "blow_molding": "blow_mold",
    "thermoforming": "thermoform",
    "rotomolding": "rotomold",
    "film": "film_blown",
    "compounding": "compounding",
}

# Map normalized form code (from FORM_NORMALIZE) to plasticos.material.form code
FORM_CODE_TO_MASTER = {
    "BAG": "OTHER",  # Bags are not a distinct form in seed data, map to OTHER
    "BALE": "BALES",
    "BALES": "BALES",
    "PELL": "PELLETS",
    "PELLET": "PELLETS",
    "RG": "REGRIND",
    "FLAKE": "FLAKE",
    "FILM": "ROLLSTOCK",
    "ROLL": "ROLLSTOCK",
    "SHEET": "SHEET",
    "PURG": "PURGE",
    "CHOP": "CHOPPED",
    "SHRED": "SHRED",
    "DENS": "DENSIFIED",
    "PART": "PARTS",
    "PATTY": "OTHER",
    "GAY": "OTHER",
    "LOG": "LOGS",
    "LOOSE": "LOOSE",
    "PAL": "PALLETS",
    "REPRO": "REGRIND",
    "SWEEP": "FLOORSWEEP",
}


class EnrichmentService(models.AbstractModel):
    _name = "plasticos.enrichment.service"
    _description = "AI-Powered CRM Enrichment Service"

    @api.model
    def _inference_stub_enabled(self):
        """Return True when inference must run in deterministic no-op mode."""
        ICP = self.env["ir.config_parameter"].sudo()
        enabled = (ICP.get_param("plasticos.inference_engine.enabled", "False") or "False").strip().lower()
        stubbed = (ICP.get_param("plasticos.inference_engine.stubbed", "True") or "True").strip().lower()
        return enabled not in {"1", "true", "yes", "on"} or stubbed in {"1", "true", "yes", "on"}

    # ── Inference Engine ────────────────────────────────────────

    @api.model
    def _get_inference_engine(self):
        """Return singleton inference engine (loaded once per worker)."""
        if self._inference_stub_enabled():
            _logger.info("Inference stub mode enabled; skipping inference engine initialization.")
            return None

        global _inference_engine
        if _inference_engine is None:
            try:
                InferenceEngine, _ = _get_inference_classes()
            except Exception as exc:
                _logger.warning("Inference classes unavailable; using no-op inference stub: %s", exc)
                return None
            # Primary KB location: resolve via odoo.addons to avoid brittle
            # relative parent-traversal that breaks if addon paths change.
            try:
                import importlib

                _ie_module = importlib.import_module("odoo.addons.plasticos_inference_engine")
                primary_kb_dir = Path(_ie_module.__file__).parent / "knowledge_base_v8.0"
            except Exception:
                # Fallback to legacy path traversal if import fails
                primary_kb_dir = (
                    Path(__file__).parent.parent.parent / "plasticos_inference_engine" / "knowledge_base_v8.0"
                )
            # Fallback: plasticos_enrichment/knowledge_base/ (legacy location)
            fallback_kb_dir = Path(__file__).parent.parent / "knowledge_base"

            if primary_kb_dir.exists():
                kb_dir = primary_kb_dir
            elif fallback_kb_dir.exists():
                kb_dir = fallback_kb_dir
                _logger.warning(
                    "Using fallback KB location: %s (primary not found: %s)",
                    fallback_kb_dir,
                    primary_kb_dir,
                )
            else:
                _logger.warning(
                    "Inference KB not found; using no-op inference stub. Checked: %s ; %s",
                    primary_kb_dir,
                    fallback_kb_dir,
                )
                return None

            _inference_engine = InferenceEngine(kb_dir)
            _logger.info(
                "Inference engine loaded from %s (polymers: %s)",
                kb_dir,
                ", ".join(_inference_engine.kb.polymers[:5]) + "..."
                if len(_inference_engine.kb.polymers) > 5
                else ", ".join(_inference_engine.kb.polymers),
            )
        return _inference_engine

    @api.model
    def run_inference(self, profile_vals: dict, entity_type: str = "supplier") -> dict:
        """
        Run inference engine on normalized profile values.
        Returns augmented profile_vals with inferred fields.

        Args:
            profile_vals: Dict with polymer, form, source_type, etc.
            entity_type: 'supplier', 'buyer', 'intake', 'material_profile'

        Returns:
            Dict with original + inferred fields (quality_tier, etc.)
        """
        engine = self._get_inference_engine()
        if engine is None:
            return dict(profile_vals)

        try:
            _, InferenceRequest = _get_inference_classes()
        except Exception as exc:
            _logger.warning("Inference request class unavailable; returning input unchanged: %s", exc)
            return dict(profile_vals)

        # Build inference request from profile_vals
        request = InferenceRequest(
            entity_type=entity_type,
            polymer=profile_vals.get("polymer"),
            form=profile_vals.get("form"),
            source_type=profile_vals.get("source_type"),
            process_type=profile_vals.get("origin_process_type"),
            mfi_value=profile_vals.get("melt_flow_index"),
            density_value=profile_vals.get("density"),
            contamination_pct=profile_vals.get("contamination_percent"),
            has_metal=profile_vals.get("has_metal"),
            has_fr=profile_vals.get("has_fr"),
            monthly_volume_lbs=profile_vals.get("monthly_volume_lbs"),
        )

        response = engine.infer(request)

        # Augment profile_vals with inferred fields (only if not already set)
        augmented = dict(profile_vals)

        # Quality tier
        if response.quality_tier.value != "unknown":
            if not augmented.get("quality_tier"):
                augmented["quality_tier"] = response.quality_tier.value
                _logger.debug(
                    "Inferred quality_tier=%s (conf=%.2f)",
                    response.quality_tier.value,
                    response.avg_confidence,
                )

        # Individual inferred fields
        for result in response.results:
            field_name = result.field
            # Map inference field names to profile field names
            field_map = {
                "mfi": "melt_flow_index",
                "density": "density",
                "moisture_ppm": "moisture_percent",
                "contamination_pct": "contamination_percent",
            }
            target_field = field_map.get(field_name, field_name)

            # Only fill if not already set and confidence is reasonable
            if not augmented.get(target_field) and result.confidence >= 0.6:
                augmented[target_field] = result.value
                _logger.debug(
                    "Inferred %s=%s (conf=%.2f, source=%s)",
                    target_field,
                    result.value,
                    result.confidence,
                    result.source.value,
                )

        return augmented

    @api.model
    def run_inference_on_profile(self, profile):
        """
        Run inference on an existing plasticos.material.profile record.
        Updates the record with inferred values (merge-not-overwrite).

        Args:
            profile: plasticos.material.profile recordset (single)

        Returns:
            Dict of fields that were updated.
        """
        profile.ensure_one()

        # Build profile_vals from existing record
        profile_vals = {
            "polymer": profile.polymer_id.code if profile.polymer_id else None,
            "form": profile.form_id.code if profile.form_id else None,
            "source_type": profile.source_type_id.code if profile.source_type_id else None,
            "origin_process_type": profile.origin_process_type,
            "melt_flow_index": profile.melt_flow_index,
            "density": profile.density,
            "contamination_percent": profile.contamination_percent,
            "has_metal": profile.has_metal,
            "has_fr": profile.has_fr,
            "monthly_volume_lbs": profile.monthly_volume_lbs,
        }

        # Determine entity type from partner
        entity_type = "supplier"
        if profile.partner_id:
            tags = profile.partner_id.category_id.mapped("name")
            if "Buyer" in tags or "Customer" in tags:
                entity_type = "buyer"

        augmented = self.run_inference(profile_vals, entity_type)

        # Merge-not-overwrite: only update fields that are empty
        update_vals = {}
        for field_name, value in augmented.items():
            if field_name in ("polymer", "form", "source_type"):
                continue  # Skip identity fields
            if value is not None and not getattr(profile, field_name, None):
                update_vals[field_name] = value

        if update_vals:
            profile.write(update_vals)
            _logger.info(
                "Inference updated profile %s: %s",
                profile.id,
                list(update_vals.keys()),
            )

        return update_vals

    # ── Resolve codes to material_profile master IDs ───────────

    @api.model
    def _resolve_polymer_id(self, code):
        """Resolve normalized polymer code to plasticos.polymer id.

        Handles mapping from POLYMER_NORMALIZE output to seed data codes.
        POLYMER_NORMALIZE produces uppercase with spaces/hyphens (e.g., "HMW HDPE", "PC-PMMA").
        Seed data uses UPPERCASE with underscores (e.g., "HDPE_HMW", "PC_PMMA").
        """
        if not code:
            return self.env["plasticos.polymer"]
        # Map normalized codes to seed data codes
        # Handles special cases where normalize output differs from seed code
        polymer_code_map = {
            "HMW HDPE": "HDPE_HMW",
            "PC-PMMA": "PC_PMMA",
            "PP-PE": "PP_PE",
            "PA": "NYLON",  # PA (Polyamide) stored as "NYLON" in seed data
            "Mixed": "MIXED",
        }
        c = polymer_code_map.get(code) or (code or "").strip().upper().replace(" ", "_").replace("-", "_")
        return self.env["plasticos.polymer"].search([("code", "=", c)], limit=1)

    @api.model
    def _resolve_form_id(self, code):
        """Resolve normalized form code to plasticos.material.form id."""
        if not code:
            return self.env["plasticos.material.form"]
        master_code = FORM_CODE_TO_MASTER.get((code or "").strip().upper())
        if not master_code:
            # Seed data uses UPPERCASE codes (BALES, PELLETS, etc.)
            master_code = (code or "").strip().upper()
        return self.env["plasticos.material.form"].search(
            [("code", "=", master_code)],
            limit=1,
        )

    @api.model
    def _resolve_source_type_id(self, code):
        """Resolve normalized source_type code to plasticos.source.type id."""
        if not code:
            return self.env["plasticos.source.type"]
        # SOURCE_TYPE_NORMALIZE uses PC, PI, CLEAN, etc.; master uses POST_CONSUMER, POST_INDUSTRIAL (UPPERCASE)
        st_map = {
            "PC": "POST_CONSUMER",
            "PI": "POST_INDUSTRIAL",
            "CLEAN": "PRIME",
            "CONT": "OFF_SPEC",
            "MIXED": "WIDE_SPEC",
            "OFF": "OFF_SPEC",
            "REUSE": "PRIME",
            "No-Value": False,
        }
        c = (code or "").strip()
        master_code = st_map.get(c) or c.upper().replace("-", "_")
        if not master_code:
            return self.env["plasticos.source.type"]
        return self.env["plasticos.source.type"].search(
            [("code", "=", master_code)],
            limit=1,
        )

    # ── Crawl ──────────────────────────────────────────────────

    @api.model
    def crawl_source(self, source):
        """Fetch content from a single enrichment.source record."""
        headers = {"User-Agent": "PlastOS-Enrichment/1.0"}
        try:
            resp = http_requests.get(
                source.url,
                headers=headers,
                timeout=30,
            )
            resp.raise_for_status()
            content = resp.text
            content_hash = hashlib.sha256(content.encode()).hexdigest()

            if content_hash == source.last_hash:
                _logger.info(
                    "Source %s unchanged, skipping.",
                    source.url,
                )
                return False

            source.write(
                {
                    "raw_content": content[:50000],
                    "last_hash": content_hash,
                    "last_crawled_at": fields.Datetime.now(),
                    "crawl_status": "success",
                    "error_message": False,
                }
            )
            return True
        except Exception as e:
            source.write(
                {
                    "crawl_status": "failed",
                    "error_message": str(e)[:500],
                }
            )
            _logger.error("Crawl failed for %s: %s", source.url, e)
            return False

    # ── AI Extraction ──────────────────────────────────────────

    @api.model
    def extract_from_source(self, source):
        """Route crawled content through AI extraction API."""
        if not source.raw_content:
            raise UserError(
                f"Source {source.url} has no crawled content.",
            )
        result = self._invoke_extraction_api(source)
        parsed = self._parse_extraction(result, source)
        source.write({"raw_content": False})
        return parsed

    def _invoke_extraction_api(self, source):
        """Call OpenAI-compatible API for structured extraction."""
        import os

        # sudo: ir.config_parameter requires elevated access to read system params
        ICP = self.env["ir.config_parameter"].sudo()
        endpoint = ICP.get_param("plasticos.enrichment.api_endpoint") or os.environ.get(
            "PLASTICOS_ENRICHMENT_API_ENDPOINT", "https://api.openai.com/v1/chat/completions"
        )
        api_key = ICP.get_param("plasticos.enrichment.api_key") or os.environ.get("OPENAI_API_KEY")
        model_name = ICP.get_param(
            "plasticos.enrichment.model",
            os.environ.get("PLASTICOS_ENRICHMENT_MODEL", "gpt-4o"),
        )

        if not endpoint:
            raise UserError(
                "Extraction API endpoint not configured. Set system parameter: plasticos.enrichment.api_endpoint "
                "or environment variable: PLASTICOS_ENRICHMENT_API_ENDPOINT"
            )

        if not api_key:
            raise UserError(
                "Extraction API key not configured. Set system parameter: plasticos.enrichment.api_key "
                "or environment variable: OPENAI_API_KEY"
            )

        system_prompt = (
            "You are a plastics recycling industry analyst. "
            "Extract all factual material identity data from the "
            "provided document for a buyer/supplier profile.\n\n"
            "For EACH distinct material the company handles, "
            "extract a separate object with these fields:\n"
            "- polymer: resin type (HDPE, PP, LDPE, PET, ABS, etc.)\n"
            "- subgrade: specific grade code if mentioned\n"
            "- form: physical form (bales, regrind, pellet, flake, "
            "film, roll, sheet, etc.)\n"
            "- source_type: clean, post-consumer, post-industrial, "
            "off-grade, mixed, contaminated\n"
            "- origin_process_type: injection, extrusion, "
            "blow_molding, thermoforming, film, compounding\n"
            "- previously_washed: true/false/null\n"
            "- previously_pelletized: true/false/null\n"
            "- melt_flow_index: numeric or null\n"
            "- density: numeric (g/cm3) or null\n"
            "- moisture_percent: numeric or null\n"
            "- contamination_percent: numeric or null\n"
            "- contains_metal: true/false/null\n"
            "- has_fr: true/false/null (flame retardant)\n"
            "- avg_lot_size_lbs: numeric or null\n"
            "- min_lot_size_lbs: numeric or null\n"
            "- max_lot_size_lbs: numeric or null\n"
            "- monthly_volume_lbs: numeric or null\n"
            "- food_grade: true/false/null\n"
            "- medical_grade: true/false/null\n\n"
            "For each field extraction also provide:\n"
            "- confidence: 0.0-1.0\n"
            "- inference_type: explicit / implicit / speculative\n"
            "- source_sentence: exact quote from the document\n\n"
            'Return JSON: {"materials": [...], '
            '"overall_confidence": float, '
            '"governance_flags": [...]}\n'
            "Use null for unknown fields. Never guess."
        )

        resp = http_requests.post(
            endpoint,
            json={
                "model": model_name,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": (
                            f"Source URL: {source.url}\n"
                            f"Source type: {source.source_type}\n\n"
                            f"{source.raw_content[:12000]}"
                        ),
                    },
                ],
                "temperature": 0.1,
            },
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=120,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        return json.loads(content)

    def _parse_extraction(self, result, source):
        """Validate and structure the AI response."""
        materials = result.get("materials", [])
        flags = result.get("governance_flags", [])
        overall = result.get("overall_confidence", 0)

        parsed_materials = []
        for mat in materials:
            if not mat.get("polymer"):
                flags.append(
                    "Material entry missing polymer — skipped.",
                )
                continue
            parsed_materials.append(mat)

        passed = overall >= 0.85 and len(flags) == 0 and len(parsed_materials) > 0

        return {
            "materials": parsed_materials,
            "overall_confidence": overall,
            "governance_passed": passed,
            "governance_flags": flags,
            "source_url": source.url,
        }

    # ── Normalization ──────────────────────────────────────────

    @api.model
    def normalize_material(self, raw_mat):
        """Normalize a single extracted material dict to PlastOS
        field values aligned with csv_schema_index taxonomy.

        Returns (profile_vals, provenance_items, unmapped).
        """
        profile_vals = {}
        provenance = []
        unmapped = []

        def _prov(field, value, raw_entry):
            provenance.append(
                {
                    "target_field": field,
                    "value": str(value),
                    "confidence": raw_entry.get("confidence", 0),
                    "inference_type": raw_entry.get(
                        "inference_type",
                        "implicit",
                    ),
                    "source_sentence": raw_entry.get(
                        "source_sentence",
                        "",
                    ),
                }
            )

        # ── polymer ──
        raw_polymer = (raw_mat.get("polymer") or "").strip().lower()
        norm = POLYMER_NORMALIZE.get(raw_polymer)
        if norm:
            profile_vals["polymer"] = norm
            _prov("polymer", norm, raw_mat)
        elif raw_polymer:
            profile_vals["polymer"] = raw_polymer.upper()
            _prov("polymer", raw_polymer.upper(), raw_mat)
            unmapped.append(("polymer", raw_mat.get("polymer")))

        # ── subgrade ──
        if raw_mat.get("subgrade"):
            profile_vals["subgrade"] = str(
                raw_mat["subgrade"],
            ).strip()
            _prov("subgrade", profile_vals["subgrade"], raw_mat)

        # ── form ──
        raw_form = (raw_mat.get("form") or "").strip().lower()
        norm_form = FORM_NORMALIZE.get(raw_form)
        if norm_form:
            profile_vals["form"] = norm_form
            _prov("form", norm_form, raw_mat)
        elif raw_form:
            unmapped.append(("form", raw_mat.get("form")))

        # ── source_type ──
        raw_st = (raw_mat.get("source_type") or "").strip().lower()
        norm_st = SOURCE_TYPE_NORMALIZE.get(raw_st)
        if norm_st:
            profile_vals["source_type"] = norm_st
            _prov("source_type", norm_st, raw_mat)
        elif raw_st:
            unmapped.append(
                (
                    "source_type",
                    raw_mat.get("source_type"),
                )
            )

        # ── origin_process_type (aligned to material_profile Selection) ──
        raw_pt = (raw_mat.get("origin_process_type") or "").strip().lower()
        norm_pt = PROCESS_TYPE_NORMALIZE.get(raw_pt)
        if norm_pt:
            profile_vals["origin_process_type"] = PROCESS_TYPE_TO_PROFILE.get(
                norm_pt,
                norm_pt,
            )
            _prov("origin_process_type", profile_vals["origin_process_type"], raw_mat)
        elif raw_pt:
            unmapped.append(
                (
                    "origin_process_type",
                    raw_mat.get("origin_process_type"),
                )
            )

        # ── boolean fields (contains_metal → has_metal for material_profile) ──
        for bf, raw_key in [
            ("previously_washed", "previously_washed"),
            ("previously_pelletized", "previously_pelletized"),
            ("has_metal", "contains_metal"),
            ("is_metalized", "is_metalized"),
            ("has_fr", "has_fr"),
            ("food_grade", "food_grade"),
            ("medical_grade", "medical_grade"),
        ]:
            val = raw_mat.get(raw_key)
            if val is not None and val is not False:
                profile_vals[bf] = bool(val)
                _prov(bf, bool(val), raw_mat)

        # ── float fields ──
        float_fields = [
            "melt_flow_index",
            "density",
            "moisture_percent",
            "contamination_percent",
            "avg_lot_size_lbs",
            "min_lot_size_lbs",
            "max_lot_size_lbs",
            "monthly_volume_lbs",
        ]
        for ff in float_fields:
            val = raw_mat.get(ff)
            if val is not None:
                try:
                    fval = float(val)
                    profile_vals[ff] = fval
                    _prov(ff, fval, raw_mat)
                except (ValueError, TypeError):
                    unmapped.append((ff, val))

        if unmapped:
            _logger.info("Unmapped extractions: %s", unmapped)

        return profile_vals, provenance, unmapped
