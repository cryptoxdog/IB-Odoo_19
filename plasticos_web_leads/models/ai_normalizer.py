# ═══════════════════════════════════════════════════════════
# Module : ai_normalizer
# Purpose: Single LLM call to normalize freeform Cognito form
#          text into canonical Odoo values.  Runs inside Odoo
#          as a plain Python helper (no Odoo model).
# ═══════════════════════════════════════════════════════════
from __future__ import annotations

import json
import logging
import re
from typing import Any

_logger = logging.getLogger(__name__)

# ── Canonical value lists fed into the prompt ────────────────
CANONICAL_POLYMERS = [
    "HDPE",
    "LDPE",
    "LLDPE",
    "PP",
    "PET",
    "rPET",
    "PS",
    "HIPS",
    "PVC",
    "EVA",
    "ABS",
    "Nylon",
    "PC",
    "PBT",
    "POM",
    "PMMA",
    "PPO",
    "TPE",
    "TPU",
    "PLA",
    "E-Waste",
]

CANONICAL_FORMS = [
    "Bale",
    "Regrind",
    "Flake",
    "Pellet",
    "Rollstock",
    "Purge",
    "Lump",
    "Film",
    "Sheet",
    "Powder",
    "Parts",
    "Re-Useable",
]

CANONICAL_SOURCE_TYPES = [
    "post_industrial",
    "post_consumer",
    "post_commercial",
    "agricultural",
    "prime",
    "wide_spec",
    "off_spec",
    "ocean_recovered",
]

CANONICAL_COLORS = [
    "natural",
    "white",
    "black",
    "clear",
    "mixed",
]

# ── Deterministic weight inference (code fallback for LLM) ───
_UNIT_WEIGHT_DEFAULTS: dict[str, int] = {
    "pallet": 1100,
    "pallets": 1100,
    "gaylord": 1000,
    "gaylords": 1000,
    "bale": 1000,
    "bales": 1000,
    "truckload": 42000,
    "truckloads": 42000,
    "truck": 42000,
    "trucks": 42000,
    "load": 42000,
    "loads": 42000,
    "box": 50,
    "boxes": 50,
    "bag": 50,
    "bags": 50,
    "drum": 400,
    "drums": 400,
    "tote": 2000,
    "totes": 2000,
    "container": 42000,
    "containers": 42000,
    "supersack": 2000,
    "super sack": 2000,
    "super sacks": 2000,
    "supersacks": 2000,
}

_DIRECT_WEIGHT_RE = re.compile(
    r"(\d[\d,]*)\s*(?:lb|lbs|pound|pounds)",
    re.IGNORECASE,
)
_TON_RE = re.compile(
    r"(\d[\d,]*)\s*(?:ton|tons)",
    re.IGNORECASE,
)
_UNIT_COUNT_RE = re.compile(
    r"(\d[\d,]*)\s*(" + "|".join(sorted(_UNIT_WEIGHT_DEFAULTS, key=len, reverse=True)) + r")\b",
    re.IGNORECASE,
)
_FULL_TRUCK_RE = re.compile(
    r"\b(?:full\s+truck|truckload|full\s+load|ftl)\b",
    re.IGNORECASE,
)


def infer_weight_from_text(text: str | None) -> int | None:
    """Deterministic weight inference — sole shared parser.

    Priority: direct lbs → tons → count × default → "truckload"/"full truck" → None.
    """
    if not text:
        return None
    text = str(text).strip()
    if not text:
        return None

    # Direct lbs: "40,000 lbs"
    m = _DIRECT_WEIGHT_RE.search(text)
    if m:
        return int(m.group(1).replace(",", ""))

    # Tons: "20 tons"
    m = _TON_RE.search(text)
    if m:
        return int(m.group(1).replace(",", "")) * 2000

    # Unit count: "30 pallets", "5 gaylords"
    m = _UNIT_COUNT_RE.search(text)
    if m:
        count = int(m.group(1).replace(",", ""))
        unit = m.group(2).lower()
        per_unit = _UNIT_WEIGHT_DEFAULTS.get(unit, 1000)
        return count * per_unit

    # Bare "truckload" / "full truck" without a number
    if _FULL_TRUCK_RE.search(text):
        return 42000

    return None


# ── System prompt (kept tight — one call, one purpose) ───────
_SYSTEM_PROMPT = """\
You are a plastics-industry material analyst working for a recycled-plastics broker.
Your job: extract structured facts from a raw web-lead form submission.

Return ONLY valid JSON — no markdown, no commentary.

Output schema:
{
  "polymer": "<one of: %(polymers)s | null if unknown>",
  "form": "<one of: %(forms)s | null if unknown>",
  "color": "<one of: %(colors)s | null if unknown>",
  "source_type": "<one of: %(source_types)s | null if unknown>",
  "estimated_lbs_per_load": <integer or null>,
  "loads_per_month": <integer or null>,
  "is_plastic": <true | false>,
  "is_commercial_source": <true | false>,
  "material_summary": "<1-sentence plain-English summary>",
  "contaminants_noted": "<string or null>",
  "confidence": <0.0-1.0 float>
}

Rules:
- Map freeform text to the CLOSEST canonical value.
- If the submitter says "40,000 lbs" or "one truckload", estimate 40000.
- ALWAYS estimate estimated_lbs_per_load even when only unit counts are given.
  Use industry-standard weights: 1 pallet of baled plastic ≈ 1,000-1,200 lbs,
  1 gaylord ≈ 800-1,200 lbs, 1 truckload ≈ 40,000-44,000 lbs,
  1 bale ≈ 800-1,200 lbs. Multiply unit count × typical weight per unit.
  Example: "30 pallets" → 30 × 1,100 ≈ 33,000. Never return null or 0 when
  a unit count is provided — always infer a reasonable lbs estimate.
- If they say "ongoing" or "monthly", set loads_per_month to an integer.
- If the material is clearly not plastic (metal, wood, glass, etc.), set is_plastic=false.
- If the source sounds residential/individual, set is_commercial_source=false.
- Do NOT invent data for fields like polymer or source_type — use null when genuinely unknown.
  But DO infer estimated_lbs_per_load from context (unit counts, form type, images).
""" % {
    "polymers": ", ".join(CANONICAL_POLYMERS),
    "forms": ", ".join(CANONICAL_FORMS),
    "colors": ", ".join(CANONICAL_COLORS),
    "source_types": ", ".join(CANONICAL_SOURCE_TYPES),
}


