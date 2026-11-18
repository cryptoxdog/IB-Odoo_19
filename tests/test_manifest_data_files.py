"""Every Odoo data file under a module's ``data/`` is loaded by its manifest.

Odoo loads only the files a manifest names in ``data`` or ``demo``. A record
file that exists but is not listed never loads, silently:
``plasticos_facility_profile/data/company_role_tag_data.xml`` was such a file
(campaign C1; listed by PR #525).

Rules, for every ``plasticos_*/__manifest__.py``:

* every ``*.xml`` and ``*.csv`` under the module's ``data/`` (recursive) is
  listed in ``data`` or ``demo``, unless ``ALLOWLIST`` names it with a reason;
* every ``data`` / ``demo`` entry exists on disk;
* every ``ALLOWLIST`` entry still exists and is still not listed (no stale
  exemption).
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MANIFESTS = sorted(ROOT.glob("plasticos_*/__manifest__.py"))

# Files under data/ that are not Odoo data on purpose. One line of reason each.
ALLOWLIST: dict[str, str] = {
    "plasticos_crm_sync/data/approved_contact_crosswalk.csv": "read by services/approved_identity.py, not Odoo data",
    "plasticos_crm_sync/data/vanillasoft_material_mapping.csv": "read by scripts/build_material_mapping.py",
    "plasticos_material_profile/data/ERP-Products.csv": "read by models/material_normalizer.py (ERP catalog)",
    "plasticos_material_profile/data/material_mapping.csv": "read by models/material_normalizer.py (phrase matrix)",
    "plasticos_crm_bridge/data/utm_source_deactivate.xml": "empty placeholder: a comment, no records",
}


def _manifest(path: Path) -> dict:
    return ast.literal_eval(path.read_text(encoding="utf-8"))


def _listed(path: Path) -> set[str]:
    manifest = _manifest(path)
    return {*manifest.get("data", []), *manifest.get("demo", [])}


def _data_files(module: Path) -> list[str]:
    data_dir = module / "data"
    if not data_dir.is_dir():
        return []
    return sorted(
        f"{module.name}/{file.relative_to(module).as_posix()}"
        for file in data_dir.rglob("*")
        if file.is_file() and file.suffix in (".xml", ".csv")
    )


def test_manifests_are_found():
    assert MANIFESTS, "no plasticos_* manifest found"


@pytest.mark.parametrize("manifest", MANIFESTS, ids=lambda path: path.parent.name)
def test_every_data_file_is_listed_in_its_manifest(manifest):
    module = manifest.parent
    listed = {f"{module.name}/{entry}" for entry in _listed(manifest)}
    unlisted = [file for file in _data_files(module) if file not in listed and file not in ALLOWLIST]
    assert not unlisted, f"data files never loaded (add them to {module.name}/__manifest__.py): {unlisted}"


@pytest.mark.parametrize("manifest", MANIFESTS, ids=lambda path: path.parent.name)
def test_every_manifest_entry_exists(manifest):
    module = manifest.parent
    missing = sorted(entry for entry in _listed(manifest) if not (module / entry).is_file())
    assert not missing, f"{module.name}/__manifest__.py lists files that do not exist: {missing}"


@pytest.mark.parametrize("entry", sorted(ALLOWLIST))
def test_allowlist_entry_is_not_stale(entry):
    path = ROOT / entry
    assert path.is_file(), f"allowlisted file no longer exists: {entry}"
    module, relative = entry.split("/", 1)
    manifest = ROOT / module / "__manifest__.py"
    assert relative not in _listed(manifest), f"{entry} is now listed in its manifest: remove it from ALLOWLIST"
