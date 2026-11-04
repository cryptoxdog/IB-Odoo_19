"""The 11-04-26 ledger and the normalizer stay one partition.

A row is applied only when every filled cell names one seeded master and the
row is not an operator hold. Applied rows equal ``_SPECS``. Every other row is
in the remaining CSV, with the ledger header unchanged and the hold reason
appended to the evidence.
"""

from __future__ import annotations

import csv
import importlib.util
import re
from pathlib import Path

from defusedxml import ElementTree

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "plasticos_material_profile"
DATA = PROFILE / "data"
LEDGER = DATA / "material_mapping_resolution_ledger_11-04-26.csv"
REMAINING = DATA / "material_mapping_resolution_remaining.csv"

OPERATOR_HOLDS = {
    "hdpe / ldpe regrind": "operator hold; polymer cell PP_PE contradicts HDPE/LDPE",
    "gaylords of amazon returns": "operator hold; no mapping onto the OTHER polymer",
}
GRADE_ALIASES = {"supersacs": "SUPERACS"}
COLOR_ALIASES = {"mixed color": "MIXED"}


def _load_normalizer():
    spec = importlib.util.spec_from_file_location(
        "material_normalizer_ledger",
        PROFILE / "models" / "material_normalizer.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _records(filename):
    root = ElementTree.parse(DATA / filename).getroot()
    records = []
    for record in root.iter("record"):
        fields = {}
        for child in record:
            if child.tag != "field":
                continue
            fields[child.get("name")] = (child.text or "").strip()
            if child.get("ref"):
                fields[child.get("name") + "_ref"] = child.get("ref")
        records.append((record.get("id"), fields))
    return records


def _codes(filename):
    return {fields["code"] for _xml, fields in _records(filename) if fields.get("code")}


def _masters():
    polymers = _records("polymer_data.xml")
    polymer_by_xml = {xml: fields["code"] for xml, fields in polymers if fields.get("code")}
    grades = _records("material_grade_data.xml")
    grade_codes = {fields["code"] for _xml, fields in grades if fields.get("code")}
    grade_by_name = {
        fields["name"].casefold(): fields["code"]
        for _xml, fields in grades
        if fields.get("name") and fields.get("code")
    }
    grade_by_name.update(GRADE_ALIASES)
    templates = {}
    for _xml, fields in _records("grade_template_data.xml"):
        code = fields.get("code")
        polymer = polymer_by_xml.get(fields.get("polymer_id_ref", ""))
        if code and polymer:
            templates[code] = polymer
    selection_source = (PROFILE / "models" / "material_profile.py").read_text()
    start = selection_source.index("polymer = fields.Selection(")
    chunk = selection_source[start : selection_source.index('string="Polymer Code"', start)]
    selection = set(re.findall(r'\("([A-Z0-9_]+)"', chunk))
    packaging = _codes("packaging_type_data.xml")
    attributes = _codes("material_attribute_data.xml")
    return {
        "polymer": set(polymer_by_xml.values()),
        "selection": selection,
        "grade": grade_codes,
        "grade_by_name": grade_by_name,
        "form": _codes("material_form_data.xml"),
        "former_forms": set(_load_grade_codes().FORMER_FORM_CODES),
        "source": _codes("source_type_data.xml"),
        "color": {code.upper(): code for code in _codes("material_color_data.xml")},
        "packaging": {code.casefold(): code for code in packaging},
        "attribute": {code.casefold(): code for code in attributes},
        "template": templates,
    }


def _load_grade_codes():
    spec = importlib.util.spec_from_file_location("grade_codes_ledger", PROFILE / "grade_codes.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _cell(row, name):
    return (row.get(name) or "").strip()


def _grade_code(raw, masters):
    alias = masters["grade_by_name"].get(raw.casefold())
    if alias:
        return alias
    upper = raw.upper().replace(" ", "_")
    if upper in masters["grade"]:
        return upper
    return None


def classify(row, masters):
    """Return ``(spec, None)`` when the row applies, else ``(None, reason)``."""
    key = _cell(row, "match_key")
    if key in OPERATOR_HOLDS:
        return None, OPERATOR_HOLDS[key]
    failures = []
    polymer = None
    raw_polymer = _cell(row, "polymer")
    if raw_polymer:
        code = raw_polymer.upper().replace("/", "_")
        if code in masters["polymer"] and code in masters["selection"]:
            polymer = code
        else:
            failures.append(f"polymer {raw_polymer} is not a seeded polymer")
    material_grade = None
    raw_grade = _cell(row, "grade")
    if raw_grade:
        material_grade = _grade_code(raw_grade, masters)
        if material_grade is None:
            failures.append(f"grade {raw_grade} is not a seeded grade")
    form = None
    raw_form = _cell(row, "form")
    if raw_form:
        form_code = raw_form.upper()
        if form_code in masters["former_forms"]:
            if material_grade and material_grade != form_code:
                failures.append(f"form {raw_form} conflicts with grade {material_grade}")
            elif material_grade is None:
                material_grade = form_code
        elif form_code in masters["form"]:
            form = form_code
        else:
            failures.append(f"form {raw_form} is not a seeded form")
    source = None
    raw_source = _cell(row, "source_type")
    if raw_source:
        source_code = raw_source.upper()
        if source_code in masters["source"]:
            source = source_code
        else:
            failures.append(f"source_type {raw_source} is not a seeded source")
    attributes = []
    raw_attributes = _cell(row, "attributes")
    if raw_attributes:
        for token in (part for part in re.split(r"[\s,]+", raw_attributes) if part):
            code = masters["attribute"].get(token.casefold())
            if code is None:
                failures.append(f"attribute {token} is not a seeded attribute")
            else:
                attributes.append(code)
    color = None
    raw_color = _cell(row, "color")
    if raw_color:
        color = COLOR_ALIASES.get(raw_color.casefold()) or masters["color"].get(raw_color.upper())
        if color is None or color not in masters["color"]:
            failures.append(f"color {raw_color} is not a seeded color")
            color = None
    packaging = None
    raw_packaging = _cell(row, "packaging_type")
    if raw_packaging:
        packaging = masters["packaging"].get(raw_packaging.casefold())
        if packaging is None:
            failures.append(f"packaging_type {raw_packaging} is not a seeded packaging type")
    if _cell(row, "process_type") or _cell(row, "filler_type"):
        failures.append("process_type or filler_type is filled")
    raw_template = _cell(row, "material_template")
    if raw_template:
        template_polymer = masters["template"].get(raw_template)
        if template_polymer is None:
            failures.append(f"material_template {raw_template} is not a grade template code")
        elif polymer and template_polymer != polymer:
            failures.append(f"material_template {raw_template} polymer {template_polymer} disagrees with {polymer}")
    if failures:
        return None, "; ".join(failures)
    return (polymer, form, source, tuple(attributes), None, material_grade, color, packaging), None


def _read(path):
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return reader.fieldnames, list(reader)


def held_rows(ledger_rows, masters):
    held = []
    for row in ledger_rows:
        spec, reason = classify(row, masters)
        if spec is not None:
            continue
        copy = dict(row)
        copy["evidence"] = f"{row['evidence']} | {reason}"
        held.append(copy)
    return held


def test_ledger_partition_matches_specs_and_remaining_csv():
    normalizer = _load_normalizer()
    masters = _masters()
    header_line = LEDGER.read_text(encoding="utf-8").splitlines()[0]
    remaining_header = REMAINING.read_text(encoding="utf-8").splitlines()[0]
    assert remaining_header == header_line
    fieldnames, ledger_rows = _read(LEDGER)
    remaining_fields, remaining_rows = _read(REMAINING)
    assert list(remaining_fields) == list(fieldnames)
    expected = held_rows(ledger_rows, masters)
    assert remaining_rows == expected
    remaining_keys = {_cell(row, "match_key") for row in remaining_rows}
    applied = 0
    for row in ledger_rows:
        key = _cell(row, "match_key")
        spec, reason = classify(row, masters)
        if spec is None:
            assert reason
            assert key in remaining_keys
            continue
        applied += 1
        assert key not in remaining_keys
        polymer, form, source, attributes, grade, material_grade, color, packaging = spec
        assert normalizer._SPECS[key] == normalizer._spec(
            polymer=polymer,
            material_grade=material_grade,
            grade=grade,
            form=form,
            source=source,
            attributes=attributes,
            packaging_type=packaging,
            color=color,
        )
    assert applied == 17
    assert len(remaining_rows) == 20
