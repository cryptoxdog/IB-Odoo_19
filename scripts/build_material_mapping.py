#!/usr/bin/env python3
"""Build the single material mapping file for the ERP and VanillaSoft importers.

Every distinct material, form, type, and color value in the two sources gets one row
per field role. Every target is an existing ``plasticos_material_profile`` master
(polymer, form, source type, attribute, color, filler, process, packaging) read from the
module's seed XML. The polymers the operator approved on 2026-11-03 are seeded there.

Statuses:
    mapped             import rule
    not_material       not a material line; never a profile
    note_not_material  call-note text; kept as a note, never a profile
    ambiguous          names more than one polymer, or a generic label that fits several
    unknown            names no existing master

Precedence, first match wins: call notes, not-material lines, approved code phrases
(``material_normalizer.py`` plus the 2026-11-03 decisions), grade templates, the October 14
open statuses, then the text rule: a value that names exactly one polymer maps to it, with
form, source, color, attribute, filler, and process set only where an existing master is named.
VanillaSoft free text carrying contact details is left out; an unlisted value is unresolved.

Usage:
    python3 scripts/build_material_mapping.py --vanillasoft <export.csv> [--erp WKSDetail.csv] [--out <csv>]
"""

from __future__ import annotations

import argparse
import ast
import csv
import importlib.util
import re
import sys
import zipfile
from collections import defaultdict
from pathlib import Path

try:
    from defusedxml import ElementTree as ET
except ImportError:
    # Fallback: this script parses only the repository's own tracked seed XML
    # (plasticos_material_profile/data/*.xml), never untrusted input. Python 3.8+
    # stdlib etree refuses external-entity declarations by default.
    import xml.etree.ElementTree as ET  # nosemgrep: python.lang.security.use-defused-xml-parse.use-defused-xml-parse

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "plasticos_material_profile"
NORMALIZER = PROFILE / "models" / "material_normalizer.py"
PREVIOUS_MAP = ROOT / "plasticos_crm_sync" / "data" / "vanillasoft_material_mapping.csv"
DEFAULT_ERP = ROOT / "plasticos_partner_import" / "erp_extracted_data" / "bulk" / "WKSDetail.csv"
DEFAULT_OUT = PROFILE / "data" / "material_mapping.csv"
WEB_LEAD = ROOT / "plasticos_web_leads" / "models" / "web_lead.py"
XLSX = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
XLSX_REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"

COLUMNS = (
    "field_role",
    "match_key",
    "source_value",
    "sources",
    "erp_lines",
    "vanillasoft_contacts",
    "status",
    "rule",
    "polymer",
    "form",
    "source_type",
    "attributes",
    "grade",
    "grade_template",
    "color",
    "filler_type",
    "process_type",
    "packaging_type",
    "note",
)
STATUSES = {"mapped", "not_material", "note_not_material", "ambiguous", "unknown"}
ROLE_ORDER = {"material": 0, "form": 1, "type": 2, "color": 3}

