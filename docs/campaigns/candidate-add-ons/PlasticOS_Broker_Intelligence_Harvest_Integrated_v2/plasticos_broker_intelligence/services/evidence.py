"""Pure evidence packaging. Zero, missing and uncertain are never equivalent."""
import hashlib
import json


def observation_identity(*, source_model, source_id, source_revision, scope_basis,
                         company_id, observation_type, actor_id, evidence_ref, observation):
    """Versioned, unambiguous replay identity including legal company scope.

    JSON array encoding prevents delimiter collisions between free-text fields.
    Source-revision and actor remain part of the original idempotency contract.
    """
    parts = ["broker-feedback/v2", source_model, source_id, str(source_revision),
             scope_basis, company_id, observation_type, actor_id, evidence_ref, observation]
    blob = json.dumps(parts, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()

def legacy_observation_identity(*, source_model, source_id, source_revision,
                                observation_type, actor_id, evidence_ref, observation):
    """Compatibility lookup for receipts created by the previous package.

    Never trust this delimiter-joined digest by itself: compare all stored
    provenance fields before returning an old receipt.
    """
    raw = (f"{source_model}:{source_id}:{source_revision}:{observation_type}:"
           f"{actor_id}:{evidence_ref}:{observation}")
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def fact(value, basis, *, zero_ambiguous=False, verified=False):
    if value is None or value is False or value == "" or (zero_ambiguous and value == 0):
        return {"state": "unknown", "value": None, "basis": "no distinguishable source observation"}
    state = "approved" if verified else basis
    return {"state": state, "value": value, "basis": basis}


def mfi_basis(value, conditions):
    item = fact(value, "recorded", zero_ambiguous=True)
    if not conditions:
        return item, {"state": "unknown", "value": None, "basis": "test conditions unavailable"}
    return item, fact(conditions, "reported")


def reject_alias(alias, exact_codes, reviewed_aliases):
    """No guess: namespace aliases require an explicit, reviewed mapping."""
    token = str(alias or "").strip().upper()
    if token in exact_codes:
        return {"candidate_code": token, "basis": "explicit canonical token", "approved": False}
    if token in reviewed_aliases and reviewed_aliases[token] in exact_codes:
        return {"candidate_code": reviewed_aliases[token], "basis": "reviewed alias mapping", "approved": False}
    return {"candidate_code": None, "basis": "alias unresolved", "approved": False}


def is_source_rejection_evidence(model, state, source_reason, observation_type, observation):
    """Only an exact source rejection event, not commentary, is source-confirmed.

    Does not attest to underlying material quality, buyer specifications, or
    truthfulness of the buyer's original statement.
    """
    reason = str(source_reason or "").strip()
    return (model in {"plasticos.offer", "plasticos.match.result"}
            and state == "rejected" and observation_type == "rejection"
            and bool(reason) and str(observation or "").strip() == reason)
