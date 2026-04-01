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

import json
import logging
from typing import Any, Optional

from .triage_helpers import coerce_bool, safe_float, safe_int, parse_weight_lbs

_logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Field map: Typeform internal key → human-readable prompt label
# Keep in sync with the actual form field IDs.
# ─────────────────────────────────────────────────────────────────────────────
_FIELD_MAP: dict[str, str] = {
    "YourBusinessCompanyName": "Company",
    "DescribeYourMaterial": "Material description",
    "WhatIsTheQuantity": "Quantity / volume",
    "HowOften": "Frequency",
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
  "polymer": string | null,                  // e.g. "HDPE", "PP", "LDPE", "PET", "PS", "ABS", "PVC"
  "material_description": string | null,     // cleaned description of the material
  "source_type": string | null,              // one of: post_industrial | post_consumer | ocean_recovered | unknown
  "source_description": string | null,       // brief description of where material comes from
  "estimated_lbs_per_load": number | null,   // weight in lbs, numeric only, null if not determinable
  "loads_per_month": number | null,          // frequency, numeric only
  "is_plastic": boolean | null,              // true if definitely plastic, false if not, null if uncertain
  "is_commercial_source": boolean | null,    // true if industrial/commercial origin, false if residential
  "confidence": number,                      // 0.0–1.0 overall confidence in this extraction
  "notes": string | null                     // any extraction caveats
}

Rules:
- DO NOT infer estimated_lbs_per_load from vague descriptions like "some" or "a few"
- DO NOT set is_commercial_source=true based on email domain alone
- If the Quantity field contains unit counts (pallets, gaylords, truckloads), \
  set estimated_lbs_per_load to null — the deterministic parser handles unit-count conversion
- Polymer codes: HDPE, LDPE, LLDPE, PP, PET, PS, ABS, PVC, PC, POM, PA (Nylon), EVA
- post_industrial = manufacturing scrap, trim, runners, off-spec
- post_consumer = used products, bottles, film, packaging after consumer use
- Confidence below 0.4 means you are guessing — reflect that in the value
"""

# ─────────────────────────────────────────────────────────────────────────────
# Validation bounds
# ─────────────────────────────────────────────────────────────────────────────
_LBS_MAX = 200_000.0   # single-load max plausible lbs
_LBS_MIN = 1.0         # anything below 1 lb is noise
_LOADS_MAX = 365.0     # max loads/month (daily = 30, weekly = 52/yr ≈ 4.3/mo)


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
        if lbs <= 0 or lbs > _LBS_MAX:
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
    for str_field in ("polymer", "source_type", "material_description",
                      "source_description", "notes"):
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
        if val and str(val).strip() and len(str(val).strip()) > 2:
            lines.append(f"{label}: {str(val).strip()}")
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
    inferred_fields: Optional[set[str]] = None,
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

        # FIX AN-05: use explicit None check, not falsy-or
        if existing is None:
            merged[field] = ai_val
            inferred_fields.add(field)
        # Special case: weight — deterministic parser always wins
        elif field == "estimated_lbs_per_load" and existing == 0:
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
    det_lbs, det_source = parse_weight_lbs(qty_raw)

    base: dict[str, Any] = {
        "raw_form_data": form_data,
        "estimated_lbs_per_load": det_lbs if det_lbs > 0 else None,
        "weight_source": det_source,
    }

    if openai_client is None:
        base["_inferred_fields"] = []
        return base

    # Step 2 — AI extraction
    try:
        user_prompt = build_user_prompt(form_data)
        response = openai_client.chat.completions.create(
            model=model,
            temperature=temperature,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        )
        raw_json = response.choices[0].message.content or "{}"
        ai_raw: dict[str, Any] = json.loads(raw_json)
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
