"""Small, dependency-free JSON recovery and bounded retry helpers for LLM calls."""

from __future__ import annotations

import json
import time
from typing import Any


def extract_json(text: str) -> dict[str, Any]:
    """Recover a JSON object from raw or Markdown-fenced model output."""
    candidate = (text or "").strip()
    if candidate.startswith("```"):
        candidate = candidate.split("\n", 1)[1] if "\n" in candidate else ""
        if candidate.rstrip().endswith("```"):
            candidate = candidate.rstrip()[:-3].rstrip()

    try:
        decoded = json.loads(candidate)
    except json.JSONDecodeError:
        start = candidate.find("{")
        if start < 0:
            raise ValueError("Model response did not contain a JSON object.") from None
        try:
            decoded, _ = json.JSONDecoder().raw_decode(candidate[start:])
        except json.JSONDecodeError as exc:
            raise ValueError("Model response did not contain valid JSON.") from exc

    if not isinstance(decoded, dict):
        raise ValueError("Model response JSON must be an object.")
    return decoded


def _usage_metadata(response: Any, *, attempts: int, model: str, elapsed_ms: int) -> dict[str, Any]:
    usage = getattr(response, "usage", None)
    return {
        "attempts": attempts,
        "model": model,
        "prompt_tokens": getattr(usage, "prompt_tokens", None),
        "completion_tokens": getattr(usage, "completion_tokens", None),
        "total_tokens": getattr(usage, "total_tokens", None),
        "elapsed_ms": elapsed_ms,
    }


def call_json_with_retry(
    *,
    client: Any,
    model: str,
    messages: list[dict[str, Any]],
    temperature: float = 0.0,
    max_attempts: int = 3,
    max_tokens: int | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Call one configured provider with bounded retries and JSON recovery."""
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least one.")

    started = time.monotonic()
    errors: list[str] = []
    for attempt in range(1, max_attempts + 1):
        try:
            kwargs: dict[str, Any] = {
                "model": model,
                "temperature": temperature,
                "response_format": {"type": "json_object"},
                "messages": messages,
            }
            if max_tokens is not None:
                kwargs["max_tokens"] = max_tokens
            response = client.chat.completions.create(**kwargs)
            content = response.choices[0].message.content or "{}"
            payload = extract_json(content)
            elapsed_ms = int((time.monotonic() - started) * 1000)
            return payload, _usage_metadata(response, attempts=attempt, model=model, elapsed_ms=elapsed_ms)
        except Exception as exc:  # Provider-specific exceptions are intentionally normalized here.
            errors.append(str(exc))

    raise ValueError(f"LLM JSON call failed after {max_attempts} attempts: {errors[-1] if errors else 'unknown error'}")
