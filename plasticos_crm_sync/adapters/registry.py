"""Provider → adapter factory registry."""

from __future__ import annotations

from typing import Any

from .base import CrmAdapterError, CrmAdapterStubError
from .hubspot import HubSpotAdapter
from .salesforce import SalesforceAdapter
from .vanillasoft.adapter import VanillaSoftAdapter
from .vanillasoft.client import VanillaSoftClient
from .zoho import ZohoAdapter

PROVIDER_SELECTION = [
    ("vanillasoft", "VanillaSoft"),
    ("hubspot", "HubSpot (stub)"),
    ("salesforce", "Salesforce (stub)"),
    ("zoho", "Zoho (stub)"),
]

LIVE_PROVIDERS = frozenset({"vanillasoft"})


def is_live_provider(provider: str) -> bool:
    return provider in LIVE_PROVIDERS


def get_adapter(provider: str, *, api_key: str = "", root_endpoint: str = "", project_id: int = 0) -> Any:
    """Return adapter instance for provider.

    Stub providers are returned as scaffold instances (methods raise CrmAdapterStubError).
    """
    key = (provider or "").strip().lower()
    if key == PROVIDER_SELECTION[0][0]:
        if not api_key or not root_endpoint or not project_id:
            raise CrmAdapterError("VanillaSoft requires api_key, root_endpoint, and project_id")
        client = VanillaSoftClient(api_key, root_endpoint)
        return VanillaSoftAdapter(client, int(project_id))
    if key == PROVIDER_SELECTION[1][0]:
        return HubSpotAdapter()
    if key == PROVIDER_SELECTION[2][0]:
        return SalesforceAdapter()
    if key == PROVIDER_SELECTION[3][0]:
        return ZohoAdapter()
    raise CrmAdapterError(f"Unknown CRM provider: {provider}")


def ensure_live_or_raise(adapter: Any) -> None:
    """Fail closed when a stub adapter is selected for sync."""
    if getattr(adapter, "live", False):
        return
    provider = getattr(adapter, "provider", "unknown")
    raise CrmAdapterStubError(f"{provider} adapter is a stub — not implemented in v1")
