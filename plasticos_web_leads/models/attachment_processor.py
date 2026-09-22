"""Durable attachment acquisition for canonical web-lead packets."""

from __future__ import annotations

import base64
import hashlib
import logging
from collections.abc import Callable, Iterable, Mapping
from typing import Any

import requests

_logger = logging.getLogger(__name__)

MAX_ATTACHMENTS = 10
MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_AGGREGATE_BYTES = 50 * 1024 * 1024
CONNECT_TIMEOUT_SECONDS = 10
READ_TIMEOUT_SECONDS = 30
MAX_ACQUISITION_ATTEMPTS = 3
ATTACHMENT_SIZE_LIMIT_ERROR = "attachment_size_limit_exceeded"
SOURCE_ID_MARKER = "[web-lead-source-id:"
COMMERCIAL_IMAGE_CHECKSUM_MARKER = "[commercial-image-checksum:"
COMMERCIAL_IMAGE_ORIGIN_MARKER = "[commercial-image-origin:"


def _error(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


def _base_result(attachment: Mapping[str, Any]) -> dict[str, Any]:
    content_type = str(attachment.get("content_type") or "application/octet-stream")
    return {
        "source_id": str(attachment.get("source_id") or ""),
        "attachment_index": int(attachment.get("attachment_index") or 0),
        "filename": str(attachment.get("filename") or "attachment"),
        "content_type": content_type,
        "declared_size_bytes": attachment.get("size_bytes"),
        "actual_size_bytes": None,
        "content_sha256": None,
        "ir_attachment_id": None,
        "acquisition_status": "failed",
        "analysis_type": "image" if content_type.startswith("image/") else "document",
        "analysis_status": "not_run" if content_type.startswith("image/") else "unsupported",
        "analysis": None,
        "error": None,
    }


def _read_response_bytes(response: Any, *, remaining_bytes: int) -> bytes:
    """Read a streamed response while rejecting an over-limit body."""
    chunks: list[bytes] = []
    total = 0
    iterator = getattr(response, "iter_content", None)
    if callable(iterator):
        for chunk in iterator(chunk_size=64 * 1024):
            if not chunk:
                continue
            total += len(chunk)
            if total > remaining_bytes:
                raise ValueError(ATTACHMENT_SIZE_LIMIT_ERROR)
            chunks.append(chunk)
        return b"".join(chunks)

    content = response.content
    if len(content) > remaining_bytes:
        raise ValueError(ATTACHMENT_SIZE_LIMIT_ERROR)
    return content


def _previous_successes(evidence_bundle: Mapping[str, Any] | None) -> dict[str, dict[str, Any]]:
    if not isinstance(evidence_bundle, Mapping):
        return {}
    rows = evidence_bundle.get("attachments")
    if not isinstance(rows, list):
        return {}
    return {
        str(row.get("source_id")): dict(row)
        for row in rows
        if isinstance(row, Mapping)
        and row.get("acquisition_status") == "success"
        and row.get("source_id")
        and row.get("ir_attachment_id")
    }


def process_attachments(
    *,
    lead: Any,
    attachments: Iterable[Mapping[str, Any]],
    analyzer: Callable[[bytes, str], dict[str, Any]] | None = None,
    evidence_bundle: Mapping[str, Any] | None = None,
    http_get: Callable[..., Any] | None = None,
) -> list[dict[str, Any]]:
    """Acquire/store every admitted attachment and preserve local failures.

    ``lead`` is deliberately duck-typed so this module remains easy to unit-test
    and avoids owning an Odoo model. Successful retry rows are reused from the
    prior evidence bundle instead of downloading a signed provider URL again.
    """
    http_get = http_get or requests.get
    rows = list(attachments)
    if len(rows) > MAX_ATTACHMENTS:
        raise ValueError(f"At most {MAX_ATTACHMENTS} packet attachments are supported.")

    existing = _previous_successes(evidence_bundle)
    results: list[dict[str, Any]] = []
    aggregate_size = 0
    Attachment = lead.env["ir.attachment"]

    for attachment in sorted(rows, key=lambda item: int(item.get("attachment_index") or 0)):
        result = _base_result(attachment)
        source_id = result["source_id"]
        declared_size = result["declared_size_bytes"]
        if source_id in existing:
            results.append(existing[source_id])
            aggregate_size += int(existing[source_id].get("actual_size_bytes") or 0)
            continue
        if not source_id:
            result["error"] = _error("missing_source_id", "Provider attachment identity is missing.")
            results.append(result)
            continue
        if not str(attachment.get("source_url") or "").startswith("https://"):
            result["error"] = _error("invalid_source_url", "Attachment URL must use HTTPS.")
            results.append(result)
            continue
        if declared_size is not None and int(declared_size) > MAX_FILE_BYTES:
            result["error"] = _error("declared_size_limit_exceeded", "Declared attachment size exceeds the V1 limit.")
            results.append(result)
            continue

        content: bytes | None = None
        last_error: Exception | None = None
        remaining = min(MAX_FILE_BYTES, MAX_AGGREGATE_BYTES - aggregate_size)
        if remaining <= 0:
            result["error"] = _error("aggregate_size_limit_exceeded", "Lead attachment aggregate exceeds the V1 limit.")
            results.append(result)
            continue

        for _attempt in range(1, MAX_ACQUISITION_ATTEMPTS + 1):
            try:
                response = http_get(
                    str(attachment["source_url"]),
                    timeout=(CONNECT_TIMEOUT_SECONDS, READ_TIMEOUT_SECONDS),
                    stream=True,
                )
                response.raise_for_status()
                content = _read_response_bytes(response, remaining_bytes=remaining)
                if not content:
                    raise ValueError("empty_attachment")
                break
            except Exception as exc:  # Network/client exceptions are attachment-local.
                last_error = exc
                content = None

        if content is None:
            code = "acquisition_failed"
            if isinstance(last_error, ValueError) and str(last_error) == ATTACHMENT_SIZE_LIMIT_ERROR:
                code = ATTACHMENT_SIZE_LIMIT_ERROR
            result["error"] = _error(code, "Attachment could not be acquired within V1 limits.")
            results.append(result)
            continue

        actual_size = len(content)
        result["actual_size_bytes"] = actual_size
        aggregate_size += actual_size
        if declared_size is not None and actual_size != int(declared_size):
            result["error"] = _error("size_mismatch", "Downloaded attachment size did not match provider metadata.")
            results.append(result)
            continue

        result["content_sha256"] = hashlib.sha256(content).hexdigest()
        # The adapter validated and retained the provider-declared MIME as packet
        # evidence. A response header is not permitted to rewrite that durable
        # contract or redirect document bytes into the image-analysis path.
        mimetype = result["content_type"]
        stored = Attachment.create(
            {
                "name": result["filename"],
                "type": "binary",
                "datas": base64.b64encode(content).decode("ascii"),
                "res_model": "plasticos.web.lead",
                "res_id": lead.id,
                "mimetype": mimetype,
            }
        )
        result["ir_attachment_id"] = stored.id
        result["acquisition_status"] = "success"
        result["content_type"] = mimetype

        if mimetype.startswith("image/"):
            if analyzer is None:
                result["analysis_status"] = "not_run"
            else:
                try:
                    result["analysis"] = analyzer(content, mimetype)
                    result["analysis_status"] = "success"
                except Exception:
                    _logger.warning("Image analysis failed for web lead %s attachment %s.", lead.id, source_id)
                    result["analysis_status"] = "failed"
                    result["error"] = _error(
                        "image_analysis_failed", "Image analysis failed; stored evidence was preserved."
                    )
        else:
            result["analysis_type"] = "document" if mimetype == "application/pdf" else "unsupported"
            result["analysis_status"] = "unsupported"
            result["error"] = _error(
                "document_text_extraction_not_enabled",
                "Document text extraction is not enabled in V1.",
            )

        results.append(result)

    return results


def copy_successful_attachments_to_intake(*, lead: Any, intake: Any, evidence_bundle: Mapping[str, Any] | None) -> None:
    """Copy every source-distinct success to a HOT intake without re-downloading.

    Provider source identity, not filename, is the idempotency key.  A source ID
    marker in the copied attachment description preserves that identity without a
    cross-module schema change to ``ir.attachment``. Distinct provider uploads
    with identical user-facing filenames therefore both reach broker review.
    """
    Attachment = lead.env["ir.attachment"]
    existing_descriptions = Attachment.search(
        [
            ("res_model", "=", "plasticos.intake"),
            ("res_id", "=", intake.id),
        ]
    ).mapped("description")
    for row in _previous_successes(evidence_bundle).values():
        source_id = str(row.get("source_id") or "")
        if not source_id:
            continue
        marker = f"{SOURCE_ID_MARKER}{source_id}]"
        if any(marker in (description or "") for description in existing_descriptions):
            continue
        attachment_id = row.get("ir_attachment_id")
        stored = Attachment.browse(attachment_id)
        if not stored.exists():
            continue
        Attachment.create(
            {
                "name": stored.name,
                "type": "binary",
                "datas": stored.datas,
                "res_model": "plasticos.intake",
                "res_id": intake.id,
                "mimetype": stored.mimetype,
                "description": marker,
            }
        )
        existing_descriptions.append(marker)


def _marker_from_description(description: Any, marker_prefix: str) -> str | None:
    """Return one complete provenance marker from an attachment description."""
    text = str(description or "")
    start = text.find(marker_prefix)
    if start < 0:
        return None
    end = text.find("]", start)
    return text[start : end + 1] if end >= 0 else None


def _provider_source_marker(attachment: Any) -> str | None:
    return _marker_from_description(getattr(attachment, "description", None), SOURCE_ID_MARKER)


def _attachment_checksum(attachment: Any) -> str | None:
    checksum = str(getattr(attachment, "checksum", "") or "").strip()
    return checksum or None


def _image_identity(attachment: Any) -> tuple[str, str]:
    """Choose provider source identity before a content checksum.

    Separate Cognito uploads can contain identical bytes but remain distinct
    submitted evidence. Legacy or manually attached images have no provider
    source marker, so their checksum avoids repeated copies through the
    web-lead → intake → offer → CRM → profile graph.
    """
    source_marker = _provider_source_marker(attachment)
    if source_marker:
        return ("provider_source", source_marker)
    checksum = _attachment_checksum(attachment)
    if checksum:
        return ("checksum", checksum)
    return (
        "origin",
        f"{getattr(attachment, 'res_model', '')}:{getattr(attachment, 'res_id', '')}:{getattr(attachment, 'id', '')}",
    )


def _commercial_copy_description(attachment: Any) -> str:
    """Preserve source provenance or add a safe non-URL copy marker."""
    description = str(getattr(attachment, "description", "") or "").strip()
    if _provider_source_marker(attachment):
        return description

    checksum = _attachment_checksum(attachment)
    marker = (
        f"{COMMERCIAL_IMAGE_CHECKSUM_MARKER}{checksum}]"
        if checksum
        else (
            f"{COMMERCIAL_IMAGE_ORIGIN_MARKER}{getattr(attachment, 'res_model', '')}:"
            f"{getattr(attachment, 'res_id', '')}:{getattr(attachment, 'id', '')}]"
        )
    )
    return description if marker in description else " ".join(part for part in (description, marker) if part)


def _replace_with_provider_source_marker(attachment: Any, provider_marker: str) -> None:
    """Upgrade an earlier checksum-only copy to durable provider provenance."""
    description = str(getattr(attachment, "description", "") or "").strip()
    if provider_marker not in description:
        attachment.write({"description": " ".join(part for part in (description, provider_marker) if part)})


def copy_images_to_commercial_record(
    *,
    env: Any,
    target_model: str,
    target_id: int,
    sources: Iterable[tuple[str, int]],
) -> int:
    """Copy all available source images to a CRM or material-profile record.

    This intentionally consumes the source records that exist *when called*:
    web lead, originating intake, previously-created offers, and CRM entry.
    Copying is idempotent. Provider source IDs dominate checksums, preserving
    distinct form uploads with identical bytes while collapsing legacy or
    manually copied duplicates along the commercial record graph.
    """
    Attachment = env["ir.attachment"]
    target_images = Attachment.search(
        [
            ("res_model", "=", target_model),
            ("res_id", "=", target_id),
            ("mimetype", "like", "image/"),
        ]
    )
    existing_by_identity = {_image_identity(image): image for image in target_images}
    existing_generic_by_checksum = {
        _attachment_checksum(image): image
        for image in target_images
        if not _provider_source_marker(image) and _attachment_checksum(image)
    }

    candidates: list[Any] = []
    seen_source_records: set[tuple[str, int]] = set()
    for source_model, source_id in sources:
        source_key = (str(source_model), int(source_id or 0))
        if not source_key[1] or source_key in seen_source_records or source_key == (target_model, target_id):
            continue
        seen_source_records.add(source_key)
        candidates.extend(
            Attachment.search(
                [
                    ("res_model", "=", source_key[0]),
                    ("res_id", "=", source_key[1]),
                    ("mimetype", "like", "image/"),
                ]
            )
        )

    provider_marker_checksums = {
        checksum
        for image in candidates
        if _provider_source_marker(image)
        for checksum in [_attachment_checksum(image)]
        if checksum
    }
    copied = 0
    for image in candidates:
        identity = _image_identity(image)
        provider_marker = _provider_source_marker(image)
        checksum = _attachment_checksum(image)

        # A canonical packet's web-lead attachment is copied before its intake
        # copy has a provider marker. Prefer the intake's marked version when
        # both refer to the same bytes.
        if not provider_marker and checksum and checksum in provider_marker_checksums:
            continue
        if identity in existing_by_identity:
            continue

        # Replace an earlier checksum-only CRM/profile copy with the provider's
        # source identity rather than storing the same image twice.
        if provider_marker and checksum and checksum in existing_generic_by_checksum:
            existing = existing_generic_by_checksum.pop(checksum)
            _replace_with_provider_source_marker(existing, provider_marker)
            existing_by_identity.pop(("checksum", checksum), None)
            existing_by_identity[identity] = existing
            continue

        copied_image = image.copy(
            {
                "res_model": target_model,
                "res_id": target_id,
                "description": _commercial_copy_description(image),
            }
        )
        existing_by_identity[identity] = copied_image
        if not provider_marker and checksum:
            existing_generic_by_checksum[checksum] = copied_image
        copied += 1

    return copied
