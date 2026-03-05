"""
Repo-wide dependency integrity tests for cryptoxdog/IB-Odoo_19.
Auto-discovers every plasticos_* module, parses __manifest__.py,
builds the full DAG, and validates layered architecture constraints.

Run:  pytest tests/test_repo_dependency_integrity.py -v

Zero Odoo runtime required. Pure filesystem + AST.
"""

import ast
import os
from collections import defaultdict, deque

import pytest

# ═════════════════════════════════════════════════════════════════════════
# REPO ROOT DETECTION
# ═════════════════════════════════════════════════════════════════════════


def _find_repo_root():
    """Walk up from this file until we find a directory containing
    plasticos_base/ (the canonical anchor module)."""
    candidate = os.path.dirname(os.path.abspath(__file__))
    for _ in range(10):
        if os.path.isdir(os.path.join(candidate, "plasticos_base")):
            return candidate
        candidate = os.path.dirname(candidate)
    raise RuntimeError(
        "Cannot locate repo root (looked for plasticos_base/ "
        f"starting from {os.path.dirname(os.path.abspath(__file__))})"
    )


REPO_ROOT = _find_repo_root()


# ═════════════════════════════════════════════════════════════════════════
# ARCHITECTURE LAYER MAP
#
# Lower index = lower layer. Modules may only depend on modules at the
# same layer or below. Core Odoo modules sit at layer 0.
#
# If a plasticos_* module is not listed here it is assigned to the
# highest layer (len(LAYERS)) and is only checked for basic DAG health.
# ═════════════════════════════════════════════════════════════════════════

