"""
Repo-wide phantom enum value detector for cryptoxdog/IB-Odoo_19.

Builds two registries of truth:
  1. Selection field options  — extracted from fields.Selection([...])
                                in every plasticos_* Python model file
  2. XML seed data values     — extracted from <field name="name">...</field>
                                and <field name="code">...</field> in every
                                data/*.xml across plasticos_* modules

Then scans all Python source files for string literals used in contexts
that imply enum comparison (==, !=, in [...], domain tuples, dict gates)
and flags any value NOT found in either registry.

Run:
    pytest tests/test_phantom_enum_values.py -v
    pytest tests/test_phantom_enum_values.py -k "TestSelectionComparisons" -v
    pytest tests/test_phantom_enum_values.py -v --tb=long   # see full diffs

Zero Odoo runtime. Pure AST + XML parsing.
"""

import ast
import os
import re
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path
from typing import NamedTuple

import pytest

# ═════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═════════════════════════════════════════════════════════════════════════

# String literals in these sets are NEVER considered enum references.
# Infrastructure noise: Odoo internals, Python builtins, generic tokens.
GLOBAL_ALLOWLIST = frozenset(
    {
        # Odoo framework strings
        "tree",
        "form",
        "kanban",
        "pivot",
        "graph",
        "list",
        "search",
        "ir.actions.act_window",
        "ir.ui.view",
        "ir.model.access",
        "manual",
        "auto",
        "True",
        "False",
        "true",
        "false",
        "utf-8",
        "utf8",
        "ascii",
        "rb",
        "wb",
        "r",
        "w",
        # Common Odoo states (these vary per model, but the framework
        # defaults are allowed globally)
        "draft",
        "confirmed",
        "done",
        "cancel",
        "sent",
        "open",
        "closed",
        "paid",
        "posted",
        # Odoo move types (account.move)
        "entry",
        "out_invoice",
        "out_refund",
        "in_invoice",
        "in_refund",
        "out_receipt",
        "in_receipt",
        # Odoo journal types
        "sale",
        "purchase",
        "cash",
        "bank",
        "general",
        # Odoo partner types
        "contact",
        "invoice",
        "delivery",
        "private",
        "other",
        # Common state values
        "new",
        "pending",
        "approved",
        "rejected",
        "expired",
        "active",
        "inactive",
        "archived",
        # Python / logging / misc
        "",
        ".",
        ",",
        ":",
        ";",
        "/",
        "-",
        "_",
        " ",
        "none",
        "None",
        "null",
        "N/A",
        "n/a",
        "yes",
        "no",
        "on",
        "off",
        # ORM verbs
        "create",
        "write",
        "unlink",
        "read",
        "=",
        "!=",
        "<",
        ">",
        "<=",
        ">=",
        "like",
        "ilike",
        "in",
        "not in",
        "=like",
        "=ilike",
        "child_of",
        "parent_of",
        # Field types
        "char",
        "text",
        "integer",
        "float",
        "boolean",
        "many2one",
        "one2many",
        "many2many",
        "selection",
        "date",
        "datetime",
        "binary",
        "html",
        "monetary",
        # Module-level noise
        "__manifest__",
        "__init__",
        # Common non-enum comparison targets
        "company",
        "person",
        # ─────────────────────────────────────────────────────────────────────
        # ODOO MANIFEST KEYS — standard __manifest__.py dict keys
        # ─────────────────────────────────────────────────────────────────────
        "name",
        "version",
        "summary",
        "description",
        "author",
        "website",
        "license",
        "category",
        "depends",
        "data",
        "demo",
        "assets",
        "installable",
        "application",
        "auto_install",
        "external_dependencies",
        "pre_init_hook",
        "post_init_hook",
        "uninstall_hook",
        "post_load",
        # ─────────────────────────────────────────────────────────────────────
        # ODOO ACTION RETURN DICT KEYS — ir.actions.act_window patterns
        # ─────────────────────────────────────────────────────────────────────
        "type",
        "res_model",
        "res_id",
        "view_mode",
        "view_id",
        "views",
        "target",
        "domain",
        "context",
        "flags",
        "search_view_id",
        "view_type",
        "limit",
        "binding_model_id",
        "binding_type",
        # ─────────────────────────────────────────────────────────────────────
        # ODOO NOTIFICATION / CLIENT ACTION KEYS
        # ─────────────────────────────────────────────────────────────────────
        "title",
        "message",
        "sticky",
        "next",
        "tag",
        "params",
        "effect",
        "fadeout",
        "buttons",
        # ─────────────────────────────────────────────────────────────────────
        # ODOO ORM CONTEXT / WIZARD KEYS
        # ─────────────────────────────────────────────────────────────────────
        "default_model",
        "default_res_id",
        "default_res_ids",
        "default_template_id",
        "default_composition_mode",
        "mark_so_as_sent",
        "force_email",
        "active_id",
        "active_ids",
        "active_model",
        "default_type",
        "default_state",
        # ─────────────────────────────────────────────────────────────────────
        # ODOO MAIL / MESSAGING KEYS
        # ─────────────────────────────────────────────────────────────────────
        "composition_mode",
        "template_id",
        "email_from",
        "partner_ids",
        "attachment_ids",
        "body",
        "subject",
        "model",
        "res_ids",
        # ─────────────────────────────────────────────────────────────────────
        # COMMON RECORD DICT KEYS (create/write vals)
        # ─────────────────────────────────────────────────────────────────────
        "state",
        "partner_id",
        "company_id",
        "user_id",
        "currency_id",
        "product_id",
        "quantity",
        "price_unit",
        "account_id",
        "move_type",
        "invoice_line_ids",
        "line_ids",
        "order_line",
        "date_order",
        "date_invoice",
        "amount",
        "total",
        "code",
        "sequence",
        "parent_id",
        "child_ids",
        # ─────────────────────────────────────────────────────────────────────
        # ACCOUNTING / JOURNAL KEYS
        # ─────────────────────────────────────────────────────────────────────
        "account_type",
        "reconcile",
        "journal_id",
        "debit",
        "credit",
        # ─────────────────────────────────────────────────────────────────────
        # COMMON RESULT/RETURN DICT KEYS
        # ─────────────────────────────────────────────────────────────────────
        "success",
        "error",
        "result",
        "status",
        "count",
        "created",
        "updated",
        "skipped",
        "failed",
        "warnings",
        "errors",
        "module",
        "record",
        "records",
        "ids",
        "values",
        # ─────────────────────────────────────────────────────────────────────
        # COMMON ODOO FIELD NAMES (used in create/write vals dicts)
        # ─────────────────────────────────────────────────────────────────────
        "ref",
        "street",
        "street2",
        "city",
        "state_id",
        "zip",
        "country_id",
        "phone",
        "mobile",
        "fax",
        "email",
        "vat",
        "comment",
        "company_type",
        "is_company",
        "customer_rank",
        "supplier_rank",
        "image",
        "image_1920",
        "image_128",
        "color",
        "priority",
        "login",
        "password",
        "group_ids",
        "groups_id",
        "default_code",
        "barcode",
        "list_price",
        "standard_price",
        "categ_id",
        "uom_id",
        "uom_po_id",
        "sale_ok",
        "purchase_ok",
        "invoice_date",
        "date_due",
        "payment_term_id",
        "fiscal_position_id",
        "pricelist_id",
        "warehouse_id",
        "location_id",
        "picking_type_id",
        # ─────────────────────────────────────────────────────────────────────
        # PLASTICOS-SPECIFIC COMMON FIELD NAMES
        # ─────────────────────────────────────────────────────────────────────
        "polymer_id",
        "is_polymer_product",
        "material_profile_id",
        "facility_id",
        "intake_id",
        "transaction_id",
        "offer_id",
        "buyer_id",
        "seller_id",
        "carrier_id",
        "lane_key",
        "rate_amount",
        "rate_date",
        "freight_cost",
        "commission_amount",
        "sell_amount",
        "buy_amount",
        "margin",
        "margin_percent",
        "lead_id",
        "lead_source",
        "source",
        "decision",
        "raw_payload",
        "company_name",
        "contact_name",
        "source_types",
        "legacy_external_id",
        "customer_name",
        "product_code",
        # ─────────────────────────────────────────────────────────────────────
        # IMPORT/SYNC RESULT KEYS
        # ─────────────────────────────────────────────────────────────────────
        "corporates",
        "facilities",
        "contacts",
        "corporates_created",
        "corporates_updated",
        "facilities_created",
        "facilities_updated",
        "contacts_created",
        "contacts_updated",
        "imported",
        "processed",
        "batch",
        "batches",
        # ─────────────────────────────────────────────────────────────────────
        # AUDIT/CHANGELOG DICT KEYS
        # ─────────────────────────────────────────────────────────────────────
        "old",
        "reason",
        "user",
        "changes",
        "mode",
        "tags",
        "xmlid",
        "partner",
        "parent",
        "id",
        # ─────────────────────────────────────────────────────────────────────
        # MATERIAL PROFILE DICT KEYS
        # ─────────────────────────────────────────────────────────────────────
        "density",
        "moisture",
        "has_metal",
        "is_metalized",
        "fr",
        "avg_lot",
        "frequency",
        "type_name",
        "pct",
        "volume",
        # ─────────────────────────────────────────────────────────────────────
        # NULL/EMPTY MARKERS
        # ─────────────────────────────────────────────────────────────────────
        "NULL",
        "FALSE",
        "(none)",
        "NA",
        "na",
        "empty",
        "blank",
        "missing",
        "undefined",
        # ─────────────────────────────────────────────────────────────────────
        # COMMON COMPARISON VALUES
        # ─────────────────────────────────────────────────────────────────────
        "New",
        "Location",
        "Company",
        "Person",
        "Contact",
        "corporate",
        # ─────────────────────────────────────────────────────────────────────
        # INFERENCE ENGINE / RULE ENGINE VALUES
        # ─────────────────────────────────────────────────────────────────────
        "property",
        "qualityassessment",
        "processingrequirement",
        "contaminationassessment",
        "backward",
        "forward",
        # Process types (inference engine)
        "injection",
        "blow molding",
        "extrusion",
        "film blown",
        "pipe extrusion",
        "rotomolding",
        "fiber",
        "raffia",
        "wire and cable",
        "pipe",
        "sheet",
        "thermoforming",
        # ─────────────────────────────────────────────────────────────────────
        # MATERIAL PROFILE DISPLAY DICT KEYS
        # ─────────────────────────────────────────────────────────────────────
        "polymer_name",
        "form_name",
        "color_name",
        "attributes",
        "sector",
        "process_type",
        # ─────────────────────────────────────────────────────────────────────
        # MODULE NAMES (used in domain[module] comparisons)
        # ─────────────────────────────────────────────────────────────────────
        "plasticos_import",
        "plasticos_partner_import",
        "plasticos_transaction",
        "plasticos_base",
        # ─────────────────────────────────────────────────────────────────────
        # GRAPH ENGINE / INTELLIGENCE DICT KEYS
        # ─────────────────────────────────────────────────────────────────────
        "lat",
        "lon",
        "latitude",
        "longitude",
        "geo",
        "distance",
        "event",
        "payload",
        "event_id",
        "timestamp",
        "match_request_id",
        "latency_ms",
        "results",
        "final",
        "structural",
        "similarity",
        "reinforcement",
        "confidence",
        "intake",
        "score",
        "components",
        "tight_supply",
        "loose_supply",
        "balanced",
        # ─────────────────────────────────────────────────────────────────────
        # WEB LEADS SYNONYM MAPPINGS (normalize external input)
        # These are intentionally NOT in the registry — they're input synonyms
        # that get normalized to canonical values
        # ─────────────────────────────────────────────────────────────────────
        "acetal",
        "baled",
        "flakes",
        "lump",
        "lumps",
        "re-useable",
        "reuseable",
        "bottle",
        "rolls",
        "ocean",
        "ongoing",
        "one-time",
        "unclear",
        # ─────────────────────────────────────────────────────────────────────
        # ENRICHMENT SERVICE FORM SYNONYMS (normalize external input)
        # ─────────────────────────────────────────────────────────────────────
        "bags",
        "films",
        "flaked",
        "gaylord",
        "pallet",
        "patties",
        "pelletized",
        "purgings",
        "regrinds",
        "reground",
        "reprocessed",
        "sheets",
        "shredded",
        "sweepings",
        # ─────────────────────────────────────────────────────────────────────
        # ENRICHMENT SERVICE FEEDSTOCK SYNONYMS
        # ─────────────────────────────────────────────────────────────────────
        "contaminated",
        "off grade",
        "offgrade",
        "post consumer",
        "post industrial",
        "postconsumer",
        "postindustrial",
        "source_type",
        # ─────────────────────────────────────────────────────────────────────
        # NEGOTIATION ENGINE DICT KEYS
        # ─────────────────────────────────────────────────────────────────────
        "round",
        "settlement",
        "acceptance",
        "volatile",
        "iso",
        # ─────────────────────────────────────────────────────────────────────
        # ENRICHMENT SERVICE PROCESS SYNONYMS
        # ─────────────────────────────────────────────────────────────────────
        "injection moulding",
        "extruded",
        "blow moulding",
        "blow mold",
        "thermoformed",
        "blown film",
        "cast film",
        "compounded",
        # ─────────────────────────────────────────────────────────────────────
        # LLM/API DICT KEYS
        # ─────────────────────────────────────────────────────────────────────
        "response_format",
        "messages",
        "temperature",
        "prompt",
        "max_tokens",
        "stop",
        "stream",
        # ─────────────────────────────────────────────────────────────────────
        # DEV TOOLS DICT KEYS
        # ─────────────────────────────────────────────────────────────────────
        "__main__",
        "latency",
        "uptime",
        "anomaly",
        "reference_model",
        "reference_id",
        "actor",
        "dbname",
        "level",
        "path",
        "func",
        "line",
        "orders",
        "payments",
        "models",
        "crons",
        "custom_fields",
        # ─────────────────────────────────────────────────────────────────────
        # GRAPH SERVICE / NEO4J DICT KEYS
        # ─────────────────────────────────────────────────────────────────────
        "hard_gate",
        "history",
        "OPEN",
        "CLOSED",
        # ─────────────────────────────────────────────────────────────────────
        # ODOO STOCK/INVENTORY VALUES
        # ─────────────────────────────────────────────────────────────────────
        "outgoing",
        "incoming",
        "internal",
        "product",
        "consu",
        "service",
        # ─────────────────────────────────────────────────────────────────────
        # EMPTY/PLACEHOLDER VALUES
        # ─────────────────────────────────────────────────────────────────────
        "{}",
        "[]",
        "()",
    }
)