# Operator decisions of 2026-11-03.
GRADE_A_FILM = ("LDPE", "FILM", None, ("clean", "dry"), "A")
DECIDED_SPECS = {
    "ldpe film a": GRADE_A_FILM,
    "ldpe a film": GRADE_A_FILM,
    "ldpe film - grade a": GRADE_A_FILM,
    "ldpe film grade a": GRADE_A_FILM,
    "99% clear ldpe film": GRADE_A_FILM,
}
DECIDED_CODES = {
    "tpu": ("TPU", None, None, (), None),
    "textile": ("TEXTILE", None, None, (), None),
    "pvb": ("PVB", None, None, (), None),
    "ubc": ("UBC", None, None, (), None),
    "tpv": ("TPV", None, None, (), None),
}
DECIDED_ALIASES = {
    "foam - pu": ("PU_FOAM", None, None, (), None),
    "mrp - grade a": ("MRP", None, None, (), None),
    "mrp-a": ("MRP", None, None, (), None),
    "mrp a": ("MRP", None, None, (), None),
    "mrp-b": ("MRP", None, None, (), None),
    "mrp a domestic quality": ("MRP", None, None, (), None),
    "wood pallets": ("WOOD_PALLETS", "PALLETS", None, ("reusable",), None),
    "wood pallets – reusable standard": ("WOOD_PALLETS", "PALLETS", None, ("reusable",), None),
    "wood pallets – reusable non-standard": ("WOOD_PALLETS", "PALLETS", None, ("reusable",), None),
    "super sacks": ("PP", None, None, (), None),
    "ibc totes (hmw)": ("HDPE_HMW", "TOTES", None, (), None),
    "hmw drums": ("HDPE_HMW", "DRUMS", None, (), None),
    "hmw": ("HDPE_HMW", None, None, (), None),
    "1-7 bottles": ("1_7_COMMINGLED_BOTTLES", "BOTTLES", "POST_CONSUMER", (), None),
    "co-mingled 1-7 all plastics": ("1_7_COMMINGLED_BOTTLES", "BOTTLES", "POST_CONSUMER", (), None),
    "1-7 mrp": ("1_7_COMMINGLED_BOTTLES", "BOTTLES", "POST_CONSUMER", (), None),
    "3-7 mixed plastic": ("3_7_COMMINGLED_BOTTLES", "BOTTLES", "POST_CONSUMER", (), None),
    "3-7 bottles": ("3_7_COMMINGLED_BOTTLES", "BOTTLES", "POST_CONSUMER", (), None),
    "mrp 3-7": ("3_7_COMMINGLED_BOTTLES", "BOTTLES", "POST_CONSUMER", (), None),
    "tubs": ("PP", "PARTS", None, (), None),
    "knock-down crates": ("HDPE", "CRATES", None, (), None),
    "drip tube": ("HDPE", None, None, (), None),
}
CONTACT_TEXT = re.compile(
    r"@|\d{3}[\s.)-]*\d{3}[\s.-]+\d{4}|\b(?:phone|fax|tel|cell|call|spoke to|spoke with|ext\.?\s*\d)\b"
)
CALL_SENTENCE = re.compile(
    r"\b(?:has|had|have|generates?|does|left a vm|probably|quoted?|interested|mentioned|sold|buys?|buying|"
    r"will|would|should|wants?|looking|sells?|gets?|getting|said|told)\b"
)
GENERIC_LABEL = "generic label; fits more than one polymer"
COMMINGLED = {"1_7_COMMINGLED_BOTTLES", "3_7_COMMINGLED_BOTTLES"}
PALLET_POLYMERS = {"PLASTIC_PALLETS", "WOOD_PALLETS"}
NOT_MATERIAL = tuple(
    re.compile(pattern)
    for pattern in (
        r"^gowns$",
        r"\bfreight\b",
        r"\bdumping fees?\b",
        r"^disposal fees?$",
        r"^trash\b",
        r"\bwater weight\b",
        r"\btare weight\b",
        r"^rejected material$",
        r"^miscellaneous$",
        r"^oversiized wood pallets-unusable$",
        r"^scrap wood$",
        r"^wood$",
        r"^wood, netal, lattice$",
        r"^disposal\b",
        r"^bad bales?$",
        r"^roofing shingles$",
        r"^fiber$",
        r"^engineering grades\b",
        r"^\d{4}-\d{2}-\d{2}( \d{2}:\d{2}:\d{2})?$",
    )
)
NEGATED_FIBERGLASS = (
    (re.compile(r"\bno metal\s*/\s*fiberglass\b"), "no metal"),
    (re.compile(r"\bno fiberglass\b"), " "),
    (re.compile(r"\bld/hd\b"), "ldpe"),
    (re.compile(r"-mcnon-struc\b"), " "),
    (re.compile(r"\bsemi-rigid\b"), "semirigid"),
    (re.compile(r"-mc(?=[a-z])"), " mc "),
)
CALL_NOTES = frozenset(
    {
        ".01 fob grade a mrp",
        "also mentioned they buy pp gf 25-50% - black has golf material. mention and request references.",
        "and occ -",
        "curb sorted no mrp - cb and pich for future -",
        "does marketing for 6 separate counties in maryland which generate mrp. got on bid list",
        "ext218 - pp sacks",
        "gas tanks and so on. pvc post industrial.",
        "generates eps",
        "generates pet",
        "had mrp and sacks. had loads of all.",
        "has 2 loads of ldpe film",
        "has ftl's of ldpe film from commercial dryer",
        "has mrp and everything else.",
        "has mrp and has c grade film",
        "has mrp b+",
        "has non-wove pp",
        "has pp sacks",
        "has pp super sacks with carbon black residue",
        "has some colored eps. sometimes has white eps he needs to sell.",
        "mentioned: pp super sacsk",
        "mrp looks like grade b",
        "pp bins and other grades. seems to be marketing direct with prices as high as .25 for film.",
        "pp super sack offered 0.06/lb. has 30k now",
        "quote on mrp. 0.05/lb and 0.12/lb",
        "should have other stuff. we sold him pvc",
        "should have tons of mrp",
        "they generate hdpe",
        "they mostly work with pet bottles.",
    }
)