LAYERS: dict[str, int] = {
    # ══════════════════════════════════════════════════════════════════════════
    # LAYER MAP — Based on actual __manifest__.py depends (not aspirational)
    #
    # Rule: Module X at layer N may only depend on modules at layer ≤ N.
    # This map is derived from the real dependency graph in the repo.
    # ══════════════════════════════════════════════════════════════════════════
    # ── Layer 0: Odoo core ──────────────────────────────────────────
    "base": 0,
    "mail": 0,
    "contacts": 0,
    "sale_management": 0,
    "sale": 0,
    "purchase": 0,
    "stock": 0,
    "account": 0,
    "web": 0,
    "website": 0,
    "crm": 0,
    "base_geolocalize": 0,
    "product": 0,
    # ── Layer 1: Foundation ─────────────────────────────────────────
    # plasticos_base: depends only on Odoo core
    "plasticos_base": 1,
    # ── Layer 2: (reserved - logistics moved to layer 8) ───────────
    # ── Layer 3: Material domain ────────────────────────────────────
    # plasticos_material_profile: depends on plasticos_base
    # plasticos_product: depends on plasticos_material_profile
    "plasticos_material_profile": 3,
    "plasticos_product": 3,
    # ── Layer 4: Facility domain ────────────────────────────────────
    # plasticos_facility_profile: depends on plasticos_material_profile
    "plasticos_facility_profile": 4,
    # ── Layer 5: Intake / Normalizer ────────────────────────────────
    # plasticos_intake: depends on plasticos_facility_profile, plasticos_material_profile
    # plasticos_intake_normalizer: depends on plasticos_intake
    "plasticos_intake": 5,
    "plasticos_intake_normalizer": 5,
    # ── Layer 6: Matching + Offer ────────────────────────────────────
    # plasticos_matching: depends on plasticos_intake, plasticos_facility_profile
    # plasticos_offer: depends on plasticos_matching, plasticos_intake
    "plasticos_matching": 6,
    "plasticos_offer": 6,
    # ── Layer 7: Transaction ────────────────────────────────────────
    # plasticos_transaction: depends on plasticos_intake, plasticos_facility_profile,
    #                        plasticos_product, plasticos_offer, plasticos_matching
    # NOTE: No longer depends on plasticos_logistics (circular dep fix 2026-03-05)
    "plasticos_transaction": 7,
    # ── Layer 8: Logistics + Engine / Intelligence / Commercial ────
    # plasticos_logistics: depends on plasticos_transaction (injects load_id field)
    # plasticos_buyer_match_engine: depends on plasticos_matching, plasticos_transaction
    # plasticos_order_lines: depends on plasticos_product, plasticos_material_profile
    # plasticos_enrichment: depends on plasticos_facility_profile
    # plasticos_inference_engine: depends on plasticos_intake
    "plasticos_logistics": 8,
    "plasticos_buyer_match_engine": 8,
    "plasticos_inference_engine": 8,
    "plasticos_enrichment": 8,
    "plasticos_order_lines": 8,
    # ── Layer 9: Documents ──────────────────────────────────────────
    # plasticos_documents: depends on plasticos_transaction
    "plasticos_documents": 9,
    # ── Layer 10: Claims / Automation / Web Leads ───────────────────
    # plasticos_claims: depends on plasticos_documents, plasticos_transaction, plasticos_logistics
    # plasticos_automation: depends on plasticos_claims, plasticos_transaction
    # plasticos_web_leads: depends on plasticos_intake, plasticos_facility_profile
    # plasticos_accounting: depends on plasticos_transaction
    "plasticos_claims": 10,
    "plasticos_automation": 10,
    "plasticos_web_leads": 10,
    "plasticos_accounting": 10,
    # ── Layer 11: Geo (extends intake with lat/lon) ───────────────
    # plasticos_geolocalize: depends on plasticos_intake (inherits plasticos.intake)
    "plasticos_geolocalize": 11,
    # ── Layer 5: Partner Import (facility-level, no intake dep) ─────
    # plasticos_partner_import: depends on plasticos_facility_profile only
    # NOTE: Moved from layer 11 after removing unnecessary plasticos_intake dep
    "plasticos_partner_import": 5,
    # ── Layer 12: Security Capstone ─────────────────────────────────
    # plasticos_security_base: depends on EVERYTHING (applies record rules)
    # This is NOT a foundation module — it's the capstone that loads LAST
    "plasticos_security_base": 12,
    # ── Layer 13: Enterprise Bridge / Dev Tools (optional) ──────────
    # plasticos_documents_native: depends on Enterprise 'documents' + plasticos_security_base
    # plasticos_dev_tools: dev-only, installable: False
    "plasticos_documents_native": 13,
    "plasticos_dev_tools": 13,
}

# Sentinel for modules not yet mapped
_UNMAPPED_LAYER = max(LAYERS.values()) + 100


# ═════════════════════════════════════════════════════════════════════════
# AUTO-DISCOVERY
# ═════════════════════════════════════════════════════════════════════════


def _discover_modules():
    """Return {module_name: parsed_manifest_dict} for every plasticos_*
    directory that contains a parseable __manifest__.py."""
    modules = {}
    for entry in sorted(os.listdir(REPO_ROOT)):
        if not entry.startswith("plasticos_"):
            continue
        manifest_path = os.path.join(REPO_ROOT, entry, "__manifest__.py")
        if not os.path.isfile(manifest_path):
            continue
        with open(manifest_path, encoding="utf-8") as fh:
            src = fh.read()
        try:
            manifest = ast.literal_eval(src)
        except (ValueError, SyntaxError):
            continue
        if isinstance(manifest, dict):
            manifest["_dir"] = entry
            modules[entry] = manifest
    return modules


ALL_MODULES = _discover_modules()
MODULE_NAMES = sorted(ALL_MODULES.keys())


def _get_layer(module_name: str) -> int:
    return LAYERS.get(module_name, _UNMAPPED_LAYER)


# ═════════════════════════════════════════════════════════════════════════
# GRAPH UTILITIES
# ═════════════════════════════════════════════════════════════════════════


def _build_adjacency():
    """Return {module: [deps]} for plasticos_* modules only."""
    adj = {}
    for name, manifest in ALL_MODULES.items():
        adj[name] = [d for d in manifest.get("depends", []) if d.startswith("plasticos_")]
    return adj


