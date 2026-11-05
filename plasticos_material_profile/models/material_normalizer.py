"""Shared material interpretation for the ERP and CRM importers.

The function resolves canonical masters. It does not create partners, products,
profiles, or transactions, and it does not commit.
"""

from __future__ import annotations

from typing import NamedTuple


class _Spec(NamedTuple):
    """One phrase. An empty slot means that component was not named."""

    polymer: str | None
    material_grade: str | None = None
    grade: str | None = None
    form: str | None = None
    source: str | None = None
    attributes: tuple[str, ...] = ()
    packaging_type: str | None = None
    color: str | None = None


def _spec(
    *,
    polymer,
    material_grade=None,
    grade=None,
    form=None,
    source=None,
    attributes=(),
    packaging_type=None,
    color=None,
):
    return _Spec(
        polymer=polymer,
        material_grade=material_grade,
        grade=grade,
        form=form,
        source=source,
        attributes=attributes,
        packaging_type=packaging_type,
        color=color,
    )


def _identity(spec):
    """Slots that must agree. Attributes, packaging, and color come from the description."""
    return (spec.polymer, spec.material_grade, spec.grade, spec.form, spec.source)


# Exact phrases only. Unknown stays unspecified: no inferred source, cleanliness,
# dryness, or other attribute, and no mapping onto the OTHER polymer.
# A form is set only when the phrase names that form. An unknown form stays empty;
# identity does not require inventing one. The material grade is what the items were
# (drums, totes, pallets), set only when the phrase names it.
_SPECS = {
    "99 clear ldpe film": _spec(polymer="LDPE", grade="A", form="FILM", attributes=("clean", "dry")),
    "ldpe grade a film": _spec(polymer="LDPE", grade="A", form="FILM", attributes=("clean", "dry")),
    "95 clear ldpe film": _spec(polymer="LDPE", grade="B", form="FILM", attributes=("clean",)),
    "ldpe grade b film": _spec(polymer="LDPE", grade="B", form="FILM", attributes=("clean",)),
    "90 clear ldpe film": _spec(polymer="LDPE", grade="C", form="FILM"),
    "ldpe grade c film": _spec(polymer="LDPE", grade="C", form="FILM"),
    "pp film (bopp)": _spec(polymer="BOPP", form="FILM"),
    "pc/abs": _spec(polymer="PC_ABS", source="POST_INDUSTRIAL"),
    "pc-abs": _spec(polymer="PC_ABS", source="POST_INDUSTRIAL"),
    "3-7": _spec(polymer="3_7_COMMINGLED_BOTTLES", material_grade="BOTTLES", source="POST_CONSUMER"),
    "3-7 commingled bottles": _spec(polymer="3_7_COMMINGLED_BOTTLES", material_grade="BOTTLES", source="POST_CONSUMER"),
    "1-7": _spec(polymer="1_7_COMMINGLED_BOTTLES", material_grade="BOTTLES", source="POST_CONSUMER"),
    "1-7 commingled bottles": _spec(polymer="1_7_COMMINGLED_BOTTLES", material_grade="BOTTLES", source="POST_CONSUMER"),
    "pe": _spec(polymer="HDPE"),
    "pallets": _spec(polymer="PLASTIC_PALLETS"),
    "hdpe drums": _spec(polymer="HDPE", material_grade="DRUMS"),
    "explicit hmw-hdpe drums": _spec(polymer="HDPE_HMW", material_grade="DRUMS"),
    "hdpe drums (hmw-hdpe)": _spec(polymer="HDPE_HMW", material_grade="DRUMS"),
    "ldpe film": _spec(polymer="LDPE", form="FILM"),
    "ldpe film a": _spec(polymer="LDPE", grade="A", form="FILM"),
    "3-7 commingled": _spec(polymer="3_7_COMMINGLED_BOTTLES", material_grade="BOTTLES"),
    "1-7 commingled": _spec(polymer="1_7_COMMINGLED_BOTTLES", material_grade="BOTTLES"),
    "pp supersacs": _spec(polymer="PP", material_grade="SUPERACS"),
    # Operator ledger 2026-11-04. Both importers resolve these phrases.
    "pp supersacs (un-lined)": _spec(
        polymer="PP", material_grade="SUPERACS", attributes=("unlined",), packaging_type="bales"
    ),
    "pp supersacs - no liners": _spec(
        polymer="PP", material_grade="SUPERACS", attributes=("unlined",), packaging_type="bales"
    ),
    "super sacks": _spec(polymer="PP", material_grade="SUPERACS", attributes=("lined",), packaging_type="bales"),
    "pp supersacs (lined)": _spec(polymer="PP", material_grade="SUPERACS", packaging_type="bales"),
    "tubs": _spec(polymer="PP", material_grade="TUBS_LIDS", source="POST_CONSUMER", packaging_type="bales"),
    "occ bales": _spec(polymer="FIBER", material_grade="OCC", source="POST_CONSUMER", packaging_type="bales"),
    "old corrugated cardboard": _spec(
        polymer="FIBER", material_grade="OCC", source="POST_CONSUMER", packaging_type="bales"
    ),
    "hd/pp cornerboards": _spec(polymer="PP_PE", source="POST_CONSUMER", packaging_type="bales"),
    "pet bottles - post industrial": _spec(
        polymer="PET", material_grade="BOTTLES", source="POST_INDUSTRIAL", packaging_type="bales"
    ),
    "clear film": _spec(polymer="LLDPE", material_grade="STRETCH_FILM", form="FILM", packaging_type="bales"),
    "mixed pails": _spec(polymer="HDPE", material_grade="BUCKETS", form="LOOSE"),
    "hdpe/pp transitional purge regrind (frac melt)": _spec(
        polymer="PP_PE", form="PURGE", source="POST_INDUSTRIAL", attributes=("frac_melt",), packaging_type="gaylords"
    ),
    "pp/hd regrind": _spec(polymer="PP_PE", form="REGRIND", packaging_type="gaylords"),
    "strapping": _spec(polymer="PET", material_grade="STRAPPING"),
    "rigids": _spec(polymer="MRP"),
}

