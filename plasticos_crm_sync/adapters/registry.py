"""Provider → adapter factory registry.

Only VanillaSoft is implemented (odoo-intent-1 ingestion milestone). The
adapter protocol in ``base.py`` is the extension contract for future CRM
sources; onboarding a new provider means adding an adapter and a selection
entry here — nothing else. See ``docs/runbooks/CRM_ADAPTER_ROADMAP.md``.
"""

from __future__ import annotations

from typing import Any

from .base import CrmAdapterError
from .vanillasoft.adapter import VanillaSoftAdapter
from .vanillasoft.client import VanillaSoftClient

PROVIDER_SELECTION = [
    ("vanillasoft", "VanillaSoft"),
]

LIVE_PROVIDERS = frozenset({"vanillasoft"})


def get_adapter(provider: str, *, api_key: str = "", root_endpoint: str = "", project_id: int = 0) -> Any:
    """Return the adapter instance for ``provider``.

    Unknown providers fail closed here — the registry is the single admission
    point and there are no stub adapters.
    """
    key = (provider or "").strip().lower()
    if key == "vanillasoft":
        if not api_key or not root_endpoint or not project_id:
            raise CrmAdapterError("VanillaSoft requires api_key, root_endpoint, and project_id")
        client = VanillaSoftClient(api_key, root_endpoint)
        return VanillaSoftAdapter(client, int(project_id))
    raise CrmAdapterError(f"Unknown CRM provider: {provider}")