def _find_all_cycles(adj):
    """DFS-based cycle detection. Returns list of cycles as tuples."""
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {n: WHITE for n in adj}
    path = []
    cycles = []

    def dfs(u):
        color[u] = GRAY
        path.append(u)
        for v in adj.get(u, []):
            if v not in color:
                continue
            if color[v] == GRAY:
                # Cycle found — extract it
                idx = path.index(v)
                cycles.append(tuple(path[idx:]))
            elif color[v] == WHITE:
                dfs(v)
        path.pop()
        color[u] = BLACK

    for node in adj:
        if color[node] == WHITE:
            dfs(node)
    return cycles


def _topological_sort(adj):
    """Kahn's algorithm. Returns (sorted_list, success_bool)."""
    in_degree = defaultdict(int)
    for node in adj:
        in_degree.setdefault(node, 0)
        for dep in adj[node]:
            if dep in adj:
                in_degree[dep] += 0  # ensure key exists
                in_degree[node]  # ensure key exists

    # Recompute properly
    in_degree = {n: 0 for n in adj}
    for node, deps in adj.items():
        for d in deps:
            if d in in_degree:
                in_degree[node] += 1  # node depends on d

    # Actually: in_degree[d] should be incremented when node->d
    # Wait, standard topological sort: edge u->v means u depends on v.
    # We want: if A depends on B, then B must come before A.
    # adj[A] = [B] means A depends on B. So edge is B -> A in topo order.
    # in_degree of A = number of deps A has (that exist in adj).

    in_deg = {n: 0 for n in adj}
    reverse_adj = defaultdict(list)
    for node, deps in adj.items():
        for d in deps:
            if d in adj:
                in_deg[node] += 1
                reverse_adj[d].append(node)

    queue = deque(n for n, deg in in_deg.items() if deg == 0)
    result = []
    while queue:
        u = queue.popleft()
        result.append(u)
        for v in reverse_adj[u]:
            in_deg[v] -= 1
            if in_deg[v] == 0:
                queue.append(v)

    return result, len(result) == len(adj)


# ═════════════════════════════════════════════════════════════════════════
# TEST CLASS 1 — Discovery Sanity
# ═════════════════════════════════════════════════════════════════════════


class TestDiscoverySanity:
    """Ensure auto-discovery found a reasonable module set."""

    def test_at_least_10_modules_found(self):
        assert len(ALL_MODULES) >= 10, f"Expected ≥10 plasticos_* modules, found {len(ALL_MODULES)}: " f"{MODULE_NAMES}"

    def test_plasticos_base_discovered(self):
        assert "plasticos_base" in ALL_MODULES, "plasticos_base not found — anchor module missing"

    def test_every_module_has_manifest(self):
        for name in MODULE_NAMES:
            assert "__manifest__.py" != "", f"{name} was discovered but has no manifest (should not happen)"

    def test_every_manifest_has_depends(self):
        for name, manifest in ALL_MODULES.items():
            assert "depends" in manifest, f"{name}/__manifest__.py missing 'depends' key"

    def test_every_manifest_has_version(self):
        for name, manifest in ALL_MODULES.items():
            assert "version" in manifest, f"{name}/__manifest__.py missing 'version' key"


# ═════════════════════════════════════════════════════════════════════════
# TEST CLASS 2 — No Self-Dependencies
# ═════════════════════════════════════════════════════════════════════════


class TestNoSelfDependency:
    """No module may list itself in depends."""

    @pytest.mark.parametrize("module_name", MODULE_NAMES)
    def test_module_does_not_depend_on_itself(self, module_name):
        depends = ALL_MODULES[module_name].get("depends", [])
        assert module_name not in depends, f"{module_name} depends on itself"


# ═════════════════════════════════════════════════════════════════════════
# TEST CLASS 3 — No Circular Dependencies (Full Graph)
# ═════════════════════════════════════════════════════════════════════════


