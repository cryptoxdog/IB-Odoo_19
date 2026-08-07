"""CRM adapter protocol and canonical DTOs (provider-agnostic)."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any, Protocol


class CrmAdapterStubError(Exception):
    """Raised by stub adapters that are not implemented in v1."""


class CrmAdapterError(Exception):
    """Adapter/client failure (HTTP, auth, parse)."""


@dataclass(frozen=True)
class CanonicalLead:
    provider: str
    external_id: str
    company: str = ""
    first_name: str = ""
    last_name: str = ""
    email: str = ""
    phone: str = ""
    mobile: str = ""
    street: str = ""
    street2: str = ""
    city: str = ""
    state_code: str = ""
    zip: str = ""
    country_code: str = ""
    lead_status_raw: str = ""
    lead_source_raw: str = ""
    owner_name: str = ""
    modified_utc: str = ""
    deleted: bool = False
    custom_fields: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class CanonicalCall:
    provider: str
    external_id: str
    contact_external_id: str
    call_datetime_utc: str = ""
    duration_seconds: int = 0
    user_name: str = ""
    result_code: str = ""
    comment: str = ""


@dataclass(frozen=True)
class CanonicalTableRow:
    provider: str
    contact_external_id: str
    table_id: str
    table_name: str
    external_row_id: str
    fields: dict[str, str] = field(default_factory=dict)


class CrmAdapter(Protocol):
    provider: str
    live: bool

    def healthcheck(self) -> dict[str, Any]: ...

    def iter_contacts(
        self,
        *,
        modified_after: str,
        limit: int = 200,
    ) -> Iterator[tuple[list[CanonicalLead], str | None, bool]]: ...

    def get_contact(self, external_id: str) -> CanonicalLead | None: ...

    def iter_calls(
        self,
        *,
        start: str,
        end: str,
        limit: int = 500,
    ) -> Iterator[list[CanonicalCall]]: ...

    def iter_table_rows(self, contact_external_id: str) -> Iterator[CanonicalTableRow]: ...


class StubCrmAdapter:
    """Shared stub behavior for non-VanillaSoft providers."""

    provider: str = "stub"
    live: bool = False

    def _raise(self) -> None:
        raise CrmAdapterStubError(f"{self.provider} adapter is a stub — not implemented in v1")

    def healthcheck(self) -> dict[str, Any]:
        self._raise()
        return {}

    def iter_contacts(self, *, modified_after: str, limit: int = 200):
        self._raise()
        yield from ()

    def get_contact(self, external_id: str) -> CanonicalLead | None:
        self._raise()
        return None

    def iter_calls(self, *, start: str, end: str, limit: int = 500):
        self._raise()
        yield from ()

    def iter_table_rows(self, contact_external_id: str):
        self._raise()
        yield from ()
