# ═══════════════════════════════════════════════════════════════════════════════
# ai_normalizer.py
# Module : plasticos_web_leads
# Purpose: Call OpenAI to extract structured fields from raw web-lead form data,
#          validate + sanitise the response, and merge with deterministic parse.
#
# FIXES APPLIED:
# AN-01 — validate_ai_output() implemented with explicit type + bounds rules
# AN-02 — numeric bounds: estimated_lbs clamped (0, 200000], loads_per_month ≥ 0
# AN-03 — build_user_prompt() skips empty/short values; maps canonical field names
# AN-04 — _SYSTEM_PROMPT updated to match current Typeform field names
# AN-05 — merge uses explicit None-check (not falsy-or chain)
# AN-06 — _inferred_fields set tracked and written to result for audit trail
#
# Imports safe helpers from triage_helpers (WL-06 fix: no duplication).
# ═══════════════════════════════════════════════════════════════════════════════
from __future__ import annotations

import logging
from typing import Any

from .ai_client import call_json_with_retry
from .inference_provider import InferenceProvider, call_structured_text, provider_audit_metadata, safe_provider_error
from .quantity_normalizer import QuantityEvidence
from .triage_helpers import coerce_bool, parse_weight_lbs, safe_float

_logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Field map: Typeform internal key → human-readable prompt label
# Keep in sync with the actual form field IDs.
# ─────────────────────────────────────────────────────────────────────────────
_FIELD_MAP: dict[str, str] = {
    "company_name": "Company",
    "YourBusinessCompanyName": "Company",
    "material_description": "Material description",
    "DescribeYourMaterial": "Material description",
    "material_composition_text": "Material composition",
    "source_description": "Source description",
    "quantity_text": "Quantity / current inventory",
    "WhatIsTheQuantity": "Quantity / volume",
    "weight_per_load_text": "Weight per load",
    "frequency_text": "Frequency",
    "HowOften": "Frequency",
    "pickup_location_text": "Location / city / state",
    "WhereIsItLocated": "Location / city / state",
    "WhatIsYourRole": "Role at company",
    "AdditionalComments": "Additional notes",
    "Email": "Email",
    "PhoneNumber": "Phone",
}

# ─────────────────────────────────────────────────────────────────────────────
# System prompt — spec-aligned, static string (FIX AN-04)
# ─────────────────────────────────────────────────────────────────────────────
_SYSTEM_PROMPT = """You are a recycled-plastics intake specialist. \
Extract structured fields from the raw web-lead form below.

Return ONLY valid JSON — no markdown, no commentary, no trailing text.

Required JSON fields (use null when unknown):
{
  "polymer": str | null,                     // e.g. "HDPE", "PP", "LDPE", "PET", "PS", "ABS", "PVC"
  "material_description": str | null,        // cleaned description of the material
  "source_type": str | null,                 // one of: post_industrial | post_consumer | ocean_recovered | unknown
  "source_description": str | null,          // brief description of where material comes from
  "estimated_lbs_per_load": number | null,   // weight in lbs, numeric only, null if not determinable
  "loads_per_month": number | null,          // frequency, numeric only
  "is_plastic": boolean | null,              // true if definitely plastic, false if not, null if uncertain
  "is_commercial_source": boolean | null,    // true if industrial/commercial origin, false if residential
  "confidence": number,                      // 0.0-1.0 overall confidence in this extraction
  "notes": str | null                        // any extraction caveats
}

Rules:
- DO NOT infer estimated_lbs_per_load from vague descriptions like "some" or "a few"
- DO NOT set is_commercial_source=true based on email domain alone
- If the Quantity field contains unit counts (pallets, gaylords, truckloads), \
  set estimated_lbs_per_load to null — the deterministic parser handles unit-count conversion
- Current inventory, per-load weight, and recurring cadence are separate facts.
- Cadence requires explicit time-basis language; unknown is null, never zero.
- Do not infer a polymer from weak context or visual appearance.
- Polymer codes: HDPE, LDPE, LLDPE, PP, PET, PS, ABS, PVC, PC, POM, PA (Nylon), EVA
- post_industrial = manufacturing scrap, trim, runners, off-spec
- post_consumer = used products, bottles, film, packaging after consumer use
- Confidence below 0.4 means you are guessing — reflect that in the value
"""

