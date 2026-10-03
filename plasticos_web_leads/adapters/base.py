"""Odoo-owned port for inbound web-lead admission.

Changing any signature in this module is a port change: bump
``PACKET_SCHEMA_VERSION`` when the packet contract changes, and update every
adapter registered in ``registry.py`` in the same change.
``tests/test_web_lead_adapter_contract.py`` enforces that contract.
"""

from __future__ import annotations

import hmac
from abc import ABC, abstractmethod
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import asdict, dataclass
from typing import Any, ClassVar

PACKET_SCHEMA_VERSION = "web-lead-packet/v1"

EVENT_SUBMITTED = "submitted"
EVENT_UPDATED = "updated"
EVENT_DELETED = "deleted"
EVENT_UNKNOWN = "unknown"
EVENT_KINDS = frozenset({EVENT_SUBMITTED, EVENT_UPDATED, EVENT_DELETED, EVENT_UNKNOWN})

# ``source_url`` is acquisition material: a signed, expiring provider link. It is
# consumed once by the transient acquisition path and never serialized into the
# durable canonical packet, an LLM prompt, or a broker-approved snapshot.
ACQUISITION_ONLY_ATTACHMENT_FIELDS = frozenset({"source_url"})


@dataclass(frozen=True)
class WebLeadAttachment:
    """Provider-declared attachment metadata before durable Odoo acquisition."""

    source_id: str
    attachment_index: int
    filename: str
    content_type: str
    size_bytes: int | None
    source_url: str


@dataclass(frozen=True)
class WebLeadPacket:
    """Provider-neutral, decision-free projection of one inbound seller submission."""

    schema_version: str
    provider: str
    provider_external_id: str
    idempotency_key: str
    submitted_at: str | None
    company_name: str
    contact_name: str
    contact_email: str
    contact_phone: str
    pickup_location_text: str
    pickup_postal_code: str
    material_description: str
    material_composition_text: str
    source_description: str
    contaminants_text: str
    quantity_text: str
    weight_per_load_text: str
    frequency_text: str
    attachments: tuple[WebLeadAttachment, ...]
    raw_payload: Mapping[str, Any]


@dataclass(frozen=True)
class InboundRequest:
    """Transport facts the port may use to authenticate one inbound HTTP call."""

    headers: Mapping[str, str]
    query: Mapping[str, str]
    raw_body: bytes
    path_token: str | None = None


@dataclass(frozen=True)
class InboundEvent:
    """Provider-neutral classification of one inbound delivery."""

    provider: str
    kind: str
    provider_external_id: str
    payload: Mapping[str, Any]


def _mapping_text(mapping: Mapping[str, str], name: str) -> str:
    """Read one mapping value, including case-insensitive header maps."""
    getter = getattr(mapping, "get", None)
    if callable(getter):
        for candidate in (name, name.lower(), name.title()):
            value = getter(candidate)
            if value:
                return str(value).strip()
    target = name.lower()
    for key, value in mapping.items():
        if str(key).lower() == target and value:
            return str(value).strip()
    return ""


def _strip_token(value: str) -> str:
    return value.strip().strip('"').strip("'")


class WebLeadAdapter(ABC):
    """Odoo-owned inbound port. Tool adapters subclass this; Odoo never imports them.

    ``provider_key`` and ``attachment_allowed_hosts`` must be non-empty on every
    concrete subclass. An incomplete subclass fails when the class is created,
    and the registry instantiates every adapter at import.
    """

    provider_key: ClassVar[str]
    # Destination policy for attachment acquisition: a host is accepted when it
    # equals an entry or is a subdomain of one. Empty means no host is trusted.
    attachment_allowed_hosts: ClassVar[tuple[str, ...]]

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if getattr(cls, "__abstractmethods__", None):
            return
        key = getattr(cls, "provider_key", "")
        hosts = getattr(cls, "attachment_allowed_hosts", ())
        hosts_ok = bool(hosts) and all(
            isinstance(host, str) and host and host == host.lower() and "://" not in host for host in hosts
        )
        if not isinstance(key, str) or not key.strip():
            raise TypeError(f"{cls.__name__} must declare a non-empty provider_key.")
        if not hosts_ok:
            raise TypeError(f"{cls.__name__} must declare lowercase attachment_allowed_hosts without a scheme.")

    @abstractmethod
    def to_packet(self, payload: Mapping[str, Any]) -> WebLeadPacket:
        """Project a provider payload into the immutable inbound packet."""

    @abstractmethod
    def classify_event(self, payload: Mapping[str, Any]) -> InboundEvent:
        """Classify one provider payload without admitting it."""

    @classmethod
    @abstractmethod
    def sample_payload(cls) -> dict[str, Any]:
        """Return one canonical submitted payload for the conformance test."""

    def presented_tokens(self, request: InboundRequest) -> tuple[str, ...]:
        """Tokens the caller presented, in header, query, then path order."""
        tokens: list[str] = []
        authorization = _mapping_text(request.headers, "Authorization")
        if authorization.lower().startswith("bearer "):
            bearer = _strip_token(authorization[7:])
            if bearer:
                tokens.append(bearer)
        for header_name in ("X-API-Key", "X-Api-Key"):
            header_token = _strip_token(_mapping_text(request.headers, header_name))
            if header_token and header_token not in tokens:
                tokens.append(header_token)
        query_token = _strip_token(_mapping_text(request.query, "access_token"))
        if query_token and query_token not in tokens:
            tokens.append(query_token)
        path_token = _strip_token(request.path_token or "")
        if path_token and path_token not in tokens:
            tokens.append(path_token)
        return tuple(tokens)

    def authenticate(self, request: InboundRequest, *, secret: str) -> bool:
        """Timing-safe match of any presented token against one stored secret.

        Providers that sign the body override this. An empty secret never matches.
        """
        stored = (secret or "").strip()
        if not stored:
            return False
        return any(hmac.compare_digest(token, stored) for token in self.presented_tokens(request))


def attachment_to_dict(attachment: WebLeadAttachment, *, include_acquisition_url: bool = False) -> dict[str, Any]:
    """Serialize attachment evidence using JSON-safe primitive values.

    The signed acquisition URL is excluded unless the caller is the transient
    acquisition path itself.
    """
    data = asdict(attachment)
    if not include_acquisition_url:
        for key in ACQUISITION_ONLY_ATTACHMENT_FIELDS:
            data.pop(key, None)
    return data


def acquisition_rows(packet: WebLeadPacket) -> list[dict[str, Any]]:
    """Attachment rows including signed URLs, for the in-request acquisition path only."""
    return [attachment_to_dict(item, include_acquisition_url=True) for item in packet.attachments]


def packet_to_dict(packet: WebLeadPacket, *, omit_raw_payload: bool = False) -> dict[str, Any]:
    """Serialize a packet without introducing a second provider-specific schema.

    Attachment rows never carry ``source_url`` here: the serialized packet is the
    durable canonical payload, the LLM input, and the snapshot source.
    """
    data = asdict(packet)
    data["attachments"] = [attachment_to_dict(item) for item in packet.attachments]
    data["raw_payload"] = deepcopy(dict(packet.raw_payload))
    if omit_raw_payload:
        data.pop("raw_payload", None)
    return data
