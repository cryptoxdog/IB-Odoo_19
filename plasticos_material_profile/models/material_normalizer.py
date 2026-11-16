"""Shared material interpretation for the ERP and CRM importers.

The function resolves canonical masters. It does not create partners, products,
profiles, or transactions, and it does not commit.
"""

from __future__ import annotations

import csv
import xml.etree.ElementTree as ET
from pathlib import Path
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
    color: tuple[str, ...] = ()
    filler_type: str | None = None
    process_type: str | None = None


def _color_codes(color) -> tuple[str, ...]:
    """One code, a space-separated cell, or a tuple. Empty stays empty."""
    if not color:
        return ()
    if isinstance(color, str):
        return tuple(part for part in color.split() if part)
    return tuple(color)


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
    filler_type=None,
    process_type=None,
):
    return _Spec(
        polymer=polymer,
        material_grade=material_grade,
        grade=grade,
        form=form,
        source=source,
        attributes=attributes,
        packaging_type=packaging_type,
        color=_color_codes(color),
        filler_type=filler_type,
        process_type=process_type,
    )


def _identity(spec):
    """Slots that must agree. Attributes, packaging, color, filler, and process come from the description."""
    return (spec.polymer, spec.material_grade, spec.grade, spec.form, spec.source)


_MATRIX = Path(__file__).resolve().parents[1] / "data" / "material_mapping.csv"
# Sheet statuses that are never a material: a call note in the Materials field,
# or a line the operator decided is not a material. Importers skip them.
_NOT_MATERIAL_STATUSES = frozenset({"not_material", "note_not_material"})
_SHEET: tuple[dict[str, _Spec], frozenset[str]] | None = None


def _cell(row, name) -> str | None:
    value = (row.get(name) or "").strip()
    return value or None


def _codes(value) -> tuple[str, ...]:
    return tuple(part for part in (value or "").split() if part)


def _sheet() -> tuple[dict[str, _Spec], frozenset[str]]:
    global _SHEET
    if _SHEET is None:
        _SHEET = _load_sheet()
    return _SHEET


def phrase_table() -> dict[str, _Spec]:
    """Mapped material phrases from the sheet. Loaded once."""
    return _sheet()[0]


def is_not_material(phrase) -> bool:
    """True when the sheet records *phrase* as a call note or as not a material.

    Such text never becomes a profile. An importer skips it instead of reporting
    an unresolved material.
    """
    return _phrase(phrase) in _sheet()[1]


def _load_sheet() -> tuple[dict[str, _Spec], frozenset[str]]:
    """One spec per mapped material row that names a polymer, and the non-material keys.

    Any other status stays out of both. Two material rows with the same key fail the load.
    """
    phrases: dict[str, _Spec] = {}
    not_material: set[str] = set()
    seen: set[str] = set()
    with _MATRIX.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row["field_role"] != "material":
                continue
            key = _phrase(row["match_key"])
            if key in seen:
                raise ValueError(f"duplicate material phrase {key}")
            seen.add(key)
            if row["status"] in _NOT_MATERIAL_STATUSES:
                not_material.add(key)
                continue
            if row["status"] != "mapped" or not (row.get("polymer") or "").strip():
                continue
            phrases[key] = _spec(
                polymer=_cell(row, "polymer"),
                material_grade=_cell(row, "material_grade"),
                grade=_cell(row, "grade"),
                form=_cell(row, "form"),
                source=_cell(row, "source_type"),
                attributes=_codes(row.get("attributes")),
                packaging_type=_cell(row, "packaging_type"),
                color=_codes(row.get("color")),
                filler_type=_cell(row, "filler_type"),
                process_type=_cell(row, "process_type"),
            )
    return phrases, frozenset(not_material)


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
        filler_type=None,
        process_type=None,
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
        self.filler_type = filler_type
        self.process_type = process_type
        # Set only by the ERP product catalog. The phrase sheet has no tier column.
        self.quality_tier = None