# Minimum length for a string to be considered an enum candidate.
# Single-character strings are almost never enum values.
MIN_ENUM_LENGTH = 2

# Maximum length — avoids treating error messages / SQL / Cypher as enums.
MAX_ENUM_LENGTH = 40

# Fields whose values are NEVER enums (technical fields).
SKIP_FIELDS = frozenset(
    {
        "_name",
        "_inherit",
        "_description",
        "_order",
        "_table",
        "_rec_name",
        "_rec_names_search",
        "_parent_name",
        "string",
        "help",
        "groups",
        "domain",
        "context",
        "comodel_name",
        "inverse_name",
        "relation",
        "column1",
        "column2",
        "ondelete",
        "tracking",
        "index",
        "required",
        "readonly",
        "copy",
        "default",
        "store",
        "compute",
        "password",
        "email",
        "phone",
        "url",
        "name",
    }
)


# ═════════════════════════════════════════════════════════════════════════
# REPO ROOT
# ═════════════════════════════════════════════════════════════════════════


def _find_repo_root():
    candidate = Path(__file__).resolve().parent
    for _ in range(10):
        if (candidate / "plasticos_base").is_dir():
            return candidate
        candidate = candidate.parent
    raise RuntimeError("Cannot locate repo root (plasticos_base/ not found)")