# ─────────────────────────────────────────────────────────────────────────────
# Validation bounds
# ─────────────────────────────────────────────────────────────────────────────
_LBS_MAX = 200_000.0  # single-load max plausible lbs
_LBS_MIN = 1.0  # anything below 1 lb is noise
_LOADS_MAX = 365.0  # max loads/month (daily = 30, weekly = 52/yr ≈ 4.3/mo)


def validate_ai_output(raw: dict[str, Any]) -> dict[str, Any]:
    """
    Sanitise and clamp AI-extracted field values. (FIX AN-01, AN-02)

    Rules applied per field:
      estimated_lbs_per_load  — must be (_LBS_MIN, _LBS_MAX]; outside → null
      loads_per_month         — must be ≥ 0; negative → null
      confidence              — clamped to [0.0, 1.0]
      is_plastic              — coerced via coerce_bool()
      is_commercial_source    — coerced via coerce_bool()
      polymer / source_type / material_description / source_description
                              — empty/whitespace-only strings → null
    """
    out: dict[str, Any] = dict(raw)

    # ── estimated_lbs_per_load ────────────────────────────────────────────
    lbs_raw = out.get("estimated_lbs_per_load")
    if lbs_raw is not None:
        lbs = safe_float(lbs_raw)
        if lbs < _LBS_MIN or lbs > _LBS_MAX:
            _logger.debug("validate_ai_output: clamping estimated_lbs_per_load %s → null", lbs_raw)
            out["estimated_lbs_per_load"] = None
        else:
            out["estimated_lbs_per_load"] = int(lbs)  # store as integer lbs

    # ── loads_per_month ───────────────────────────────────────────────────
    loads_raw = out.get("loads_per_month")
    if loads_raw is not None:
        loads = safe_float(loads_raw)
        if loads < 0:
            out["loads_per_month"] = None
        else:
            out["loads_per_month"] = int(loads)

    # ── confidence ────────────────────────────────────────────────────────
    conf_raw = out.get("confidence")
    if conf_raw is not None:
        out["confidence"] = max(0.0, min(1.0, safe_float(conf_raw)))

    # ── boolean fields ────────────────────────────────────────────────────
    for bool_field in ("is_plastic", "is_commercial_source"):
        if bool_field in out:
            out[bool_field] = coerce_bool(out[bool_field])

    # ── string fields: empty → null ───────────────────────────────────────
    for str_field in ("polymer", "source_type", "material_description", "source_description", "notes"):
        val = out.get(str_field)
        if isinstance(val, str) and not val.strip():
            out[str_field] = None
        elif isinstance(val, str):
            out[str_field] = val.strip()

    return out


def build_user_prompt(form_data: dict[str, Any]) -> str:
    """
    Build the user-turn prompt from raw form data. (FIX AN-03)

    - Maps known Typeform field IDs to human labels
    - Skips empty strings and values ≤ 2 characters
    - Appends unmapped fields as "Extra" lines (values > 2 chars only)
    """
    if not form_data:
        return "No form data provided."

    lines: list[str] = ["=== Web Lead Form Data ==="]
    seen_keys: set[str] = set()

    # Mapped fields first, in defined order
    for field_id, label in _FIELD_MAP.items():
        val = form_data.get(field_id)
        val_str = str(val).strip() if val is not None else ""
        if len(val_str) > 2:
            lines.append(f"{label}: {val_str}")
            seen_keys.add(field_id)

    # Extra / unmapped fields
    for k, v in form_data.items():
        if k in seen_keys:
            continue
        val_str = str(v).strip() if v is not None else ""
        if len(val_str) > 2:
            lines.append(f"Extra — {k}: {val_str}")

    if len(lines) == 1:
        return "No form data provided."

    return "\n".join(lines)


