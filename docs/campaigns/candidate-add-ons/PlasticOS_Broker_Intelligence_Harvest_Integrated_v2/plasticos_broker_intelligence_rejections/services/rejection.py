"""Refusal evidence stays a proposal, never a buyer blacklist or match-scoring input."""

CODES = (
    "WRONG_FORM",
    "NO_FILM_PROGRAM",
    "MOISTURE_HIGH",
    "LABELS_PAPER_HIGH",
    "METAL_PRESENT",
    "SPEC_INCOMPLETE",
    "MFI_OUT_OF_RANGE",
    "COLOR_WRONG",
    "FILLER_HIGH",
    "LOGISTICS_WINDOW",
    "QUALITY_HISTORY",
    "OTHER",
)


def candidate_code(raw_statement, manually_selected=None):
    value = str(raw_statement or "").strip().upper()
    if manually_selected:
        if manually_selected not in CODES:
            raise ValueError("Unsupported rejection meaning")
        return manually_selected, "manually proposed; not verified"
    if value in CODES:
        return value, "literal canonical code supplied as the entire recorded reason"
    return None, "raw buyer language requires independent interpretation; aliases unresolved"


def select_unique_reference(records):
    """Never pick one of two approved rejection references by incidental ORM order."""
    if len(records) == 1:
        return records[0], []
    if len(records) > 1:
        return None, [
            {
                "reason": "multiple_approved_references",
                "missing_prerequisites": ["Reviewer must resolve overlapping approved references."],
                "knowledge_keys": sorted(x.stable_key for x in records),
            }
        ]
    return None, []


def response(raw_statement, selected_code, approved_reference=None, *, deferred_guidance=None):
    code, basis = candidate_code(raw_statement, selected_code)
    return {
        "schema": "broker-rejection-advice/v1",
        "raw_counterparty_statement": raw_statement or "",
        "proposed_code": code,
        "classification_basis": basis,
        "verified_classification": False,
        "approved_guidance": approved_reference,
        "deferred_guidance": list(deferred_guidance or []),
        "missing_verification": [
            "Confirm the buyer's verbatim objection and material/lot scope.",
            "Ask whether the condition is buyer-specific, temporary, or general.",
            "Request attributable measurements and buyer specification if relevant.",
        ],
        "conditional_recovery": (
            ["Review the cited approved procedure with the broker and verify prerequisites."]
            if approved_reference
            else []
        ),
        "abstain": approved_reference is None,
        "automatic_exclusion": False,
        "offer_transition": False,
        "matching_change": False,
    }
