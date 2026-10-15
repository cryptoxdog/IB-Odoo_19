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
    "ldpe film": ("LDPE", "FILM", None, (), None),
    "pp supersacs": ("PP", None, None, (), None),
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

    polymer_code, form_code, source_code, attribute_codes, grade = specs[0]
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