# CRM lead phrases that are not worksheet phrases. The whole collapsed
# description must match. A hit in ``_SPECS`` wins and never reaches this table.
# Bare LDPE is film. A trailing hyphen on HDPE- stays HDPE, distinct from HDPE-HMW.
_CRM_EXACT = {
    key: _spec(polymer=polymer, form=form)
    for key, polymer, form in (
        ("ldpe", "LDPE", "FILM"),
        ("nylon", "NYLON", None),
        ("metal", "METAL", None),
        ("e-waste", "EWASTE", None),
        ("hdpe-", "HDPE", None),
        ("hdpe-hmw", "HDPE_HMW", None),
        ("plastic pallets", "PLASTIC_PALLETS", None),
        ("gaylord boxes", "GAYLORD_BOXES", None),
        ("hdpe", "HDPE", None),
        ("pp", "PP", None),
        ("mrp", "MRP", None),
        ("pet", "PET", None),
        ("abs", "ABS", None),
        ("pc", "PC", None),
        ("ps", "PS", None),
        ("hips", "HIPS", None),
        ("pvc", "PVC", None),
        ("eps", "EPS", None),
        ("bopp", "BOPP", None),
        ("tpo", "TPO", None),
        ("tpe", "TPE", None),
        ("pbt", "PBT", None),
        ("lldpe", "LLDPE", None),
    )
}