def merge_ai_into_record(
    record: dict[str, Any],
    ai_result: dict[str, Any],
    *,
    inferred_fields: set[str] | None = None,
) -> dict[str, Any]:
    """
    Merge validated AI result into an existing record dict. (FIX AN-05, AN-06)

    Rules:
    - Existing non-None values are NOT overwritten by AI values.
    - AI values are written only into fields that are currently None.
    - estimated_lbs_per_load: deterministic parse always wins if non-zero;
      AI value used only when deterministic returns 0.
    - All fields written from AI are recorded in inferred_fields set.
    """
    if inferred_fields is None:
        inferred_fields = set()

    merged = dict(record)

    for field, ai_val in ai_result.items():
        if ai_val is None:
            continue  # AI didn't know — skip
        existing = merged.get(field)

        if existing is None:
            merged[field] = ai_val
            inferred_fields.add(field)

    merged["_inferred_fields"] = sorted(inferred_fields)
    return merged


def normalize_lead(
    form_data: dict[str, Any],
    openai_client=None,
    *,
    model: str = "gpt-4o-mini",
    temperature: float = 0.0,
    quantity_evidence: QuantityEvidence | None = None,
) -> dict[str, Any]:
    """
    Full normalization pipeline for a web lead.

    Steps:
      1. Deterministic weight parse from WhatIsTheQuantity field
      2. AI extraction (if client provided)
      3. Validation / sanitisation of AI output
      4. Merge: deterministic values win over AI values
      5. Audit trail written to _inferred_fields

    Returns the merged record dict. Falls back gracefully if AI is unavailable.
    """
    # Step 1 — deterministic weight
    qty_raw = form_data.get("WhatIsTheQuantity") or ""
    if quantity_evidence is None:
        det_lbs, det_source = parse_weight_lbs(qty_raw)
        deterministic_lbs = det_lbs if det_lbs > 0 else None
    else:
        deterministic_lbs = quantity_evidence.load_weight_lbs
        det_source = quantity_evidence.weight_source

    base: dict[str, Any] = {
        "raw_form_data": form_data,
        "estimated_lbs_per_load": deterministic_lbs,
        "weight_source": det_source,
    }
    if quantity_evidence is not None:
        base["loads_per_month"] = quantity_evidence.loads_per_month

    if openai_client is None:
        base["_inferred_fields"] = []
        return base

    # Step 2 — AI extraction
    try:
        user_prompt = build_user_prompt(form_data)
        ai_raw, metadata = call_json_with_retry(
            client=openai_client,
            model=model,
            temperature=temperature,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        )
        base["_ai_call_metadata"] = metadata
    except Exception as exc:
        _logger.warning("normalize_lead: AI extraction failed: %s", exc)
        base["_inferred_fields"] = []
        base["_ai_error"] = str(exc)
        return base

    # Step 3 — validate
    ai_validated = validate_ai_output(ai_raw)

    # Step 4+5 — merge with audit trail
    inferred: set[str] = set()
    result = merge_ai_into_record(base, ai_validated, inferred_fields=inferred)
    return result


def normalize_with_provider(
    raw_payload: dict[str, Any],
    provider: InferenceProvider,
    *,
    quantity_evidence: QuantityEvidence | None = None,
) -> dict[str, Any]:
    """Normalize with a configured role-selected provider profile.

    Provider/model selection is configuration, not code. Deterministic quantity
    evidence stays authoritative over the returned LLM extraction.
    """
    form_data = raw_payload or {}
    if quantity_evidence is None:
        det_lbs, det_source = parse_weight_lbs(form_data.get("WhatIsTheQuantity") or "")
        deterministic_lbs = det_lbs if det_lbs > 0 else None
    else:
        deterministic_lbs = quantity_evidence.load_weight_lbs
        det_source = quantity_evidence.weight_source

    base: dict[str, Any] = {
        "raw_form_data": form_data,
        "estimated_lbs_per_load": deterministic_lbs,
        "weight_source": det_source,
    }
    if quantity_evidence is not None:
        base["loads_per_month"] = quantity_evidence.loads_per_month

    try:
        ai_raw, metadata = call_structured_text(
            provider,
            system_prompt=_SYSTEM_PROMPT,
            user_prompt=build_user_prompt(form_data),
        )
    except Exception as exc:
        error = safe_provider_error(exc, provider, role="text_normalization")
        base["_inferred_fields"] = []
        base["_ai_error"] = error["error"]
        base["_provider_used"] = provider.provider
        base["_provider_metadata"] = error["provider"]
        return base

    result = merge_ai_into_record(base, validate_ai_output(ai_raw), inferred_fields=set())
    result["_provider_used"] = provider.provider
    result["_provider_metadata"] = provider_audit_metadata(provider, role="text_normalization")
    result["_ai_call_metadata"] = metadata
    return result


