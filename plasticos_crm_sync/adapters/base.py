"""CRM adapter protocol and canonical DTOs (provider-agnostic)."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any, Protocol

# Operator-excluded VanillaSoft columns (v1.4). Match is the collapsed label,
# so a double space in "NAICS Code  Description" cannot sneak through.
EXCLUDED_SOURCE_FIELDS = (
    "Load Ready",
    "ClosedFlag",
    "Team",
    "Call Back Date",
    "Call Back Time",
    "Scheduled Call User",
    "SIC Code",
    "SIC Code Description",
    "NAICS Code",
    "NAICS Code  Description",
    "Sales Volume Range",
    "Sales Volume",
    "Employees",
    "Square Footage",
    "Fleet Size",
    "Product (MFR)",
    "Truck Size (E)",
    "Equipment",
    "Price Quoted (MRP)",
    "FOB/FAS (MRP)",
    "Price Quoted (PPS)",
    "FOB/FAS (PPS)",
    "Melt (LDPE)",
    "Density (LDPE)",
    "Price Quoted (LDPE)",
    "FOB/FAS (LDPE)",
    "Melt (HDPE)",
    "Density (HDPE)",
    "Load Ready (HDPE)",
    "Price Quoted (HDPE)",
    "FOB/FAS (HDPE)",
    "Melt (PP)",
    "Density (PP)",
    "Price Quoted (PP)",
    "FOB/FAS (PP)",
)


def source_field_key(name: str) -> str:
    return " ".join(str(name or "").split()).casefold()


_EXCLUDED_SOURCE_KEYS = frozenset(source_field_key(name) for name in EXCLUDED_SOURCE_FIELDS)


def is_excluded_source_field(name: str) -> bool:
    return source_field_key(name) in _EXCLUDED_SOURCE_KEYS


def omit_excluded_source_fields(fields: dict | None) -> dict:
    """Drop excluded source columns. Free-text values of other fields stay."""
    return {key: value for key, value in (fields or {}).items() if not is_excluded_source_field(str(key))}


class CrmAdapterError(Exception):
    """Adapter/client failure (HTTP, auth, parse)."""


@dataclass(frozen=True)
class CanonicalPhone:
    """One enabled source number with its provider label.

    ``kind`` is the ``plasticos.partner.phone`` label the number takes on a
    person: ``mobile``, ``fax`` or ``other``. ``label`` is the provider name
    as given (``Mobile 2``, ``Business``), kept for labelled evidence.
    """

    label: str
    number: str
    kind: str


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
    phone_numbers: tuple[str, ...] = ()
    mobile_numbers: tuple[str, ...] = ()
    contact_note: str = ""
    phone_entries: tuple[CanonicalPhone, ...] = ()
    website: str = ""
    job_title: str = ""


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