def build_user_prompt(raw_payload: dict[str, Any]) -> str:
    """Build the user-message content from a raw Cognito form payload."""
    parts = []

    # Case-insensitive key → label mapping
    field_map = {
        "yourbusinesscompanyname": "Company",
        "yourname": "Contact",
        "describeyourmaterial": "Material Description",
        "whattypeofplastic": "Plastic Type",
        "whatisthequantity": "Quantity (units/pallets/bales)",
        "weightperload": "Weight Per Load",
        "howoftendoyouhavethismaterial": "Frequency",
        "arethereanycontaminants": "Contaminants",
        "whatisthesourceofthismaterial": "Source",
        "howisthematerialcurrentlystored": "Storage",
        "additionalnotes": "Notes",
    }

    # Build lowercase→original key index for case-insensitive access
    lower_payload = {str(k).lower(): v for k, v in raw_payload.items()}
    matched_lower_keys: set[str] = set()

    for lower_key, label in field_map.items():
        val = lower_payload.get(lower_key, "")
        if val:
            parts.append(f"{label}: {val}")
            matched_lower_keys.add(lower_key)

    # Catch any extra fields not in the map
    for k, v in raw_payload.items():
        if str(k).lower() not in matched_lower_keys and v and isinstance(v, str) and len(v) > 2:
            parts.append(f"{k}: {v}")

    return "\n".join(parts) if parts else "No form data provided."


def normalize_with_llm(
    raw_payload: dict[str, Any],
    api_key: str,
    model: str = "gpt-4o",
    base_url: str | None = None,
) -> dict[str, Any]:
    """Call OpenAI-compatible API to normalize a raw form payload.

    Returns the parsed JSON dict on success, or a fallback dict with
    ``"error"`` key on failure.  Never raises.
    """
    return _call_llm_single(raw_payload, api_key, model, base_url)


def normalize_with_fallback(
    raw_payload: dict[str, Any],
    providers: list[dict[str, Any]],
) -> dict[str, Any]:
    """Try each provider in order until one succeeds.

    ``providers`` is a list of dicts from config.get_llm_providers_ordered(),
    each containing: provider, api_key, model, base_url.
    """
    if not providers:
        return {"error": "No LLM providers configured with API keys."}

    last_error = ""
    for prov in providers:
        _logger.info("Trying LLM provider: %s (model=%s)", prov["provider"], prov["model"])
        result = _call_llm_single(
            raw_payload,
            api_key=prov["api_key"],
            model=prov["model"],
            base_url=prov.get("base_url"),
        )
        if not result.get("error"):
            result["_provider_used"] = prov["provider"]
            return result
        last_error = result["error"]
        _logger.warning(
            "Provider %s failed: %s — trying next fallback.",
            prov["provider"],
            last_error,
        )

    return {"error": f"All LLM providers failed. Last error: {last_error}"}


def _call_llm_single(
    raw_payload: dict[str, Any],
    api_key: str,
    model: str = "gpt-4o",
    base_url: str | None = None,
) -> dict[str, Any]:
    """Call a single OpenAI-compatible API to normalize a raw form payload.

    Anthropic and Mistral both expose OpenAI-compatible endpoints, so
    the openai Python client works for all three providers.
    """
    try:
        from openai import OpenAI  # type: ignore[import-untyped]
    except ImportError:
        _logger.error("openai package not installed — AI normalization unavailable.")
        return {"error": "openai package not installed"}

    user_content = build_user_prompt(raw_payload)
    _logger.debug("AI normalizer user prompt:\n%s", user_content)

    try:
        client_kwargs: dict[str, Any] = {"api_key": api_key}
        if base_url:
            client_kwargs["base_url"] = base_url
        client = OpenAI(**client_kwargs)

        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            temperature=0.1,
            max_tokens=600,
            response_format={"type": "json_object"},
        )

        raw_text = response.choices[0].message.content or "{}"
        result = json.loads(raw_text)

        # Backfill: if LLM returned null/0 for weight, try deterministic inference
        if not result.get("estimated_lbs_per_load"):
            joined_text = " ".join(str(v) for v in raw_payload.values() if isinstance(v, str))
            inferred = infer_weight_from_text(joined_text)
            if inferred:
                result["estimated_lbs_per_load"] = inferred
                result["_lbs_source"] = "deterministic_fallback"

        _logger.info(
            "AI normalization complete: polymer=%s, form=%s, lbs=%s",
            result.get("polymer"),
            result.get("form"),
            result.get("estimated_lbs_per_load"),
        )
        return result

    except json.JSONDecodeError as exc:
        _logger.warning("AI returned non-JSON: %s", exc)
        return {"error": f"JSON parse error: {exc}"}
    except Exception as exc:
        _logger.exception("AI normalization failed")
        return {"error": str(exc)}