# Text-rule vocabulary: existing master names plus the operator-approved spellings below.
POLYMER_WORDS = {
    "NYLON": ("nylon", "pa", "pa6", "pa66"),
    "PC_ABS": ("pc/abs", "pc-abs"),
    "3_7_COMMINGLED_BOTTLES": ("3-7",),
    "1_7_COMMINGLED_BOTTLES": ("1-7",),
    "PMMA": ("acrylic",),
    "POM": ("acetal",),
    "HDPE_HMW": ("hmw-hdpe", "hmwpe", "hmw"),
    "MRP": ("mixed rigid plastic", "mixed rigid plastics"),
    "PU_FOAM": ("pu foam", "foam - pu"),
    "PET": ("rpet",),
    "TEXTILE": ("textile",),
    "HDPE": ("hd", "pe"),
    "LDPE": ("ld",),
    "PP": ("super sacks", "super sack", "supersacs", "supersacks", "super sacs", "supersack"),
    "PVC": ("vinyl siding",),
    "AUTO_PARTS": ("auto parts",),
}
POLYMER_WORDS["HDPE_HMW"] = (*POLYMER_WORDS["HDPE_HMW"], "hdpe-hmw", "hd hmw", "hd/hmw", "ibc")
POLYMER_WORDS["MRP"] = (
    *POLYMER_WORDS["MRP"],
    "bulky rigid plastic",
    "bulky rigid plastics",
    "brp",
    "mixed plastic material",
)
COLOR_WORDS = {"MIXED": ("mc",), "GRAY": ("grey",)}
FORM_WORDS = {
    "PARTS": ("tubs & lids", "tubs and lids", "tubs"),
    "CRATES": ("knock-down crates", "knockdown bins", "knockdowns", "knockdown", "knock-down"),
}
NO_SUGGEST_POLYMERS = {"OTHER", "MIXED"}
NO_SUGGEST_ATTRIBUTES = {"mixed"}
NO_SUGGEST_FORMS = {"OTHER"}
HINT_DECISIONS = {
    "stacked": ("packaging_type", "palletized"),
    "stretch film (thin)": ("form", "FILM"),
    "blow mold": ("process_type", "blow_mold"),
    "roto mold": ("process_type", "rotomold"),
}
COLOR_DECISIONS = {"grey": ("GRAY", ""), "clear with print": ("CLEAR", "printed")}
PROCESS_WORDS = {"blow_mold": ("blow mold",), "rotomold": ("roto mold", "rotomold")}
ATTRIBUTE_WORDS = {
    "reusable": ("reuseable", "re-usable", "re-useable"),
    "with_metal": ("w/ metal", "w/metal", "w metal", "metal contamination"),
    "oily": ("oil contaminated",),
    "no_metal": ("metal removed", "all metal & wheels removed"),
    "no_print": ("unprinted", "non-printed", "non printed"),
    "pp_contaminated": ("w/ pp contamination", "with pp contamination", "pp contamination", "pp contaminated"),
    "pvc_contaminated": ("w/ pvc contamination", "with pvc contamination", "pvc contamination", "pvc contaminated"),
    "not_repairable": ("non-repairable", "non repairable", "unrepairable"),
    "rigid": ("rigids",),
    "frac_melt": ("frac-melt", "fractional melt"),
    "copolymer": ("co-polymer", "co polymer"),
    "homopolymer": ("homo-polymer", "homo polymer"),
    "non_woven": ("nonwoven", "non woven", "non-wove"),
}
FILLER_WORDS = {"talc": ("talc filler", "talc-filled")}
HINT_TARGETS = ("source_type", "form", "attributes", "filler_type", "process_type")
MASTER_OF = {
    "packaging_type": "packaging",
    "source_type": "source_type",
    "form": "form",
    "attributes": "attribute",
    "filler_type": "filler",
    "process_type": "process",
}

VS_PHRASE_FIELDS = ("Materials", "Materials (MRF's)")
VS_PREFIX_ROLES = (("material (", "material"), ("form (", "form"), ("type (", "type"), ("color (", "color"))
VS_EXACT_ROLES = {"material form": "form", "material type": "type"}


def collapse(value) -> str:
    return " ".join(str(value or "").split())


def key_of(value) -> str:
    return collapse(value).casefold()


def split_values(value) -> list[str]:
    """Mirror plasticos_crm_sync ``_split_material_values`` then the comma split."""
    text = str(value or "").replace("|", "\n").replace(";", "\n")
    parts = []
    for piece in text.splitlines():
        for item in piece.split(","):
            collapsed = collapse(item)
            if collapsed:
                parts.append(collapsed)
    return parts


