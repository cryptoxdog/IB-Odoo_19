"""Pure deterministic evidence assessment; no Odoo, AI, commercial execution or default weights."""

import re

SCHEMA = "broker-advice/v2"
ALLOWED = {
    "plasticos.intake": "intake",
    "plasticos.web.lead": "web_lead",
    "plasticos.offer": "offer",
    "plasticos.match.result": "match_result",
}
_STOP = frozenset(
    {
        "the",
        "and",
        "for",
        "from",
        "with",
        "what",
        "this",
        "that",
        "could",
        "should",
        "before",
        "about",
        "which",
        "there",
        "does",
        "have",
        "when",
        "these",
        "your",
        "would",
    }
)


def keywords(value):
    return frozenset(x for x in re.findall(r"[a-z0-9]{3,}", str(value or "").lower()) if x not in _STOP)


def rank_approved(question, facts, records, scope, *, limit=7):
    """Uses common words solely for retrieval, never as proof of any business property.

    Records are already ACL-filtered, current state=approved and scope-filtered by the caller.
    """
    context = (
        question
        + " "
        + " ".join(
            str(f.get("value") or "")
            for f in facts.values()
            if f.get("state")
            not in {"unknown", "conflicted", "unverified", "recorded_default_possible", "recorded_unverified"}
        )
    )
    tokens = keywords(context)
    ranked = []
    for record in records:
        if record.get("state") != "approved" or record.get("applies_to") not in ("all", scope):
            continue
        overlap = tokens & keywords(
            " ".join(str(record.get(k) or "") for k in ("name", "reviewed_meaning", "topic_tags"))
        )
        if not overlap:
            continue
        requirements = [x.strip() for x in str(record.get("prerequisite_keys") or "").split(",") if x.strip()]
        missing = [
            key
            for key in requirements
            if facts.get(key, {}).get("state") not in {"reported", "observed", "measured", "approved", "derived"}
        ]
        ranked.append((len(overlap), str(record.get("stable_key") or ""), record, missing))
    ranked.sort(key=lambda x: (-x[0], x[1]))
    return [(r, m) for _, _, r, m in ranked[:limit]]


def build_response(
    model, record_id, revision, question, facts, records, *, retrieval_complete=True, candidates_examined=None
):
    """Structured advice with citation and prerequisite guards; no speculative completion."""
    if model not in ALLOWED:
        raise ValueError("Unsupported advice source")
    scoped = ALLOWED[model]
    selected = rank_approved(question, facts, records, scoped)
    active, deferred = [], []
    for row, unmet in selected:
        # Retrieval cannot turn malformed source metadata into an apparently valid citation.
        digest = str(row.get("source_sha256") or "")
        if not re.fullmatch(r"[0-9a-f]{64}", digest) or not row.get("source_file") or not row.get("source_selector"):
            deferred.append(
                {
                    "knowledge_key": row.get("stable_key"),
                    "reason": "source_citation_unavailable",
                    "missing_prerequisites": [],
                }
            )
            continue
        citation = {
            "file": row["source_file"],
            "sha256": digest,
            "selector": row["source_selector"],
            "candidate": row.get("source_candidate_id"),
        }
        item = {
            "key": row["stable_key"],
            "version": row["version"],
            "title": row["name"],
            "reviewed_meaning": row["reviewed_meaning"],
            "conditions": row["evidence_requirements"],
            "workflow_scope": row.get("workflow_scope") or "not specified",
            "applicability_verified": False,
            "citation": citation,
            "basis": "human-reviewed reference, not a measured record fact",
            "relevance": "keyword retrieval only",
        }
        if unmet:
            deferred.append({"knowledge_key": row["stable_key"], "missing_prerequisites": unmet})
        else:
            active.append(item)
    unknowns = [
        key
        for key, fact in facts.items()
        if fact.get("state")
        in {"unknown", "conflicted", "unverified", "recorded_default_possible", "recorded_unverified"}
    ]
    followups = []
    if "polymer" in unknowns:
        followups.append("Confirm polymer identity using an attributable material observation or test.")
    if "form" in unknowns:
        followups.append("Confirm material form and the buyer's applicable line requirements.")
    if "quantity_lbs" in unknowns:
        followups.append("Obtain an attributable quantity and distinguish estimate from certified commercial weight.")
    if "mfi_conditions" in unknowns:
        followups.append("Obtain the MFI test conditions and applicable buyer specification before comparing values.")
    if "moisture_pct" in unknowns or "contamination_pct" in unknowns:
        followups.append("Request a source-bound quality observation or test; do not infer a zero from an empty field.")
    if "buyer_spec" in unknowns:
        followups.append("Ask the buyer for their current, product-specific acceptance requirements.")
    if "rejection_reason" in unknowns and scoped in {"offer", "match_result"}:
        followups.append("Obtain the buyer's verbatim rejection reason and its applicable scope.")
    if active:
        followups.append(
            "Verify that each cited reference's reviewed material and workflow scope applies to this record."
        )
    if not retrieval_complete:
        followups.append(
            "Ask a broker to review the full approved-knowledge set; this result evaluated a bounded subset."
        )
    if not active:
        followups.append("Escalate to a broker for review; no applicable approved guidance establishes a conclusion.")
    seen = set()
    next_actions = [x for x in followups if not (x in seen or seen.add(x))][:8]
    return {
        "schema": SCHEMA,
        "source": {"model": model, "id": int(record_id), "revision": str(revision or "unknown")},
        "question": question or "",
        "facts": facts,
        "unknowns": unknowns,
        "approved_knowledge": active,
        "deferred_knowledge": deferred,
        "next_human_actions": next_actions,
        "knowledge_retrieval": {
            "complete": bool(retrieval_complete),
            "candidates_examined": (candidates_examined if candidates_examined is not None else len(records)),
            "candidate_limit": 150 if not retrieval_complete else None,
        },
        "uncertainty": "unresolved" if unknowns or not active or not retrieval_complete else "conditional",
        "abstentions": [
            "No live price, material certificate, buyer compatibility, or commercial disposition is inferred."
        ],
        "commercial_action": "none",
        "external_messages_sent": 0,
    }
