"""Cognito Forms adapter for the provider-neutral web-lead packet."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from .base import PACKET_SCHEMA_VERSION, WebLeadAttachment, WebLeadPacket

_COGNITO_ATTACHMENT_FIELDS = (
    "UploadPhotosOfYourScrapUpTo10",
    "UploadPhotos",
    "Photos",
    "Attachments",
    "Files",
)


class CognitoAdapter:
    """Project the live Cognito webhook shape into a decision-free packet."""

    provider_key = "cognito"

    @staticmethod
    def _text(value: Any) -> str:
        return value.strip() if isinstance(value, str) else ""

    @classmethod
    def _first_text(cls, payload: Mapping[str, Any], *keys: str) -> str:
        for key in keys:
            value = cls._text(payload.get(key))
            if value:
                return value
        return ""

    @classmethod
    def _contact_name(cls, payload: Mapping[str, Any]) -> str:
        raw_name = payload.get("Name")
        if isinstance(raw_name, Mapping):
            first_and_last = cls._text(raw_name.get("FirstAndLast"))
            if first_and_last:
                return first_and_last
            first = cls._text(raw_name.get("First"))
            last = cls._text(raw_name.get("Last"))
            return " ".join(part for part in (first, last) if part)
        if isinstance(raw_name, str):
            return raw_name.strip()
        return cls._first_text(payload, "YourName")

    @classmethod
    def _entry(cls, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        entry = payload.get("Entry")
        return entry if isinstance(entry, Mapping) else {}

    @classmethod
    def _external_id(cls, payload: Mapping[str, Any]) -> str:
        entry = cls._entry(payload)
        return cls._text(entry.get("Number")) or cls._first_text(payload, "Id", "EntryId", "entry_id")

    @classmethod
    def _attachment_items(cls, payload: Mapping[str, Any]) -> tuple[str, list[Any]]:
        for field_name in _COGNITO_ATTACHMENT_FIELDS:
            if field_name in payload:
                items = payload.get(field_name)
                if items is None:
                    return field_name, []
                if not isinstance(items, list):
                    raise ValueError(f"Cognito attachment field {field_name} must be a list.")
                return field_name, items
        return "", []

    @classmethod
    def _attachments(cls, payload: Mapping[str, Any]) -> tuple[WebLeadAttachment, ...]:
        _field_name, items = cls._attachment_items(payload)
        if len(items) > 10:
            raise ValueError("Cognito submission contains more than 10 attachments.")

        seen_source_ids: set[str] = set()
        attachments: list[WebLeadAttachment] = []
        for index, item in enumerate(items):
            if not isinstance(item, Mapping):
                raise ValueError(f"Cognito attachment {index + 1} must be an object.")

            source_id = cls._text(item.get("Id")) or cls._text(item.get("id"))
            filename = cls._text(item.get("Name")) or cls._text(item.get("name"))
            source_url = cls._text(item.get("File")) or cls._text(item.get("url")) or cls._text(item.get("Url"))
            content_type = cls._text(item.get("ContentType")) or cls._text(item.get("content_type"))
            size_value = item.get("Size", item.get("size"))

            if not source_id:
                raise ValueError(f"Cognito attachment {index + 1} is missing Id.")
            if source_id in seen_source_ids:
                raise ValueError(f"Duplicate Cognito attachment source ID: {source_id}.")
            if not filename:
                raise ValueError(f"Cognito attachment {index + 1} is missing Name.")
            if not source_url.startswith("https://"):
                raise ValueError(f"Cognito attachment {index + 1} has an invalid HTTPS File URL.")

            size_bytes: int | None = None
            if size_value is not None and str(size_value).strip() != "":
                try:
                    size_bytes = int(size_value)
                except (TypeError, ValueError) as exc:
                    raise ValueError(f"Cognito attachment {index + 1} has an invalid Size.") from exc
                if size_bytes <= 0:
                    raise ValueError(f"Cognito attachment {index + 1} Size must be positive.")

            seen_source_ids.add(source_id)
            attachments.append(
                WebLeadAttachment(
                    source_id=source_id,
                    attachment_index=index,
                    filename=filename,
                    content_type=content_type or "application/octet-stream",
                    size_bytes=size_bytes,
                    source_url=source_url,
                )
            )
        return tuple(attachments)

    def to_packet(self, payload: Mapping[str, Any]) -> WebLeadPacket:
        """Map a current Cognito payload without inferring commercial facts."""
        if not isinstance(payload, Mapping):
            raise ValueError("Cognito payload must be a JSON object.")

        entry = self._entry(payload)
        external_id = self._external_id(payload)
        return WebLeadPacket(
            schema_version=PACKET_SCHEMA_VERSION,
            provider=self.provider_key,
            provider_external_id=external_id,
            idempotency_key=f"CG-{external_id}" if external_id else "",
            submitted_at=self._text(entry.get("DateSubmitted")) or None,
            company_name=self._first_text(payload, "YourBusinessCompanyName", "CompanyName"),
            contact_name=self._contact_name(payload),
            contact_email=self._first_text(payload, "Email", "EmailAddress"),
            contact_phone=self._first_text(payload, "Phone", "PhoneNumber"),
            pickup_location_text=self._first_text(payload, "LocationOfPickUpCityState", "WhereIsItLocated"),
            pickup_postal_code=self._first_text(payload, "LocationOfPickUpZip"),
            material_description=self._first_text(payload, "WhatIsIt", "DescribeYourMaterial", "WhatTypeOfPlastic"),
            material_composition_text=self._first_text(payload, "WhatMaterialIsItMadeFrom", "WhatTypeOfPlastic"),
            source_description=self._first_text(payload, "WhatIsTheSourceOfThisMaterial", "Source"),
            contaminants_text=self._first_text(payload, "AreThereAnyContaminants"),
            quantity_text=self._first_text(payload, "WhatIsTheQuantity"),
            weight_per_load_text=self._first_text(payload, "WeightPerLoad"),
            frequency_text=self._first_text(payload, "HowOften"),
            attachments=self._attachments(payload),
            raw_payload=deepcopy(dict(payload)),
        )
