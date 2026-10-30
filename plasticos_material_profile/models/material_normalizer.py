"""Shared material interpretation for the ERP and CRM importers.

The function resolves canonical masters. It does not create partners, products,
profiles, or transactions, and it does not commit.
"""

from __future__ import annotations

# Exact phrases only. Unknown stays unspecified: no inferred source, cleanliness,
# dryness, or other attribute, and no mapping onto the OTHER polymer.
# A form is set only when the phrase names that form. An unknown form stays empty;
# identity does not require inventing one.
_SPECS = {
    "99 clear ldpe film": ("LDPE", "FILM", None, ("clean", "dry"), "A"),
    "ldpe grade a film": ("LDPE", "FILM", None, ("clean", "dry"), "A"),
    "95 clear ldpe film": ("LDPE", "FILM", None, ("clean",), "B"),
    "ldpe grade b film": ("LDPE", "FILM", None, ("clean",), "B"),
    "90 clear ldpe film": ("LDPE", "FILM", None, (), "C"),
    "ldpe grade c film": ("LDPE", "FILM", None, (), "C"),
    "pp film (bopp)": ("BOPP", "FILM", None, (), None),
    "pc/abs": ("PC_ABS", None, "POST_INDUSTRIAL", (), None),
    "pc-abs": ("PC_ABS", None, "POST_INDUSTRIAL", (), None),
    "3-7": ("3_7_COMMINGLED_BOTTLES", "BOTTLES", "POST_CONSUMER", (), None),
    "3-7 commingled bottles": ("3_7_COMMINGLED_BOTTLES", "BOTTLES", "POST_CONSUMER", (), None),
    "1-7": ("1_7_COMMINGLED_BOTTLES", "BOTTLES", "POST_CONSUMER", (), None),
    "1-7 commingled bottles": ("1_7_COMMINGLED_BOTTLES", "BOTTLES", "POST_CONSUMER", (), None),
    "pe": ("HDPE", None, None, (), None),
    "pallets": ("PLASTIC_PALLETS", None, None, (), None),
    "hdpe drums": ("HDPE", "DRUMS", None, (), None),
    "explicit hmw-hdpe drums": ("HDPE_HMW", "DRUMS", None, (), None),
    "hdpe drums (hmw-hdpe)": ("HDPE_HMW", "DRUMS", None, (), None),
    "ldpe film": ("LDPE", "FILM", None, (), None),
    "ldpe film a": ("LDPE", "FILM", None, (), "A"),
    "3-7 commingled": ("3_7_COMMINGLED_BOTTLES", "BOTTLES", None, (), None),
    "1-7 commingled": ("1_7_COMMINGLED_BOTTLES", "BOTTLES", None, (), None),
    "pp supersacs": ("PP", None, None, (), None),
}