def load_masters() -> dict[str, dict[str, str]]:
    masters: dict[str, dict[str, str]] = {}
    for name, filename in (
        ("polymer", "polymer_data.xml"),
        ("form", "material_form_data.xml"),
        ("source_type", "source_type_data.xml"),
        ("attribute", "material_attribute_data.xml"),
        ("color", "material_color_data.xml"),
        ("filler", "filler_type_data.xml"),
        ("packaging", "packaging_type_data.xml"),
    ):
        table: dict[str, str] = {}
        # Trusted input: repository-tracked seed XML only (defusedxml used when
        # installed). nosemgrep suppresses use-defused-xml-parse for this line.
        tree = ET.parse(PROFILE / "data" / filename)  # nosemgrep
        for record in tree.iter("record"):
            fields = {field.get("name"): collapse(field.text) for field in record.findall("field")}
            if fields.get("code"):
                table[fields["code"]] = fields.get("name") or fields["code"]
        masters[name] = table
    process_codes = _import_repo_module("plasticos_process_codes", PROFILE / "process_codes.py")
    masters["process"] = {code: process_codes.PROCESS_LABELS[code] for code in process_codes.PROCESS_CODES}
    return masters


def _import_repo_module(name: str, path: Path):
    """Import an Odoo-free module from this repository by file path."""
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_rules() -> dict[str, tuple[tuple, str]]:
    normalizer = _import_repo_module("plasticos_material_normalizer", NORMALIZER)
    rules: dict[str, tuple[tuple, str]] = {}
    for table, rule in (("_CRM_ALIASES", "approved_alias"), ("_CRM_EXACT", "crm_code"), ("_SPECS", "worksheet_phrase")):
        for key, spec in getattr(normalizer, table).items():
            rules[key] = (spec, rule)
    for key, spec in DECIDED_ALIASES.items():
        rules[key] = (spec, "approved_alias")
    for key, spec in DECIDED_CODES.items():
        rules[key] = (spec, "crm_code")
    for key, spec in DECIDED_SPECS.items():
        rules[key] = (spec, "worksheet_phrase")
    for key in CALL_NOTES:
        rules.pop(key, None)
    return rules


def load_previous() -> dict[str, dict[str, str]]:
    with PREVIOUS_MAP.open(newline="", encoding="utf-8") as handle:
        return {key_of(row["source_token"]): row for row in csv.DictReader(handle)}


def load_workbook(path: Path | None) -> dict[str, dict[str, str]]:
    """POLYMER MAPPING rows of the October 14 decision workbook, keyed by match key."""
    if path is None:
        return {}
    archive = zipfile.ZipFile(path)
    shared = []
    if "xl/sharedStrings.xml" in archive.namelist():
        root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
        shared = ["".join(t.text or "" for t in si.iter(XLSX + "t")) for si in root.findall(XLSX + "si")]
    book = ET.fromstring(archive.read("xl/workbook.xml"))
    rels = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    targets = {rel.get("Id"): rel.get("Target").lstrip("/").replace("xl/", "") for rel in rels}
    sheet = next(item for item in book.find(XLSX + "sheets") if item.get("name") == "POLYMER MAPPING")
    rows = []
    for row in ET.fromstring(archive.read("xl/" + targets[sheet.get(XLSX_REL)])).iter(XLSX + "row"):
        values = {}
        for cell in row.findall(XLSX + "c"):
            column = re.match(r"[A-Z]+", cell.get("r")).group()
            value = cell.find(XLSX + "v")
            if cell.get("t") == "inlineStr":
                values[column] = "".join(t.text or "" for t in cell.iter(XLSX + "t"))
            elif value is not None:
                values[column] = shared[int(value.text)] if cell.get("t") == "s" else value.text
        rows.append(values)
    header = rows.index(next(row for row in rows if row.get("B") == "VanillaSoft source token"))
    return {
        key_of(row["B"]): {"category": row.get("F", ""), "decision": row.get("J", ""), "proposed": row.get("G", "")}
        for row in rows[header + 1 :]
        if row.get("B")
    }