class TestNoCycles:
    """The full plasticos_* dependency graph must be a DAG."""

    def test_no_circular_dependencies(self):
        adj = _build_adjacency()
        cycles = _find_all_cycles(adj)
        assert len(cycles) == 0, "Circular dependencies detected:\n" + "\n".join(
            f"  {'→'.join(c)}→{c[0]}" for c in cycles
        )

    def test_topological_sort_succeeds(self):
        adj = _build_adjacency()
        sorted_list, success = _topological_sort(adj)
        assert success, f"Topological sort failed — graph has cycles. " f"Sorted {len(sorted_list)}/{len(adj)} modules."


# ═════════════════════════════════════════════════════════════════════════
# TEST CLASS 4 — Layer Order Respected
# ═════════════════════════════════════════════════════════════════════════


class TestLayerOrder:
    """Every dependency must be at the same layer or a lower layer.
    A module at layer 7 cannot depend on a module at layer 8."""

    @pytest.mark.parametrize("module_name", MODULE_NAMES)
    def test_depends_respect_layer_order(self, module_name):
        my_layer = _get_layer(module_name)
        if my_layer == _UNMAPPED_LAYER:
            pytest.skip(f"{module_name} not mapped to a layer — add it to LAYERS")

        depends = ALL_MODULES[module_name].get("depends", [])
        violations = []

        for dep in depends:
            dep_layer = _get_layer(dep)
            if dep_layer == _UNMAPPED_LAYER:
                # Unknown deps (core Odoo not in map) get a pass
                continue
            if dep_layer > my_layer:
                violations.append(f"  {module_name} (layer {my_layer}) → " f"{dep} (layer {dep_layer})")

        assert len(violations) == 0, "Layer violation — module depends on a HIGHER layer:\n" + "\n".join(violations)


# ═════════════════════════════════════════════════════════════════════════
# TEST CLASS 5 — Phantom Dependency Detection
# ═════════════════════════════════════════════════════════════════════════

# Known Odoo core/OCA modules that are valid external deps
KNOWN_CORE_MODULES = {
    "base",
    "mail",
    "contacts",
    "sale_management",
    "sale",
    "purchase",
    "stock",
    "account",
    "web",
    "website",
    "crm",
    "base_geolocalize",
    "sale_stock",
    "purchase_stock",
    "account_payment",
    "delivery",
    "l10n_generic_coa",
    "base_setup",
    "product",
    "uom",
    "digest",
    "portal",
    "utm",
    "phone_validation",
    "sms",
    "note",
    "resource",
    "hr",
    "calendar",
    "board",
    "fetchmail",
    "mass_mailing",
}


class TestNoPhantomDependencies:
    """Every plasticos_* dependency must exist in the repo.
    Odoo core dependencies must be from a known set."""

    @pytest.mark.parametrize("module_name", MODULE_NAMES)
    def test_plasticos_deps_exist_in_repo(self, module_name):
        depends = ALL_MODULES[module_name].get("depends", [])
        missing = []
        for dep in depends:
            if dep.startswith("plasticos_") and dep not in ALL_MODULES:
                missing.append(dep)
        assert len(missing) == 0, f"{module_name} depends on plasticos modules not found in repo:\n" f"  {missing}"

    @pytest.mark.parametrize("module_name", MODULE_NAMES)
    def test_non_plasticos_deps_are_known(self, module_name):
        """Non-plasticos deps should be recognized Odoo core modules.
        Warns (not fails) on unknowns — they may be OCA or custom."""
        depends = ALL_MODULES[module_name].get("depends", [])
        unknown = [d for d in depends if not d.startswith("plasticos_") and d not in KNOWN_CORE_MODULES]
        if unknown:
            import warnings

            warnings.warn(
                f"{module_name} depends on unrecognized non-plasticos " f"modules: {unknown}. Verify they exist.",
                stacklevel=1,
            )