REPO_ROOT = _find_repo_root()


# ═════════════════════════════════════════════════════════════════════════
# DATA STRUCTURES
# ═════════════════════════════════════════════════════════════════════════


class EnumSource(NamedTuple):
    """Where a canonical enum value was defined."""

    value: str
    source_file: str
    source_type: str  # "selection" | "xml_name" | "xml_code" | "xml_id"


class EnumUsage(NamedTuple):
    """Where a string literal was used as an apparent enum value."""

    value: str
    file: str
    line: int
    context: str  # "comparison" | "domain" | "dict_key" | "in_list"


# ═════════════════════════════════════════════════════════════════════════
# REGISTRY BUILDER 1: Selection fields from Python
# ═════════════════════════════════════════════════════════════════════════


def _extract_selection_options_from_source(src: str, filepath: str):
    """Parse Python source, find fields.Selection([...]) calls,
    extract (key, label) tuples. Returns {field_name: set(keys)}."""

    field_options: dict[str, set[str]] = defaultdict(set)
    all_options: set[str] = set()
    sources: list[EnumSource] = []

    # Pattern: field_name = fields.Selection([(key, label), ...], ...)
    # We use AST for reliable extraction.
    try:
        tree = ast.parse(src, filename=filepath)
    except SyntaxError:
        return field_options, all_options, sources

    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name):
            continue
        field_name = target.id

        # Check if RHS is fields.Selection(...)
        call = node.value
        if not isinstance(call, ast.Call):
            continue
        func = call.func
        if not (isinstance(func, ast.Attribute) and func.attr == "Selection"):
            continue

        # First positional arg should be a list of tuples
        if not call.args:
            continue
        selection_list = call.args[0]
        if not isinstance(selection_list, ast.List):
            continue

        for elt in selection_list.elts:
            if isinstance(elt, ast.Tuple) and len(elt.elts) >= 2:
                key_node = elt.elts[0]
                if isinstance(key_node, ast.Constant) and isinstance(key_node.value, str):
                    key = key_node.value
                    field_options[field_name].add(key)
                    all_options.add(key)
                    sources.append(
                        EnumSource(
                            value=key,
                            source_file=filepath,
                            source_type="selection",
                        )
                    )

    return field_options, all_options, sources


