"""Provider-agnostic structured text and vision inference for web-lead triage.

The Odoo configuration owns provider order, credentials, model names, and role
selection.  This module has no classification authority: it only returns
validated, auditable inference evidence or a bounded provider-local error.
"""

from __future__ import annotations

import base64
import logging
from dataclasses import dataclass
from typing import Any

from .ai_client import call_json_with_retry, extract_json
from .evidence_keys import KEY_ERROR, KEY_ERROR_TYPE, KEY_MODEL, KEY_PROVIDER, KEY_ROLE, KEY_TRANSPORT

_logger = logging.getLogger(__name__)

ROLE_TEXT_NORMALIZATION = "text_normalization"
ROLE_VISION_ANALYSIS = "vision_analysis"
ROLE_ECONOMIC_EVALUATION = "economic_evaluation"
SUPPORTED_INFERENCE_ROLES = (
    ROLE_TEXT_NORMALIZATION,
    ROLE_VISION_ANALYSIS,
    ROLE_ECONOMIC_EVALUATION,
)

TRANSPORT_OPENAI_COMPATIBLE = "openai_compatible"
TRANSPORT_ANTHROPIC_MESSAGES = "anthropic_messages"
SUPPORTED_TRANSPORTS = (
    TRANSPORT_OPENAI_COMPATIBLE,
    TRANSPORT_ANTHROPIC_MESSAGES,
)


@dataclass(frozen=True)
class InferenceProvider:
    """A configured provider selected for one non-authoritative inference role."""

    provider: str
    transport: str
    api_key: str
    model: str
    base_url: str | None = None
    workspace_id: str | None = None
    temperature: float = 0.0

    @property
    def audit_label(self) -> str:
        return f"{self.provider}:{self.model}"


def provider_audit_metadata(provider: InferenceProvider, *, role: str) -> dict[str, str]:
    """Return credential-free selection data for durable evidence."""
    return {
        KEY_ROLE: role,
        KEY_PROVIDER: provider.provider,
        KEY_TRANSPORT: provider.transport,
        KEY_MODEL: provider.model,
    }


def _openai_client(provider: InferenceProvider) -> Any:
    try:
        from openai import OpenAI  # type: ignore[import-untyped]
    except ImportError as exc:
        raise RuntimeError("The OpenAI Python SDK is required for the configured provider transport.") from exc

    kwargs: dict[str, Any] = {"api_key": provider.api_key}
    if provider.base_url:
        kwargs["base_url"] = provider.base_url
    if provider.workspace_id:
        kwargs["default_headers"] = {"anthropic-workspace-id": provider.workspace_id}
    return OpenAI(**kwargs)


def _anthropic_client(provider: InferenceProvider) -> Any:
    try:
        from anthropic import Anthropic  # type: ignore[import-untyped]
    except ImportError as exc:
        raise RuntimeError("The anthropic Python SDK is required for the configured provider transport.") from exc

    kwargs: dict[str, Any] = {"api_key": provider.api_key}
    if provider.base_url:
        kwargs["base_url"] = provider.base_url.rstrip("/")
    if provider.workspace_id:
        kwargs["default_headers"] = {"anthropic-workspace-id": provider.workspace_id}
    return Anthropic(**kwargs)


def _anthropic_text(response: Any) -> str:
    for block in getattr(response, "content", ()):
        if getattr(block, "type", None) == "text":
            return str(getattr(block, "text", ""))
    raise ValueError("Anthropic response did not include a text content block.")


def _anthropic_usage_metadata(response: Any, provider: InferenceProvider) -> dict[str, Any]:
    usage = getattr(response, "usage", None)
    return {
        "attempts": 1,
        "model": provider.model,
        "prompt_tokens": getattr(usage, "input_tokens", None),
        "completion_tokens": getattr(usage, "output_tokens", None),
        "total_tokens": None,
    }


def _call_anthropic_json(
    provider: InferenceProvider,
    *,
    system_prompt: str,
    user_content: Any,
    max_tokens: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    client = _anthropic_client(provider)
    response = client.messages.create(
        model=provider.model,
        max_tokens=max_tokens,
        temperature=provider.temperature,
        system=system_prompt,
        messages=[{"role": "user", "content": user_content}],
    )
    return extract_json(_anthropic_text(response)), _anthropic_usage_metadata(response, provider)


def call_structured_text(
    provider: InferenceProvider,
    *,
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 1024,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Run a provider-selected structured text inference call."""
    if provider.transport == TRANSPORT_ANTHROPIC_MESSAGES:
        return _call_anthropic_json(
            provider,
            system_prompt=system_prompt,
            user_content=user_prompt,
            max_tokens=max_tokens,
        )
    if provider.transport == TRANSPORT_OPENAI_COMPATIBLE:
        client = _openai_client(provider)
        return call_json_with_retry(
            client=client,
            model=provider.model,
            temperature=provider.temperature,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
    raise ValueError(f"Unsupported inference transport: {provider.transport!r}")


def call_structured_vision(
    provider: InferenceProvider,
    *,
    system_prompt: str,
    image_bytes: bytes,
    content_type: str,
    prompt: str,
    max_tokens: int = 512,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Run a provider-selected structured vision inference call on admitted bytes."""
    encoded = base64.b64encode(image_bytes).decode("ascii")
    if provider.transport == TRANSPORT_ANTHROPIC_MESSAGES:
        return _call_anthropic_json(
            provider,
            system_prompt=system_prompt,
            user_content=[
                {
                    "type": "image",
                    "source": {"type": "base64", "media_type": content_type, "data": encoded},
                },
                {"type": "text", "text": prompt},
            ],
            max_tokens=max_tokens,
        )
    if provider.transport == TRANSPORT_OPENAI_COMPATIBLE:
        client = _openai_client(provider)
        response = client.chat.completions.create(
            model=provider.model,
            temperature=provider.temperature,
            response_format={"type": "json_object"},
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{content_type};base64,{encoded}", "detail": "low"},
                        },
                        {"type": "text", "text": prompt},
                    ],
                },
            ],
        )
        content = response.choices[0].message.content or "{}"
        return extract_json(content), {
            "attempts": 1,
            "model": provider.model,
            "prompt_tokens": getattr(getattr(response, "usage", None), "prompt_tokens", None),
            "completion_tokens": getattr(getattr(response, "usage", None), "completion_tokens", None),
            "total_tokens": getattr(getattr(response, "usage", None), "total_tokens", None),
        }
    raise ValueError(f"Unsupported inference transport: {provider.transport!r}")


def safe_provider_error(exc: Exception, provider: InferenceProvider, *, role: str) -> dict[str, Any]:
    """Preserve a credential-free, provider-scoped error in audit evidence."""
    _logger.warning(
        "Web-lead %s inference failed via %s (%s)",
        role,
        provider.audit_label,
        type(exc).__name__,
    )
    return {
        KEY_ERROR: "provider_inference_failed",
        KEY_ERROR_TYPE: type(exc).__name__,
        KEY_PROVIDER: provider_audit_metadata(provider, role=role),
    }