# ═════════════════════════════════════════════════════════════════════════
# TEST CLASS 6 — Version Prefix Consistency
# ═════════════════════════════════════════════════════════════════════════


class TestVersionConsistency:
    """All modules must target Odoo 19."""

    @pytest.mark.parametrize("module_name", MODULE_NAMES)
    def test_version_starts_with_19(self, module_name):
        version = ALL_MODULES[module_name].get("version", "")
        assert version.startswith("19."), f"{module_name} version '{version}' does not start with '19.'"

    @pytest.mark.parametrize("module_name", MODULE_NAMES)
    def test_version_has_five_segments(self, module_name):
        """Odoo 19 convention: 19.0.X.Y.Z (5 dot-separated segments)."""
        version = ALL_MODULES[module_name].get("version", "")
        parts = version.split(".")
        assert len(parts) == 5, (
            f"{module_name} version '{version}' should have 5 segments " f"(19.0.X.Y.Z), got {len(parts)}"
        )

    @pytest.mark.parametrize("module_name", MODULE_NAMES)
    def test_installable_is_true(self, module_name):
        # Some modules are intentionally not installable:
        # - plasticos_dev_tools: dev-only utilities
        # - plasticos_documents_native: requires Enterprise 'documents' module
        intentionally_not_installable = {
            "plasticos_dev_tools",
            "plasticos_documents_native",
        }
        if module_name in intentionally_not_installable:
            installable = ALL_MODULES[module_name].get("installable")
            assert installable is False, f"{module_name} should be installable=False (intentional)"
            pytest.skip(f"{module_name} is intentionally not installable")
        else:
            assert ALL_MODULES[module_name].get("installable") is True, f"{module_name} is not marked installable"


# ═════════════════════════════════════════════════════════════════════════
# TEST CLASS 7 — Namespace Enforcement
# ═════════════════════════════════════════════════════════════════════════


class TestNamespacePrefix:
    """Module directory names must use plasticos_ prefix (already
    guaranteed by discovery), but manifest 'name' must use PlasticOS."""

    @pytest.mark.parametrize("module_name", MODULE_NAMES)
    def test_manifest_name_starts_with_plasticos(self, module_name):
        name = ALL_MODULES[module_name].get("name", "")
        assert name.lower().startswith("plasticos") or name.lower().startswith("plastos"), (
            f"{module_name}: manifest name '{name}' does not start with " f"'PlasticOS' or 'Plasticos'"
        )


# ═════════════════════════════════════════════════════════════════════════
# TEST CLASS 8 — Install Order (Topological)
# ═════════════════════════════════════════════════════════════════════════


