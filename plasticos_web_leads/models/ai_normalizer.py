# ═══════════════════════════════════════════════════════════
# Module : ai_normalizer
# Purpose: Single LLM call to normalize freeform Cognito form
#          text into canonical Odoo values.  Runs inside Odoo
#          as a plain Python helper (no Odoo model).
# ═══════════════════════════════════════════════════════════
from __future__ import annotations

import json
import logging
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
- If they say "ongoing" or "monthly", set loads_per_month to an integer.
- If the material is clearly not plastic (metal, wood, glass, etc.), set is_plastic=false.
- If the source sounds residential/individual, set is_commercial_source=false.
- Do NOT invent data — use null when genuinely unknown.
""" % {
    "polymers": ", ".join(CANONICAL_POLYMERS),
    "forms": ", ".join(CANONICAL_FORMS),
    "colors": ", ".join(CANONICAL_COLORS),
    "source_types": ", ".join(CANONICAL_SOURCE_TYPES),
}


def build_user_prompt(raw_payload: dict[str, Any]) -> str:
    """Build the user-message content from a raw Cognito form payload."""
    parts = []

    # Extract known Cognito field names (case-insensitive search)
    field_map = {
        "YourBusinessCompanyName": "Company",
        "YourName": "Contact",
        "DescribeYourMaterial": "Material Description",
        "WhatTypeOfPlastic": "Plastic Type",
        "WhatIsTheQuantity": "Quantity",
        "HowOftenDoYouHaveThisMaterial": "Frequency",
        "AreThereAnyContaminants": "Contaminants",
        "WhatIsTheSourceOfThisMaterial": "Source",
        "HowIsTheMaterialCurrentlyStored": "Storage",
        "AdditionalNotes": "Notes",
    }

    for cognito_key, label in field_map.items():
        val = raw_payload.get(cognito_key, "")
        if val:
            parts.append(f"{label}: {val}")

    # Catch any extra fields not in the map
    mapped_keys = set(field_map.keys())
    for k, v in raw_payload.items():
        if k not in mapped_keys and v and isinstance(v, str) and len(v) > 2:
            parts.append(f"{k}: {v}")

    return "\n".join(parts) if parts else "No form data provided."


def normalize_with_llm(
    raw_payload: dict[str, Any],
    api_key: str,
    model: str = "gpt-4.1-mini",
    base_url: str | None = None,
) -> dict[str, Any]:
    """Call OpenAI-compatible API to normalize a raw form payload.

    Returns the parsed JSON dict on success, or a fallback dict with
    ``"error"`` key on failure.  Never raises.
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
