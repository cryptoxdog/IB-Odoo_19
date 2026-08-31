"""Manifest contract: version format, self-dependency, phantom dependencies.

This is the target of the ``manifest-contract`` pre-push hook
(.pre-commit-config.yaml) and of the "Manifest contract check (version, depends
order)" row in AGENTS.md.

Architecture note (2026-08 reconciliation): a file of this name existed until
M7 / TASK-051 (#139), where it was deleted along with
``plasticos_buyer_match_engine`` — the single module it was written against. The
hook entry pointing at it was not updated, so from #139 onward every
``git push`` invoked ``pytest tests/test_repo_dependency_integrity.py``, which
exits 4 (file not found). The documented manifest gate has been broken since.

Rather than restore a single-module test, the contract is re-derived here across
every ``plasticos_*`` module in the repository, so it cannot go stale when the
addon set changes.

NOT asserted here: declaration order of ``depends`` by architectural layer. The
deleted test checked that against a hand-curated LAYER_ORDER list covering one
module's dependencies. Twelve current manifests would fail a topological-depth
reading of that rule, and Odoo itself does not care about declaration order —
turning it into a hard gate is a manifest-reordering change, not a test fix.
Circular dependencies (the ordering property that does matter) are enforced by
ci/check_circular_deps.py.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Odoo core / enterprise addons that legitimately do not exist in this checkout.
# Kept as an explicit allowlist (not derived from the manifests) so that a typo'd
# or invented addon name is rejected instead of silently deferred to install time.
# Every entry below is currently declared by a plasticos_* module that installs
# under the install-smoke gate.
KNOWN_ODOO_ADDONS = frozenset(
    {
        "account",
        "barcodes",
        "base",
        "base_automation",
        "base_geolocalize",
        "base_setup",
        "calendar",
        "contacts",
        "crm",
        "documents",
        "documents_account",
        "mail",
        "portal",
        "product",
        "purchase",
        "purchase_stock",
        "sale",
        "sale_management",
        "sale_stock",
        "sales_team",
        "spreadsheet_dashboard",
        "stock",
        "utm",
        "web",
        "website",
    }
)

VERSION_RE = re.compile(r"^19\.0\.\d+\.\d+\.\d+$")


def _plasticos_manifests() -> dict[str, dict]:
    """Every plasticos_* module in the repo, mapped to its parsed manifest."""
    out: dict[str, dict] = {}
    for entry in sorted(REPO_ROOT.iterdir()):
        manifest = entry / "__manifest__.py"
        if entry.name.startswith("plasticos_") and manifest.is_file():
            out[entry.name] = ast.literal_eval(manifest.read_text(encoding="utf-8"))
    return out


MANIFESTS = _plasticos_manifests()


def test_manifests_are_discovered():
    """Guardrail: an empty registry would make every check below vacuous."""
    assert len(MANIFESTS) >= 25, f"Only {len(MANIFESTS)} plasticos_* manifests found — discovery is broken"


def test_every_manifest_declares_required_fields():
    missing = [
        f"{mod}: {field}"
        for mod, data in MANIFESTS.items()
        for field in ("name", "version", "depends")
        if field not in data
    ]
    assert not missing, "Manifests missing required fields:\n  " + "\n  ".join(missing)


def test_version_is_odoo_19_five_part():
    """Every module version must be 19.0.X.Y.Z (Odoo series + three-part module version)."""
    bad = [
        f"{mod}: {data.get('version')!r}"
        for mod, data in MANIFESTS.items()
        if not VERSION_RE.match(str(data.get("version", "")))
    ]
    assert not bad, "Manifest versions must match 19.0.X.Y.Z:\n  " + "\n  ".join(bad)


def test_no_module_depends_on_itself():
    bad = [mod for mod, data in MANIFESTS.items() if mod in data.get("depends", [])]
    assert not bad, f"Modules declaring a self-dependency: {bad}"


def test_no_phantom_plasticos_dependencies():
    """Every declared plasticos_* dependency must exist as a module in this repo.

    Catches dependencies left behind by a module retirement — the failure mode
    that made this file necessary in the first place.
    """
    phantom = [
        f"{mod} -> {dep}"
        for mod, data in MANIFESTS.items()
        for dep in data.get("depends", [])
        if dep.startswith("plasticos_") and dep not in MANIFESTS
    ]
    assert not phantom, "Dependencies on non-existent plasticos_* modules:\n  " + "\n  ".join(phantom)


def test_no_unknown_non_plasticos_dependencies():
    """Non-plasticos dependencies must be recognised Odoo addons.

    Keeps the allowlist explicit so a typo'd or invented addon name is rejected
    rather than silently deferred to install time.
    """
    unknown = [
        f"{mod} -> {dep}"
        for mod, data in MANIFESTS.items()
        for dep in data.get("depends", [])
        if not dep.startswith("plasticos_") and dep not in KNOWN_ODOO_ADDONS
    ]
    assert not unknown, (
        "Unrecognised non-plasticos dependencies. If these are real Odoo addons, "
        "add them to KNOWN_ODOO_ADDONS:\n  " + "\n  ".join(unknown)
    )


def test_retired_modules_absent_from_every_depends():
    """M7 / TASK-051: no manifest may depend on a retired local-intelligence module."""
    retired = ("plasticos_buyer_match_engine", "plasticos_inference_engine")
    offenders = [
        f"{mod} -> {dep}" for mod, data in MANIFESTS.items() for dep in data.get("depends", []) if dep in retired
    ]
    assert not offenders, "Manifests still depending on M7-retired modules:\n  " + "\n  ".join(offenders)