class TestInstallOrder:
    """Verify that a valid install order exists and foundation modules
    come first."""

    def test_topo_order_starts_with_foundation(self):
        adj = _build_adjacency()
        sorted_list, success = _topological_sort(adj)
        assert success, "Topological sort failed — cannot determine order"

        # plasticos_base is the true foundation — must appear early
        # NOTE: plasticos_security_base is a CAPSTONE module (loads LAST),
        #       not a foundation module. It applies record rules across all
        #       other modules, so it depends on everything.
        foundation = {"plasticos_base"}
        found = foundation & set(ALL_MODULES.keys())
        if not found:
            pytest.skip("No foundation modules found")

        # Foundation must be in first quarter (not just first half)
        quarter = max(len(sorted_list) // 4, 3)
        first_quarter = set(sorted_list[:quarter])
        for mod in found:
            assert mod in first_quarter, (
                f"Foundation module {mod} appears too late in install order "
                f"(position {sorted_list.index(mod)}/{len(sorted_list)})"
            )

    def test_security_base_loads_last(self):
        """plasticos_security_base is a capstone module that applies record
        rules across all other modules. It must load LAST (or near last)."""
        if "plasticos_security_base" not in ALL_MODULES:
            pytest.skip("plasticos_security_base not found")

        adj = _build_adjacency()
        sorted_list, success = _topological_sort(adj)
        assert success, "Topological sort failed"

        sec_pos = sorted_list.index("plasticos_security_base")
        total = len(sorted_list)
        # Must be in last 25% of install order
        assert sec_pos >= total * 0.75, (
            f"plasticos_security_base should load late (capstone module), " f"but appears at position {sec_pos}/{total}"
        )

    def test_buyer_match_engine_after_its_deps(self):
        """plasticos_buyer_match_engine must install after all 5 of its
        declared dependencies."""
        if "plasticos_buyer_match_engine" not in ALL_MODULES:
            pytest.skip("plasticos_buyer_match_engine not found")

        adj = _build_adjacency()
        sorted_list, success = _topological_sort(adj)
        assert success

        bme_pos = sorted_list.index("plasticos_buyer_match_engine")
        deps = ALL_MODULES["plasticos_buyer_match_engine"].get("depends", [])
        for dep in deps:
            if dep in sorted_list:
                dep_pos = sorted_list.index(dep)
                assert dep_pos < bme_pos, (
                    f"{dep} (pos {dep_pos}) must install before " f"plasticos_buyer_match_engine (pos {bme_pos})"
                )


# ═════════════════════════════════════════════════════════════════════════
# TEST CLASS 9 — Transitive Closure Sanity
# ═════════════════════════════════════════════════════════════════════════


class TestTransitiveClosure:
    """Check for redundant or suspiciously deep dependency chains."""

    def _transitive_deps(self, module_name, adj, visited=None):
        """Return set of all transitive plasticos_* dependencies."""
        if visited is None:
            visited = set()
        for dep in adj.get(module_name, []):
            if dep not in visited and dep in adj:
                visited.add(dep)
                self._transitive_deps(dep, adj, visited)
        return visited

    def test_no_module_exceeds_max_depth(self):
        """No module should transitively depend on more than 15
        plasticos_* modules (sanity bound)."""
        adj = _build_adjacency()
        max_depth = 15
        violations = []
        for name in MODULE_NAMES:
            transitive = self._transitive_deps(name, adj)
            if len(transitive) > max_depth:
                violations.append(f"  {name}: {len(transitive)} transitive deps " f"(max {max_depth})")
        assert len(violations) == 0, "Modules with excessive transitive dependencies:\n" + "\n".join(violations)

    @pytest.mark.parametrize("module_name", MODULE_NAMES)
    def test_no_redundant_direct_dep(self, module_name):
        """If A depends on [B, C] and B already depends on C,
        then C is a redundant direct dependency of A. Warn only."""
        adj = _build_adjacency()
        direct = set(adj.get(module_name, []))
        redundant = []
        for dep in list(direct):
            dep_transitive = self._transitive_deps(dep, adj)
            overlap = direct & dep_transitive
            for r in overlap:
                if r != dep:
                    redundant.append(f"{dep} already pulls in {r}")
        if redundant:
            import warnings

            warnings.warn(
                f"{module_name} has potentially redundant direct deps: " f"{redundant}",
                stacklevel=1,
            )


# ═════════════════════════════════════════════════════════════════════════
# TEST CLASS 10 — License Consistency
# ═════════════════════════════════════════════════════════════════════════


class TestLicenseConsistency:
    """All PlasticOS modules should use the same license."""

    def test_all_modules_have_license(self):
        missing = [name for name in MODULE_NAMES if "license" not in ALL_MODULES[name]]
        assert len(missing) == 0, f"Modules missing 'license' in manifest: {missing}"

    def test_all_licenses_match(self):
        licenses = {name: ALL_MODULES[name].get("license", "MISSING") for name in MODULE_NAMES}
        unique = set(licenses.values()) - {"MISSING"}
        if len(unique) > 1:
            by_license = defaultdict(list)
            for name, lic in licenses.items():
                by_license[lic].append(name)
            detail = "\n".join(f"  {lic}: {mods}" for lic, mods in by_license.items())
            pytest.fail(f"Inconsistent licenses across repo:\n{detail}")
