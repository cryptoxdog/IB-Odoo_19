# ═══════════════════════════════════════════════════════════
# Model : plasticos.web.lead
# Purpose: Web lead ingestion with AI-powered triage pipeline:
#          1. Receive a provider packet through the inbound adapter port
#          2. One broker inference call (text, photos, and PDF page text together)
#          3. Deterministic qualification decides HOT/REVIEW/COLD
#          4. HOT with a grounded per-load weight → one intake
#             HOT without that weight stays HOT in review, with no intake
# ═══════════════════════════════════════════════════════════
from __future__ import annotations

import base64
import logging
import re
import uuid
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

import psycopg2
import psycopg2.errorcodes
from markupsafe import escape

from odoo import api, fields, models
from odoo.exceptions import AccessError, ConcurrencyError, UserError

from ..adapters.base import (
    EVENT_SUBMITTED,
    PACKET_SCHEMA_VERSION,
    InboundEvent,
    WebLeadPacket,
    acquisition_rows,
    packet_to_dict,
)
from ..adapters.registry import get_adapter
from ..zip_place import resolve_pickup
from .attachment_processor import copy_successful_attachments_to_intake, process_attachments
from .classification_engine import (
    DISPOSITION_COLD,
    DISPOSITION_HOT,
    DISPOSITION_REVIEW,
    MASS_BASIS_CALCULATED,
    MASS_BASIS_SELLER_STATED,
    QUALIFICATION_MODE_LEGACY,
    QUALIFICATION_MODE_LIVE,
    agreed_confident_polymer,
    build_qualification_signals,
    classify_lead,
    derive_final_disposition,
    detect_hard_exclusions,
    detect_risk_indicators,
    mass_basis,
)
from .economic_policy import PLANNING_DEFAULTS_V1, evaluate_economic_eligibility
from .evidence_keys import (
    ASSESSMENT_STATUS_ASSESSED,
    ASSESSMENT_STATUS_UNAVAILABLE,
    KEY_ASSESSMENT,
    KEY_DECISION,
    KEY_ECONOMIC_ASSESSMENT,
    KEY_ECONOMIC_ELIGIBILITY,
    KEY_HOT_QUALIFIERS,
    KEY_MANUAL_OVERRIDE,
    KEY_QUALIFICATION,
    KEY_REASONS,
    KEY_REVIEW_REASONS,
    KEY_REVIEW_REQUIRED,
    KEY_STATUS,
    KEY_VALIDATION_ISSUES,
    KEY_VISION,
    scrub_acquisition_secrets,
)
from .evidence_reconciler import reconcile_evidence
from .inference_provider import InferenceProvider, run_broker_inference
from .material_catalog import CatalogEntry, accept_value, match_codes, match_distinct, split_phrase
from .material_identity import merge_form_and_grade, split_material_code
from .quantity_normalizer import QuantityEvidence, normalize_quantity_evidence
from .triage_helpers import SINGLE_LOAD_REVIEW_CAP_LBS, WEIGHT_SOURCE_AREA, replay_stored_mass

_logger = logging.getLogger(__name__)

# One multimodal broker call replaces text normalization, per-image vision, and
# the economic provider call. Lane A owns ``run_broker_inference``. Lane B owns
# ``PLANNING_DEFAULTS_V1``. This flag is the switch those lanes read.
ONE_PASS_ORCHESTRATION = True
_PARSE_STATUS_PARSED = "parsed"
_ALIGNMENT_STATUS_ALIGNED = "aligned"
_REPRESENTATIVENESS_WHOLE_LOT = "confirmed_whole_lot"

# Identity of Lane B's planning object. The pound figures stay inside that object.
_PLANNING_POLICY_REF = "web-lead-planning-defaults/v1"
_GROUNDED_MASS_BASES = frozenset({MASS_BASIS_SELLER_STATED, MASS_BASIS_CALCULATED})
_WEIGHT_KEYS_NOT_GROUNDED = frozenset({"estimated_lbs", "estimated_lbs_per_load", "estimated_lbs_high", "lbs_source"})
_MFI_PROPERTIES = frozenset({"mfi", "melt flow", "melt flow index", "melt index"})
_DENSITY_PROPERTIES = frozenset({"density", "specific gravity"})
_MOISTURE_PROPERTIES = frozenset({"moisture", "moisture content", "moisture pct"})
_MFI_UNITS = frozenset({"g/10min", "dg/min"})
_DENSITY_UNITS = frozenset({"g/cm3", "g/cm³", "g/cm^3", "g/cc", "g/ml"})
_MOISTURE_UNITS = frozenset({"%", "percent", "pct", "wt%", "wt.%"})
_WHOLE_LOT_PHRASE = re.compile(r"\b(?:entire|whole)\b.{0,48}\b(?:offered\s+lot|lot|load)\b", re.IGNORECASE)
_PHOTO_WORD = re.compile(r"\b(?:photo|photos|picture|pictures|image|images)\b", re.IGNORECASE)
_SPEC_WORD = re.compile(r"\b(?:spec|specs|specification|specifications|datasheet|data\s+sheet)\b", re.IGNORECASE)
_ALIGNMENT_LABELS = {
    "aligned": "Aligned",
    "possible_variance": "Possible variance",
    "offer_variance": "Offer variance",
    "unknown": "Unknown",
}


def _json_ready(value: Any) -> Any:
    """Ordinary JSON values. A planning dataclass is never stored."""
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    if isinstance(value, Mapping):
        return {str(key): _json_ready(item) for key, item in value.items()}
    return str(value)


def _planning_basis(defaults: Any) -> dict[str, Any]:
    """Lane B's planning object, as JSON, for the evidence bundle only.

    Pound figures are not copied onto a load-weight field.
    """
    if hasattr(defaults, "as_evidence"):
        payload = defaults.as_evidence()
    elif isinstance(defaults, Mapping):
        payload = _json_ready(dict(defaults))
    else:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    payload.setdefault("policy_ref", _PLANNING_POLICY_REF)
    return payload