# Operator-approved VanillaSoft aliases (POLYMER MAPPING sheet, ALIAS rows, approved 2026-10-30).
# Polymer is the sheet's code. material_grade is what the items were. grade is the A/B/C letter.
# A form is set only when the phrase names exactly one form master.
# The whole collapsed description must match; ``_SPECS`` and ``_CRM_EXACT`` win over this table.
_CRM_ALIASES = {
    key: _spec(polymer=polymer, material_grade=material_grade, grade=grade, form=form)
    for key, (polymer, form, grade, material_grade) in {
        "pet bottles": ("PET", None, None, "BOTTLES"),
        "pp supersacs": ("PP", None, None, "SUPERACS"),
        "hdpe bottles": ("HDPE", None, None, "BOTTLES"),
        "ldpe stretch film": ("LDPE", "FILM", None, "STRETCH_FILM"),
        "pet industrial": ("PET", None, None, None),
        "hdpe bottles - mixed color": ("HDPE", None, None, "BOTTLES"),
        "hdpe bottles - natural": ("HDPE", None, None, "BOTTLES"),
        "ldpe film b": ("LDPE", "FILM", "B", None),
        "acrylic / pmma": ("PMMA", None, None, None),
        "ldpe film": ("LDPE", "FILM", None, None),
        "nylon 6": ("NYLON", None, None, None),
        "pet strapping": ("PET", None, None, "STRAPPING"),
        "mrp export": ("MRP", None, None, None),
        "pvc flex": ("PVC", None, None, None),
        "hdpe buckets": ("HDPE", None, None, "BUCKETS"),
        "nylon 6.6": ("NYLON", None, None, None),
        "pp regrind": ("PP", "REGRIND", None, None),
        "ldpe post industrial": ("LDPE", None, None, None),
        "ibc totes (hmw-hdpe)": ("HDPE_HMW", None, None, "IBC_TOTES"),
        "hdpe totes": ("HDPE", None, None, "TOTES"),
        "hdpe bottles - z bales": ("HDPE", None, None, None),
        "hdpe crates": ("HDPE", None, None, "CRATES"),
        "mrp domestic": ("MRP", None, None, None),
        "ldpe film mixed color": ("LDPE", "FILM", None, None),
        "pp parts": ("PP", "PARTS", None, None),
        "ldpe film c": ("LDPE", "FILM", "C", None),
        "pet bottles - 70/30 curbside": ("PET", None, None, "BOTTLES"),
        "pp bottles - domestic pack": ("PP", None, None, "BOTTLES"),
        "hdpe toters (roll-out carts)": ("HDPE", None, None, "TOTERS"),
        "mrp-a": ("MRP", None, None, None),
        "tpo bumpers": ("TPO", None, None, "BUMPERS"),
        "acetal": ("POM", None, None, None),
        "pp purge": ("PP", "PURGE", None, None),
        "pp tubs/lids": ("PP", None, None, None),
        "hdpe pipe": ("HDPE", None, None, None),
        "mrp a": ("MRP", None, None, None),
        "ld/lldpe thick/stretch": ("LLDPE", None, None, None),
        "pp crates": ("PP", None, None, "CRATES"),
        "pp repro": ("PP", None, None, None),
        "ldpe purge": ("LDPE", "PURGE", None, None),
        "mrp - export": ("MRP", None, None, None),
        "pp bottles": ("PP", None, None, "BOTTLES"),
        "hdpe roto-mold tanks": ("HDPE", None, None, None),
        "hdpe corrugated pipe": ("HDPE", None, None, None),
        "ldpe logs": ("LDPE", "LOGS", None, None),
        "mrp - domestic": ("MRP", None, None, None),
        "pet bottles - deposit bill": ("PET", None, None, "BOTTLES"),
        "hdpe pill bottles": ("HDPE", None, None, "BOTTLES"),
        "mrp c&d": ("MRP", None, None, None),
        "pc - polycarb": ("PC", None, None, None),
        "hdpe drip tube": ("HDPE", None, None, None),
        "ldpe nursery film": ("LDPE", "FILM", None, None),
        "ldpe redemption bags": ("LDPE", None, None, None),
        "mrp-b": ("MRP", None, None, None),
        "e-waste - dark": ("EWASTE", None, None, None),
        "ldpe camelback": ("LDPE", None, None, None),
        "ldpe cotton film": ("LDPE", "FILM", None, None),
        "mrp industrial": ("MRP", None, None, None),
        "pa": ("NYLON", None, None, None),
        "pp bottles domestic": ("PP", None, None, "BOTTLES"),
        "pp hangers": ("PP", None, None, None),
        ".01 fob grade a mrp": ("MRP", None, None, None),
        "acrylic": ("PMMA", None, None, None),
        "also mentioned they buy pp gf 25-50% - black has golf material. mention and request references.": (
            "PP",
            None,
            None,
            None,
        ),
        "and occ -": ("OCC", None, None, None),
        "bopp printed": ("BOPP", None, None, None),
        "crate grade hdpe": ("HDPE", None, None, "CRATES"),
        "curb sorted no mrp - cb and pich for future -": ("MRP", None, None, None),
        "does marketing for 6 separate counties in maryland which generate mrp. got on bid list": (
            "MRP",
            None,
            None,
            None,
        ),
        "e-waste - light": ("EWASTE", None, None, None),
        "ext218 - pp sacks": ("PP", None, None, None),
        "gas tanks and so on. pvc post industrial.": ("PVC", None, None, None),
        "generates eps": ("EPS", None, None, None),
        "generates pet": ("PET", None, None, None),
        "had mrp and sacks. had loads of all.": ("MRP", None, None, None),
        "has 2 loads of ldpe film": ("LDPE", "FILM", None, None),
        "has ftl's of ldpe film from commercial dryer": ("LDPE", "FILM", None, None),
        "has mrp and everything else.": ("MRP", None, None, None),
        "has mrp and has c grade film": ("MRP", None, None, None),
        "has mrp b+": ("MRP", None, None, None),
        "has non-wove pp": ("PP", None, None, None),
        "has pp sacks": ("PP", None, None, None),
        "has pp super sacks with carbon black residue": ("PP", None, None, None),
        "has some colored eps. sometimes has white eps he needs to sell.": ("EPS", None, None, None),
        "hdpe bott": ("HDPE", None, None, None),
        "hdpe bottles.": ("HDPE", None, None, "BOTTLES"),
        "hdpe dumpster lids": ("HDPE", None, None, None),
        "hdpe gas tanks": ("HDPE", None, None, None),
        "hmw-hdpe/dunnage": ("HDPE_HMW", None, None, None),
        "ldpe house wrap": ("LDPE", None, None, None),
        "ldpe money bags and shrink wrap.": ("LDPE", None, None, None),
        "ldpe rolls": ("LDPE", "ROLLSTOCK", None, None),
        "mentioned: pp super sacsk": ("PP", None, None, None),
        "mrp looks like grade b": ("MRP", None, None, None),
        "pc regrind.": ("PC", "REGRIND", None, None),
        "pet baled": ("PET", None, None, None),
        "pet bott": ("PET", None, None, None),
        "pet preforms": ("PET", None, None, None),
        "plastic & textile nylon": ("NYLON", None, None, None),
        "pp battery casing": ("PP", None, None, None),
        "pp bins and other grades. seems to be marketing direct with prices as high as .25 for film.": (
            "PP",
            None,
            None,
            None,
        ),
        "pp rolls": ("PP", "ROLLSTOCK", None, None),
        "pp super sack offered 0.06/lb. has 30k now": ("PP", None, None, None),
        "quote on mrp. 0.05/lb and 0.12/lb": ("MRP", None, None, None),
        "should have other stuff. we sold him pvc": ("PVC", None, None, None),
        "should have tons of mrp": ("MRP", None, None, None),
        "they generate hdpe": ("HDPE", None, None, None),
        "they mostly work with pet bottles.": ("PET", None, None, "BOTTLES"),
    }.items()
}
_CRM_ALIASES["hdpe frac melt"] = _spec(polymer="HDPE", attributes=("frac_melt",))
_CRM_ALIASES["pvc rigid"] = _spec(polymer="PVC", attributes=("rigid",))
_CRM_ALIASES["ldpe thick gauge"] = _spec(polymer="LDPE", attributes=("thick_gauge",))