def load_grade_templates() -> dict[str, dict[str, str]]:
    """Seeded plasticos.grade.template names with their masters."""
    refs = {}
    for filename, _prefix, column in (
        ("polymer_data.xml", "polymer_", "polymer"),
        ("material_form_data.xml", "form_", "form"),
        ("source_type_data.xml", "source_", "source_type"),
        ("material_color_data.xml", "color_", "color"),
        ("packaging_type_data.xml", "packaging_", "packaging_type"),
    ):
        tree = ET.parse(PROFILE / "data" / filename)  # nosemgrep -- trusted repo-tracked seed XML
        for record in tree.iter("record"):
            code = next((collapse(f.text) for f in record.findall("field") if f.get("name") == "code"), "")
            refs[record.get("id")] = (column, code)
    templates = {}
    grade_tree = ET.parse(PROFILE / "data" / "grade_template_data.xml")  # nosemgrep -- trusted repo-tracked seed XML
    for record in grade_tree.iter("record"):
        row = {"attributes": []}
        for field in record.findall("field"):
            name = field.get("name")
            if field.get("ref") in refs:
                column, code = refs[field.get("ref")]
                row[column] = code
            elif name == "name":
                row["name"] = collapse(field.text)
            elif name == "code":
                row["grade_template"] = collapse(field.text)
            elif name == "is_clean" and collapse(field.text) == "True":
                row["attributes"].append("clean")
            elif name == "no_metal" and collapse(field.text) == "True":
                row["attributes"].append("no_metal")
        row["attributes"] = " ".join(row["attributes"])
        templates[key_of(row.pop("name"))] = row
    return templates


def load_web_lead_vocabulary() -> dict[str, tuple[str, str]]:
    """Form and source words the web-lead importer already maps."""
    tree = ast.parse(WEB_LEAD.read_text(encoding="utf-8"))
    constants = {}
    tables = {}
    for node in tree.body:
        target = node.targets[0] if isinstance(node, ast.Assign) else getattr(node, "target", None)
        if not isinstance(target, ast.Name) or node.value is None:
            continue
        if isinstance(node.value, ast.Constant):
            constants[target.id] = node.value.value
        if target.id in {"_FORM_NORMALIZE", "_SOURCE_NORMALIZE"} and isinstance(node.value, ast.Dict):
            tables[target.id] = {
                (constants[k.id] if isinstance(k, ast.Name) else k.value): v.value
                for k, v in zip(node.value.keys, node.value.values)
            }
    vocabulary = {}
    for word, code in tables["_FORM_NORMALIZE"].items():
        vocabulary[word] = ("form", code)
    for word, code in tables["_SOURCE_NORMALIZE"].items():
        vocabulary[word] = ("source_type", code.upper())
    return vocabulary


class Census:
    def __init__(self) -> None:
        self.values: dict[tuple[str, str], dict] = {}

    def add(self, role: str, value: str, source: str, contact: str | None = None) -> None:
        key = key_of(value)
        if not key:
            return
        entry = self.values.setdefault(
            (role, key), {"value": collapse(value), "sources": set(), "erp": 0, "contacts": set()}
        )
        entry["sources"].add(source)
        if contact is None:
            entry["erp"] += 1
        else:
            entry["contacts"].add(contact)


def read_erp(path: Path, census: Census) -> None:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            census.add("material", row.get("InvoiceDesc"), "erp:InvoiceDesc")


def vanillasoft_role(header: str) -> str | None:
    label = collapse(header).casefold()
    if header in VS_PHRASE_FIELDS or label in {"materials", "material"}:
        return "material"
    if label in VS_EXACT_ROLES:
        return VS_EXACT_ROLES[label]
    for prefix, role in VS_PREFIX_ROLES:
        if label.startswith(prefix):
            return role
    return None


def read_vanillasoft(path: Path, census: Census) -> None:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        for index, row in enumerate(csv.DictReader(handle)):
            contact = row.get("ContactID") or str(index)
            for header, value in row.items():
                role = vanillasoft_role(header or "")
                if not role:
                    continue
                for part in split_values(value):
                    census.add(role, part, f"vanillasoft:{collapse(header)}", contact)


def word_pattern(word: str) -> re.Pattern:
    return re.compile(r"(?<![a-z0-9])" + re.escape(word) + r"(?![a-z0-9])")


def vocabulary(masters, kind, extra=None, skip=(), codes=True):
    words = []
    for code, name in masters[kind].items():
        if code in skip:
            continue
        spellings = {name.casefold()}
        if codes:
            spellings |= {code.casefold(), code.casefold().replace("_", " ")}
        for word in spellings:
            words.append((word, code))
    for code, aliases in (extra or {}).items():
        if code in masters[kind] and code not in skip:
            words.extend((alias, code) for alias in aliases)
    return sorted({(word, code) for word, code in words if word}, key=lambda item: -len(item[0]))


def find_all(text: str, words) -> tuple[set[str], str]:
    found = set()
    for word, code in words:
        pattern = word_pattern(word)
        if pattern.search(text):
            found.add(code)
            text = pattern.sub(" ", text)
    return found, text


