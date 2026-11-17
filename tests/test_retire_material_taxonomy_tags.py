"""The plasticos_base material-taxonomy partner tags are retired (C1 lane G1).

``plasticos_base/data/material_taxonomy.xml`` loaded 108 ``res.partner.category``
records that copied the material vocabulary of ``plasticos_material_profile``.
The file is no longer loaded, and post-migrate 19.0.1.1.15 removes exactly
those records by their ``plasticos_base`` external ids.
"""

from __future__ import annotations

import ast
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "plasticos_base"
MIGRATION = BASE / "migrations" / "19.0.1.1.15" / "post-migrate.py"


def _retired_ids() -> tuple[str, ...]:
    tree = ast.parse(MIGRATION.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "RETIRED_TAG_XMLIDS" for target in node.targets
        ):
            return tuple(ast.literal_eval(node.value))
    raise AssertionError("RETIRED_TAG_XMLIDS not found in the migration")


def _module_constant(name: str) -> str:
    tree = ast.parse(MIGRATION.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
            return ast.literal_eval(node.value)
    raise AssertionError(f"{name} not found in the migration")


def test_taxonomy_file_is_gone_and_not_loaded():
    assert not (BASE / "data" / "material_taxonomy.xml").exists()
    manifest = ast.literal_eval((BASE / "__manifest__.py").read_text(encoding="utf-8"))
    assert "data/material_taxonomy.xml" not in manifest["data"]
    assert manifest["version"] == "19.0.1.1.15"


PARTNER_TAGS_RETIRED = (
    "tag_needs_enrichment",
    "tag_key_account",
    "tag_preferred_carrier",
    "category_material_focus",
    "tag_mf_pallets",
    "tag_mf_hdpe_drums",
    "tag_mf_ag_film",
    "tag_mf_ldpe_film",
    "tag_mf_baled_pet",
    "tag_mf_baled_hdpe",
    "tag_mf_mixed_rigid",
    "tag_mf_pp_supersacks",
    "tag_mf_pvc_pipe",
    "tag_mf_stretch_wrap",
)


def test_migration_names_the_108_taxonomy_and_14_partner_tags_once():
    ids = _retired_ids()
    assert len(ids) == 108 + len(PARTNER_TAGS_RETIRED)
    assert len(set(ids)) == len(ids)
    assert set(PARTNER_TAGS_RETIRED) <= set(ids)
    for group in (
        "category_polymers",
        "category_material_types",
        "category_forms",
        "category_source_types",
        "category_colors",
        "category_grades",
    ):
        assert group in ids


def test_migration_removes_only_plasticos_base_partner_tags():
    assert _module_constant("MODULE") == "plasticos_base"
    assert _module_constant("TAG_MODEL") == "res.partner.category"
    source = MIGRATION.read_text(encoding="utf-8")
    assert '("module", "=", MODULE)' in source
    assert '("model", "=", TAG_MODEL)' in source
    assert '("name", "in", list(RETIRED_TAG_XMLIDS))' in source
    # Partner usage is logged before anything is removed.
    assert source.index("res_partner_res_partner_category_rel") < source.index("tags.unlink()")


def test_partner_tags_keep_only_do_not_contact_and_the_two_company_types():
    kept = set(re.findall(r'id="([^"]+)"', (BASE / "data" / "partner_tags.xml").read_text(encoding="utf-8")))
    # Operational keeps only Do Not Contact. Exporter and Toll Processor stay as records for
    # plasticos_facility_profile to move into Company Type (operator D25); this PR does not touch them.
    assert kept == {"category_operational", "tag_do_not_contact", "tag_exporter", "tag_toll_processor"}
    assert not kept & set(_retired_ids())


def test_no_reference_to_a_retired_tag_remains():
    tracked = subprocess.run(
        ["git", "ls-files", "--", "*.py", "*.xml", "*.csv"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.split()
    ids = _retired_ids()
    pattern = re.compile(r"plasticos_base\.(" + "|".join(map(re.escape, ids)) + r")\b")
    allowed = {
        "plasticos_base/migrations/19.0.1.1.15/post-migrate.py",
        # Archived the BALE tag earlier; raise_if_not_found=False keeps it safe once the tag is gone.
        "plasticos_base/migrations/19.0.1.1.14/post-migrate.py",
        # This test names that call to prove it tolerates the missing tag.
        "tests/test_retire_material_taxonomy_tags.py",
    }
    hits = []
    for rel in tracked:
        if rel in allowed or not (ROOT / rel).is_file():
            continue
        text = (ROOT / rel).read_text(encoding="utf-8", errors="ignore")
        hits.extend(f"{rel}: {match.group(0)}" for match in pattern.finditer(text))
        if rel.startswith("plasticos_base/") and "material_taxonomy" in text:
            hits.append(f"{rel}: material_taxonomy")
    assert hits == []


def test_earlier_bale_migration_tolerates_the_missing_tag():
    source = (BASE / "migrations" / "19.0.1.1.14" / "post-migrate.py").read_text(encoding="utf-8")
    assert 'env.ref("plasticos_base.form_bale", raise_if_not_found=False)' in source