# One collapsed word for web-lead eligibility. The words are the active seed
# names and codes, not a second list. The phrase lookup does not use them.
_SEED_FILES = {
    "attribute": "material_attribute_data.xml",
    "color": "material_color_data.xml",
    "filler": "filler_type_data.xml",
    "form": "material_form_data.xml",
    "grade": "material_grade_data.xml",
    "packaging": "packaging_type_data.xml",
    "polymer": "polymer_data.xml",
    "process": "process_type_data.xml",
    "source": "source_type_data.xml",
}
_SEED_WORDS: dict[str, dict[str, str]] = {}
GRADE_WORD_PRIORITY = ("PALLETS", "TOTES", "CRATES")
# Commas and periods ride on the word in seller text (``pallets,``, ``crates.``).
# They are not part of the lookup key. A hyphen inside a word stays.
_EDGE_PUNCTUATION = ".,;:!?\"'`()[]{}"


def seed_words(kind: str) -> dict[str, str]:
    """One-word names for an active seed master, keyed by the collapsed word."""
    cached = _SEED_WORDS.get(kind)
    if cached is None:
        cached = _words_for(_SEED_FILES[kind])
        _SEED_WORDS[kind] = cached
    return cached


def form_words() -> dict[str, str]:
    return seed_words("form")


def grade_words() -> dict[str, str]:
    return seed_words("grade")


def _field_text(fields, name) -> str:
    field = fields.get(name)
    if field is None or field.text is None:
        return ""
    return field.text.strip()


def _words_for(filename: str) -> dict[str, str]:
    words: dict[str, str] = {}
    path = Path(__file__).resolve().parents[1] / "data" / filename
    root = ET.parse(path).getroot()  # noqa: S314 - this module's own seed file, not external XML
    for record in root.iter("record"):
        fields = {field.get("name"): field for field in record.findall("field")}
        active = fields.get("active")
        if active is not None and (active.get("eval") or "").casefold() == "false":
            continue
        code = _field_text(fields, "code")
        if not code:
            continue
        for label in (code, _field_text(fields, "name")):
            word = label.casefold()
            if not word or "_" in word or " " in word or "&" in word:
                continue
            words.setdefault(word, code)
            if len(word) >= 4 and word.endswith("s") and not word.endswith(("ss", "cs", "us", "is", "os")):
                words.setdefault(word[:-1], code)
    return words


def classify_material_word(token) -> tuple[str | None, str | None]:
    """Return ``(form_code, grade_code)`` for one word. One of them is empty.

    Edge punctuation is removed before the seed form and grade names are read.
    """
    word = _phrase(token).strip(_EDGE_PUNCTUATION)
    if not word or " " in word:
        return None, None
    form_code = form_words().get(word)
    if form_code:
        return form_code, None
    return None, grade_words().get(word)


