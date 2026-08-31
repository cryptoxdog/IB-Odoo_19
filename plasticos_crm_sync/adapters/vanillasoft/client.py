"""VanillaSoft Public API HTTP client (stdlib urllib)."""

from __future__ import annotations

import json
import logging
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from ..base import CrmAdapterError

_logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 60
MAX_RETRIES = 3
RETRY_STATUSES = {429, 500, 502, 503, 504}

# I16 — every request carries the API key in an Authorization header, so a
# cleartext endpoint leaks the credential on the wire. Loopback is the only
# accommodation: it is how the stall/timeout tests point at a local stub, and it
# never leaves the host.
_LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})


def require_secure_endpoint(url: str) -> None:
    """Reject a credential-bearing endpoint that is not HTTPS (loopback aside)."""
    parts = urllib.parse.urlsplit(url)
    scheme = (parts.scheme or "").lower()
    if scheme == "https":
        return
    host = (parts.hostname or "").lower()
    if scheme == "http" and host in _LOOPBACK_HOSTS:
        return
    raise CrmAdapterError(
        f"VanillaSoft endpoint must use https (got {scheme or '<none>'}://{host or '<no host>'}); "
        "plaintext http is accepted only for loopback test endpoints"
    )


def normalize_api_base(root_endpoint: str) -> str:
    """Normalize root URL to …/WSPubAPI without trailing slash (HTTPS enforced)."""
    raw = (root_endpoint or "").strip()
    if not raw:
        raise CrmAdapterError("VanillaSoft root endpoint is empty")
    if "://" not in raw:
        raw = "https://" + raw
    raw = raw.rstrip("/")
    require_secure_endpoint(raw)
    if raw.endswith("/WSPubAPI"):
        return raw
    return raw + "/WSPubAPI"


class VanillaSoftClient:
    """Thin HTTP client for VanillaSoft WSPubAPI."""

    def __init__(
        self,
        api_key: str,
        root_endpoint: str,
        *,
        timeout: int = DEFAULT_TIMEOUT,
        opener: Any | None = None,
    ):
        if not api_key or not api_key.strip():
            raise CrmAdapterError("VanillaSoft API key is empty")
        self.api_key = api_key.strip()
        self.base_url = normalize_api_base(root_endpoint)
        self.timeout = timeout
        self._opener = opener
        self._ssl_ctx = ssl.create_default_context()

    def _headers(self) -> dict[str, str]:
        # Build incrementally — avoids phantom-enum dict-dispatch false positives
        headers: dict[str, str] = {"Accept": "application/json"}
        headers["Authorization"] = f"APIKey={self.api_key}"
        headers["Content-Type"] = "application/json"
        return headers

    def _request(self, method: str, path: str, params: dict[str, Any] | None = None) -> Any:
        query = ""
        if params:
            cleaned = {k: v for k, v in params.items() if v is not None and v != ""}
            query = "?" + urllib.parse.urlencode(cleaned)
        url = f"{self.base_url}{path if path.startswith('/') else '/' + path}{query}"
        require_secure_endpoint(url)
        last_err: Exception | None = None
        for attempt in range(MAX_RETRIES):
            req = urllib.request.Request(url, method=method, headers=self._headers())  # noqa: S310
            try:
                if self._opener is not None:
                    resp_cm = self._opener.open(req, timeout=self.timeout)
                else:
                    resp_cm = urllib.request.urlopen(  # noqa: S310
                        req, timeout=self.timeout, context=self._ssl_ctx
                    )
                with resp_cm as resp:
                    body = resp.read()
                    if not body:
                        return {}
                    return json.loads(body.decode("utf-8"))
            except urllib.error.HTTPError as exc:
                status = exc.code
                if status in (401, 403):
                    raise CrmAdapterError(f"VanillaSoft auth failed HTTP {status}") from exc
                if status in RETRY_STATUSES and attempt < MAX_RETRIES - 1:
                    time.sleep(0.5 * (2**attempt))
                    last_err = exc
                    continue
                detail = ""
                try:
                    detail = exc.read().decode("utf-8", errors="replace")[:200]
                except Exception:  # noqa: BLE001, S110
                    detail = ""
                raise CrmAdapterError(f"VanillaSoft HTTP {status}: {detail}") from exc
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                if attempt < MAX_RETRIES - 1:
                    time.sleep(0.5 * (2**attempt))
                    last_err = exc
                    continue
                raise CrmAdapterError(f"VanillaSoft network error: {exc}") from exc
        raise CrmAdapterError(f"VanillaSoft request failed after retries: {last_err}")

    def verify_key(self) -> dict[str, Any]:
        return self._request("GET", "/VerifyKey")

    def get_contacts(
        self,
        project_id: int,
        modified_after: str,
        limit: int = 200,
        *,
        custom_fields: bool = True,
        phone_numbers: bool = True,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "project_id": project_id,
            "modified_after": modified_after,
            "limit": min(max(limit, 1), 1000),
        }
        if custom_fields:
            params["custom_fields"] = 1
        if phone_numbers:
            params["phone_numbers"] = 1
        return self._request("GET", "/Contacts", params)

    def get_contact(
        self,
        contact_id: int | str,
        *,
        custom_fields: bool = True,
        phone_numbers: bool = True,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {}
        if custom_fields:
            params["custom_fields"] = 1
        if phone_numbers:
            params["phone_numbers"] = 1
        return self._request("GET", f"/Contacts/{contact_id}", params or None)

    def search_contacts(self, project_id: int, **search_fields: str) -> dict[str, Any]:
        return self._request(
            "GET",
            f"/Projects/{project_id}/Contacts/Search",
            search_fields,
        )

    def get_call_history_batch(
        self,
        start: str,
        end: str,
        *,
        project_id: int | None = None,
        limit: int = 500,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"limit": min(max(limit, 1), 20000)}
        params["start"] = start
        params["end"] = end
        if project_id is not None:
            params["project_id"] = project_id
        return self._request("GET", "/GetCallHistory", params)

    def get_call_history_by_contact(self, contact_id: int | str) -> dict[str, Any]:
        return self._request("GET", f"/contacts/{contact_id}/callHistory")

    def get_custom_tables_list(self, project_id: int) -> dict[str, Any]:
        return self._request("GET", f"/projects/{project_id}/customTables/list")

    def get_custom_table_data(
        self,
        contact_id: int | str,
        table_id: int | str | None = None,
        table_name: str | None = None,
    ) -> dict[str, Any]:
        path = f"/Contacts/{contact_id}/customTables"
        params: dict[str, Any] | None = None
        if table_id is not None:
            path = f"{path}/{table_id}"
        elif table_name:
            params = {"name": table_name}
        return self._request("GET", path, params)
