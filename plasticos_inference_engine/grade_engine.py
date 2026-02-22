"""
plasticos_inference/grade_engine.py
Matches an InferenceRequest to material grades and infers
MFI, density, PCR compatibility from the best-matching grade.
"""

from __future__ import annotations

import logging
from typing import Any

from .kb_loader import KBIndex
from .models import (
    GradeMatch,
    InferenceRequest,
    InferenceResult,
    InferenceSource,
)

logger = logging.getLogger("plasticos_inference.grade_engine")

# Process keyword → grade ID fragments
_PROCESS_KEYWORDS: dict[str, tuple[str, ...]] = {
    "injection molding": ("injection",),
    "blow molding": ("blowmolding", "blow"),
    "extrusion": ("extrusion", "extrus", "sheet"),
    "film extrusion": ("film",),
    "pipe extrusion": ("pipe",),
    "thermoforming": ("thermoform",),
    "rotomolding": ("rotomolding", "roto"),
    "fiber": ("fiber", "nonwoven"),
    "raffia": ("raffia",),
    "wire and cable": ("wirecable", "wire"),
    "compounding": ("compound",),
}

_FORM_KEYWORDS: dict[str, tuple[str, ...]] = {
    "bale": ("bale",),
    "regrind": ("regrind", "reg"),
    "pellet": ("pellet", "pell"),
    "flake": ("flake",),
    "film": ("film",),
    "roll": ("roll",),
    "pipe": ("pipe",),
    "sheet": ("sheet",),
}


def _extract_properties(grade: dict[str, Any]) -> dict[str, Any]:
    """Extract relevant properties from a grade dict for GradeMatch."""
    props: dict[str, Any] = {}
    for key in ("mfi", "density", "pcr_compatible", "applications", "notes"):
        if key in grade:
            props[key] = grade[key]
    return props


def match_grades(
    request: InferenceRequest,
    polymer_key: str,
    kb: KBIndex,
) -> list[GradeMatch]:
    """
    Find all grades that match the request, scored by relevance.
    """
    grades = kb.material_grades.get(polymer_key, [])
    if not grades:
        return []

    process = (request.process_type or "").lower()
    form = (request.form or "").lower()
    matches: list[GradeMatch] = []

    for grade in grades:
        gid = (grade.get("gradeid") or "").lower()
        gname = (grade.get("gradename") or "").lower()
        score = _score_grade(gid, gname, grade, process, form)
        if score > 0.0:
            matches.append(
                GradeMatch(
                    grade_id=grade.get("gradeid", "?"),
                    grade_name=grade.get("gradename", "?"),
                    polymer=polymer_key,
                    source_file=grade.get("_source_file", ""),
                    match_score=score,
                    properties=_extract_properties(grade),
                )
            )

    # Sort best match first
    matches.sort(key=lambda m: m.match_score, reverse=True)
    return matches