# ═════════════════════════════════════════════════════════════════════════
# REGISTRY BUILDER 2: XML data records
# ═════════════════════════════════════════════════════════════════════════


def _extract_xml_enum_values(xml_path: str):
    """Parse an Odoo data XML file. Extract:
    - <field name="name">VALUE</field>
    - <field name="code">VALUE</field>
    - record id attributes (as external ID keys)
    Returns (set_of_names, set_of_codes, set_of_external_ids, sources)."""

    names: set[str] = set()
    codes: set[str] = set()
    ext_ids: set[str] = set()
    sources: list[EnumSource] = []

    try:
        tree = ET.parse(xml_path)
    except ET.ParseError:
        return names, codes, ext_ids, sources

    root = tree.getroot()
    rel_path = str(Path(xml_path).relative_to(REPO_ROOT))

    for record in root.iter("record"):
        record_id = record.get("id", "")
        if record_id:
            ext_ids.add(record_id)

        for field in record.findall("field"):
            fname = field.get("name", "")
            text = (field.text or "").strip()
            if not text:
                continue

            if fname == "name":
                names.add(text)
                sources.append(EnumSource(text, rel_path, "xml_name"))
            elif fname == "code":
                codes.add(text)
                sources.append(EnumSource(text, rel_path, "xml_code"))

    return names, codes, ext_ids, sources


# ═════════════════════════════════════════════════════════════════════════
# SCANNER: Find string literals used as enum values in Python
# ═════════════════════════════════════════════════════════════════════════


class _EnumUsageVisitor(ast.NodeVisitor):
    """AST visitor that finds string literals used in enum-like contexts:
    1. rec.field == "value"  /  rec.field != "value"
    2. "value" in [list]     /  field in ("a", "b", "c")
    3. ('field', '=', 'value')  — Odoo domain tuples
    4. state-dict keys: {"draft": ..., "done": ...}
    """

    def __init__(self, filepath):
        self.filepath = filepath
        self.usages: list[EnumUsage] = []
        self._selection_field_names: set[str] = set()

    def _record(self, value, lineno, context):
        if not isinstance(value, str):
            return
        if len(value) < MIN_ENUM_LENGTH or len(value) > MAX_ENUM_LENGTH:
            return
        if value in GLOBAL_ALLOWLIST:
            return
        if value in SKIP_FIELDS:
            return
        # Skip if it looks like a path, URL, or sentence
        if "/" in value and len(value) > 10:
            return
        if " " in value and value.count(" ") > 3:
            return
        if value.startswith("http"):
            return
        # Skip field-name-shaped strings (contain only lower + underscore)
        if re.match(r"^[a-z][a-z0-9_.]+$", value) and "." in value:
            return

        self.usages.append(
            EnumUsage(
                value=value,
                file=self.filepath,
                line=lineno,
                context=context,
            )
        )

    def visit_Compare(self, node):
        """Catch: expr == "value", expr != "value", expr in ["a","b"]."""
        for op, comparator in zip(node.ops, node.comparators):
            if isinstance(op, ast.Eq | ast.NotEq):
                if isinstance(comparator, ast.Constant) and isinstance(comparator.value, str):
                    self._record(comparator.value, node.lineno, "comparison")
                # Also catch "value" == expr
                if isinstance(node.left, ast.Constant) and isinstance(node.left.value, str):
                    self._record(node.left.value, node.lineno, "comparison")

            elif isinstance(op, ast.In):
                # expr in ("a", "b", "c") or expr in ["a", "b"]
                if isinstance(comparator, ast.Tuple | ast.List | ast.Set):
                    for elt in comparator.elts:
                        if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                            self._record(elt.value, node.lineno, "in_list")

        self.generic_visit(node)

    def visit_Tuple(self, node):
        """Catch Odoo domain tuples: ('field', '=', 'value')."""
        if len(node.elts) == 3:
            field_node, op_node, val_node = node.elts
            if (
                isinstance(field_node, ast.Constant)
                and isinstance(field_node.value, str)
                and isinstance(op_node, ast.Constant)
                and isinstance(op_node.value, str)
                and op_node.value in ("=", "!=", "in", "not in", "like", "ilike", "=like", "=ilike")
            ):
                if isinstance(val_node, ast.Constant) and isinstance(val_node.value, str):
                    field_name = field_node.value
                    if field_name not in SKIP_FIELDS:
                        self._record(val_node.value, node.lineno, f"domain[{field_name}]")
                elif isinstance(val_node, ast.Tuple | ast.List):
                    field_name = field_node.value
                    for elt in val_node.elts:
                        if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                            if field_name not in SKIP_FIELDS:
                                self._record(elt.value, node.lineno, f"domain[{field_name}]")

        self.generic_visit(node)

    def visit_Subscript(self, node):
        """Catch dict-key access with string literals on known state dicts."""
        self.generic_visit(node)

    def visit_Dict(self, node):
        """Catch state-mapping dicts where ALL keys are short strings
        that look like enum values (heuristic for enum dispatch tables).

        SKIP dicts that look like:
        - ORM create/write vals (keys are field names with underscores)
        - Action return dicts (type, res_model, etc.)
        - Result/stats dicts (created, updated, etc.)
        """
        if not node.keys:
            self.generic_visit(node)
            return

        str_keys = []
        for k in node.keys:
            if isinstance(k, ast.Constant) and isinstance(k.value, str):
                str_keys.append(k.value)

        # Only flag if dict has 3+ string keys AND all keys are short
        if not (len(str_keys) >= 3 and len(str_keys) == len(node.keys) and all(len(k) <= 25 for k in str_keys)):
            self.generic_visit(node)
            return

        # HEURISTIC: Skip if keys look like field names (contain underscore)
        # Field name dicts: {'partner_id': x, 'company_id': y, ...}
        underscore_keys = sum(1 for k in str_keys if "_" in k)
        if underscore_keys >= len(str_keys) * 0.5:
            # More than half have underscores = probably field names
            self.generic_visit(node)
            return

        # HEURISTIC: Skip if keys are in GLOBAL_ALLOWLIST
        # (already filtered in _record, but skip entire dict if mostly allowed)
        allowed_keys = sum(1 for k in str_keys if k in GLOBAL_ALLOWLIST)
        if allowed_keys >= len(str_keys) * 0.5:
            self.generic_visit(node)
            return

        # Only record keys that aren't already allowed
        for k in str_keys:
            self._record(k, node.lineno, "dict_dispatch_key")

        self.generic_visit(node)