def shield(text: str, phrases) -> tuple[str, dict[str, str]]:
    """Hide polymer phrases that contain an attribute word, e.g. 'mixed rigid plastic'."""
    hidden = {}
    for phrase in phrases:
        pattern = word_pattern(phrase)
        if pattern.search(text):
            token = f"zzshield{len(hidden)}zz"
            hidden[token] = phrase
            text = pattern.sub(token, text)
    return text, hidden


def suggest_material(key: str, vocab) -> dict:
    for pattern, replacement in NEGATED_FIBERGLASS:
        key = pattern.sub(replacement, key)
    key, hidden = shield(key, vocab["shielded"])
    attributes, text = find_all(key, vocab["attribute"])
    for token, phrase in hidden.items():
        text = text.replace(token, phrase)
    colors, text = find_all(text, vocab["color"])
    polymers, text = find_all(text, vocab["polymer"])
    fillers, text = find_all(text, vocab["filler"])
    processes, text = find_all(text, vocab["process"])
    forms, text = find_all(text, vocab["form"])
    sources, _text = find_all(text.replace("-", " "), vocab["source"])
    return {
        "polymers": polymers,
        "forms": forms,
        "sources": sources,
        "attributes": attributes,
        "colors": colors,
        "fillers": fillers,
        "processes": processes,
    }


def hyphen_free(value: str) -> str:
    return " ".join(value.replace("-", " ").split())


def exact_master(key: str, table: dict[str, str]) -> str | None:
    wanted = hyphen_free(key)
    hits = {
        code
        for code, name in table.items()
        if wanted
        in {hyphen_free(code.casefold()), hyphen_free(code.casefold().replace("_", " ")), hyphen_free(name.casefold())}
    }
    return hits.pop() if len(hits) == 1 else None


def singular_plural(key: str, table: dict[str, str]) -> str | None:
    for variant in (key + "s", key[:-1] if key.endswith("s") else None):
        if variant:
            code = exact_master(variant, table)
            if code:
                return code
    return None


GRADE_A = re.compile(r"(?:\bgrade a|\bldpe a|\bfilm a|\ba film)(?![\w/+-])(?! minus)")
BALED = re.compile(r"\bbaled?\b|\bbales\b")


def drum_template(key, row):
    return row["polymer"] == "HDPE" and row["form"] == "DRUMS"


def ibc_template(key, row):
    return row["polymer"] == "HDPE_HMW" and row["form"] == "TOTES" and re.search(r"\bibc\b", key)


def ldpe_film_a_template(key, row):
    return row["polymer"] == "LDPE" and row["form"] in {"", "FILM"} and (row["grade"] == "A" or GRADE_A.search(key))


TEMPLATE_MATCH = (
    ("HDPE_DRUMS", drum_template),
    ("IBC_TOTES", ibc_template),
    ("LDPE_FILM_A", ldpe_film_a_template),
)


def apply_template(key: str, row: dict[str, str], templates) -> None:
    """Route a mapped material to its grade template; the template fills only empty columns."""
    if row["field_role"] != "material" or row["status"] != "mapped" or row["grade_template"]:
        return
    by_code = {template["grade_template"]: template for template in templates.values()}
    for code, matches in TEMPLATE_MATCH:
        if not matches(key, row):
            continue
        template = by_code[code]
        row["grade_template"] = code
        for column in ("form", "source_type", "color"):
            row[column] = row[column] or template.get(column, "")
        if not row["packaging_type"]:
            row["packaging_type"] = "bales" if BALED.search(key) else template.get("packaging_type", "")
        attributes = set(row["attributes"].split()) | set(template.get("attributes", "").split())
        row["attributes"] = " ".join(sorted(attributes))
        if code == "LDPE_FILM_A":
            row["grade"] = row["grade"] or "A"
        return


def spec_row(spec) -> dict[str, str]:
    polymer, form, source, attributes, grade = spec
    return {
        "polymer": polymer or "",
        "form": form or "",
        "source_type": source or "",
        "attributes": " ".join(attributes),
        "grade": grade or "",
    }