def infer_from_grades(
    request: InferenceRequest,
    polymer_key: str,
    kb: KBIndex,
) -> list[InferenceResult]:
    """
    Infer MFI, density, and PCR from the best-matching grade.
    Only fills fields that are None on the request.
    """
    matches = match_grades(request, polymer_key, kb)
    if not matches:
        return []

    best = matches[0]
    grade_data = _find_grade_dict(kb, polymer_key, best.grade_id)
    if not grade_data:
        return []

    results: list[InferenceResult] = []
    src_file = grade_data.get("_source_file", "")
    gname = best.grade_name

    # MFI
    if request.mfi_value is None:
        mfi = _extract_range(grade_data, "meltflowrate", "meltindex")
        if mfi:
            results.append(
                InferenceResult(
                    field="mfi_range",
                    value={"min": mfi[0], "max": mfi[1]},
                    confidence=round(0.78 * best.match_score, 3),
                    source=InferenceSource.YAML_GRADE,
                    source_id=best.grade_id,
                    source_file=src_file,
                    reasoning=f"MFI {mfi[0]}–{mfi[1]} g/10min from {gname}",
                )
            )

    # Density
    if request.density_value is None:
        dens = _extract_range(grade_data, "density")
        if dens:
            results.append(
                InferenceResult(
                    field="density_range",
                    value={"min": dens[0], "max": dens[1]},
                    confidence=round(0.80 * best.match_score, 3),
                    source=InferenceSource.YAML_GRADE,
                    source_id=best.grade_id,
                    source_file=src_file,
                    reasoning=f"Density {dens[0]}–{dens[1]} g/cm³ from {gname}",
                )
            )

    # PCR compatibility
    pcr = grade_data.get("pcrcompatibility")
    if isinstance(pcr, dict) and pcr.get("maxpcrpct") is not None:
        results.append(
            InferenceResult(
                field="max_pcr_pct",
                value=pcr["maxpcrpct"],
                confidence=round(0.75 * best.match_score, 3),
                source=InferenceSource.YAML_GRADE,
                source_id=best.grade_id,
                source_file=src_file,
                reasoning=f"Max PCR {pcr['maxpcrpct']}% from {gname}",
            )
        )

    # Mechanical properties
    mech = grade_data.get("mechanicalproperties", {})
    if isinstance(mech, dict):
        for prop_key, field_name in [
            ("tensilestrengthmpa", "tensile_strength_mpa"),
            ("flexuralmodulusmpa", "flexural_modulus_mpa"),
            ("impactstrengthjm", "impact_strength_jm"),
            ("hdtc", "hdt_c"),
        ]:
            val = mech.get(prop_key)
            if isinstance(val, list | tuple) and len(val) == 2:
                results.append(
                    InferenceResult(
                        field=field_name,
                        value={"min": val[0], "max": val[1]},
                        confidence=round(0.70 * best.match_score, 3),
                        source=InferenceSource.YAML_GRADE,
                        source_id=best.grade_id,
                        source_file=src_file,
                        reasoning=f"{field_name} {val[0]}–{val[1]} from {gname}",
                    )
                )

    return results


# ── Private helpers ──────────────────────────────────────────


def _score_grade(gid: str, gname: str, grade: dict, process: str, form: str) -> float:
    """Score how well a grade matches process/form context (0.0–1.0)."""
    score = 0.3  # base: same polymer

    # Process match
    if process:
        kws = _PROCESS_KEYWORDS.get(process, (process.replace(" ", ""),))
        for kw in kws:
            if kw in gid or kw in gname:
                score += 0.5
                break

    # Form match
    if form:
        kws = _FORM_KEYWORDS.get(form, (form.replace(" ", ""),))
        for kw in kws:
            if kw in gid or kw in gname:
                score += 0.2
                break

    # Virgin grade bonus (more reliable properties)
    if grade.get("type") == "virgin":
        score += 0.05

    return min(score, 1.0)


def _find_grade_dict(kb: KBIndex, polymer: str, grade_id: str) -> dict | None:
    for grade in kb.material_grades.get(polymer, []):
        if grade.get("gradeid") == grade_id:
            return grade
    return None


def _extract_range(grade: dict, *keys: str) -> tuple[float, float] | None:
    """Walk nested dicts for a [min, max] range under any key."""
    for key in keys:
        node = grade.get(key)
        if node is None:
            continue
        if isinstance(node, dict):
            for v in node.values():
                if isinstance(v, list | tuple) and len(v) == 2:
                    try:
                        return (float(v[0]), float(v[1]))
                    except (ValueError, TypeError):
                        continue
                if isinstance(v, dict):
                    for vv in v.values():
                        if isinstance(vv, list | tuple) and len(vv) == 2:
                            try:
                                return (float(vv[0]), float(vv[1]))
                            except (ValueError, TypeError):
                                continue
        elif isinstance(node, list | tuple) and len(node) == 2:
            try:
                return (float(node[0]), float(node[1]))
            except (ValueError, TypeError):
                pass
    return None