class MaterialNormalization:
    """One material phrase resolved to existing masters, or left unresolved."""

    def __init__(
        self,
        source_description,
        polymer,
        form,
        source_type,
        attributes,
        grade,
        unresolved,
        material_grade,
        *,
        color,
        packaging_type,
    ):
        self.source_description = source_description
        self.polymer = polymer
        self.material_grade = material_grade
        self.form = form
        self.source_type = source_type
        self.attributes = attributes
        self.grade = grade
        self.unresolved = tuple(unresolved)
        self.color = color
        self.packaging_type = packaging_type


def normalize_material(env, description, grade_evidence=None, structured=None, *, crm_aliases=False):
    """Resolve one material phrase.

    ``description`` is preserved. ``grade_evidence`` and ``structured`` count
    only when they are themselves a worksheet phrase. A disagreement on polymer,
    form, source, grade letter, or material grade is unresolved and does not
    pick a side. Attributes, color, and packaging come from the description
    when it matches. With ``crm_aliases``, a description that misses ``_SPECS``
    may match ``_CRM_EXACT``, then ``_CRM_ALIASES``. Hints stay on ``_SPECS``.
    """
    source = _collapse(description)
    text = _phrase(description)
    specs = []
    description_spec = _SPECS.get(text)
    if description_spec is None and crm_aliases:
        description_spec = _CRM_EXACT.get(text) or _CRM_ALIASES.get(text)
    if description_spec is not None:
        specs.append(description_spec)
    for hint in (_phrase(grade_evidence), *_structured_phrases(structured)):
        spec = _SPECS.get(hint)
        if spec is not None:
            specs.append(spec)
    if not source:
        source = _collapse(grade_evidence)
    if len({_identity(spec) for spec in specs}) > 1:
        return _empty(env, source, ("conflicting material evidence",))
    if not specs:
        reason = (
            ("unresolved material",) if source or _phrase(grade_evidence) or _structured_phrases(structured) else ()
        )
        return _empty(env, source, reason)
    return _realize(env, source, specs[0])