def _build_openai_client(api_key: str | None, base_url: str | None = None):
    """Construct an OpenAI-compatible client, or None if key/package is missing.

    Mirrors the construction pattern in image_analyzer.analyze_image so all
    providers (OpenAI, Anthropic, Mistral) are reached through the OpenAI SDK's
    compatibility layer via their respective base_url.
    """
    if not api_key:
        return None
    try:
        from openai import OpenAI  # type: ignore[import-untyped]
    except ImportError:
        _logger.error("openai package not installed — AI normalization unavailable.")
        return None
    client_kwargs: dict[str, Any] = {"api_key": api_key}
    if base_url:
        client_kwargs["base_url"] = base_url
    return OpenAI(**client_kwargs)


def normalize_with_fallback(
    raw_payload: dict[str, Any],
    providers: list[dict[str, Any]],
    *,
    temperature: float = 0.0,
    quantity_evidence: QuantityEvidence | None = None,
) -> dict[str, Any]:
    """
    Run normalize_lead across an ordered list of LLM providers with fallback.

    Each provider dict has the shape returned by
    plasticos.web.lead.config.get_llm_providers_ordered()::

        {"provider": str, "api_key": str, "model": str, "base_url": str | None}

    Behaviour:
      - Tries providers in order (primary → secondary → tertiary).
      - Returns the merged record from the FIRST provider that succeeds, with
        "_provider_used" set to that provider's slug.
      - If a provider's AI call fails (normalize_lead sets "_ai_error"), the
        next provider is attempted.
      - If every provider fails — or none are configured — returns the
        deterministic-only base dict with "_provider_used"="none" and "error"
        set, so the caller can log the failure without crashing.
    """
    form_data = raw_payload or {}

    if not providers:
        if quantity_evidence is None:
            result = normalize_lead(form_data, None, temperature=temperature)
        else:
            result = normalize_lead(form_data, None, temperature=temperature, quantity_evidence=quantity_evidence)
        result["_provider_used"] = "none"
        result["error"] = "no_llm_provider_configured"
        return result

    last_error: str | None = None
    for prov in providers:
        slug = prov.get("provider") or "unknown"
        client = _build_openai_client(prov.get("api_key"), prov.get("base_url"))
        if client is None:
            # Same import/key failure would affect every provider — stop early.
            last_error = "openai_client_unavailable"
            break
        kwargs: dict[str, Any] = {
            "model": prov.get("model") or "gpt-4o-mini",
            "temperature": temperature,
        }
        if quantity_evidence is not None:
            kwargs["quantity_evidence"] = quantity_evidence
        result = normalize_lead(form_data, client, **kwargs)
        ai_error = result.get("_ai_error")
        if not ai_error:
            result["_provider_used"] = slug
            return result
        last_error = "provider_inference_failed"
        _logger.warning("normalize_with_fallback: provider %s failed", slug)

    if quantity_evidence is None:
        result = normalize_lead(form_data, None, temperature=temperature)
    else:
        result = normalize_lead(form_data, None, temperature=temperature, quantity_evidence=quantity_evidence)
    result["_provider_used"] = "none"
    result["error"] = last_error or "all_llm_providers_failed"
    return result