def _scan_python_for_enum_usage(src: str, filepath: str) -> list[EnumUsage]:
    """Scan a Python source file for string literals used as enum values."""
    try:
        tree = ast.parse(src, filename=filepath)
    except SyntaxError:
        return []
    visitor = _EnumUsageVisitor(filepath)
    visitor.visit(tree)
    return visitor.usages


# ═════════════════════════════════════════════════════════════════════════
# MODULE DISCOVERY
# ═════════════════════════════════════════════════════════════════════════


def _discover_plasticos_modules():
    """Return sorted list of plasticos_* module directory names."""
    return sorted(
        entry
        for entry in os.listdir(REPO_ROOT)
        if entry.startswith("plasticos_")
        and os.path.isdir(REPO_ROOT / entry)
        and (REPO_ROOT / entry / "__manifest__.py").is_file()
    )


def _iter_python_files(module_dir: Path):
    """Yield (relative_path, contents) for all .py files in a module.
    Skips docs/ and any directory named docs."""
    for dirpath, _, filenames in os.walk(module_dir):
        if "docs" in Path(dirpath).parts:
            continue
        for fname in sorted(filenames):
            if fname.endswith(".py") and fname != "__pycache__":
                full = Path(dirpath) / fname
                rel = full.relative_to(REPO_ROOT)
                with open(full, encoding="utf-8", errors="replace") as fh:
                    yield str(rel), fh.read()


def _iter_xml_data_files(module_dir: Path):
    """Yield absolute paths to XML files in data/ and demo/ directories."""
    for subdir in ("data", "demo"):
        data_dir = module_dir / subdir
        if not data_dir.is_dir():
            continue
        for fname in sorted(os.listdir(data_dir)):
            if fname.endswith(".xml"):
                yield str(data_dir / fname)


# ═════════════════════════════════════════════════════════════════════════
# BUILD GLOBAL REGISTRIES (run once at module load time)
# ═════════════════════════════════════════════════════════════════════════


def _build_registries():
    """Build the complete enum registry from all plasticos_* modules.

    Returns:
        selection_by_field: {field_name: set(valid_keys)}
        all_selection_keys: set of every Selection key
        xml_names: set of every <field name="name"> value
        xml_codes: set of every <field name="code"> value
        xml_ext_ids: set of every record id= attribute
        all_canonical: union of all above
        all_sources: list[EnumSource]
    """
    modules = _discover_plasticos_modules()

    selection_by_field = defaultdict(set)
    all_selection_keys = set()
    xml_names = set()
    xml_codes = set()
    xml_ext_ids = set()
    all_sources = []

    for mod in modules:
        mod_path = REPO_ROOT / mod

        # ── Python Selection fields ──
        for rel_path, src in _iter_python_files(mod_path):
            field_opts, opts, sources = _extract_selection_options_from_source(src, rel_path)
            for field_name, keys in field_opts.items():
                selection_by_field[field_name].update(keys)
            all_selection_keys.update(opts)
            all_sources.extend(sources)

        # ── XML data records ──
        for xml_path in _iter_xml_data_files(mod_path):
            names, codes, ext_ids, sources = _extract_xml_enum_values(xml_path)
            xml_names.update(names)
            xml_codes.update(codes)
            xml_ext_ids.update(ext_ids)
            all_sources.extend(sources)

    all_canonical = all_selection_keys | xml_names | xml_codes
    # Also add lowercased variants (code might compare case-insensitively)
    all_canonical_lower = {v.lower() for v in all_canonical}

    return (
        selection_by_field,
        all_selection_keys,
        xml_names,
        xml_codes,
        xml_ext_ids,
        all_canonical,
        all_canonical_lower,
        all_sources,
    )


