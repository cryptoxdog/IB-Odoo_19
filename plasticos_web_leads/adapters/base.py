"""Pure provider-neutral contracts for inbound web-lead admission."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import asdict, dataclass
from typing import Any, Protocol

PACKET_SCHEMA_VERSION = "web-lead-packet/v1"


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


class WebLeadProviderAdapter(Protocol):
    """Pure projection protocol implemented by a concrete inbound provider adapter."""

    provider_key: str

    def to_packet(self, payload: Mapping[str, Any]) -> WebLeadPacket:
        """Project a provider payload into the immutable inbound packet."""


def attachment_to_dict(attachment: WebLeadAttachment) -> dict[str, Any]:
    """Serialize attachment evidence using JSON-safe primitive values."""
    return asdict(attachment)


def packet_to_dict(packet: WebLeadPacket, *, omit_raw_payload: bool = False) -> dict[str, Any]:
    """Serialize a packet without introducing a second provider-specific schema."""
    data = asdict(packet)
    data["attachments"] = [attachment_to_dict(item) for item in packet.attachments]
    data["raw_payload"] = deepcopy(dict(packet.raw_payload))
    if omit_raw_payload:
        data.pop("raw_payload", None)
    return data
