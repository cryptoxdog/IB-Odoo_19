"""Fail-closed registry of supported inbound web-lead providers."""

from __future__ import annotations

from .base import WebLeadProviderAdapter
from .cognito import CognitoAdapter

_ADAPTERS: dict[str, WebLeadProviderAdapter] = {
    "cognito": CognitoAdapter(),
}


def get_adapter(provider: str) -> WebLeadProviderAdapter:
    """Return a known adapter or fail closed for unsupported providers."""
    normalized = (provider or "").strip().lower()
    try:
        return _ADAPTERS[normalized]
    except KeyError as exc:
        raise ValueError(f"Unsupported web-lead provider: {provider!r}") from exc