(
    SELECTION_BY_FIELD,
    ALL_SELECTION_KEYS,
    XML_NAMES,
    XML_CODES,
    XML_EXT_IDS,
    ALL_CANONICAL,
    ALL_CANONICAL_LOWER,
    ALL_SOURCES,
) = _build_registries()


def _build_all_usages():
    """Scan every Python file in every plasticos_* module for enum usage.

    Skips test files (tests/) since test fixtures contain synthetic data
    that isn't meant to be in the enum registry.
    """
    modules = _discover_plasticos_modules()
    usages = []
    for mod in modules:
        mod_path = REPO_ROOT / mod
        for rel_path, src in _iter_python_files(mod_path):
            # Skip test files — they contain synthetic test data
            if "/tests/" in rel_path or "\\tests\\" in rel_path:
                continue
            usages.extend(_scan_python_for_enum_usage(src, rel_path))
    return usages


ALL_USAGES = _build_all_usages()


def _is_phantom(value: str) -> bool:
    """Return True if `value` appears in code but NOT in any registry."""
    if value in ALL_CANONICAL:
        return False
    if value.lower() in ALL_CANONICAL_LOWER:
        return False
    return True


# ═════════════════════════════════════════════════════════════════════════
# FIXTURES
# ═════════════════════════════════════════════════════════════════════════

MODULES = _discover_plasticos_modules()


# ═════════════════════════════════════════════════════════════════════════
# TEST CLASS 1 — Registry Sanity
# ═════════════════════════════════════════════════════════════════════════


class TestRegistrySanity:
    """Verify the enum registries loaded correctly."""

    def test_selection_fields_found(self):
        assert len(ALL_SELECTION_KEYS) > 0, "No Selection field options found in any plasticos_* module"

    def test_xml_names_found(self):
        assert len(XML_NAMES) > 0, "No XML <field name='name'> values found in any data/*.xml"

    def test_known_polymers_in_registry(self):
        """Spot-check: HDPE, PP, PET must be in XML names."""
        for polymer in ["HDPE", "PP", "PET", "LDPE"]:
            assert polymer in XML_NAMES, f"Expected polymer '{polymer}' not found in XML names"

    def test_known_forms_in_registry(self):
        for form in ["BALE", "FILM", "FLAKE", "PELL"]:
            assert form in XML_NAMES, f"Expected form '{form}' not found in XML names"

    def test_known_selection_keys_in_registry(self):
        """Spot-check: form codes should be registered (via Selection or XML data).

        Note: form_preference is now a computed Selection derived from a
        Many2one to material.form.  Its canonical codes live in XML data
        (material_form_data.xml) and in form_codes.py, so we check
        ALL_CANONICAL (union of Selection keys + XML codes + XML names).
        """
        for key in ["bales", "flake", "pellets"]:
            assert key in ALL_CANONICAL, f"Expected form code '{key}' not found in canonical registry"

    def test_application_class_options(self):
        expected = {"food", "medical", "automotive", "packaging", "agricultural", "construction"}
        actual = SELECTION_BY_FIELD.get("application_class", set())
        assert expected == actual, f"application_class mismatch.\n  Expected: {expected}\n  Actual:   {actual}"

    def test_process_type_options(self):
        expected = {
            "injection",
            "blow_mold",
            "extrusion",
            "film_blown",
            "film_cast",
            "thermoform",
            "rotomold",
            "compounding",
            "other",
        }
        actual = SELECTION_BY_FIELD.get("process_type", set())
        assert expected == actual

    def test_feedstock_type_options(self):
        expected = {"post_industrial", "post_consumer", "mixed", "virgin", "unknown"}
        actual = SELECTION_BY_FIELD.get("feedstock_type", set())
        assert expected == actual


# ═════════════════════════════════════════════════════════════════════════
# TEST CLASS 2 — Selection Field Comparisons
# ═════════════════════════════════════════════════════════════════════════


class TestSelectionComparisons:
    """For every string literal used in a domain like
    ('field', '=', 'value') — if `field` is a known Selection field,
    then `value` must be in that field's option set."""

    def test_domain_values_match_selection_options(self):
        violations = []
        for usage in ALL_USAGES:
            # Extract field name from domain context
            if not usage.context.startswith("domain["):
                continue
            field_name = usage.context[7:-1]  # strip "domain[" and "]"
            if field_name not in SELECTION_BY_FIELD:
                continue

            valid = SELECTION_BY_FIELD[field_name]
            if usage.value not in valid:
                violations.append(
                    f"  {usage.file}:{usage.line} — "
                    f"('{field_name}', '=', '{usage.value}') "
                    f"but valid options are {sorted(valid)}"
                )

        assert len(violations) == 0, "Domain values that don't match Selection options:\n" + "\n".join(violations)


# ═════════════════════════════════════════════════════════════════════════
# TEST CLASS 3 — Phantom Enum Values (Full Scan)
# ═════════════════════════════════════════════════════════════════════════


