"""
plasticos_inference/contamination_engine.py
Matches contamination profiles from YAML KBs to infer
typical contaminants, sorting purity, and processing requirements.
"""

from __future__ import annotations

from .kb_loader import KBIndex
from .models import (
    InferenceRequest,
    InferenceResult,
    InferenceSource,
)


def match_contamination(
    request: InferenceRequest,
    polymer_key: str,
    kb: KBIndex,
) -> list[InferenceResult]:
    """
    Find the best-matching contamination profile and infer
    contamination characteristics.
    """
    profiles = kb.contamination_profiles.get(polymer_key, [])
    if not profiles:
        return []

    source = (request.source_type or "").lower()
    form = (request.form or "").lower()
    app = (request.origin_application or "").lower()

    best: dict | None = None
    best_score = 0.0

    for prof in profiles:
        score = _score_profile(prof, source, form, app)
        if score > best_score:
            best = prof
            best_score = score

    if best is None or best_score < 0.3:
        return []

    results: list[InferenceResult] = []
    src_file = best.get("_source_file", "")
    prof_id = best.get("profileid", "unknown")

    # Typical contaminants list
    contam_list = best.get("typicalcontaminants")
    if contam_list:
        results.append(
            InferenceResult(
                field="typical_contaminants",
                value=contam_list,
                confidence=round(0.72 * best_score, 3),
                source=InferenceSource.YAML_CONTAMINATION,
                source_id=prof_id,
                source_file=src_file,
                reasoning=f"Contamination profile '{prof_id}' matched " f"(score {best_score:.2f})",
            )
        )

    # Sorting purity
    purity = best.get("sortingpuritypct")
    if purity is not None:
        results.append(
            InferenceResult(
                field="sorting_purity_pct",
                value=purity,
                confidence=round(0.70 * best_score, 3),
                source=InferenceSource.YAML_CONTAMINATION,
                source_id=prof_id,
                source_file=src_file,
                reasoning=f"Expected sorting purity {purity}% from '{prof_id}'",
            )
        )

    # Processing requirements (washing, drying, etc.)
    proc_reqs = best.get("processingrequirements", {})
    if isinstance(proc_reqs, dict):
        for req_key, req_val in proc_reqs.items():
            if req_val:
                results.append(
                    InferenceResult(
                        field=f"processing_{req_key}",
                        value=req_val,
                        confidence=round(0.68 * best_score, 3),
                        source=InferenceSource.YAML_CONTAMINATION,
                        source_id=prof_id,
                        source_file=src_file,
                        reasoning=f"Processing requirement '{req_key}' from '{prof_id}'",
                    )
                )

    # Contamination level estimate (if not provided on request)
    if request.contamination_pct is None:
        contam_level = best.get("contaminationlevel", "")
        quality_tier = best.get("qualitytier")
        if contam_level or quality_tier:
            results.append(
                InferenceResult(
                    field="contamination_level_hint",
                    value={"level": contam_level, "tier": quality_tier},
                    confidence=round(0.60 * best_score, 3),
                    source=InferenceSource.YAML_CONTAMINATION,
                    source_id=prof_id,
                    source_file=src_file,
                    reasoning=f"Contamination level '{contam_level}' (tier {quality_tier}) " f"from '{prof_id}'",
                )
            )

    return results


def _score_profile(prof: dict, source: str, form: str, app: str) -> float:
    """Score how well a contamination profile matches the request (0–1)."""
    score = 0.0
    prof_source = (prof.get("source") or "").lower()
    # prof_material reserved for future use

    # Source mention match
    source_map = {
        "pi": ("pir", "post-industrial", "manufacturing"),
        "pir": ("pir", "post-industrial", "manufacturing"),
        "pc": ("post-consumer", "pcr", "sorted"),
        "pcr": ("post-consumer", "pcr", "sorted"),
        "mixed": ("mixed", "unsorted"),
    }
    keywords = source_map.get(source, (source,))
    if any(kw in prof_source for kw in keywords):
        score += 0.5

    # Form match
    if form and form in prof_source:
        score += 0.2

    # Application match
    if app and app in prof_source:
        score += 0.3

    return min(score, 1.0)
