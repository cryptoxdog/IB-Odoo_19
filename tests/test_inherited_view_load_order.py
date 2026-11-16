"""Upgrade-safe load order for inherited views of a view another module owns.

When a module's data file writes an inherited view, Odoo validates the whole
combined view: the root plus every extension this module already holds in the
database. On an upgrade that includes extensions whose stored arch is still the
previous version's, because their data file has not been reloaded yet.

An extension that embeds an inline sub-view (``<field name="x_ids"><list>...``)
names fields of the comodel. When one of those fields is renamed or removed,
the stored arch is invalid until its file reloads. If a sibling extension of
the same root loads first, its write validates the stale arch and the upgrade
aborts with ``Field "..." does not exist``. A fresh install never holds a stale
arch, so nothing else in CI sees this.

Reproduced on 2026-11-12: ``color_id`` became ``color_ids`` on
``plasticos.material.profile`` (PR #491). ``views/material_profile_views.xml``
(res.partner stat button) loaded before ``views/partner_material_ux.xml``
(res.partner Material Profiles tab, inline profile list), and upgrading an
existing database failed at ``view_partner_form_material_tab_base``.

Invariant, per module: among the extensions of one root view defined outside
the module, no extension without an inline sub-view loads before one with an
inline sub-view. Two embedding siblings cannot be protected by order alone and
are not judged here.
"""

from __future__ import annotations

import ast
from pathlib import Path
from xml.etree import ElementTree

REPO_ROOT = Path(__file__).resolve().parent.parent
MODULE = "plasticos_material_profile"
TAB_FILE = "views/partner_material_ux.xml"
STAT_BUTTON_FILE = "views/material_profile_views.xml"


def _manifest_data(module_dir: Path) -> list[str]:
    manifest = ast.literal_eval((module_dir / "__manifest__.py").read_text(encoding="utf-8"))
    return list(manifest.get("data", []))


def _embeds_inline_subview(arch: ElementTree.Element) -> bool:
    # ``arch`` is itself a <field> element of the record; judge only what it contains.
    return any(field is not arch and field.find(".//field") is not None for field in arch.iter("field"))


def _inherited_views(module_dir: Path, data_files: list[str]) -> list[dict]:
    """Inherited view records in load order: file, id, root reference, embeds flag."""
    module = module_dir.name
    records: list[dict] = []
    for data_file in data_files:
        if not data_file.endswith(".xml"):
            continue
        tree = ElementTree.parse(module_dir / data_file)  # noqa: S314 - repository-owned XML
        for record in tree.getroot().iter("record"):
            if record.get("model") != "ir.ui.view":
                continue
            fields = {field.get("name"): field for field in record.findall("field")}
            inherit = fields.get("inherit_id")
            arch = fields.get("arch")
            if inherit is None or arch is None or not inherit.get("ref"):
                continue
            ref = inherit.get("ref")
            records.append(
                {
                    "file": data_file,
                    "xmlid": f"{module}.{record.get('id')}" if "." not in record.get("id") else record.get("id"),
                    "parent": ref if "." in ref else f"{module}.{ref}",
                    "embeds": _embeds_inline_subview(arch),
                }
            )
    return records


def load_order_violations(module_dir: Path, data_files: list[str]) -> list[str]:
    module = module_dir.name
    records = _inherited_views(module_dir, data_files)
    parent_of = {record["xmlid"]: record["parent"] for record in records}

    def root(xmlid: str) -> str:
        seen = set()
        while xmlid in parent_of and xmlid not in seen:
            seen.add(xmlid)
            xmlid = parent_of[xmlid]
        return xmlid

    violations: list[str] = []
    plain_seen: dict[str, dict] = {}
    for record in records:
        root_ref = root(record["xmlid"])
        if root_ref.startswith(f"{module}."):
            continue
        if not record["embeds"]:
            plain_seen.setdefault(root_ref, record)
        elif root_ref in plain_seen and plain_seen[root_ref]["file"] != record["file"]:
            earlier = plain_seen[root_ref]
            violations.append(
                f"{module}: {earlier['file']} ({earlier['xmlid']}) loads before "
                f"{record['file']} ({record['xmlid']}); both extend {root_ref} and the later one "
                "embeds an inline sub-view. Move the embedding file first in the manifest data list."
            )
    return violations


def test_embedding_extensions_load_before_their_siblings() -> None:
    violations: list[str] = []
    module_dirs = sorted(path.parent for path in REPO_ROOT.glob("plasticos_*/__manifest__.py"))
    assert module_dirs, "no plasticos_* modules found"
    for module_dir in module_dirs:
        violations.extend(load_order_violations(module_dir, _manifest_data(module_dir)))
    assert not violations, "\n".join(violations)


def test_partner_material_tab_loads_before_partner_stat_button() -> None:
    data_files = _manifest_data(REPO_ROOT / MODULE)
    assert data_files.index(TAB_FILE) < data_files.index(STAT_BUTTON_FILE)


def test_checker_rejects_the_order_that_broke_the_upgrade() -> None:
    """Falsifying half: the manifest order shipped in 19.0.5.13.1 must be reported."""
    module_dir = REPO_ROOT / MODULE
    data_files = _manifest_data(module_dir)
    broken = [name for name in data_files if name != TAB_FILE]
    broken.append(TAB_FILE)
    violations = load_order_violations(module_dir, broken)
    assert len(violations) == 1
    assert STAT_BUTTON_FILE in violations[0]
    assert TAB_FILE in violations[0]