def normalize_material(env, description, grade_evidence=None, structured=None, *, crm_aliases=False):
    """Resolve one material phrase from the sheet.

    ``description`` is preserved. ``grade_evidence`` and ``structured`` count
    only when they are themselves a mapped phrase. A disagreement on polymer,
    form, source, grade letter, or material grade is unresolved and does not
    pick a side. Attributes, color, packaging, filler, and process come from the
    description when it matches. ``crm_aliases`` is accepted so existing callers
    still run; both importers read the same rows.
    """
    del crm_aliases
    source = _collapse(description)
    text = _phrase(description)
    phrases = phrase_table()
    specs = []
    description_spec = phrases.get(text)
    if description_spec is not None:
        specs.append(description_spec)
    for hint in (_phrase(grade_evidence), *_structured_phrases(structured)):
        spec = phrases.get(hint)
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
    color, color_missing = _colors(env, spec.color)
    packaging_type, packaging_missing = _master(env, "plasticos.packaging.type", spec.packaging_type)
    filler_type, filler_missing = _master(env, "plasticos.filler.type", spec.filler_type)
    process_type, process_missing = _process_code(spec.process_type)
    unresolved = tuple(
        item
        for item in (
            polymer_missing,
            material_grade_missing,
            form_missing,
            source_missing,
            *color_missing,
            packaging_missing,
            filler_missing,
            process_missing,
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
        filler_type=filler_type,
        process_type=process_type,
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
        filler_type=env["plasticos.filler.type"].browse(),
        process_type=None,
    )


def _process_code(code):
    """Return the profile selection code, or a missing-master reason."""
    if not code:
        return None, None
    from ..process_codes import PROCESS_CODES  # noqa: PLC0415 - ledger loader imports this file by path

    if code not in PROCESS_CODES:
        return None, f"missing process type {code}"
    return code, None


def _master(env, model, code):
    if not code:
        return env[model].browse(), None
    found = env[model].search([("code", "=", code)], limit=1)
    if not found:
        return env[model].browse(), f"missing {model} {code}"
    return found, None


def _colors(env, codes):
    found = env["plasticos.material.color"].browse()
    missing = []
    for code in codes:
        color, reason = _master(env, "plasticos.material.color", code)
        if reason:
            missing.append(reason)
        else:
            found |= color
    return found, missing


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


# ── ERP product catalog ──────────────────────────────────────────────────────
# ``data/ERP-Products.csv`` maps an ERP product name to masters. It is read by
# its own columns and is not the phrase sheet: ``normalize_material`` and
# ``phrase_table`` never open it. Its status column is blank on every row, so a
# row counts when it names a polymer.

ERP_PRODUCT_NOT_IN_CATALOG = "product not in catalog"
ERP_PRODUCT_WITHOUT_POLYMER = "catalog row without polymer"

_ERP_CATALOG_FILE = Path(__file__).resolve().parents[1] / "data" / "ERP-Products.csv"
_ERP_CATALOG: dict[str, _ErpProduct] | None = None


class _ErpProduct(NamedTuple):
    """One catalog row. ``spec`` is empty when the row names no polymer."""

    source_value: str
    spec: _Spec | None
    quality_tier: str | None


def _listed_codes(value) -> tuple[str, ...]:
    """Codes in a multi-value cell. The catalog separates them with a comma, a space, or both."""
    return _codes((value or "").replace(",", " "))


def erp_product_catalog() -> dict[str, _ErpProduct]:
    """Catalog rows keyed by product name, whitespace-collapsed and case-folded. Loaded once."""
    global _ERP_CATALOG
    if _ERP_CATALOG is None:
        _ERP_CATALOG = _load_erp_catalog(_ERP_CATALOG_FILE)
    return _ERP_CATALOG


def _load_erp_catalog(path) -> dict[str, _ErpProduct]:
    """One entry per material row. Two rows with the same product name fail the load."""
    catalog: dict[str, _ErpProduct] = {}
    with Path(path).open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            if (row.get("field_role") or "").strip() != "material":
                continue
            key = _phrase(row.get("source_value"))
            if not key:
                continue
            if key in catalog:
                raise ValueError(f"duplicate ERP product {key}")
            spec = None
            if _cell(row, "polymer"):
                spec = _spec(
                    polymer=_cell(row, "polymer"),
                    material_grade=_cell(row, "material_grade"),
                    form=_cell(row, "form"),
                    source=_cell(row, "source_type"),
                    attributes=_listed_codes(row.get("attributes")),
                    packaging_type=_cell(row, "packaging_type"),
                    color=_listed_codes(row.get("color")),
                    filler_type=_cell(row, "filler_type"),
                    process_type=_cell(row, "process_type"),
                )
            catalog[key] = _ErpProduct(_collapse(row.get("source_value")), spec, _cell(row, "quality_tier"))
    return catalog


def normalize_erp_product(env, product):
    """Resolve one ERP product name through the catalog to existing masters.

    An unknown product, a row without a polymer, and a code whose master is not
    in the database are unresolved. Nothing is guessed and no master is created.
    ``quality_tier`` on the result is a ``plasticos.material.quality.tier`` record.
    """
    source = _collapse(product)
    entry = erp_product_catalog().get(_phrase(product))
    if entry is None:
        return _erp_unresolved(env, source, (ERP_PRODUCT_NOT_IN_CATALOG,))
    if entry.spec is None:
        return _erp_unresolved(env, source, (ERP_PRODUCT_WITHOUT_POLYMER,))
    result = _realize(env, source, entry.spec)
    tier, tier_missing = _master(env, "plasticos.material.quality.tier", entry.quality_tier)
    if result.unresolved or tier_missing:
        return _erp_unresolved(env, source, (*result.unresolved, *((tier_missing,) if tier_missing else ())))
    result.quality_tier = tier
    return result


def _erp_unresolved(env, source, unresolved):
    result = _empty(env, source, unresolved)
    result.quality_tier = env["plasticos.material.quality.tier"].browse()
    return result
