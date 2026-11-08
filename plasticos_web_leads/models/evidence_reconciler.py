"""Pure deterministic reconciliation of seller, AI, and attachment evidence."""

from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from typing import Any

from .quantity_normalizer import QuantityEvidence

EVIDENCE_SCHEMA_VERSION = "web-lead-evidence/v1"


def _seller_says_no_contamination(value: str) -> bool:
    return value.strip().lower() in {"", "no", "none", "n/a", "na", "clean"}


def _vision_rows(attachments: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [
        dict(row.get("analysis") or {})
        for row in attachments
        if row.get("analysis_type") == "image" and row.get("analysis_status") == "success"
    ]


def reconcile_evidence(
    *,
    canonical_payload: Mapping[str, Any],
    quantity: QuantityEvidence,
    ai_normalized: Mapping[str, Any] | None,
    attachments: Sequence[Mapping[str, Any]],
    run_id: str | None = None,
) -> dict[str, Any]:
    """Preserve direct seller facts and record material conflicts explicitly."""
    seller = dict(canonical_payload)
    seller.pop("raw_payload", None)
    ai = dict(ai_normalized or {})
    attachment_rows = [dict(row) for row in attachments]
    vision = _vision_rows(attachment_rows)
    conflicts: list[dict[str, Any]] = []
    clarifications = list(quantity.clarification_requests)

    seller_contaminants = str(seller.get("contaminants_text") or "")
    if _seller_says_no_contamination(seller_contaminants) and any(
        item.get("contamination_visible") is True for item in vision
    ):
        conflicts.append(
            {
                "field": "contamination",
                "seller_value": seller_contaminants,
                "vision_value": "observed",
                "status": "Conflicting",
            }
        )

    seller_material = " ".join(
        str(seller.get(key) or "") for key in ("material_description", "material_composition_text")
    ).lower()
    ai_polymer = str(ai.get("polymer") or "").lower().strip()
    if ai_polymer and seller_material and ai_polymer not in seller_material:
        conflicts.append(
            {
                "field": "polymer",
                "seller_value": seller_material,
                "ai_value": ai_polymer,
                "status": "Conflicting",
            }
        )

    if attachment_rows and not vision:
        clarifications.append("Review submitted attachment evidence because no visual analysis succeeded.")

    return dict(
        schema_version=EVIDENCE_SCHEMA_VERSION,
        run_id=run_id or uuid.uuid4().hex,
        seller=seller,
        quantity=quantity.to_dict(),
        ai=ai,
        attachments=attachment_rows,
        vision=vision,
        conflicts=conflicts,
        clarification_requests=sorted(set(clarifications)),
        classification_inputs=dict(
            weight_source=quantity.weight_source,
            is_plastic_hint=ai.get("is_plastic"),
            is_commercial_hint=ai.get("is_commercial_source"),
        ),
    )