def _seller_claims_for_broker(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    """Seller facts for the one call, without signed URLs or contact channels."""
    claims = scrub_acquisition_secrets(payload)
    for key in ("contact_name", "contact_email", "contact_phone"):
        claims.pop(key, None)
    return claims


def _image_content_bytes(payload: Any) -> bytes:
    """Decode an attachment's stored base64 payload into image bytes."""
    raw = payload.encode("ascii", errors="ignore") if isinstance(payload, str) else payload
    if not isinstance(raw, (bytes, bytearray)) or not raw:
        return b""
    try:
        decoded = base64.b64decode(bytes(raw), validate=False)
    except (ValueError, TypeError):
        return b""
    return decoded or b""


def _pdf_page_strings(documents: list[dict[str, Any]]) -> list[str]:
    """Page strings a caller already extracted. Bytes and empty pages stay out."""
    pages: list[str] = []
    for document in documents:
        for page in document.get("pages") or []:
            if not isinstance(page, Mapping):
                continue
            text = page.get("text")
            if page.get("parse_status") == _PARSE_STATUS_PARSED and isinstance(text, str) and text.strip():
                pages.append(text)
    return pages


def _reading_from_broker(result: Mapping[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Material and photo rows from the one broker result, never a second call."""
    inner = result.get("evidence_bundle") if isinstance(result.get("evidence_bundle"), Mapping) else {}
    decisions = result.get("decision_inputs") if isinstance(result.get("decision_inputs"), Mapping) else {}
    normalized = decisions.get("ai_normalized")
    if not isinstance(normalized, Mapping):
        normalized = inner.get("ai") if isinstance(inner.get("ai"), Mapping) else {}
    material = {key: value for key, value in dict(normalized).items() if key not in _WEIGHT_KEYS_NOT_GROUNDED}
    photos = inner.get("photo_findings")
    if not isinstance(photos, list):
        photos = inner.get("vision") if isinstance(inner.get("vision"), list) else []
    return material, [dict(row) for row in photos if isinstance(row, Mapping)]


def _grounded_load_lbs(quantity_evidence: QuantityEvidence | None) -> int:
    """Seller-stated or seller-calculated per-load pounds. Planning mass is not grounded."""
    if quantity_evidence is None:
        return 0
    lbs = float(quantity_evidence.load_weight_lbs or 0)
    if mass_basis(quantity_evidence.weight_source, lbs) not in _GROUNDED_MASS_BASES or lbs <= 0:
        return 0
    return int(lbs)


def _broker_request_media(
    lead: Any, rows: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Images for the one call, PDF pages already on the rows, and media that stayed unknown."""
    images: list[dict[str, Any]] = []
    documents: list[dict[str, Any]] = []
    omissions: list[dict[str, Any]] = []
    attachments = lead.env["ir.attachment"]
    for index, row in enumerate(rows):
        content_type = str(row.get("content_type") or "")
        position = row.get("attachment_index", index)
        if content_type.startswith("image/"):
            source_ref = f"photo.{position}"
            stored = attachments.browse(row.get("ir_attachment_id")) if row.get("ir_attachment_id") else attachments
            content = (
                _image_content_bytes(stored.datas) if row.get("acquisition_status") == "success" and stored else b""
            )
            if content:
                image: dict[str, Any] = {}
                image["source_ref"] = source_ref
                image["source_id"] = row.get("source_id")
                image["content_type"] = content_type
                image["content"] = content
                images.append(image)
            else:
                error = row.get("error") if isinstance(row.get("error"), Mapping) else {}
                omissions.append(
                    {
                        "source_ref": source_ref,
                        "kind": "photo",
                        "parse_status": "unknown",
                        "reason": (
                            "image_bytes_missing"
                            if row.get("acquisition_status") == "success" and not error.get("code")
                            else error.get("code") or row.get("analysis_status") or "image_unavailable"
                        ),
                    }
                )
            continue
        if content_type == "application/pdf":
            source_ref = f"pdf.{position}"
            pages = [dict(page) for page in row.get("pages") or [] if isinstance(page, Mapping)]
            documents.append({"source_ref": source_ref, "source_id": row.get("source_id"), "pages": pages})
            parsed = [page for page in pages if page.get("parse_status") == _PARSE_STATUS_PARSED and page.get("text")]
            if not parsed:
                error = row.get("error") if isinstance(row.get("error"), Mapping) else {}
                omissions.append(
                    {
                        "source_ref": source_ref,
                        "kind": "pdf",
                        "parse_status": "unknown",
                        "reason": error.get("code") or "document_text_extraction_not_enabled",
                    }
                )
            continue
        error = row.get("error") if isinstance(row.get("error"), Mapping) else {}
        omissions.append(
            {
                "source_ref": f"file.{position}",
                "kind": "file",
                "parse_status": "unknown",
                "reason": error.get("code") or row.get("analysis_status") or "unsupported",
            }
        )
    return images, documents, omissions


def _assessment_record(result: Mapping[str, Any]) -> dict[str, Any]:
    """Map the one-pass qualification onto the assessment record the validator already reads."""
    embedded = result.get("economic_assessment") or result.get(KEY_ECONOMIC_ASSESSMENT)
    if isinstance(embedded, Mapping) and embedded.get(KEY_STATUS):
        return dict(embedded)
    qualification = result.get("qualification") if isinstance(result.get("qualification"), Mapping) else {}
    recommendation = qualification.get("recommended_disposition")
    known = recommendation in {DISPOSITION_HOT, DISPOSITION_REVIEW, DISPOSITION_COLD}
    status = result.get(KEY_STATUS)
    if status not in {ASSESSMENT_STATUS_ASSESSED, ASSESSMENT_STATUS_UNAVAILABLE, "invalid"}:
        status = ASSESSMENT_STATUS_ASSESSED if known else ASSESSMENT_STATUS_UNAVAILABLE
    contradictory = qualification.get("contradictory_evidence_refs")
    if not isinstance(contradictory, list):
        contradictory = qualification.get("negative_evidence_refs") or []
    clarifications = qualification.get("recommended_clarification") or []
    record: dict[str, Any] = {
        "schema_version": result.get("schema_version") or "web-lead-broker-inference/v1",
        KEY_STATUS: status,
        KEY_ASSESSMENT: {
            "recommended_disposition": recommendation if known else None,
            "opportunity_signal": qualification.get("opportunity_signal") or "unknown",
            "commercial_rationale": qualification.get("commercial_rationale") or "",
            "supporting_evidence_refs": list(qualification.get("supporting_evidence_refs") or []),
            "contradictory_evidence_refs": list(contradictory),
            "missing_information": list(qualification.get("missing_information") or []),
            "recommended_clarification": list(clarifications),
            "clarifications": list(clarifications),
        },
    }
    if status != ASSESSMENT_STATUS_ASSESSED:
        record["reason"] = result.get("reason") or "broker_inference_unavailable"
    return record


def _apply_one_pass_evidence(
    bundle: dict[str, Any], result: Mapping[str, Any], media_omissions: list[dict[str, Any]]
) -> dict[str, Any]:
    """Write the one broker bundle onto the lead. Planning mass stays inside planning_basis."""
    inner = result.get("evidence_bundle") if isinstance(result.get("evidence_bundle"), Mapping) else {}
    alignment = inner.get("alignment")
    if not isinstance(alignment, Mapping):
        alignment = result.get("representation_alignment")
    if not isinstance(alignment, Mapping):
        alignment = {}
        alignment["status"] = "unknown"
        alignment["representativeness"] = "unknown"
        alignment["source_refs"] = []
    bundle["representation_alignment"] = dict(alignment)
    bundle["planning_basis"] = _planning_basis(PLANNING_DEFAULTS_V1)
    bundle["media_omissions"] = list(media_omissions)
    specs = inner.get("document_specifications")
    bundle["document_specifications"] = list(specs) if isinstance(specs, list) else []
    photos = inner.get("photo_findings")
    if not isinstance(photos, list):
        photos = inner.get("vision") if isinstance(inner.get("vision"), list) else []
    bundle["photo_findings"] = list(photos)
    pages = inner.get("pdf_page_text")
    if isinstance(pages, list):
        bundle["pdf_page_text"] = list(pages)
    economic = inner.get(KEY_ECONOMIC_ASSESSMENT)
    if isinstance(economic, Mapping) and economic.get(KEY_STATUS):
        bundle[KEY_ECONOMIC_ASSESSMENT] = dict(economic)
    else:
        bundle[KEY_ECONOMIC_ASSESSMENT] = _assessment_record(result)
    issues = result.get(KEY_VALIDATION_ISSUES)
    if isinstance(issues, list):
        bundle["broker_validation_issues"] = list(issues)
    if result.get(KEY_STATUS):
        bundle["broker_status"] = result.get(KEY_STATUS)
    if result.get("reason"):
        bundle["broker_reason"] = result.get("reason")
    return bundle


def _property_aliases(name: str) -> tuple[str, ...]:
    if name in _MFI_PROPERTIES:
        return ("melt flow index", "melt flow rate", "melt flow", "melt index", "mfi", "mfr")
    if name in _DENSITY_PROPERTIES:
        return ("specific gravity", "density")
    if name in _MOISTURE_PROPERTIES or name.startswith("moisture"):
        return ("moisture content", "moisture")
    text = " ".join(name.split())
    return (text,) if text else ()


def _number_in_text(text: str, value: float) -> bool:
    forms = {f"{value:g}", str(value)}
    if value == int(value):
        forms.add(str(int(value)))
    for form in forms:
        if re.search(rf"(?<![\d.]){re.escape(form)}(?![\d.])", text):
            return True
    return False


def _unit_in_text(text: str, unit: Any) -> bool:
    key = re.sub(r"\s+", "", str(unit or "").casefold())
    if not key:
        return False
    return key in re.sub(r"\s+", "", text.casefold())


def _text_substantiates(text: str, row: Mapping[str, Any]) -> bool:
    """The cited text states this property, this number, and this unit."""
    haystack = text.casefold()
    name = _spec_property_name(row)
    if not any(alias and alias in haystack for alias in _property_aliases(name)):
        return False
    number = _spec_float(row)
    if number is None or not _number_in_text(haystack, number):
        return False
    return _unit_in_text(haystack, row.get("unit"))


def _photo_finding_text(photo: Mapping[str, Any]) -> str:
    skipped = {"source_id", "source_ref", "content", "content_type", "content_sha256"}
    return "\n".join(str(value) for key, value in photo.items() if key not in skipped and isinstance(value, str))


def _citation_text(ref: Any, bundle: Mapping[str, Any]) -> str:
    text = str(ref or "").strip()
    if not text:
        return ""
    if text.startswith("seller."):
        seller = bundle.get("seller") if isinstance(bundle.get("seller"), Mapping) else {}
        value = seller.get(text.split(".", 1)[1])
        return value.strip() if isinstance(value, str) else ""
    photos = bundle.get("photo_findings") if isinstance(bundle.get("photo_findings"), list) else []
    if text.startswith("vision."):
        suffix = text.split(".", 1)[1]
        if suffix.isdigit() and 0 <= int(suffix) < len(photos) and isinstance(photos[int(suffix)], Mapping):
            return _photo_finding_text(photos[int(suffix)])
        return ""
    if text.startswith("pdf.page."):
        pages = bundle.get("pdf_page_text") if isinstance(bundle.get("pdf_page_text"), list) else []
        suffix = text.rsplit(".", 1)[-1]
        if suffix.isdigit() and 0 <= int(suffix) < len(pages):
            return str(pages[int(suffix)] or "").strip()
        return ""
    for photo in photos:
        if isinstance(photo, Mapping) and text in {photo.get("source_id"), photo.get("source_ref")}:
            return _photo_finding_text(photo)
    return ""


def _admitted_photo(bundle: Mapping[str, Any]) -> bool:
    photos = bundle.get("photo_findings")
    if not isinstance(photos, list):
        photos = bundle.get("vision") if isinstance(bundle.get("vision"), list) else []
    return any(isinstance(photo, Mapping) and (photo.get("source_id") or photo.get("source_ref")) for photo in photos)


def _seller_confirmation_text(bundle: Mapping[str, Any], alignment: Mapping[str, Any]) -> str:
    ref = str(alignment.get("seller_confirmation_ref") or "").strip()
    if not ref.startswith("seller."):
        return ""
    return _citation_text(ref, bundle)


def _bundle_has_substantiated_spec(bundle: Mapping[str, Any]) -> bool:
    rows = bundle.get("document_specifications")
    if not isinstance(rows, list):
        return False
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        refs = row.get("source_refs") or []
        if isinstance(refs, str):
            refs = [refs]
        if any(_text_substantiates(_citation_text(ref, bundle), row) for ref in refs):
            return True
    return False


def representation_alignment_label(bundle: Mapping[str, Any] | None) -> str:
    """Category label. 100/100 requires checked photo, spec, and seller coverage.

    The model's own coverage flags are not verification. The score is a display
    string and is not stored as a measurement.
    """
    evidence = bundle if isinstance(bundle, Mapping) else {}
    alignment = evidence.get("representation_alignment")
    if not isinstance(alignment, Mapping):
        alignment = {}
    status = str(alignment.get("status") or "unknown")
    label = _ALIGNMENT_LABELS.get(status, status)
    if status != _ALIGNMENT_STATUS_ALIGNED or alignment.get("representativeness") != _REPRESENTATIVENESS_WHOLE_LOT:
        return label
    confirmation = _seller_confirmation_text(evidence, alignment)
    confirmed = (
        _admitted_photo(evidence)
        and _bundle_has_substantiated_spec(evidence)
        and bool(_WHOLE_LOT_PHRASE.search(confirmation))
        and bool(_PHOTO_WORD.search(confirmation))
        and bool(_SPEC_WORD.search(confirmation))
    )
    if confirmed:
        return "100/100"
    return label


def _spec_property_name(row: Mapping[str, Any]) -> str:
    return " ".join(str(row.get("property") or "").casefold().replace("%", " ").split())


def _spec_float(row: Mapping[str, Any]) -> float | None:
    raw = row.get("value")
    if isinstance(raw, bool) or raw is None or (isinstance(raw, str) and re.search(r"\bto\b|-", raw)):
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    text = str(raw).strip().replace(",", "")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _spec_unit_supported(name: str, unit: Any) -> bool:
    key = str(unit or "").strip().casefold()
    if name in _MFI_PROPERTIES:
        return key in _MFI_UNITS
    if name in _DENSITY_PROPERTIES:
        return key in _DENSITY_UNITS
    if name in _MOISTURE_PROPERTIES or name.startswith("moisture"):
        return key in _MOISTURE_UNITS
    return False


def _spec_ref_resolves(ref: Any, bundle: Mapping[str, Any], row: Mapping[str, Any]) -> bool:
    """The cited seller text, photo finding, or PDF page states this spec."""
    return _text_substantiates(_citation_text(ref, bundle), row)


def _intake_spec_facts(specs: Any, bundle: Mapping[str, Any] | None = None) -> tuple[dict[str, float], str]:
    """Intake columns only when one substantiated value agrees.

    The cited text must state the property, the number, and the unit. Two
    different values for the same property stay in the notes and fill no column.
    """
    evidence = bundle if isinstance(bundle, Mapping) else {}
    measures: dict[str, float] = {}
    notes: list[str] = []
    seen: dict[str, set[float]] = {}
    proven: dict[str, set[float]] = {}
    if not isinstance(specs, list):
        return measures, ""
    for row in specs:
        if not isinstance(row, Mapping):
            continue
        name = _spec_property_name(row)
        refs = [str(item) for item in row.get("source_refs") or [] if item]
        detail = f"{row.get('property')}: {row.get('value')} {row.get('unit') or ''}".strip()
        if row.get("test_conditions"):
            detail += f" ({row.get('test_conditions')})"
        if refs:
            detail += f" [{', '.join(refs)}]"
        notes.append(detail)
        target = None
        if name in _MFI_PROPERTIES:
            target = "mfi_value"
        elif name in _DENSITY_PROPERTIES:
            target = "density_value"
        elif name in _MOISTURE_PROPERTIES or name.startswith("moisture"):
            target = "moisture_pct"
        number = _spec_float(row)
        if target is None or number is None:
            continue
        seen.setdefault(target, set()).add(number)
        if _spec_unit_supported(name, row.get("unit")) and any(_spec_ref_resolves(ref, evidence, row) for ref in refs):
            proven.setdefault(target, set()).add(number)
    for target, numbers in seen.items():
        if len(numbers) == 1 and proven.get(target) == numbers:
            measures[target] = next(iter(numbers))
    return measures, "\n".join(note for note in notes if note)


# Identity namespace of rejected inbound deliveries. Distinct from the packet
# idempotency key so a later valid resubmission is admitted, not replayed.
REJECTED_LEAD_PREFIX = "REJ-"

# A lead becomes broker-approved only through
# ``action_approve_for_commercial_preparation``, which mints the immutable
# review snapshot in the same transaction. That action marks its status write
# with a module-private object token; RPC clients can only send JSON values in
# a context, so no remote caller (and no ``sudo()``) can reproduce it.
_APPROVAL_STATUS_KEY = "plasticos_web_leads_approval_status_write"
_APPROVAL_STATUS_TOKEN = object()
REVIEW_STATUS_APPROVED = "approved"

# ── Pallet weight assumption when no lbs given ───────────────────────────────
_LBS_PER_PALLET_ASSUMPTION = 1_500  # conservative: typical plastic pallet

# Active rows of the ten vocabulary masters. Inactive rows, including form BALES, stay out.
_CATALOG_MODELS: tuple[tuple[str, str], ...] = (
    ("polymer", "plasticos.polymer"),
    ("form", "plasticos.material.form"),
    ("material_grade", "plasticos.material.grade"),
    ("quality_tier", "plasticos.material.quality.tier"),
    ("source_type", "plasticos.source.type"),
    ("color", "plasticos.material.color"),
    ("attribute", "plasticos.material.attribute"),
    ("filler", "plasticos.filler.type"),
    ("packaging", "plasticos.packaging.type"),
    ("process", "plasticos.process.type"),
)
_OMIT_ATTRIBUTE_CODES = frozenset({"reusable"})


def _merged_attributes(
    attribute_text: Any,
    seller_attributes: tuple[str, ...],
    photo_rows: list[dict[str, Any]],
    catalog: Mapping[str, tuple[CatalogEntry, ...]],
) -> tuple[str, ...]:
    """Joint attribute codes, or the seller phrase plus photo codes. reusable is a quality tier."""
    if isinstance(attribute_text, (list, tuple)):
        attribute_text = " ".join(str(item) for item in attribute_text)
    joint = tuple(
        code
        for code in match_codes(str(attribute_text or ""), catalog.get("attribute", ()))
        if code.casefold() not in _OMIT_ATTRIBUTE_CODES
    )
    if joint:
        return joint
    photo_values = [
        str(item)
        for row in photo_rows
        if isinstance(row, dict) and not row.get("error")
        for item in (
            row.get("observed_attributes")
            if isinstance(row.get("observed_attributes"), (list, tuple))
            else [row.get("observed_attributes")]
        )
        if item
    ]
    seen: list[str] = []
    for code in (*seller_attributes, *match_codes(" ".join(photo_values), catalog.get("attribute", ()))):
        if code.casefold() in _OMIT_ATTRIBUTE_CODES or code in seen:
            continue
        seen.append(code)
    return tuple(seen)


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


def _declared_material_text(canonical: dict, raw: dict) -> str:
    """The seller's own material words, as the merge and the stored-evidence replay read them."""
    return " ".join(
        str(value or "")
        for value in (
            canonical.get("material_description"),
            canonical.get("material_composition_text"),
            raw.get("DescribeYourMaterial"),
            raw.get("WhatIsIt"),
        )
    )


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
    REVIEW leads keep their evidence and get an assigned broker activity; no intake.
    COLD leads are stored for reference but do not create downstream records.

    Pipeline (admit_inbound → create_from_packet):
      1. Project the provider payload into a provider-neutral packet
      2. Create web.lead record (decision=review, state=received: not yet classified)
      3. _run_triage_pipeline():
           a. Image analysis (Vision)
           b. AI normalization (LLM), with those photo rows as well as the seller text
           c. _merge_ai_and_vision() — weight fallback cascade here
           d. classify_lead() — legacy HOT/COLD, kept for shadow comparison
           e. commercial qualification → validated HOT/REVIEW/COLD (live mode routes on it)
           f. HOT → _create_intake() + notify admin; REVIEW → broker activity
           f. Submitted photos are already stored, on HOT and on COLD
    """

    _name = "plasticos.web.lead"
    _description = "Web Lead"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "submitted_at desc, id desc"
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
    submitted_at = fields.Datetime(
        string="Submitted",
        index=True,
        tracking=True,
        help="When the seller submitted the form. The list sorts on this date.",
    )
    assigned_user_id = fields.Many2one(
        "res.users",
        string="Assigned To",
        tracking=True,
        index=True,
        ondelete="set null",
        domain=[("share", "=", False)],
        help="Queue assignee until an opportunity exists. The opportunity salesperson is the commercial owner after that.",
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
    representation_alignment_display = fields.Char(
        string="Representation Alignment",
        compute="_compute_representation_alignment_display",
        help=(
            "Display only. 100/100 appears only when the photo and the specs are cited as the whole "
            "offered lot. This is not a stored score, a purity claim, or a weight."
        ),
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
            ("review", "REVIEW"),
            ("cold", "COLD"),
        ],
        required=True,
        # A lead that has not been classified yet is not COLD. ``state`` tells an
        # unprocessed lead (received / error) from a completed REVIEW (review_pending).
        default="review",
        index=True,
        tracking=True,
        help=(
            "HOT: commercially compelling, an intake exists for broker review. "
            "REVIEW: potentially valuable, a broker must clarify missing or conflicting facts. "
            "COLD: clearly unsuitable on direct evidence."
        ),
    )
    decision_reasons = fields.Json(
        readonly=True,
        help="Reasons for the HOT/REVIEW/COLD disposition, including the model recommendation and any override.",
    )

    # ═══════════════════════════════════════════════════════════
    # Extracted Fields (denormalized for display)
    # ═══════════════════════════════════════════════════════════

    company_name = fields.Char(string="Company")
    contact_name = fields.Char(string="Contact Name")
    contact_email = fields.Char(string="Contact Email")
    contact_phone = fields.Char(string="Contact Phone")
    pickup_postal_code = fields.Char(
        string="ZIP",
        index=True,
        help="Pickup ZIP as the seller submitted it. Location is derived from these digits.",
    )
    pickup_location_text = fields.Char(
        string="Seller Location",
        help="The seller's own location words. They are kept and are not turned into Location.",
    )
    pickup_place = fields.Char(
        string="Location",
        readonly=True,
        index=True,
        help="Preferred city and state for the pickup ZIP, for example Charlotte, NC.",
    )
    material_description = fields.Text(string="Material Description")
    quantity_text = fields.Char(
        string="Quantity (Form Input)",
        help="Raw quantity text from the form — unprocessed, for display only.",
    )
    estimated_lbs_per_load = fields.Integer(string="Lbs/Load")
    estimated_lbs_high = fields.Integer(
        string="Lbs High",
        help="High end of a seller weight range. Empty when the seller stated one weight.",
    )
    lead_image_ids = fields.Many2many(
        "ir.attachment",
        string="Lead Images",
        compute="_compute_lead_image_ids",
        help="Image files already stored on this lead. A cold decision does not remove them.",
    )
    estimated_loads_per_month = fields.Integer(string="Loads/Month")
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
            ("review_pending", "Review Pending"),
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
            "Internal human-review handoff state for a HOT intake, a REVIEW lead, or a failed "
            "lead that needs recovery. 'Blocked' is a "
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

    @api.depends("evidence_bundle")
    def _compute_representation_alignment_display(self):
        for record in self:
            bundle = record.evidence_bundle if isinstance(record.evidence_bundle, Mapping) else None
            record.representation_alignment_display = representation_alignment_label(bundle)

    @api.depends("review_snapshot_ids")
    def _compute_review_snapshot_count(self):
        for record in self:
            record.review_snapshot_count = len(record.review_snapshot_ids)

    @api.depends("write_date")
    def _compute_lead_image_ids(self):
        """Image attachments already linked to the lead. This field stores nothing of its own."""
        attachments = self.env["ir.attachment"]
        if self.ids:
            attachments = attachments.search(
                [
                    ("res_model", "=", self._name),
                    ("res_id", "in", self.ids),
                ]
            ).filtered(lambda attachment: (attachment.mimetype or "").startswith("image/"))
        grouped: dict[int, Any] = {}
        for attachment in attachments:
            grouped.setdefault(attachment.res_id, self.env["ir.attachment"])
            grouped[attachment.res_id] |= attachment
        for lead in self:
            lead.lead_image_ids = grouped.get(lead.id, self.env["ir.attachment"])

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

    @api.model_create_multi
    def create(self, vals_list):
        if any(vals.get("review_status") == REVIEW_STATUS_APPROVED for vals in vals_list):
            raise AccessError(
                "A web lead is broker-approved only through its Approve action, which records the approval evidence."
            )
        return super().create(vals_list)

    def _check_approval_status_write(self, vals):
        """Refuse a transition to approved that did not come from the approval action.

        Rewriting ``approved`` on a lead that is already approved (a triage
        replay) is not a transition and stays allowed.
        """
        if vals.get("review_status") != REVIEW_STATUS_APPROVED:
            return
        if self.env.context.get(_APPROVAL_STATUS_KEY) is _APPROVAL_STATUS_TOKEN:
            return
        if any(rec.review_status != REVIEW_STATUS_APPROVED for rec in self):
            raise AccessError(
                "A web lead is broker-approved only through its Approve action, which records the approval evidence."
            )

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
        self._check_approval_status_write(vals)
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
    def _rejected_external_id(self, provider_key: str, body: Mapping[str, Any]) -> str:
        """The provider's stable submission id for a rejected delivery, or ``""``."""
        try:
            event = get_adapter(provider_key).classify_event(body)
        except (ValueError, TypeError):
            return ""
        return (event.provider_external_id or "").strip()

    @api.model
    def record_rejected_inbound(self, provider_key: str, body: Mapping[str, Any], reason: str) -> PlasticosWebLead:
        """Store a permanently rejected submission without running triage.

        Delivery identity is deterministic: when the provider's stable
        submission id is available, repeated deliveries of the same invalid
        submission update the one rejection row instead of adding another. The
        rejection keeps its own identity namespace (``REJ-<provider>-<id>``), so
        a later valid resubmission of that entry admits normally under its
        packet key. Without a stable id the rejection gets a server identity.
        """
        external_id = self._rejected_external_id(provider_key, body)
        if external_id:
            lead_id = f"{REJECTED_LEAD_PREFIX}{provider_key}-{external_id}"
            existing = self._find_existing_lead(lead_id)
            if existing:
                return self._refresh_rejected_inbound(existing, body, reason)
        else:
            lead_id = self._next_lead_identity()
        vals = {
            "lead_id": lead_id,
            "source": "web_lead",
            "provider_key": provider_key,
            "provider_external_id": external_id or False,
            "raw_payload": dict(body),
            "decision": "cold",
            "state": "error",
            "error_message": reason,
        }
        lead, created = self._create_or_replay(vals)
        if not created:
            return self._refresh_rejected_inbound(lead, body, reason)
        _logger.info("Web lead %s stored as a rejected inbound from provider %s.", lead.lead_id, provider_key)
        return lead

    @api.model
    def _refresh_rejected_inbound(
        self, lead: PlasticosWebLead, body: Mapping[str, Any], reason: str
    ) -> PlasticosWebLead:
        """A repeated invalid delivery refreshes the stored reason; it never adds a row."""
        values: dict[str, Any] = {}
        if lead.error_message != reason:
            values["error_message"] = reason
        if dict(lead.raw_payload or {}) != dict(body):
            values["raw_payload"] = dict(body)
        if values:
            lead.write(values)
        _logger.info("Repeated rejected inbound for web lead %s; no new row.", lead.lead_id)
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
        postal_code, location_text, location = resolve_pickup(
            packet.pickup_postal_code,
            packet.pickup_location_text,
        )
        vals = {
            "lead_id": str(lead_id),
            "source": "web_lead",
            "lead_source_id": web_lead_source.id if web_lead_source else False,
            "decision": DISPOSITION_REVIEW,
            "raw_payload": dict(packet.raw_payload),
            "provider_key": packet.provider,
            "provider_external_id": packet.provider_external_id or False,
            "canonical_payload": packet_to_dict(packet, omit_raw_payload=True),
            "company_name": packet.company_name or "Unknown",
            "contact_name": packet.contact_name,
            "contact_email": packet.contact_email,
            "contact_phone": packet.contact_phone,
            "pickup_postal_code": postal_code or False,
            "pickup_location_text": location_text or False,
            "pickup_place": location or False,
            "material_description": packet.material_description,
            "quantity_text": packet.weight_per_load_text or packet.quantity_text,
            "has_contaminants": contaminants.lower() not in negative_contaminant_values,
            "contaminant_notes": contaminants or False,
            "image_urls": image_urls,
            "state": "received",
            "submitted_at": self._coerce_submitted_at(packet.submitted_at) or False,
        }
        lead, created = self._create_or_replay(vals)
        if not created:
            self._assert_equivalent_packet_replay(lead, packet)
            return lead
        _logger.info("Web lead %s created from provider packet %s.", lead.lead_id, packet.provider)
        if not lead.submitted_at:
            lead.write({"submitted_at": lead.create_date})
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
          [ATTACH] 1. Store admitted attachments. PDF page text is whatever the processor parsed.
          [BROKER] 2. One multimodal call (``run_broker_inference``). No separate text, vision, or economic call.
          [MERGE]  3. Merge the material reading. Photo findings stay in the evidence bundle.
          [CLASS]  4. Deterministic qualification. The validator decides.
          [WRITE]  5. Persist the decision, alignment, planning basis, and media omissions together.
          [HOT]    6. Create one intake only when the per-load weight is grounded.

        ``packet`` is the in-memory admission packet and the only carrier of
        signed attachment URLs. A later re-triage has no packet: it reuses prior
        successful acquisitions and records the rest as unavailable.
        """
        self.ensure_one()
        config = self.env["plasticos.web.lead.config"].get_config()
        catalog = self._material_catalog()
        run_id = uuid.uuid4().hex
        log_lines = [f"[RUN] {run_id} started"]

        try:
            canonical_payload = self.canonical_payload or {}
            is_packet_path = bool(canonical_payload)
            triage_input = canonical_payload if is_packet_path else self.raw_payload or {}
            broker_corrections: dict[str, Any] = {}
            if is_packet_path:
                # A re-run assesses the facts a broker corrected during REVIEW. The
                # submitted packet itself is never rewritten.
                triage_input, broker_corrections = self._triage_input_with_broker_corrections(canonical_payload)
                if broker_corrections:
                    log_lines.append(f"[CORRECTIONS] {sorted(broker_corrections)}")
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

            images: list[dict[str, Any]] = []
            documents: list[dict[str, Any]] = []
            media_omissions: list[dict[str, Any]] = []
            if is_packet_path:
                packet_attachments = (
                    acquisition_rows(packet) if packet is not None else list(triage_input.get("attachments") or [])
                )
                log_lines.append(f"[ATTACHMENTS] processing={len(packet_attachments)}")
                attachment_evidence = process_attachments(
                    lead=self,
                    attachments=packet_attachments,
                    analyzer=None,
                    evidence_bundle=self.evidence_bundle,
                    allowed_hosts=self._attachment_allowed_hosts(config),
                )
                images, documents, media_omissions = _broker_request_media(self, attachment_evidence)
            else:
                urls = self.image_urls or []
                if urls:
                    log_lines.append("[ATTACHMENTS] SKIPPED legacy URL path; only admitted attachment bytes are sent.")
                else:
                    log_lines.append("[ATTACHMENTS] none.")

            provider_spec = config.get_one_pass_provider()
            provider = InferenceProvider(**provider_spec) if provider_spec else None
            if provider is not None:
                log_lines.append(f"[BROKER] provider={provider.provider}:{provider.model}")
            else:
                log_lines.append("[BROKER] no provider configured.")
            broker_result = run_broker_inference(
                provider,
                seller=_seller_claims_for_broker(triage_input),
                images=images,
                pdf_page_text=_pdf_page_strings(documents),
                planning_defaults=PLANNING_DEFAULTS_V1,
                catalog=catalog,
                quantity_evidence=quantity_evidence,
            )
            if not isinstance(broker_result, Mapping):
                broker_result = {}
            ai_data, vision_results = _reading_from_broker(broker_result)
            log_lines.append("[BROKER] one call. Text, vision, and economic providers were not called.")

            merged = self._merge_ai_and_vision(
                ai_data,
                vision_results,
                quantity_evidence=quantity_evidence,
                seller_payload=triage_input if is_packet_path else None,
                catalog=catalog,
            )
            if is_packet_path and quantity_evidence is not None:
                evidence_bundle = reconcile_evidence(
                    canonical_payload=triage_input,
                    quantity=quantity_evidence,
                    ai_normalized=ai_data,
                    attachments=attachment_evidence,
                    run_id=run_id,
                    polymer_entries=catalog["polymer"],
                )
                log_lines.append(f"[RECONCILE] conflicts={len(evidence_bundle['conflicts'])}")
                if broker_corrections:
                    evidence_bundle["broker_corrections"] = broker_corrections
            else:
                evidence_bundle = {"schema_version": "web-lead-evidence/v1", "run_id": run_id, "conflicts": []}
            if is_packet_path:
                evidence_bundle["seller"] = _seller_claims_for_broker(triage_input)
            evidence_bundle = _apply_one_pass_evidence(evidence_bundle, broker_result, media_omissions)

            grounded_lbs = _grounded_load_lbs(quantity_evidence)
            if quantity_evidence is not None:
                merged["estimated_lbs"] = grounded_lbs
                if not grounded_lbs and quantity_evidence.weight_source != WEIGHT_SOURCE_AREA:
                    merged["lbs_source"] = quantity_evidence.weight_source or "none"

            economic_eligibility = evaluate_economic_eligibility(
                estimated_lbs=float(merged.get("estimated_lbs") or 0),
                standard_hot_min_lbs=config.hot_min_lbs or 10_000,
                reusable_item_hot_min_lbs=config.reusable_item_hot_min_lbs or 8_000,
                polymer_code=merged.get("polymer"),
                form_code=merged.get("form"),
                material_grade_code=merged.get("material_grade"),
                reusable_item_policy_codes=config.get_reusable_item_policy_codes(),
            )
            log_lines.append(
                f"[POLICY] class={economic_eligibility.opportunity_class} "
                f"threshold={economic_eligibility.applicable_hot_min_lbs:,.0f}lbs"
            )

            log_lines.append("[CLASS] Running legacy deterministic classification.")
            result = classify_lead(
                polymer=merged.get("polymer"),
                form_code=merged.get("form"),
                material_grade_code=merged.get("material_grade"),
                quality_tier_code=merged.get("quality_tier"),
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
                vision_evidence=vision_results,
            )
            log_lines.append(f"[CLASS] legacy_decision={result.decision}")

            mode = config.get_qualification_mode()
            economic_assessment = evidence_bundle.get(KEY_ECONOMIC_ASSESSMENT)
            qualification = None
            log_lines.append(
                f"[BROKER] status={economic_assessment.get(KEY_STATUS) if economic_assessment else 'missing'}"
            )
            signals = None
            if mode != QUALIFICATION_MODE_LEGACY and economic_assessment is not None:
                signals = self._qualification_signals(merged, evidence_bundle, economic_eligibility.to_dict(), config)
                qualification = derive_final_disposition(assessment_record=economic_assessment, signals=signals)
            if qualification is not None:
                qualification["routing_mode"] = mode
                qualification["legacy_decision"] = result.decision
                log_lines.append(
                    f"[QUALIFY] mode={mode} recommendation={qualification['model_recommendation']} "
                    f"final={qualification['final_disposition']} legacy={result.decision}"
                )

            live = mode == QUALIFICATION_MODE_LIVE and qualification is not None
            decision = qualification["final_disposition"] if live else result.decision

            defer_hot_intake = decision == DISPOSITION_HOT and grounded_lbs <= 0
            review_reasons = self._collect_review_reasons(
                decision=decision,
                live=live,
                legacy_result=result,
                merged=merged,
                ai_data=ai_data,
                economic_assessment=economic_assessment,
                evidence_bundle=evidence_bundle,
                qualification=qualification,
            )
            if defer_hot_intake:
                review_reasons.append("Per-load weight is not grounded. The lead stays HOT and no intake is created.")

            decision_reasons = {
                KEY_REASONS: qualification["reasons"] if live else result.reasons,
                "cold_gates": qualification["hard_exclusions"] if live else result.cold_gates_triggered,
                KEY_HOT_QUALIFIERS: [] if live else result.hot_qualifiers_met,
                KEY_ECONOMIC_ELIGIBILITY: economic_eligibility.to_dict(),
                KEY_REVIEW_REQUIRED: bool(review_reasons),
                KEY_REVIEW_REASONS: review_reasons,
                KEY_VISION: result.vision_evidence,
            }
            if qualification is not None:
                decision_reasons[KEY_QUALIFICATION] = qualification
                decision_reasons["legacy_classification"] = {
                    KEY_DECISION: result.decision,
                    KEY_REASONS: result.reasons,
                    "cold_gates": result.cold_gates_triggered,
                    KEY_HOT_QUALIFIERS: result.hot_qualifiers_met,
                }
            values = {
                "decision": decision,
                "decision_reasons": decision_reasons,
                "ai_normalized": ai_data,
                "ai_vision_results": vision_results,
                "ai_analysis": merged,
                "estimated_lbs_per_load": grounded_lbs,
                "estimated_lbs_high": (
                    int(quantity_evidence.load_weight_lbs_high)
                    if grounded_lbs and quantity_evidence is not None and quantity_evidence.load_weight_lbs_high
                    else 0
                ),
                "estimated_loads_per_month": int(merged.get("loads_per_month") or 0),
                "frequency": merged.get("frequency", ""),
                "review_status": "clarification_required" if review_reasons else "pending",
                "review_required_reason": "\n".join(sorted(set(review_reasons))) or False,
                "evidence_bundle": evidence_bundle,
            }
            if defer_hot_intake:
                values["state"] = "review_pending"
            self.write(values)

            if defer_hot_intake:
                log_lines.append("[HOT] No grounded per-load weight. Intake waits. Review activity kept.")
                self._schedule_lead_review_activity(
                    config,
                    summary=self._review_activity_summary(),
                    note=(
                        "<p>This HOT lead has no grounded per-load weight, so no intake was created. "
                        "Any planning figure stays in the evidence bundle.</p>"
                        f"<ul><li><b>Company:</b> {escape(self.company_name or 'Unknown')}</li></ul>"
                        "<p><b>Action:</b> record the verified Lbs/Load, then Re-Run Triage or Promote to HOT.</p>"
                    ),
                )
            elif decision == DISPOSITION_HOT:
                log_lines.append("[HOT] Creating intake and scheduling human review.")
                intake_facts = dict(merged)
                intake_facts["estimated_lbs"] = grounded_lbs
                self._process_hot_lead_triage(intake_facts, config)
                if evidence_bundle is not None:
                    copy_successful_attachments_to_intake(
                        lead=self, intake=self.intake_id, evidence_bundle=evidence_bundle
                    )
                crm_lead = getattr(self, "crm_lead_id", None)
                synchronize_images = getattr(crm_lead, "_propagate_available_commercial_images", None)
                if callable(synchronize_images):
                    synchronize_images()
            elif decision == DISPOSITION_REVIEW:
                log_lines.append("[REVIEW] Assigning broker clarification. No intake or opportunity.")
                self._route_review_lead(config)
            else:
                log_lines.append("[COLD] Archiving lead. Stored photos stay on the lead.")
                self.write({"state": "skipped"})

        except Exception as exc:
            _logger.exception("Triage pipeline error for lead %s", self.lead_id)
            log_lines.append(f"[ERROR] {exc}")
            self.write({"state": "error", "error_message": str(exc)})
            try:
                with self.env.cr.savepoint():
                    self._schedule_lead_review_activity(
                        config,
                        summary=f"Recover failed web lead: {self.lead_id}",
                        note=(
                            "<p>Web-lead processing failed. The submission and its evidence are kept.</p>"
                            "<p><b>Action:</b> fix the cause, then use Retry Processing.</p>"
                        ),
                    )
            except Exception:
                _logger.exception("Could not queue recovery work for failed web lead %s", self.lead_id)

        log_lines.append(f"[RUN] {run_id} finished")
        self.write({"triage_log": "\n".join(log_lines)})

    @staticmethod
    def _collect_review_reasons(
        *, decision, live, legacy_result, merged, ai_data, economic_assessment, evidence_bundle, qualification
    ):
        """Broker-visible reasons a HOT or REVIEW lead needs attention before commercial work."""
        review_reasons = list(legacy_result.review_reasons) if (decision == DISPOSITION_HOT and not live) else []
        if float(merged.get("estimated_lbs") or 0) > SINGLE_LOAD_REVIEW_CAP_LBS or ai_data.get(
            "weight_above_review_cap"
        ):
            review_reasons.append("Weight is above the single-load review cap.")
        if economic_assessment is not None and decision in (DISPOSITION_HOT, DISPOSITION_REVIEW):
            review_reasons.extend(evidence_bundle.get("clarification_requests", []))
            review_reasons.extend(
                f"Evidence conflict: {item.get('field', 'unknown')}" for item in evidence_bundle.get("conflicts", [])
            )
            review_reasons.extend(economic_assessment.get(KEY_ASSESSMENT, {}).get("clarifications", []))
            if economic_assessment.get(KEY_STATUS) != ASSESSMENT_STATUS_ASSESSED:
                review_reasons.append(
                    "Economic assessment is unavailable; broker review is required before commercial work."
                )
        if live and decision == DISPOSITION_REVIEW:
            if qualification["review_priority"] == "high":
                review_reasons.append("High priority: the commercial assessment sees a strong opportunity.")
            review_reasons.extend(qualification["reasons"])
            review_reasons.extend(qualification["missing_information"])
        return review_reasons

    def _triage_input_with_broker_corrections(self, canonical_payload):
        """Overlay facts a broker corrected on the lead onto the submitted packet.

        Returns ``(triage_input, corrections)``. A correction is a lead field
        that differs from what the submission (or the previous run) produced.
        The stored ``canonical_payload`` stays the seller's submission; each
        correction keeps both values so submitted and corrected facts stay
        distinguishable.
        """
        self.ensure_one()
        submitted = dict(canonical_payload or {})
        triage_input = dict(submitted)
        corrections: dict[str, Any] = {}
        previous = self.ai_analysis if isinstance(self.ai_analysis, dict) else {}

        def _record(field, before, after):
            corrections[field] = dict(submitted=before, corrected=after)

        material = (self.material_description or "").strip()
        if material and material != (submitted.get("material_description") or "").strip():
            triage_input["material_description"] = material
            _record("material_description", submitted.get("material_description"), material)

        submitted_quantity = (submitted.get("weight_per_load_text") or submitted.get("quantity_text") or "").strip()
        quantity = (self.quantity_text or "").strip()
        if quantity and quantity != submitted_quantity:
            # The corrected text replaces both seller quantity boxes; the one
            # parser then separates mass, inventory, and cadence again.
            triage_input["quantity_text"] = quantity
            triage_input["weight_per_load_text"] = ""
            _record("quantity_text", submitted_quantity, quantity)

        if previous:
            verified_lbs = int(self.estimated_lbs_per_load or 0)
            if verified_lbs > 0 and verified_lbs != int(previous.get("estimated_lbs") or 0):
                triage_input["weight_per_load_text"] = str(verified_lbs)
                _record("estimated_lbs_per_load", previous.get("estimated_lbs"), verified_lbs)
            loads = int(self.estimated_loads_per_month or 0)
            if loads > 0 and loads != int(previous.get("loads_per_month") or 0):
                triage_input["frequency_text"] = f"{loads} loads per month"
                _record("estimated_loads_per_month", previous.get("loads_per_month"), loads)

        contaminants = (self.contaminant_notes or "").strip()
        if contaminants and contaminants != (submitted.get("contaminants_text") or "").strip():
            triage_input["contaminants_text"] = contaminants
            _record("contaminants_text", submitted.get("contaminants_text"), contaminants)
        return triage_input, corrections

    # ═══════════════════════════════════════════════════════════
    # Merge AI + Vision
    # ═══════════════════════════════════════════════════════════

    def _material_catalog(self) -> dict[str, tuple[CatalogEntry, ...]]:
        """Active rows of the ten vocabulary masters. Inactive rows stay out."""
        catalog: dict[str, tuple[CatalogEntry, ...]] = {}
        for kind, model_name in _CATALOG_MODELS:
            model = self.env[model_name]
            domain = [("active", "=", True)] if "active" in model._fields else []
            entries: list[CatalogEntry] = []
            for record in model.search(domain):
                code = (record.code or "").strip()
                if not code or (kind == "attribute" and code.casefold() in _OMIT_ATTRIBUTE_CODES):
                    continue
                description = record.description if "description" in record._fields else ""
                full_name = record.full_name if "full_name" in record._fields else ""
                entries.append(CatalogEntry(code, record.name or "", description or "", full_name or ""))
            catalog[kind] = tuple(entries)
        return catalog

    def _merge_ai_and_vision(
        self,
        ai_data: dict[str, Any],
        vision_results: list[dict[str, Any]],
        *,
        quantity_evidence: QuantityEvidence | None = None,
        seller_payload: Mapping[str, Any] | None = None,
        catalog: Mapping[str, tuple[CatalogEntry, ...]] | None = None,
    ) -> dict[str, Any]:
        """Merge text AI normalization with vision analysis.

        Authority rules:
        - The joint reply, which has already seen the seller text and the photos, is the reading.
        - A photo code fills a slot that reply left empty when the seller named no different code.
        - A seller-named polymer that disagrees with a confident photo stays the seller code.
        - The classifier still receives the original photo rows.

        Legacy-path weight fallback cascade (FIX — resolves WeightPerLoad="unknown" bug):
          1. AI estimated_lbs_per_load (most reliable when AI ran)
          2. Vision estimated_lbs (any image gave a weight estimate)
          3. WhatIsTheQuantity × _LBS_PER_PALLET_ASSUMPTION (unit count fallback)
          4. 0 (classification will gate on cold_max_lbs)

        Canonical packet path uses the one seller-mass reading first. An area
        quantity stays area, including when an earlier model call stored that
        area number as pounds. A stated unit count uses the unit weight table.
        """
        catalog = catalog or self._material_catalog()
        merged: dict[str, Any] = {}
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
        # The corrected triage input when the pipeline passes one, else the submitted packet.
        canonical = seller_payload if seller_payload is not None else (self.canonical_payload or {})
        merged["source_description"] = (
            canonical.get("source_description")
            if quantity_evidence is not None
            else raw.get("WhatIsTheSourceOfThisMaterial", "") or raw.get("Source", "") or ""
        ) or ""

        # Seller item words name a grade. They are not written into the form
        # slot: a physical form from text AI or vision has to survive beside them.
        declared_material = _declared_material_text(canonical, raw)

        # ── Weight fallback cascade ────────────────────────────────────
        if quantity_evidence is not None:
            if quantity_evidence.weight_source == WEIGHT_SOURCE_AREA:
                lbs = 0
                lbs_source = WEIGHT_SOURCE_AREA
            else:
                lbs = quantity_evidence.load_weight_lbs or 0
                lbs_source = quantity_evidence.weight_source
                if not lbs:
                    ai_lbs = _safe_int(ai_data.get("estimated_lbs_per_load"), 0)
                    if ai_lbs > 0:
                        lbs = ai_lbs
                        lbs_source = "ai_text"
            merged["estimated_lbs_high"] = quantity_evidence.load_weight_lbs_high
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

        # ── Vision supplies form, grade, color, and contamination ──────
        vision_form = None
        vision_grade = None
        vision_color = None
        vision_packaging = None
        if vision_results:
            valid_vision = [v for v in vision_results if not v.get("error")]
            best_vision = max(valid_vision, key=lambda v: v.get("confidence", 0), default={})
            if best_vision:
                vision_form = best_vision.get("observed_form")
                vision_grade = best_vision.get("observed_material_grade")
                vision_color = best_vision.get("observed_color")
                vision_packaging = best_vision.get("observed_packaging")
                merged["vision_summary"] = best_vision.get("visual_summary", "")
            # One clean photo never erases contamination another photo shows.
            dirty = [v for v in valid_vision if v.get("contamination_visible") is True]
            if dirty:
                merged["contamination_visible"] = True
                notes = [str(v.get("contamination_notes") or "").strip() for v in dirty]
                merged["contamination_notes"] = "; ".join(dict.fromkeys(note for note in notes if note)) or None

        seller = split_phrase(declared_material, catalog)

        def _slot(ai_key: str, kind: str, photo_value: Any = None) -> str | None:
            entries = catalog.get(kind, ())
            accepted = accept_value(ai_data.get(ai_key), entries)
            if accepted:
                return accepted
            seller_code = seller.get(ai_key)
            if seller_code:
                return seller_code
            return accept_value(photo_value, entries)

        # A seller who names two polymers ("HDPE and PP regrind") leaves the
        # identity unresolved: neither the text AI, a photo, nor label length
        # picks one of them. Exactly one named polymer still resolves.
        seller_polymers = match_distinct(
            declared_material, catalog.get("polymer", ()), catalog.get("material_grade", ())
        )
        seller_polymer = seller_polymers[0] if len(seller_polymers) == 1 else None
        vision_polymer = accept_value(
            agreed_confident_polymer(list(vision_results or [])),
            catalog.get("polymer", ()),
        )
        joint_polymer = accept_value(ai_data.get("polymer"), catalog.get("polymer", ()))
        if len(seller_polymers) > 1:
            merged["polymer"] = None
            merged["polymer_source"] = None
        elif seller_polymer and vision_polymer and seller_polymer != vision_polymer:
            merged["polymer"] = seller_polymer
            merged["polymer_source"] = "seller_text"
        elif joint_polymer:
            merged["polymer"] = joint_polymer
            merged["polymer_source"] = "text_ai"
        elif seller_polymer:
            merged["polymer"] = seller_polymer
            merged["polymer_source"] = "seller_text"
        elif vision_polymer:
            merged["polymer"] = vision_polymer
            merged["polymer_source"] = "vision"
        else:
            merged["polymer"] = None
            merged["polymer_source"] = None

        # Grade and form stay in separate slots. A drum grade must not erase
        # regrind, and an AI form must not hide the item word.
        merged["form"], merged["material_grade"] = merge_form_and_grade(
            ai_data.get("form"),
            declared_material,
            vision_form,
            catalog.get("form", ()),
            catalog.get("material_grade", ()),
        )
        explicit_grade = accept_value(ai_data.get("material_grade"), catalog.get("material_grade", ()))
        if explicit_grade:
            merged["material_grade"] = explicit_grade
        elif not merged["material_grade"]:
            merged["material_grade"] = accept_value(vision_grade, catalog.get("material_grade", ()))

        merged["color"] = _slot("color", "color", vision_color)
        merged["source_type"] = _slot("source_type", "source_type")
        merged["filler_type"] = _slot("filler_type", "filler")
        merged["packaging_type"] = _slot("packaging_type", "packaging", vision_packaging)
        merged["process_type"] = _slot("process_type", "process")
        merged["quality_tier"] = _slot("quality_tier", "quality_tier")
        merged["attributes"] = _merged_attributes(
            ai_data.get("attributes"),
            seller["attributes"],
            list(vision_results or []),
            catalog,
        )
        return merged

    # ═══════════════════════════════════════════════════════════
    # Stored evidence replay
    # ═══════════════════════════════════════════════════════════

    @api.model
    def _coerce_submitted_at(self, value: Any) -> str | bool:
        """Return a naive UTC datetime string, or False when the seller date is missing."""
        if not value:
            return False
        if isinstance(value, datetime):
            parsed = value
        else:
            text = str(value).strip()
            if not text:
                return False
            try:
                parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
            except ValueError:
                return False
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone(UTC).replace(tzinfo=None)
        return fields.Datetime.to_string(parsed)

    @api.model
    def _submitted_at_from_payload(self, raw_payload: Any, canonical_payload: Any = None) -> str | bool:
        """Seller submission time from the raw Cognito entry, then the stored packet."""
        raw = raw_payload if isinstance(raw_payload, dict) else {}
        entry = raw.get("Entry")
        if isinstance(entry, dict):
            coerced = self._coerce_submitted_at(entry.get("DateSubmitted"))
            if coerced:
                return coerced
        canonical = canonical_payload if isinstance(canonical_payload, dict) else {}
        return self._coerce_submitted_at(canonical.get("submitted_at"))

    def _reclassify_stored_leads(self):
        """Replay stored evidence for leads that never received an intake."""
        leads = self if self else self.env["plasticos.web.lead"]
        if not self:
            leads = leads.search(
                [
                    ("state", "in", ("received", "skipped", "error")),
                    ("intake_id", "=", False),
                ]
            )
        for lead in leads:
            lead._reclassify_from_stored_evidence()

    def _reclassify_from_stored_evidence(self):
        """Call ``classify_lead`` on stored text and model output. No new model call."""
        self.ensure_one()
        if self.intake_id or self.state not in ("received", "skipped", "error"):
            return
        mass = replay_stored_mass(
            quantity_text=self.quantity_text,
            estimated_lbs=self.estimated_lbs_per_load,
        )
        lbs = float(mass.lbs or 0)
        analysis = dict(self.ai_analysis) if isinstance(self.ai_analysis, dict) else {}
        normalized = self.ai_normalized if isinstance(self.ai_normalized, dict) else {}
        raw_polymer = str(analysis.get("polymer") or normalized.get("polymer") or "").strip()
        catalog = self._material_catalog()
        polymer_entries = catalog["polymer"]
        polymer = accept_value(raw_polymer, polymer_entries) if raw_polymer else None
        # Replay keeps a two-polymer seller description unresolved, as the merge does.
        declared_material = _declared_material_text(self.canonical_payload or {}, self.raw_payload or {})
        if len(match_distinct(declared_material, polymer_entries, catalog.get("material_grade", ()))) > 1:
            polymer = None
        config = self.env["plasticos.web.lead.config"].get_config()
        economic = evaluate_economic_eligibility(
            estimated_lbs=lbs,
            standard_hot_min_lbs=config.hot_min_lbs or 10_000,
            reusable_item_hot_min_lbs=config.reusable_item_hot_min_lbs or 8_000,
            polymer_code=polymer,
            form_code=analysis.get("form"),
            material_grade_code=analysis.get("material_grade"),
            reusable_item_policy_codes=config.get_reusable_item_policy_codes(),
        )
        result = classify_lead(
            polymer=polymer,
            form_code=analysis.get("form"),
            material_grade_code=analysis.get("material_grade"),
            quality_tier_code=analysis.get("quality_tier"),
            material_description=self.material_description,
            estimated_lbs=lbs,
            source_description=str(analysis.get("source_description") or ""),
            source_type=analysis.get("source_type"),
            is_plastic_hint=analysis.get("is_plastic"),
            is_commercial_hint=analysis.get("is_commercial_source"),
            weight_source=mass.source,
            reject_materials=config.get_reject_materials(),
            reject_sources=config.get_reject_sources(),
            hot_min_lbs=economic.applicable_hot_min_lbs,
            cold_max_lbs=config.cold_max_lbs or 8_000,
            economic_eligible=economic.eligible,
            economic_policy_reasons=list(economic.reasons),
            vision_evidence=list(self.ai_vision_results) if isinstance(self.ai_vision_results, list) else [],
        )
        review_reasons = list(result.review_reasons) if result.decision == "hot" else []
        if lbs > SINGLE_LOAD_REVIEW_CAP_LBS:
            review_reasons.append("Weight is above the single-load review cap.")
        self.write(
            {
                "decision": result.decision,
                "decision_reasons": {
                    KEY_REASONS: result.reasons,
                    "cold_gates": result.cold_gates_triggered,
                    KEY_HOT_QUALIFIERS: result.hot_qualifiers_met,
                    KEY_ECONOMIC_ELIGIBILITY: economic.to_dict(),
                    KEY_REVIEW_REQUIRED: bool(review_reasons),
                    KEY_REVIEW_REASONS: review_reasons,
                    KEY_VISION: result.vision_evidence,
                },
                "estimated_lbs_per_load": int(lbs) if lbs > 0 else 0,
                "estimated_lbs_high": int(mass.lbs_high) if mass.lbs_high and lbs > 0 else 0,
                "review_status": "clarification_required" if review_reasons else self.review_status,
                "review_required_reason": "\n".join(sorted(set(review_reasons))) or False,
                "state": "skipped" if result.decision != "hot" else "review_pending" if lbs <= 0 else self.state,
            }
        )
        if result.decision != "hot" or lbs <= 0:
            if result.decision == "hot" and lbs <= 0:
                self._schedule_lead_review_activity(
                    config,
                    summary=self._review_activity_summary(),
                    note=(
                        "<p>This HOT lead has no grounded per-load weight, so no intake was created.</p>"
                        "<p><b>Action:</b> record the verified Lbs/Load, then Re-Run Triage or Promote to HOT.</p>"
                    ),
                )
            return
        merged = dict(analysis)
        merged["polymer"] = polymer
        merged["estimated_lbs"] = lbs
        merged["loads_per_month"] = self.estimated_loads_per_month or analysis.get("loads_per_month") or 0
        # A lead newly promoted to HOT gets exactly one reviewer handoff:
        # _process_hot_lead_triage notifies only when it creates the intake.
        self._process_hot_lead_triage(merged, config)

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
            if not self.env.context.get("skip_hot_notify"):
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
        Writes every catalog code the merge accepted. An empty slot stays empty.
        Analysis stored before merge split form from grade is split here.

        FIX: removed inconsistent qty_per_load defaults (1 vs 40000).
        0-lbs fallback is 1 (meaningful minimum) so the field doesn't explode.
        """
        if "material_grade" in merged:
            form_value, grade_value = merged.get("form"), merged.get("material_grade")
        else:
            from odoo.addons.plasticos_material_profile.grade_codes import GRADE_CODES

            form_value, grade_value = split_material_code(merged.get("form"), GRADE_CODES)
        # An unknown source stays empty on the intake. A configured default is not
        # evidence about this seller and is never written as if it were.
        source_type_code = merged.get("source_type") or None
        qty_per_load = float(merged.get("estimated_lbs") or 0)
        if qty_per_load <= 0:
            # Never invent a quantity: an intake needs a stated or verified per-load weight.
            raise UserError(
                f"Lead '{self.lead_id}' has no verified per-load weight. "
                "Record the confirmed Lbs/Load before creating an intake."
            )
        loads_per_month = max(merged.get("loads_per_month", 0), 0)
        deal_type = _FREQ_TO_DEAL.get(merged.get("frequency", ""), "spot")

        def _one(model, code):
            if not code:
                return model.browse()
            return model.search([("code", "=ilike", str(code))], limit=1)

        polymer_rec = _one(self.env["plasticos.polymer"], merged.get("polymer"))
        form_rec = _one(self.env["plasticos.material.form"], form_value)
        grade_rec = _one(self.env["plasticos.material.grade"], grade_value)
        source_type_rec = _one(self.env["plasticos.source.type"], source_type_code)
        color_rec = _one(self.env["plasticos.material.color"], merged.get("color"))
        packaging_rec = _one(self.env["plasticos.packaging.type"], merged.get("packaging_type"))
        quality_tier_rec = _one(self.env["plasticos.material.quality.tier"], merged.get("quality_tier"))
        filler_rec = _one(self.env["plasticos.filler.type"], merged.get("filler_type"))
        attribute_codes = [code for code in (merged.get("attributes") or ()) if code]
        attribute_recs = (
            self.env["plasticos.material.attribute"].search([("code", "in", attribute_codes)])
            if attribute_codes
            else self.env["plasticos.material.attribute"]
        )

        web_lead_source = self.env["utm.source"].search([("name", "=", "Web Lead Form")], limit=1)

        from odoo.addons.plasticos_intake.source_origin import web_lead_source_address

        intake_vals = {
            "pending_company_name": self.company_name or "Unknown",
            "source_lead_id": self.id,
            "polymer_id": polymer_rec.id if polymer_rec else False,
            "form_id": form_rec.id if form_rec else False,
            "material_grade_id": grade_rec.id if grade_rec else False,
            "source_type_id": source_type_rec.id if source_type_rec else False,
            "lead_source_id": web_lead_source.id if web_lead_source else False,
            "quantity_per_load_lbs": qty_per_load,
            "loads_per_month": loads_per_month,
            "deal_type": deal_type,
            "contamination_notes": (
                merged.get("contaminants_noted") or merged.get("contamination_notes") or self.contaminant_notes or False
            ),
            "assigned_user_id": self.assigned_user_id.id or False,
        }
        if color_rec:
            intake_vals["color_ids"] = [(6, 0, color_rec.ids)]
        if packaging_rec:
            intake_vals["packaging_type_id"] = packaging_rec.id
        if quality_tier_rec:
            intake_vals["quality_tier_id"] = quality_tier_rec.id
        if filler_rec:
            intake_vals["filler_type_id"] = filler_rec.id
        if attribute_recs:
            intake_vals["material_attribute_ids"] = [(6, 0, attribute_recs.ids)]
        if merged.get("process_type"):
            intake_vals["origin_process_type"] = merged["process_type"]
        intake_vals.update(
            web_lead_source_address(self.pickup_postal_code, self.pickup_place, self.pickup_location_text)
        )
        bundle = self.evidence_bundle if isinstance(self.evidence_bundle, Mapping) else {}
        measures, spec_notes = _intake_spec_facts(bundle.get("document_specifications"), bundle)
        intake_vals.update(measures)
        if spec_notes:
            intake_vals["intake_notes"] = spec_notes

        return self.env["plasticos.intake"].create(intake_vals)

    def _eligible_reviewer(self, config):
        """The configured reviewer, only while an active internal user who can resolve the work.

        Resolving a REVIEW lead, approving a HOT snapshot, and recording a
        promotion or rejection all write the web lead. A reviewer without that
        right would hold work they cannot complete, so they are not eligible.
        """
        reviewer = getattr(config, "hot_intake_reviewer_id", None)
        if not reviewer or not reviewer.exists() or not reviewer.active or reviewer.share:
            return None
        if not self.env["plasticos.web.lead"].with_user(reviewer).has_access("write"):
            return None
        return reviewer

    def _blocked_reviewer_reason(self, config):
        reviewer = getattr(config, "hot_intake_reviewer_id", None)
        if reviewer and reviewer.exists() and reviewer.active and not reviewer.share:
            return f"Configured reviewer {reviewer.name} cannot edit web leads, so they could not resolve this work."
        return "No web-lead reviewer is configured (HOT Intake Reviewer)."

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
            reason = self._blocked_reviewer_reason(config)
            self.write({"mack_review_state": "blocked", "mack_review_reason": reason})
            self.message_post(
                body=(
                    f"HOT lead intake was created, but the internal review handoff is blocked: {reason} "
                    "Configure a HOT Intake Reviewer who can edit web leads, then use Route Review."
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
        """Re-attempt a blocked human handoff after a reviewer has been configured.

        A HOT lead routes its intake review; a REVIEW lead routes its
        clarification work; a failed lead routes its recovery work.
        """
        config = self.env["plasticos.web.lead.config"].get_config()
        for rec in self:
            if rec.intake_id:
                rec._notify_admin_hot_intake(rec.intake_id, config)
            elif rec.state == "review_pending":
                rec._route_review_lead(config)
            elif rec.state == "error":
                rec._schedule_lead_review_activity(
                    config,
                    summary=f"Recover failed web lead: {rec.lead_id}",
                    note="<p>Web-lead processing failed. Fix the cause, then use Retry Processing.</p>",
                )
            else:
                raise UserError("Only a HOT intake, a REVIEW lead, or a failed lead has a review handoff to route.")
        return True

    # ═══════════════════════════════════════════════════════════
    # Commercial qualification: REVIEW lifecycle
    # ═══════════════════════════════════════════════════════════

    def _qualification_signals(self, merged, evidence_bundle, eligibility, config):
        """Deterministic evidence dimensions handed to the model and the validator."""
        self.ensure_one()
        bundle = evidence_bundle or {}
        seller = bundle.get("seller") or self.canonical_payload or {}
        material_text = " ".join(
            str(value or "")
            for value in (
                seller.get("material_description"),
                seller.get("material_composition_text"),
                self.material_description,
            )
        )
        source_text = f"{merged.get('source_description') or ''} {merged.get('source_type') or ''}"
        risk_indicators = detect_risk_indicators(
            polymer=merged.get("polymer"),
            material_text=material_text,
            source_text=source_text,
            reject_materials=config.get_reject_materials(),
            reject_sources=config.get_reject_sources(),
        )
        hard_exclusions = detect_hard_exclusions(
            polymer=merged.get("polymer"),
            material_text=material_text,
            is_plastic_hint=merged.get("is_plastic"),
            reject_materials=config.get_reject_materials(),
        )
        return build_qualification_signals(
            seller=seller,
            merged=merged,
            quantity=bundle.get("quantity"),
            vision=bundle.get("vision"),
            conflicts=bundle.get("conflicts"),
            clarification_requests=bundle.get("clarification_requests"),
            economic_eligibility=eligibility,
            risk_indicators=risk_indicators,
            hard_exclusions=hard_exclusions,
            cold_max_lbs=config.cold_max_lbs or 8_000,
            polymer_entries=self._material_catalog()["polymer"],
        )

    def _review_activity_summary(self):
        return f"Clarify REVIEW web lead: {self.lead_id}"

    def _schedule_lead_review_activity(self, config, *, summary, note):
        """One internal activity on this lead for the configured reviewer, or a visible blocked handoff.

        Deduplicated by lead, reviewer, and purpose (the summary). The webhook
        worker is never an implicit reviewer.
        """
        self.ensure_one()
        reviewer = self._eligible_reviewer(config)
        if reviewer is None:
            reason = self._blocked_reviewer_reason(config)
            self.write({"mack_review_state": "blocked", "mack_review_reason": reason})
            self.message_post(
                body=(
                    f"This web lead needs broker work, but the review handoff is blocked: {reason} "
                    "Configure a HOT Intake Reviewer who can edit web leads, then use Route Review."
                )
            )
            _logger.warning("Web lead %s has no configured internal reviewer.", self.lead_id)
            return False
        existing = self.env["mail.activity"].search_count(
            [
                ("res_model", "=", self._name),
                ("res_id", "=", self.id),
                ("user_id", "=", reviewer.id),
                ("summary", "=", summary),
            ]
        )
        if not existing:
            self.activity_schedule("mail.mail_activity_data_todo", user_id=reviewer.id, summary=summary, note=note)
        self.write(
            {
                "mack_review_state": "queued",
                "mack_review_reason": f"Internal review is assigned to {reviewer.name}.",
            }
        )
        return True

    def _route_review_lead(self, config):
        """Make a REVIEW disposition actionable: queue state, clarification status, assigned work."""
        self.ensure_one()
        self.write({"state": "review_pending", "review_status": "clarification_required"})
        qualification = (self.decision_reasons or {}).get(KEY_QUALIFICATION) or {}
        questions = list(qualification.get("recommended_clarification") or []) + list(
            qualification.get("missing_information") or []
        )
        items = "".join(f"<li>{escape(question)}</li>" for question in dict.fromkeys(questions))
        priority = "High priority. " if qualification.get("review_priority") == "high" else ""
        self._schedule_lead_review_activity(
            config,
            summary=self._review_activity_summary(),
            note=(
                f"<p>{priority}This web lead may be worth pursuing but needs facts before an intake.</p>"
                f"<ul><li><b>Company:</b> {escape(self.company_name or 'Unknown')}</li></ul>"
                + (f"<p><b>Ask the seller:</b></p><ul>{items}</ul>" if items else "")
                + "<p><b>Action:</b> record the verified facts and notes, then Promote to HOT, "
                "Re-Run Triage, or Reject After Review.</p>"
            ),
        )

    def _close_lead_review_activities(self, feedback):
        self.ensure_one()
        activities = self.env["mail.activity"].search(
            [
                ("res_model", "=", self._name),
                ("res_id", "=", self.id),
                ("summary", "=", self._review_activity_summary()),
            ]
        )
        if activities:
            activities.action_feedback(feedback=feedback)

    def _manual_override_record(self, decision, rationale, **extra):
        """Actor, rationale, and time of a broker disposition change, stored in decision_reasons."""
        self.ensure_one()
        return dict(
            previous_decision=self.decision,
            decision=decision,
            actor_id=self.env.user.id,
            actor=self.env.user.display_name,
            rationale=(rationale or "")[:2000],
            at=fields.Datetime.to_string(fields.Datetime.now()),
            **extra,
        )

    def action_promote_to_hot(self):
        """Broker promotion of a REVIEW (or COLD) lead to HOT once its facts are verified.

        Requires a rationale in Broker Review Notes and a verified per-load
        weight. Records the actor and rationale, then reuses the one idempotent
        HOT path, so a repeated promotion never duplicates the intake or the
        opportunity. It does not approve a snapshot or start any commercial step.
        """
        config = self.env["plasticos.web.lead.config"].get_config()
        for rec in self:
            if rec.intake_id:
                raise UserError("Intake already exists for this lead.")
            if rec.state == "error":
                raise UserError("Retry processing of a failed lead before promoting it.")
            rationale = (rec.review_notes or "").strip()
            if not rationale:
                raise UserError("Record the broker rationale in Broker Review Notes before promoting to HOT.")
            if (rec.estimated_lbs_per_load or 0) <= 0:
                raise UserError(
                    "Record the verified per-load weight (Lbs/Load) before promoting to HOT. "
                    "An intake is never created from an invented quantity."
                )
            merged = dict(rec.ai_analysis or rec.ai_normalized or {})
            merged["estimated_lbs"] = rec.estimated_lbs_per_load
            merged["loads_per_month"] = rec.estimated_loads_per_month or merged.get("loads_per_month") or 0
            reasons = dict(rec.decision_reasons or {})
            reasons[KEY_MANUAL_OVERRIDE] = rec._manual_override_record(
                DISPOSITION_HOT, rationale, verified_lbs_per_load=rec.estimated_lbs_per_load
            )
            previous = rec.decision
            rec.write({"decision": DISPOSITION_HOT, "decision_reasons": reasons, "review_status": "pending"})
            rec._close_lead_review_activities("Promoted to HOT by broker.")
            rec._process_hot_lead_triage(merged, config)
            rec.message_post(
                body=f"{rec.env.user.display_name} promoted this lead from {previous.upper()} to HOT. "
                f"Rationale: {rationale[:500]}"
            )
        return True

    def _write_recovered_assessment(self, assessment, history, extras=None):
        """Replace the assessment, and the one-pass keys, inside a processed lead's bundle.

        Not reachable over RPC (leading underscore) and not driven by context:
        the processed-lead write guard has no bypass. Seller facts and the
        disposition stay as stored. Planning mass is not written onto a load field.
        """
        self.ensure_one()
        bundle = dict(self.evidence_bundle or {})
        bundle[KEY_ECONOMIC_ASSESSMENT] = assessment
        bundle["economic_assessment_history"] = list(history)
        for key, value in (extras or {}).items():
            bundle[key] = value
        # Skips only this model's processed-lead guard; the ORM, ACLs, and tracking still apply.
        return super().write({"evidence_bundle": bundle})

    def action_retry_economic_assessment(self):
        """One-pass recovery for a lead that already has an intake.

        Re-runs the one broker call over stored evidence. It does not re-read
        acquisition URLs, recreate attachments, intake, or opportunity, change
        the disposition or the stored load weight, or touch an approved snapshot.
        A lead without an intake is reassessed with Re-Run Triage instead.
        """
        config = self.env["plasticos.web.lead.config"].get_config()
        for rec in self:
            rec.check_access("write")
            if not rec.intake_id:
                raise UserError("Use Re-Run Triage to reassess a lead that has no intake.")
            bundle = dict(rec.evidence_bundle or {})
            if not bundle:
                raise UserError("This lead has no stored evidence bundle to reassess.")
            spec = config.get_one_pass_provider()
            provider = InferenceProvider(**spec) if spec else None
            images, documents, media_omissions = _broker_request_media(rec, list(bundle.get("attachments") or []))
            catalog = rec._material_catalog()
            bundle["seller"] = _seller_claims_for_broker(rec.canonical_payload or {})
            broker_result = run_broker_inference(
                provider,
                seller=bundle["seller"],
                images=images,
                pdf_page_text=_pdf_page_strings(documents),
                planning_defaults=PLANNING_DEFAULTS_V1,
                catalog=catalog,
                quantity_evidence=bundle.get("quantity"),
            )
            if not isinstance(broker_result, Mapping):
                broker_result = {}
            stamped = _apply_one_pass_evidence(dict(bundle), broker_result, media_omissions)
            assessment = stamped.get(KEY_ECONOMIC_ASSESSMENT) or {}
            previous = bundle.get(KEY_ECONOMIC_ASSESSMENT) or {}
            history = list(bundle.get("economic_assessment_history") or [])
            if previous:
                history.append(
                    {
                        key: previous.get(key)
                        for key in (KEY_STATUS, "reason", "schema_version", KEY_ASSESSMENT)
                        if key in previous
                    }
                )
            extras = {
                key: stamped.get(key)
                for key in (
                    "representation_alignment",
                    "planning_basis",
                    "media_omissions",
                    "document_specifications",
                    "photo_findings",
                    "field_evidence",
                    "conflicts",
                )
            }
            rec._write_recovered_assessment(assessment, history[-10:], extras)
            rec.message_post(
                body=f"Broker inference re-run: status {assessment.get(KEY_STATUS)}. "
                "Disposition, load weight, intake, and approved snapshots are unchanged."
            )
        return True

    def action_approve_for_commercial_preparation(self):
        """Approve the lead; the immutable review snapshot is recorded in the same transaction.

        The snapshot model's ``_record_broker_approval`` is the only path that
        can mint a snapshot: it derives approver, time, revision, lead/intake
        binding, payload and hash itself, so no caller can supply provenance.
        The status write carries the module-private token, so this is the only
        path to ``approved``. Both writes share one transaction: if either
        fails, neither persists. The broker stays on the lead form.
        """
        self.ensure_one()
        # Serialize approvals of one lead. Odoo cursors run at REPEATABLE READ:
        # a concurrent approval that committed first raises a serialization
        # failure here, and the request retry then sees the approved state.
        # justification: atomic row lock; the ORM has no SELECT ... FOR UPDATE.
        self.env.cr.execute("SELECT id FROM plasticos_web_lead WHERE id = %s FOR UPDATE", [self.id])
        self.invalidate_recordset(["review_status", "review_snapshot_ids"])
        if self.review_status == REVIEW_STATUS_APPROVED and self.review_snapshot_ids:
            return True

        self.env["plasticos.web.lead.review.snapshot"]._record_broker_approval(self)
        self.with_context(**{_APPROVAL_STATUS_KEY: _APPROVAL_STATUS_TOKEN}).write(
            {"review_status": REVIEW_STATUS_APPROVED}
        )
        self.message_post(body=f"Broker approved this lead for commercial preparation ({self.env.user.display_name}).")
        return True

    def action_request_clarification(self):
        """Record that evidence requires seller/broker clarification before approval."""
        self.ensure_one()
        self.write({"review_status": "clarification_required"})
        self.message_post(body="Broker marked this lead as requiring clarification before commercial preparation.")
        return True

    def action_reject_after_review(self):
        """Record a broker-reviewed rejection without deleting source evidence.

        A REVIEW lead leaves the queue as COLD with the broker as the actor; a
        HOT lead keeps its intake and evidence for audit.
        """
        self.ensure_one()
        values = {"review_status": "rejected"}
        if not self.intake_id and self.decision == DISPOSITION_REVIEW:
            reasons = dict(self.decision_reasons or {})
            reasons[KEY_MANUAL_OVERRIDE] = self._manual_override_record(DISPOSITION_COLD, self.review_notes or "")
            values.update({"decision": DISPOSITION_COLD, "decision_reasons": reasons, "state": "skipped"})
        self.write(values)
        if not self.intake_id:
            self._close_lead_review_activities("Rejected after broker review.")
        self.message_post(body="Broker rejected this lead after review; evidence remains retained for audit.")
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
        """Re-run the full AI triage pipeline (reassessment for a lead with no intake)."""
        for rec in self:
            if rec.state not in ("error", "skipped", "received", "review_pending"):
                raise UserError("Only errored, skipped, received, or review-pending leads can be re-triaged.")
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
        """Manual intake creation. Same validated path as Promote to HOT: rationale and verified weight."""
        return self.action_promote_to_hot()

    def action_force_hot(self):
        """Manual override to HOT. Same validated path as Promote to HOT: rationale and verified weight."""
        return self.action_promote_to_hot()

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
