# ═══════════════════════════════════════════════════════════
# Module : image_analyzer
# Purpose: Single Vision API call to extract objective facts
#          from material images uploaded via Cognito forms.
# ═══════════════════════════════════════════════════════════
from __future__ import annotations

import json
import logging
from typing import Any

_logger = logging.getLogger(__name__)

_VISION_SYSTEM_PROMPT = """\
You are a plastics-industry visual analyst.  Examine the image of recycled
plastic material and extract ONLY objective, observable facts.

Return ONLY valid JSON — no markdown, no commentary.

Output schema:
{
  "observed_polymer_hint": "<best guess polymer type or null>",
  "observed_form": "<bales|regrind|flake|pellet|film|lump|purge|parts|other|null>",
  "observed_color": "<natural|white|black|clear|mixed|other|null>",
  "contamination_visible": <true|false>,
  "contamination_notes": "<description or null>",
  "packaging_type": "<gaylord|supersack|loose|palletized|bulk_trailer|other|null>",
  "estimated_condition": "<clean|lightly_contaminated|heavily_contaminated|null>",
  "visual_summary": "<1-sentence objective description>",
  "confidence": <0.0-1.0 float>
}

Rules:
- Describe ONLY what you can see.  Do NOT speculate on weight, volume, or price.
- If the image is blurry, dark, or not of plastic material, set confidence < 0.3.
- Use null for any field you cannot determine from the image.
"""


def analyze_image(
    image_url: str,
    api_key: str,
    model: str = "gpt-4.1-mini",
    base_url: str | None = None,
) -> dict[str, Any]:
    """Send a single image URL to the Vision API and return structured facts.

    Returns the parsed JSON dict on success, or a dict with ``"error"``
    key on failure.  Never raises.
    """
    try:
        from openai import OpenAI  # type: ignore[import-untyped]
    except ImportError:
        _logger.error("openai package not installed — vision analysis unavailable.")
        return {"error": "openai package not installed"}

    _logger.info("Analyzing image: %s", image_url[:120])

    try:
        client_kwargs: dict[str, Any] = {"api_key": api_key}
        if base_url:
            client_kwargs["base_url"] = base_url
        client = OpenAI(**client_kwargs)

        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": _VISION_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": ("Analyze this image of recycled plastic material. Return structured JSON only."),
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": image_url, "detail": "low"},
                        },
                    ],
                },
            ],
            temperature=0.1,
            max_tokens=400,
            response_format={"type": "json_object"},
        )

        raw_text = response.choices[0].message.content or "{}"
        result = json.loads(raw_text)
        _logger.info(
            "Vision analysis complete: form=%s, color=%s, confidence=%.2f",
            result.get("observed_form"),
            result.get("observed_color"),
            result.get("confidence", 0),
        )
        return result

    except json.JSONDecodeError as exc:
        _logger.warning("Vision API returned non-JSON: %s", exc)
        return {"error": f"JSON parse error: {exc}"}
    except Exception as exc:
        _logger.exception("Vision analysis failed for %s", image_url[:80])
        return {"error": str(exc)}


def analyze_multiple_images(
    image_urls: list[str],
    api_key: str,
    model: str = "gpt-4.1-mini",
    base_url: str | None = None,
    max_images: int = 5,
) -> list[dict[str, Any]]:
    """Analyze up to ``max_images`` URLs sequentially.

    Returns a list of result dicts (one per image).
    """
    results: list[dict[str, Any]] = []
    for url in image_urls[:max_images]:
        result = analyze_image(url, api_key, model, base_url)
        result["source_url"] = url
        results.append(result)
    return results