def classify_material(key, rules, previous, vocab, workbook, templates) -> dict[str, str]:
    book = workbook.get(key, {})
    if key in CALL_NOTES or book.get("category") == "IGNORED_TEXT":
        source = "2026-11-03 decision" if key in CALL_NOTES else "workbook IGNORED_TEXT"
        return {
            "status": "note_not_material",
            "rule": "call_note",
            "note": f"call-note text; kept as a note ({source})",
        }
    if any(pattern.search(key) for pattern in NOT_MATERIAL):
        return {"status": "not_material", "rule": "not_material", "note": "not a material (2026-11-03 decision)"}
    template = templates.get(key)
    if key in rules:
        spec, rule = rules[key]
        row = {"status": "mapped", "rule": rule, **spec_row(spec)}
        if template and template.get("polymer") == row["polymer"] and template.get("form", "") in {"", row["form"]}:
            row["packaging_type"] = template.get("packaging_type", "")
        return row
    if template:
        return {"status": "mapped", "rule": "grade_template", **template}
    old = previous.get(key)
    if old and old["status"] in {"pending_decision", "held"}:
        return {"status": "ambiguous", "rule": "", "note": old["note"] or GENERIC_LABEL}
    found = suggest_material(key, vocab)
    polymers = found["polymers"]
    if old and old["status"] == "no_master" and len(polymers) != 1:
        return {"status": "unknown", "rule": "", "note": old["note"]}
    detail = {
        "form": next(iter(found["forms"])) if len(found["forms"]) == 1 else "",
        "source_type": next(iter(found["sources"])) if len(found["sources"]) == 1 else "",
        "attributes": " ".join(sorted(found["attributes"])),
        "color": next(iter(found["colors"])) if len(found["colors"]) == 1 else "",
        "filler_type": next(iter(found["fillers"])) if len(found["fillers"]) == 1 else "",
        "process_type": next(iter(found["processes"])) if len(found["processes"]) == 1 else "",
    }
    if not polymers and re.search(r"\bpallets?\b", key):
        polymers = {"PLASTIC_PALLETS"}
    if not polymers and re.search(r"\btubs\b", key):
        polymers = {"PP"}
    if not polymers and re.search(r"\bknock-?downs?\b", key):
        polymers = {"HDPE"}
    if len(polymers) == 1:
        polymer = next(iter(polymers))
        if polymer in PALLET_POLYMERS:
            detail["form"] = "PALLETS"
        if polymer in COMMINGLED:
            detail["form"] = detail["form"] or "BOTTLES"
            detail["source_type"] = detail["source_type"] or "POST_CONSUMER"
        return {"status": "mapped", "rule": "names_one_polymer", "polymer": polymer, **detail}
    if len(polymers) > 1:
        return {"status": "ambiguous", "rule": "", "note": "names polymers " + " ".join(sorted(polymers))}
    return {"status": "unknown", "rule": "", "note": "names no polymer master"}


def classify_hint(key, rules, masters, web_words) -> dict[str, str]:
    """A form or type value. Both columns carry source, form, attribute, filler, and process words."""
    if any(pattern.search(key) for pattern in NOT_MATERIAL):
        return {"status": "not_material", "rule": "not_material", "note": "do not map (2026-11-03 decision)"}
    for column in HINT_TARGETS:
        code = exact_master(key, masters[MASTER_OF[column]])
        if code:
            return {"status": "mapped", "rule": f"{column}_master", column: code}
    for code, spellings in ATTRIBUTE_WORDS.items():
        if key in spellings:
            return {"status": "mapped", "rule": "attribute_spelling", "attributes": code}
    if key in HINT_DECISIONS:
        column, code = HINT_DECISIONS[key]
        return {"status": "mapped", "rule": "hint_decision", column: code}
    if key in rules:
        spec, _rule = rules[key]
        return {
            "status": "mapped",
            "rule": "material_phrase",
            **spec_row(spec),
            "note": "material phrase in a hint field",
        }
    if key in web_words:
        column, code = web_words[key]
        if code in masters[MASTER_OF[column]] and code != "OTHER":
            return {"status": "mapped", "rule": "web_lead_vocabulary", column: code}
    for column in ("form", "source_type"):
        code = singular_plural(key, masters[MASTER_OF[column]])
        if code:
            return {"status": "mapped", "rule": f"{column}_plural", column: code}
    return {"status": "unknown", "rule": "", "note": "matches no master; kept in profile notes"}


def classify_color(key, masters) -> dict[str, str]:
    code = exact_master(key, masters["color"])
    if code:
        return {"status": "mapped", "rule": "color_master", "color": code}
    if key in COLOR_DECISIONS:
        color, attribute = COLOR_DECISIONS[key]
        return {"status": "mapped", "rule": "color_decision", "color": color, "attributes": attribute}
    return {"status": "unknown", "rule": "", "note": "matches no color master"}