class TestPhantomEnumValues:
    """Detect string literals used in enum-like contexts that don't exist
    in ANY registry (Selection fields OR XML seed data)."""

    def test_no_phantom_comparison_values(self):
        """String values in == / != comparisons must exist somewhere."""
        phantoms = []
        for usage in ALL_USAGES:
            if usage.context != "comparison":
                continue
            if _is_phantom(usage.value):
                phantoms.append(f"  {usage.file}:{usage.line} — '{usage.value}' (comparison)")

        if phantoms:
            pytest.fail(
                "Phantom values in comparisons "
                "(not found in Selection fields or XML data):\n"
                + "\n".join(phantoms[:50])  # cap output
                + (f"\n  ... and {len(phantoms) - 50} more" if len(phantoms) > 50 else "")
            )

    def test_no_phantom_domain_values(self):
        """Values in domain tuples must exist somewhere."""
        phantoms = []
        for usage in ALL_USAGES:
            if not usage.context.startswith("domain["):
                continue
            if _is_phantom(usage.value):
                field_name = usage.context[7:-1]
                phantoms.append(f"  {usage.file}:{usage.line} — ('{field_name}', op, '{usage.value}')")

        if phantoms:
            pytest.fail(
                "Phantom values in Odoo domain tuples:\n"
                + "\n".join(phantoms[:50])
                + (f"\n  ... and {len(phantoms) - 50} more" if len(phantoms) > 50 else "")
            )

    def test_no_phantom_in_list_values(self):
        """Values in `x in ["a", "b"]` must exist somewhere."""
        phantoms = []
        for usage in ALL_USAGES:
            if usage.context != "in_list":
                continue
            if _is_phantom(usage.value):
                phantoms.append(f"  {usage.file}:{usage.line} — '{usage.value}'")

        if phantoms:
            pytest.fail(
                "Phantom values in `in [...]` checks:\n"
                + "\n".join(phantoms[:50])
                + (f"\n  ... and {len(phantoms) - 50} more" if len(phantoms) > 50 else "")
            )


# ═════════════════════════════════════════════════════════════════════════
# TEST CLASS 4 — Per-Module Phantom Audit
# ═════════════════════════════════════════════════════════════════════════


class TestPerModulePhantomAudit:
    """Run phantom detection per-module so failures pinpoint the offender."""

    @pytest.mark.parametrize("module_name", MODULES)
    def test_module_has_no_phantom_enums(self, module_name):
        module_usages = [
            u for u in ALL_USAGES if u.file.startswith(module_name + "/") or u.file.startswith(module_name + os.sep)
        ]
        phantoms = [u for u in module_usages if _is_phantom(u.value)]

        if phantoms:
            detail = "\n".join(f"  {u.file}:{u.line} — '{u.value}' ({u.context})" for u in phantoms[:20])
            extra = f"\n  ... and {len(phantoms) - 20} more" if len(phantoms) > 20 else ""
            pytest.fail(f"{module_name}: {len(phantoms)} phantom enum value(s):\n" + detail + extra)


# ═════════════════════════════════════════════════════════════════════════
# TEST CLASS 5 — Selection Field Cross-Module Consistency
# ═════════════════════════════════════════════════════════════════════════


class TestSelectionFieldConsistency:
    """When multiple modules define the SAME Selection field name
    (e.g., via _inherit), their option sets must be identical or
    one must be a strict superset of the other."""

    def _find_selection_collisions(self):
        """Return {field_name: {module: set(options)}} for fields
        defined in multiple modules."""
        field_by_module = defaultdict(lambda: defaultdict(set))

        for mod in MODULES:
            mod_path = REPO_ROOT / mod
            for rel_path, src in _iter_python_files(mod_path):
                field_opts, _, _ = _extract_selection_options_from_source(src, rel_path)
                for field_name, keys in field_opts.items():
                    field_by_module[field_name][mod].update(keys)

        # Keep only fields defined in >1 module
        return {fname: dict(modules) for fname, modules in field_by_module.items() if len(modules) > 1}

    def test_shared_selection_fields_are_compatible(self):
        collisions = self._find_selection_collisions()
        violations = []

        for field_name, module_opts in collisions.items():
            all_sets = list(module_opts.values())
            # Check: is one a superset of all others?
            union = set().union(*all_sets)
            for mod, opts in module_opts.items():
                if opts != union and not union.issuperset(opts):
                    violations.append(f"  Field '{field_name}' in {mod}: {sorted(opts)} vs union {sorted(union)}")

        # This is a warning, not a hard fail — extension modules
        # legitimately add options via selection_add
        if violations:
            import warnings

            warnings.warn(
                "Selection fields defined in multiple modules with different option sets:\n" + "\n".join(violations),
                stacklevel=1,
            )


# ═════════════════════════════════════════════════════════════════════════
# TEST CLASS 6 — XML↔Selection Alignment
# ═════════════════════════════════════════════════════════════════════════


