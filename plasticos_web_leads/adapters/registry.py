"""Fail-closed registry of supported inbound web-lead providers."""

from __future__ import annotations

from .base import WebLeadAdapter
from .cognito import CognitoFormsAdapter

_ADAPTERS: dict[str, WebLeadAdapter] = {
    "cognito": CognitoFormsAdapter(),
}


def registered_provider_keys() -> tuple[str, ...]:
    """Provider keys Odoo will accept on the generic inbound route."""
    return tuple(_ADAPTERS)


def get_adapter(provider: str) -> WebLeadAdapter:
    """Return a known adapter or fail closed for unsupported providers."""
    normalized = (provider or "").strip().lower()
    try:
        return _ADAPTERS[normalized]
    except KeyError as exc:
        raise ValueError(f"Unsupported web-lead provider: {provider!r}") from exc