def build(erp: Path, vanillasoft: Path, workbook_path: Path | None) -> list[dict[str, str]]:
    masters = load_masters()
    rules = load_rules()
    previous = load_previous()
    workbook = load_workbook(workbook_path)
    templates = load_grade_templates()
    web_words = load_web_lead_vocabulary()
    vocab = {
        "polymer": vocabulary(masters, "polymer", POLYMER_WORDS, NO_SUGGEST_POLYMERS),
        "form": vocabulary(masters, "form", FORM_WORDS, skip=NO_SUGGEST_FORMS),
        "source": vocabulary(masters, "source_type"),
        "attribute": [
            item for item in vocabulary(masters, "attribute", ATTRIBUTE_WORDS) if item[1] not in NO_SUGGEST_ATTRIBUTES
        ],
        "color": vocabulary(masters, "color", COLOR_WORDS, codes=False),
        "filler": vocabulary(masters, "filler", FILLER_WORDS, skip={"other"}, codes=False),
        "process": vocabulary(masters, "process", PROCESS_WORDS, skip={"other"}),
    }
    vocab["shielded"] = [
        word
        for word, _code in vocab["polymer"]
        if any(word != spelling and word_pattern(spelling).search(word) for spelling, _ in vocab["attribute"])
    ]
    census = Census()
    read_erp(erp, census)
    read_vanillasoft(vanillasoft, census)
    for key in rules:
        census.values.setdefault(("material", key), {"value": key, "sources": {"code"}, "erp": 0, "contacts": set()})
    for key in templates:
        census.values.setdefault(
            ("material", key), {"value": key, "sources": {"grade_template"}, "erp": 0, "contacts": set()}
        )

    rows = []
    left_out = 0
    for (role, key), entry in census.values.items():
        vanillasoft_only = not entry["erp"] and entry["sources"] - {"code", "grade_template"}
        if vanillasoft_only and key not in rules and CONTACT_TEXT.search(key):
            left_out += 1
            continue
        if role == "material" and vanillasoft_only and key not in rules and CALL_SENTENCE.search(key):
            result = {"status": "note_not_material", "rule": "call_note", "note": "call-note text; kept as a note"}
        elif role == "material":
            result = classify_material(key, rules, previous, vocab, workbook, templates)
        elif role == "color":
            result = classify_color(key, masters)
        else:
            result = classify_hint(key, rules, masters, web_words)
        recorded = key in rules or key in previous or key in CALL_NOTES
        if vanillasoft_only and not recorded and result["status"] in {"note_not_material", "unknown"}:
            left_out += 1
            continue
        row = dict.fromkeys(COLUMNS, "")
        row.update(
            {
                "field_role": role,
                "match_key": key,
                "source_value": entry["value"],
                "sources": ";".join(sorted(entry["sources"])),
                "erp_lines": str(entry["erp"]),
                "vanillasoft_contacts": str(len(entry["contacts"])),
            }
        )
        row.update(result)
        apply_template(key, row, templates)
        rows.append(row)
    rows.sort(
        key=lambda row: (
            ROLE_ORDER[row["field_role"]],
            -(int(row["erp_lines"]) + int(row["vanillasoft_contacts"])),
            row["match_key"],
        )
    )
    check(rows, masters)
    print(f"left out {left_out} unresolved VanillaSoft free-text values")
    return rows


def check(rows, masters) -> None:
    seen = set()
    errors = []
    for row in rows:
        ident = (row["field_role"], row["match_key"])
        if ident in seen:
            errors.append(f"duplicate {ident}")
        seen.add(ident)
        for column, kind in (
            ("polymer", "polymer"),
            ("form", "form"),
            ("source_type", "source_type"),
            ("color", "color"),
            ("filler_type", "filler"),
            ("process_type", "process"),
            ("packaging_type", "packaging"),
        ):
            if row[column] and row[column] not in masters[kind]:
                errors.append(f"{ident}: {column} {row[column]} is not a master")
        for code in row["attributes"].split():
            if code not in masters["attribute"]:
                errors.append(f"{ident}: attribute {code} is not a master")
        if row["status"] == "mapped" and row["field_role"] == "material" and not row["polymer"]:
            errors.append(f"{ident}: mapped material without polymer")
        if row["status"] not in STATUSES:
            errors.append(f"{ident}: status {row['status']}")
    if errors:
        raise SystemExit("\n".join(errors))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--vanillasoft", required=True, type=Path)
    parser.add_argument("--erp", default=DEFAULT_ERP, type=Path)
    parser.add_argument("--workbook", type=Path, help="October 14 polymer mapping decisions workbook")
    parser.add_argument("--out", default=DEFAULT_OUT, type=Path)
    args = parser.parse_args()
    rows = build(args.erp, args.vanillasoft, args.workbook)
    with args.out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    counts = defaultdict(int)
    for row in rows:
        counts[(row["field_role"], row["status"])] += 1
    for (role, status), count in sorted(counts.items(), key=lambda item: (ROLE_ORDER[item[0][0]], item[0][1])):
        print(f"{role:9} {status:18} {count}")
    print(f"rows {len(rows)} -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
