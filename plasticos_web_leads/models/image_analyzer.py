# ═══════════════════════════════════════════════════════════════════════════════
# image_analyzer.py
# Module : plasticos_web_leads
# Purpose: Analyse attached lead images via OpenAI Vision; merge multi-image
#          results into a single structured dict for downstream classification.
#
# FIXES APPLIED:
# IA-01 — merge_vision_results([]) / all-errors → returns None, no crash
# IA-02 — contamination_visible: any-positive logic writes back to merged dict
# IA-03 — observed_polymer_hint nulled when source confidence < threshold
# IA-04 — contamination_notes from all results aggregated
# IA-05 — error results filtered before any merge / confidence comparison
# ═══════════════════════════════════════════════════════════════════════════════
from __future__ import annotations

import base64
import logging
from typing import Any, Optional

_logger = logging.getLogger(__name__)

# Minimum result-level confidence for field-level acceptance (FIX IA-03)
_MIN_CONFIDENCE_THRESHOLD: float = 0.30

_VISION_SYSTEM_PROMPT = """You are a recycled-plastics materials specialist.
Analyse the image and return ONLY valid JSON with these fields (null if unknown):
{
  "observed_form": string | null,           // Bale | Pellet | Regrind | Flake | Film | Other
  "observed_color": string | null,          // dominant color(s)
  "observed_polymer_hint": string | null,   // HDPE | PP | PET | PS | PVC | LDPE | ABS | null
  "contamination_visible": boolean | null,
  "contamination_notes": string | null,
  "cleanliness": string | null,             // Clean | Lightly Contaminated | Heavily Contaminated
  "quantity_visible": boolean | null,
  "quantity_notes": string | null,
  "confidence": number                      // 0.0–1.0
}
Rules:
- Do NOT guess polymer from colour alone; only identify if markings/shape are definitive
- contamination_visible must be true if ANY contamination is apparent
- confidence < 0.3 indicates image quality is too poor for reliable extraction
"""


def _encode_image(image_bytes: bytes) -> str:
    return base64.b64encode(image_bytes).decode("utf-8")


def analyse_image(
    image_bytes: bytes,
    openai_client,
    *,
    model: str = "gpt-4o",
    mime_type: str = "image/jpeg",
) -> dict[str, Any]:
    """
    Analyse a single image. Returns a result dict or {"error": "..."} on failure.
    """
    try:
        import json
        b64 = _encode_image(image_bytes)
        response = openai_client.chat.completions.create(
            model=model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": _VISION_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{b64}",
                                "detail": "low",
                            },
                        },
                        {"type": "text", "text": "Analyse this plastic material image."},
                    ],
                },
            ],
            max_tokens=512,
        )
        raw = response.choices[0].message.content or "{}"
        return json.loads(raw)
    except Exception as exc:
        _logger.warning("analyse_image: failed: %s", exc)
        return {"error": str(exc)}


def merge_vision_results(
    results: list[dict[str, Any]],
    *,
    min_confidence: float = _MIN_CONFIDENCE_THRESHOLD,
) -> Optional[dict[str, Any]]:
    """
    Merge a list of per-image analysis results into one canonical dict.

    Strategy:
      1. Filter out error results (FIX IA-05)
      2. If no valid results remain, return None (FIX IA-01)
      3. Sort by confidence descending; use highest-confidence result as base
      4. contamination_visible: True wins if ANY result flagged it (FIX IA-02)
      5. contamination_notes: aggregate all non-empty notes (FIX IA-04)
      6. observed_polymer_hint: null if base confidence < min_confidence (FIX IA-03)

    Returns:
      Merged dict, or None if no usable results.
    """
    if not results:
        return None  # FIX IA-01: no crash on empty list

    # FIX IA-05 — filter errors before any processing
    valid = [r for r in results if "error" not in r]
    if not valid:
        return None  # FIX IA-01: no crash when all results are errors

    # Sort by confidence descending
    valid.sort(key=lambda r: r.get("confidence", 0.0), reverse=True)
    base = dict(valid[0])  # highest-confidence result is the base

    # FIX IA-02 — contamination_visible: any positive wins (write back to base)
    if any(r.get("contamination_visible") is True for r in valid):
        base["contamination_visible"] = True
    elif all(r.get("contamination_visible") is False for r in valid):
        base["contamination_visible"] = False
    # else: mixed None/False → keep base value

    # FIX IA-04 — aggregate contamination_notes from all results
    notes: list[str] = []
    for r in valid:
        n = (r.get("contamination_notes") or "").strip()
        if n and n not in notes:
            notes.append(n)
    if notes:
        base["contamination_notes"] = "; ".join(notes)

    # FIX IA-03 — null polymer hint if base confidence is too low
    base_conf = base.get("confidence", 0.0)
    if base_conf < min_confidence:
        base["observed_polymer_hint"] = None
        _logger.debug(
            "merge_vision_results: observed_polymer_hint nulled (confidence %.2f < %.2f)",
            base_conf, min_confidence,
        )

    return base
