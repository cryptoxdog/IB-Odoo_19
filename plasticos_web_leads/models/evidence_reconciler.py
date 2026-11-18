"""Pure deterministic reconciliation of seller, AI, and attachment evidence."""

from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from typing import Any

from .evidence_keys import KEY_MASS_LABEL
from .material_catalog import CatalogEntry, accept_value, match_codes
from .quantity_normalizer import QuantityEvidence

EVIDENCE_SCHEMA_VERSION = "web-lead-evidence/v1"


def polymer_code(value: str | None, entries: Sequence[CatalogEntry] = ()) -> str:
    """Catalog polymer code for one model token. An unlisted token is empty."""
    return accept_value(value, entries) or ""


def polymers_named(text: str | None, entries: Sequence[CatalogEntry] = ()) -> set[str]:
    """Polymer codes the seller's own words name in the catalog."""
    return set(match_codes(text, entries))


def _polyethylene_family(codes: set[str]) -> set[str]:
    # "PE" sellers often write polyethylene for HDPE/LDPE/LLDPE; one family is not a conflict.
    return {"PE" if code in {"HDPE", "LDPE", "LLDPE"} else code for code in codes}


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
    polymer_entries: Sequence[CatalogEntry] = (),
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
    )
    seller_polymers = polymers_named(seller_material, polymer_entries)
    ai_polymer = polymer_code(ai.get("polymer"), polymer_entries)
    if ai_polymer and seller_polymers and ai_polymer not in seller_polymers:
        if not (_polyethylene_family({ai_polymer}) & _polyethylene_family(seller_polymers)):
            conflicts.append(
                {
                    "field": "polymer",
                    "seller_value": sorted(seller_polymers),
                    "ai_value": ai_polymer,
                    "status": "Conflicting",
                }
            )

    # Each photo is kept. Two confident photos naming different polymers, or a
    # confident photo naming a polymer other than the text, is a conflict.
    confident_hints = sorted(
        {
            polymer_code(item.get("observed_polymer_hint"), polymer_entries)
            for item in vision
            if item.get("observed_polymer_hint") and float(item.get("confidence") or 0.0) >= 0.7
        }
    )
    stated = seller_polymers | ({ai_polymer} if ai_polymer else set())
    if len(confident_hints) > 1 or (
        confident_hints and stated and not (_polyethylene_family(set(confident_hints)) & _polyethylene_family(stated))
    ):
        conflicts.append(
            {
                "field": "polymer_vision",
                "text_value": sorted(stated),
                "vision_value": confident_hints,
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
        classification_inputs={
            "weight_source": quantity.weight_source,
            KEY_MASS_LABEL: quantity.mass_label,
            "is_plastic_hint": ai.get("is_plastic"),
            "is_commercial_hint": ai.get("is_commercial_source"),
        },
    )