class TestXmlSelectionAlignment:
    """Where XML seed data and Selection fields describe the SAME
    domain concept, their values should align."""

    def test_xml_colors_are_canonical(self):
        """Color names in XML must not have trailing whitespace or
        inconsistent casing."""
        color_names = {s.value for s in ALL_SOURCES if "color" in s.source_file.lower() and s.source_type == "xml_name"}
        for name in color_names:
            assert name == name.strip(), f"Color '{name}' has trailing whitespace"
            # First letter should be capitalized (Natural, not natural)
            if name and name[0].islower() and "/" not in name:
                pytest.fail(f"Color '{name}' should be title-cased")

    def test_xml_polymer_names_are_uppercase(self):
        """Polymer codes (HDPE, PP, PET) should be uppercase in XML.

        Note: This only checks actual polymer category codes, not
        material types (Clean, Dirty, etc.) or other taxonomy entries.
        """
        # Known material type names that are NOT polymer codes
        # (these are quality/condition descriptors, not polymer abbreviations)
        MATERIAL_TYPE_NAMES = frozenset(
            {
                # Quality/condition descriptors
                "Clean",
                "Dirty",
                "Dry",
                "Wet",
                "Metalized",
                "Mixed",
                "Printed",
                "Unprinted",
                "Colored",
                "Natural",
                "Clear",
                "Opaque",
                "Translucent",
                "Contaminated",
                "Sorted",
                "Unsorted",
                # Color descriptors
                "Dark",
                "Light",
                "Black",
                "White",
                "Red",
                "Blue",
                "Green",
                "Yellow",
                "Orange",
                "Purple",
                "Pink",
                "Brown",
                "Gray",
                "Grey",
                # Form descriptors
                "Baled",
                "Loose",
                "Ground",
                "Flaked",
                "Pellet",
                "Granule",
                # Material property descriptors
                "Metal",
                "Metallic",
                "Foil",
                "Film",
                "Sheet",
                "Rigid",
                "Flexible",
                "Reusable",
                "Recyclable",
                "Compostable",
                "Biodegradable",
                # Taxonomy category names (not polymer codes)
                "Grades",
                "Types",
                "Forms",
                "Colors",
                "Categories",
                "Polymers",
                "Materials",
                "Fillers",
                "Additives",
                "Prime",
                "Wide",
                "Narrow",
                "Standard",
                "Print",  # Other taxonomy entries
                "Other",
                "Unknown",
                "Various",
                "Multiple",
                "None",
            }
        )

        polymer_names = {
            s.value
            for s in ALL_SOURCES
            if "taxonomy" in s.source_file.lower()
            and s.source_type == "xml_name"
            and any(cat in s.source_file for cat in ["material_taxonomy", "polymer"])
        }
        # Filter to things that look like polymer codes:
        # - Short (≤8 chars)
        # - Alphabetic
        # - NOT in the material types list
        short_codes = {n for n in polymer_names if len(n) <= 8 and n.isalpha() and n not in MATERIAL_TYPE_NAMES}
        for code in short_codes:
            # Allow rPET (recycled PET) as special case
            if code != code.upper() and code not in ("rPET",):
                pytest.fail(f"Polymer code '{code}' should be uppercase (got mixed/lower case)")


# ═════════════════════════════════════════════════════════════════════════
# TEST CLASS 7 — Equipment Code Alignment
# ═════════════════════════════════════════════════════════════════════════


class TestEquipmentCodeAlignment:
    """Validate that equipment codes used in _compute_equipment_flags
    match the codes defined in equipment type seed data XML."""

    def test_equipment_codes_in_compute_match_seed_data(self):
        """Codes used in `"code_value" in codes` comparisons must
        exist in equipment type XML seed data."""
        # Find equipment codes used in Python
        used_codes = set()
        for mod in MODULES:
            mod_path = REPO_ROOT / mod
            for _rel_path, src in _iter_python_files(mod_path):
                if "equipment" not in src.lower():
                    continue
                # Pattern: "some_code" in codes
                for match in re.finditer(r'["\'](\w+)["\']\s+in\s+codes', src):
                    used_codes.add(match.group(1))

        if not used_codes:
            pytest.skip("No equipment code comparisons found")

        # Find equipment codes defined in XML
        xml_codes = set()
        for mod in MODULES:
            for xml_path in _iter_xml_data_files(REPO_ROOT / mod):
                try:
                    tree = ET.parse(xml_path)
                except ET.ParseError:
                    continue
                for record in tree.getroot().iter("record"):
                    model = record.get("model", "")
                    if "equipment" not in model:
                        continue
                    for field in record.findall("field"):
                        if field.get("name") == "code":
                            text = (field.text or "").strip()
                            if text:
                                xml_codes.add(text)

        if not xml_codes:
            pytest.skip("No equipment type seed data found")

        missing = used_codes - xml_codes
        assert len(missing) == 0, (
            f"Equipment codes used in Python but missing from XML seed data:\n"
            f"  Used in code:      {sorted(used_codes)}\n"
            f"  Defined in XML:    {sorted(xml_codes)}\n"
            f"  MISSING (phantom): {sorted(missing)}"
        )


# ═════════════════════════════════════════════════════════════════════════
# TEST CLASS 8 — Reporting (always passes, prints audit)
# ═════════════════════════════════════════════════════════════════════════


class TestPhantomAuditReport:
    """Generate a human-readable report of all phantoms found.
    This test always passes — it writes to stdout for inspection."""

    def test_print_phantom_summary(self, capsys):
        phantoms = [u for u in ALL_USAGES if _is_phantom(u.value)]
        by_module = defaultdict(list)
        for p in phantoms:
            mod = p.file.split("/")[0] if "/" in p.file else p.file.split(os.sep)[0]
            by_module[mod].append(p)

        lines = [
            "═══ PHANTOM ENUM AUDIT ═══",
            f"Total canonical values:   {len(ALL_CANONICAL)}",
            f"  Selection field keys:   {len(ALL_SELECTION_KEYS)}",
            f"  XML name values:        {len(XML_NAMES)}",
            f"  XML code values:        {len(XML_CODES)}",
            f"Total enum usages found:  {len(ALL_USAGES)}",
            f"Total phantoms detected:  {len(phantoms)}",
            "",
        ]
        for mod in sorted(by_module):
            items = by_module[mod]
            lines.append(f"  {mod}: {len(items)} phantom(s)")
            for item in items[:5]:
                lines.append(f"    L{item.line} '{item.value}' ({item.context})")
            if len(items) > 5:
                lines.append(f"    ... +{len(items) - 5} more")

        report = "\n".join(lines)
        print(f"\n{report}")
        # This test always passes — it's for visibility only
        assert True