# CRM lead phrases that are not worksheet phrases. The whole collapsed
# description must match. A hit in ``_SPECS`` wins and never reaches this table.
# Bare LDPE is film. A trailing hyphen on HDPE- stays HDPE, distinct from HDPE-HMW.
_CRM_EXACT = {
    key: (polymer, form, None, (), None)
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
# Polymer is the sheet's code. A form is set only when the phrase names exactly one form master.
# The whole collapsed description must match; ``_SPECS`` and ``_CRM_EXACT`` win over this table.
_CRM_ALIASES = {
    key: (polymer, form, None, (), grade)
    for key, (polymer, form, grade) in {
        "pet bottles": ("PET", "BOTTLES", None),
        "pp supersacs": ("PP", None, None),
        "hdpe bottles": ("HDPE", "BOTTLES", None),
        "ldpe stretch film": ("LDPE", "FILM", None),
        "pet industrial": ("PET", None, None),
        "hdpe bottles - mixed color": ("HDPE", "BOTTLES", None),
        "hdpe bottles - natural": ("HDPE", "BOTTLES", None),
        "ldpe film b": ("LDPE", "FILM", "B"),
        "acrylic / pmma": ("PMMA", None, None),
        "hdpe frac melt": ("HDPE", None, None),
        "ldpe film": ("LDPE", "FILM", None),
        "nylon 6": ("NYLON", None, None),
        "pvc rigid": ("PVC", None, None),
        "pet strapping": ("PET", None, None),
        "mrp export": ("MRP", None, None),
        "pp supersacs (un-lined)": ("PP", None, None),
        "pvc flex": ("PVC", None, None),
        "hdpe buckets": ("HDPE", "BUCKETS", None),
        "nylon 6.6": ("NYLON", None, None),
        "pp regrind": ("PP", "REGRIND", None),
        "pp supersacs (lined)": ("PP", None, None),
        "ldpe post industrial": ("LDPE", None, None),
        "ibc totes (hmw-hdpe)": ("HDPE_HMW", "TOTES", None),
        "hdpe totes": ("HDPE", "TOTES", None),
        "hdpe bottles - z bales": ("HDPE", None, None),
        "hdpe crates": ("HDPE", "CRATES", None),
        "mrp domestic": ("MRP", None, None),
        "ldpe film mixed color": ("LDPE", "FILM", None),
        "pp parts": ("PP", "PARTS", None),
        "ldpe film c": ("LDPE", "FILM", "C"),
        "pet bottles - 70/30 curbside": ("PET", "BOTTLES", None),
        "pp bottles - domestic pack": ("PP", "BOTTLES", None),
        "hdpe toters (roll-out carts)": ("HDPE", None, None),
        "mrp-a": ("MRP", None, None),
        "tpo bumpers": ("TPO", None, None),
        "acetal": ("POM", None, None),
        "pp purge": ("PP", "PURGE", None),
        "pp tubs/lids": ("PP", None, None),
        "hdpe pipe": ("HDPE", None, None),
        "mrp a": ("MRP", None, None),
        "ld/lldpe thick/stretch": ("LLDPE", None, None),
        "pp crates": ("PP", "CRATES", None),
        "pp repro": ("PP", None, None),
        "ldpe purge": ("LDPE", "PURGE", None),
        "mrp - export": ("MRP", None, None),
        "pp bottles": ("PP", "BOTTLES", None),
        "hdpe roto-mold tanks": ("HDPE", None, None),
        "hdpe corrugated pipe": ("HDPE", None, None),
        "ldpe logs": ("LDPE", "LOGS", None),
        "mrp - domestic": ("MRP", None, None),
        "pet bottles - deposit bill": ("PET", "BOTTLES", None),
        "hdpe pill bottles": ("HDPE", "BOTTLES", None),
        "ldpe thick gauge": ("LDPE", None, None),
        "mrp c&d": ("MRP", None, None),
        "pc - polycarb": ("PC", None, None),
        "hdpe drip tube": ("HDPE", None, None),
        "ldpe nursery film": ("LDPE", "FILM", None),
        "ldpe redemption bags": ("LDPE", None, None),
        "mrp-b": ("MRP", None, None),
        "e-waste - dark": ("EWASTE", None, None),
        "ldpe camelback": ("LDPE", None, None),
        "ldpe cotton film": ("LDPE", "FILM", None),
        "mrp industrial": ("MRP", None, None),
        "pa": ("NYLON", None, None),
        "pp bottles domestic": ("PP", "BOTTLES", None),
        "pp hangers": ("PP", None, None),
        ".01 fob grade a mrp": ("MRP", None, None),
        "acrylic": ("PMMA", None, None),
        "also mentioned they buy pp gf 25-50% - black has golf material. mention and request references.": (
            "PP",
            None,
            None,
        ),
        "and occ -": ("OCC", None, None),
        "bopp printed": ("BOPP", None, None),
        "crate grade hdpe": ("HDPE", "CRATES", None),
        "curb sorted no mrp - cb and pich for future -": ("MRP", None, None),
        "does marketing for 6 separate counties in maryland which generate mrp. got on bid list": ("MRP", None, None),
        "e-waste - light": ("EWASTE", None, None),
        "ext218 - pp sacks": ("PP", None, None),
        "gas tanks and so on. pvc post industrial.": ("PVC", None, None),
        "generates eps": ("EPS", None, None),
        "generates pet": ("PET", None, None),
        "had mrp and sacks. had loads of all.": ("MRP", None, None),
        "has 2 loads of ldpe film": ("LDPE", "FILM", None),
        "has ftl's of ldpe film from commercial dryer": ("LDPE", "FILM", None),
        "has mrp and everything else.": ("MRP", None, None),
        "has mrp and has c grade film": ("MRP", None, None),
        "has mrp b+": ("MRP", None, None),
        "has non-wove pp": ("PP", None, None),
        "has pp sacks": ("PP", None, None),
        "has pp super sacks with carbon black residue": ("PP", None, None),
        "has some colored eps. sometimes has white eps he needs to sell.": ("EPS", None, None),
        "hdpe bott": ("HDPE", None, None),
        "hdpe bottles.": ("HDPE", "BOTTLES", None),
        "hdpe dumpster lids": ("HDPE", None, None),
        "hdpe gas tanks": ("HDPE", None, None),
        "hmw-hdpe/dunnage": ("HDPE_HMW", None, None),
        "ldpe house wrap": ("LDPE", None, None),
        "ldpe money bags and shrink wrap.": ("LDPE", None, None),
        "ldpe rolls": ("LDPE", "ROLLSTOCK", None),
        "mentioned: pp super sacsk": ("PP", None, None),
        "mrp looks like grade b": ("MRP", None, None),
        "pc regrind.": ("PC", "REGRIND", None),
        "pet baled": ("PET", None, None),
        "pet bott": ("PET", None, None),
        "pet preforms": ("PET", None, None),
        "plastic & textile nylon": ("NYLON", None, None),
        "pp battery casing": ("PP", None, None),
        "pp bins and other grades. seems to be marketing direct with prices as high as .25 for film.": (
            "PP",
            None,
            None,
        ),
        "pp rolls": ("PP", "ROLLSTOCK", None),
        "pp super sack offered 0.06/lb. has 30k now": ("PP", None, None),
        "quote on mrp. 0.05/lb and 0.12/lb": ("MRP", None, None),
        "should have other stuff. we sold him pvc": ("PVC", None, None),
        "should have tons of mrp": ("MRP", None, None),
        "they generate hdpe": ("HDPE", None, None),
        "they mostly work with pet bottles.": ("PET", "BOTTLES", None),
    }.items()
}


class MaterialNormalization:
    """One material phrase resolved to existing masters, or left unresolved."""

    def __init__(self, source_description, polymer, form, source_type, attributes, grade, unresolved):
        self.source_description = source_description
        self.polymer = polymer
        self.form = form
        self.source_type = source_type
        self.attributes = attributes
        self.grade = grade
        self.unresolved = tuple(unresolved)


def normalize_material(env, description, grade_evidence=None, structured=None):
    """Resolve one material phrase.

    ``description`` is preserved. ``grade_evidence`` and ``structured`` count
    only when they are themselves an approved phrase. A disagreement between
    those phrases is unresolved and does not pick a side.
    """
    source = _collapse(description)
    specs = []
    for text in (_phrase(description), _phrase(grade_evidence), *_structured_phrases(structured)):
        spec = _SPECS.get(text)
        if spec is not None:
            specs.append(spec)
    if not source:
        source = _collapse(grade_evidence)
    if len(set(specs)) > 1:
        return _empty(env, source, ("conflicting material evidence",))
    if not specs:
        reason = (
            ("unresolved material",) if source or _phrase(grade_evidence) or _structured_phrases(structured) else ()
        )
        return _empty(env, source, reason)
    return _realize(env, source, specs[0])


def normalize_crm_material(env, description, grade_evidence=None, structured=None):
    """Resolve one CRM material phrase.

    A description that is already a worksheet phrase uses
    :func:`normalize_material`. Any other description may match ``_CRM_EXACT``,
    then ``_CRM_ALIASES``.
    Grade evidence and structured hints still match ``_SPECS`` only, so a hint
    that is only a CRM identity does not add a second material. Two different
    specs conflict.
    """
    text = _phrase(description)
    if text in _SPECS:
        return normalize_material(env, description, grade_evidence=grade_evidence, structured=structured)
    source = _collapse(description)
    if not source:
        source = _collapse(grade_evidence)
    specs = []
    exact = _CRM_EXACT.get(text) or _CRM_ALIASES.get(text)
    if exact is not None:
        specs.append(exact)
    for hint in (_phrase(grade_evidence), *_structured_phrases(structured)):
        spec = _SPECS.get(hint)
        if spec is not None:
            specs.append(spec)
    if len(set(specs)) > 1:
        return _empty(env, source, ("conflicting material evidence",))
    if not specs:
        reason = (
            ("unresolved material",) if source or _phrase(grade_evidence) or _structured_phrases(structured) else ()
        )
        return _empty(env, source, reason)
    return _realize(env, source, specs[0])


def _realize(env, source, spec):
    polymer_code, form_code, source_code, attribute_codes, grade = spec
    polymer, polymer_missing = _master(env, "plasticos.polymer", polymer_code)
    form, form_missing = _master(env, "plasticos.material.form", form_code)
    source_type, source_missing = _master(env, "plasticos.source.type", source_code)
    attributes, attribute_missing = _attributes(env, attribute_codes)
    unresolved = tuple(item for item in (polymer_missing, form_missing, source_missing, *attribute_missing) if item)
    if unresolved:
        return _empty(env, source, unresolved)
    return MaterialNormalization(source, polymer, form, source_type, attributes, grade, ())


def _empty(env, source, unresolved):
    return MaterialNormalization(
        source,
        env["plasticos.polymer"].browse(),
        env["plasticos.material.form"].browse(),
        env["plasticos.source.type"].browse(),
        env["plasticos.material.attribute"].browse(),
        None,
        unresolved,
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