def _realize(env, source, spec):
    polymer, polymer_missing = _master(env, "plasticos.polymer", spec.polymer)
    material_grade, material_grade_missing = _master(env, "plasticos.material.grade", spec.material_grade)
    form, form_missing = _master(env, "plasticos.material.form", spec.form)
    source_type, source_missing = _master(env, "plasticos.source.type", spec.source)
    attributes, attribute_missing = _attributes(env, spec.attributes)
    color, color_missing = _master(env, "plasticos.material.color", spec.color)
    packaging_type, packaging_missing = _master(env, "plasticos.packaging.type", spec.packaging_type)
    unresolved = tuple(
        item
        for item in (
            polymer_missing,
            material_grade_missing,
            form_missing,
            source_missing,
            color_missing,
            packaging_missing,
            *attribute_missing,
        )
        if item
    )
    if unresolved:
        return _empty(env, source, unresolved)
    return MaterialNormalization(
        source,
        polymer,
        form,
        source_type,
        attributes,
        spec.grade,
        (),
        material_grade,
        color=color,
        packaging_type=packaging_type,
    )


def _empty(env, source, unresolved):
    return MaterialNormalization(
        source,
        env["plasticos.polymer"].browse(),
        env["plasticos.material.form"].browse(),
        env["plasticos.source.type"].browse(),
        env["plasticos.material.attribute"].browse(),
        None,
        unresolved,
        env["plasticos.material.grade"].browse(),
        color=env["plasticos.material.color"].browse(),
        packaging_type=env["plasticos.packaging.type"].browse(),
    )


def _master(env, model, code):
    if not code:
        return env[model].browse(), None
    found = env[model].search([("code", "=", code)], limit=1)
    if not found:
        return env[model].browse(), f"missing {model} {code}"
    return found, None


def _attributes(env, codes):
    found = env["plasticos.material.attribute"].browse()
    missing = []
    for code in codes:
        attribute, reason = _master(env, "plasticos.material.attribute", code)
        if reason:
            missing.append(reason)
        else:
            found |= attribute
    return found, missing


def _structured_phrases(structured):
    if not structured:
        return []
    if isinstance(structured, str):
        values = [structured]
    elif isinstance(structured, dict):
        values = list(structured.values())
    elif isinstance(structured, (list, tuple)):
        values = list(structured)
    else:
        return []
    return [phrase for phrase in (_phrase(value) for value in values) if phrase]


def _phrase(value) -> str:
    return _collapse(value).casefold()


def _collapse(value) -> str:
    return " ".join(str(value or "").split())
