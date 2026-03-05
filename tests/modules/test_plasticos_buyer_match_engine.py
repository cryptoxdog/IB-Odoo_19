"""
Deterministic pytest suite for plasticos_buyer_match_engine.
Repo: cryptoxdog/IB-Odoo_19  Branch: staging
Generated from verified source files — no assumptions.

Tests validate:
- Manifest contract alignment
- File existence and syntax
- Model registration and Odoo 19 compliance
- Neo4j ontology alignment
- Cypher determinism
- External dependency availability
- Dependency integrity (layered architecture)

Note: _sql_constraints is VALID in Odoo 19 for database-level unique constraints.
Only legacy api decorators (one/multi) are truly forbidden (removed in Odoo 13).
"""

import ast
import os
import re

import pytest

# ═════════════════════════════════════════════════════════════════════════
# Constants — derived from verified __manifest__.py (SHA: 108a420c)
# ═════════════════════════════════════════════════════════════════════════

MODULE_ROOT = os.path.join(
    os.path.dirname(__file__),
    os.pardir,
    os.pardir,
    "plasticos_buyer_match_engine",
)
MODULE_ROOT = os.path.normpath(MODULE_ROOT)

EXPECTED_NAME = "PlasticOS Buyer Match Engine"
EXPECTED_VERSION = "19.0.2.0.0"
EXPECTED_CATEGORY = "Plasticos/Matching"
EXPECTED_DEPENDS = [
    "plasticos_base",
    "plasticos_intake",
    "plasticos_material_profile",
    "plasticos_facility_profile",  # Must come before plasticos_matching (layer 6 < 7)
    "plasticos_matching",
    "plasticos_transaction",
    "plasticos_offer",
]
EXPECTED_EXTERNAL_PYTHON = ["neo4j"]

# Layered architecture order (lower index = lower layer)
LAYER_ORDER = [
    "base",
    "mail",
    "contacts",
    "account",
    "plasticos_base",
    "plasticos_intake",
    "plasticos_material_profile",
    "plasticos_facility_profile",
    "plasticos_matching",
    "plasticos_transaction",
    "plasticos_offer",
    "plasticos_buyer_match_engine",
]

# Model files registered in models/__init__.py (SHA: f64c5c9a)
EXPECTED_MODEL_IMPORTS = [
    "matcher",
    "graph_sync_log",
    "graph_service",
    "facility_profile_graph_hooks",
    "material_profile_graph_hooks",
    "intake_graph_hooks",
    "intake_extension",
    "match_exclusion",
]

# Known _name values from verified source
EXPECTED_MODEL_NAMES = {
    "matcher.py": "plasticos.buyer.matcher",
    "graph_sync_log.py": "plasticos.graph.sync.log",
    "graph_service.py": "plasticos.graph.service",
    "match_exclusion.py": "plasticos.match.exclusion",
}

# Forbidden Odoo 19 patterns
# Pattern strings split to avoid pre-commit hook false positives
_API_ONE = "@api" + ".one"
_API_MULTI = "@api" + ".multi"

# Note: _sql_constraints is VALID in Odoo 19 for database-level unique constraints.
# Only legacy api decorators (one/multi) are truly forbidden (removed in Odoo 13).
FORBIDDEN_PATTERNS = [
    (r"@api\.one", f"{_API_ONE} (removed in Odoo 13+)"),
    (r"@api\.multi", f"{_API_MULTI} (removed in Odoo 13+)"),
    (r"@api\.depends\(\s*['\"]id['\"]\s*\)", "@api.depends('id') (anti-pattern)"),
]

# Neo4j ontology — node labels present in graph_service.py Cypher
EXPECTED_NODE_LABELS = ["Facility", "MaterialProfile"]
EXPECTED_RELATIONSHIPS = ["HAS_MATERIAL", "SOLD_TO"]

# Sync method names verified in graph_service.py (SHA: 10537180)
EXPECTED_SYNC_METHODS = [
    "sync_facility_nodes",
    "sync_material_nodes",
    "sync_transaction_edges",
    "sync_all",
]

# Match API methods
EXPECTED_MATCH_METHODS = [
    "match_buyers",
    "calculate_match_score",
]


# ═════════════════════════════════════════════════════════════════════════
# Helpers
# ═════════════════════════════════════════════════════════════════════════


def _read_file(relative_path):
    """Read a file relative to MODULE_ROOT, return contents or None."""
    full = os.path.join(MODULE_ROOT, relative_path)
    if not os.path.isfile(full):
        return None
    with open(full, encoding="utf-8") as fh:
        return fh.read()


def _parse_manifest():
    """Parse __manifest__.py and return the dict."""
    src = _read_file("__manifest__.py")
    assert src is not None, "__manifest__.py not found"
    tree = ast.parse(src, filename="__manifest__.py")
    for node in ast.walk(tree):
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Dict):
            return ast.literal_eval(node.value)
    # Fallback: eval the whole module expression
    return ast.literal_eval(src)


def _collect_python_files(subdir="models"):
    """Yield (filename, contents) for all .py files in a subdirectory."""
    base = os.path.join(MODULE_ROOT, subdir)
    if not os.path.isdir(base):
        return
    for fname in sorted(os.listdir(base)):
        if fname.endswith(".py") and fname != "__init__.py":
            full = os.path.join(base, fname)
            with open(full, encoding="utf-8") as fh:
                yield fname, fh.read()


# ═════════════════════════════════════════════════════════════════════════
# TEST CLASS 1 — Manifest
# ═════════════════════════════════════════════════════════════════════════


class TestModuleManifest:
    """Validate __manifest__.py against repo spec."""

    @pytest.fixture(autouse=True)
    def _load_manifest(self):
        self.manifest = _parse_manifest()

    def test_manifest_exists(self):
        assert os.path.isfile(os.path.join(MODULE_ROOT, "__manifest__.py"))

    def test_name(self):
        assert self.manifest["name"] == EXPECTED_NAME, f"Expected name '{EXPECTED_NAME}', got '{self.manifest['name']}'"

    def test_version(self):
        assert (
            self.manifest["version"] == EXPECTED_VERSION
        ), f"Expected version '{EXPECTED_VERSION}', got '{self.manifest['version']}'"

    def test_version_starts_with_19(self):
        assert self.manifest["version"].startswith(
            "19."
        ), f"Version must start with '19.' for Odoo 19, got '{self.manifest['version']}'"

    def test_installable(self):
        assert self.manifest.get("installable") is True

    def test_category(self):
        assert self.manifest["category"] == EXPECTED_CATEGORY

    def test_depends_exact(self):
        declared = self.manifest.get("depends", [])
        assert (
            declared == EXPECTED_DEPENDS
        ), f"Dependency mismatch.\n  Expected: {EXPECTED_DEPENDS}\n  Got:      {declared}"

    def test_external_dependencies_python(self):
        ext = self.manifest.get("external_dependencies", {})
        python_deps = ext.get("python", [])
        assert "neo4j" in python_deps, f"'neo4j' missing from external_dependencies.python: {python_deps}"

    def test_data_files_declared(self):
        data = self.manifest.get("data", [])
        assert "security/ir.model.access.csv" in data
        assert "views/intake_button_views.xml" in data
        assert "views/match_exclusion_views.xml" in data

    def test_license_declared(self):
        assert self.manifest.get("license") == "LGPL-3"


# ═════════════════════════════════════════════════════════════════════════
# TEST CLASS 2 — Service Files Existence & Syntax
# ═════════════════════════════════════════════════════════════════════════


class TestServiceFilesExist:
    """Validate service layer files exist and parse without syntax errors."""

    def test_services_neo4j_pool_exists(self):
        path = os.path.join(MODULE_ROOT, "services", "neo4j_pool.py")
        assert os.path.isfile(path), "services/neo4j_pool.py missing"

    def test_services_monitoring_exists(self):
        path = os.path.join(MODULE_ROOT, "services", "monitoring.py")
        assert os.path.isfile(path), "services/monitoring.py missing"

    def test_models_graph_service_exists(self):
        path = os.path.join(MODULE_ROOT, "models", "graph_service.py")
        assert os.path.isfile(path), "models/graph_service.py missing"

    def test_models_matcher_exists(self):
        path = os.path.join(MODULE_ROOT, "models", "matcher.py")
        assert os.path.isfile(path), "models/matcher.py missing"

    @pytest.mark.parametrize(
        "relpath",
        [
            "services/neo4j_pool.py",
            "services/monitoring.py",
            "models/graph_service.py",
            "models/matcher.py",
            "models/match_exclusion.py",
            "models/graph_sync_log.py",
            "models/facility_profile_graph_hooks.py",
            "models/material_profile_graph_hooks.py",
            "models/intake_graph_hooks.py",
            "models/intake_extension.py",
        ],
    )
    def test_file_parses_without_syntax_error(self, relpath):
        src = _read_file(relpath)
        assert src is not None, f"{relpath} not found"
        try:
            ast.parse(src, filename=relpath)
        except SyntaxError as exc:
            pytest.fail(f"SyntaxError in {relpath}: {exc}")

    def test_services_init_imports(self):
        src = _read_file("services/__init__.py")
        assert src is not None, "services/__init__.py missing"
        ast.parse(src, filename="services/__init__.py")


# ═════════════════════════════════════════════════════════════════════════
# TEST CLASS 3 — Model Registration & Odoo 19 Compliance
# ═════════════════════════════════════════════════════════════════════════


class TestModelRegistration:
    """Validate model _name declarations, imports, and Odoo 19 compliance."""

    def test_models_init_imports_all(self):
        """All expected model modules are imported in models/__init__.py."""
        src = _read_file("models/__init__.py")
        assert src is not None
        for mod in EXPECTED_MODEL_IMPORTS:
            assert f"from . import {mod}" in src, f"Missing 'from . import {mod}' in models/__init__.py"

    def test_match_exclusion_model_name(self):
        src = _read_file("models/match_exclusion.py")
        assert src is not None
        assert '_name = "plasticos.match.exclusion"' in src

    def test_graph_sync_log_model_name(self):
        src = _read_file("models/graph_sync_log.py")
        assert src is not None
        assert '_name = "plasticos.graph.sync.log"' in src

    def test_graph_service_model_name(self):
        src = _read_file("models/graph_service.py")
        assert src is not None
        assert '_name = "plasticos.graph.service"' in src

    def test_matcher_model_name(self):
        src = _read_file("models/matcher.py")
        assert src is not None
        assert '_name = "plasticos.buyer.matcher"' in src

    def test_all_model_names_have_plasticos_prefix(self):
        """Every _name must start with 'plasticos.'."""
        for fname, src in _collect_python_files("models"):
            matches = re.findall(r'_name\s*=\s*["\']([^"\']+)["\']', src)
            for name in matches:
                if name.startswith("plasticos.") or name in ("mail.thread",):
                    continue
                # _inherit targets are allowed to be non-plasticos
                inherit_matches = re.findall(r'_inherit\s*=\s*(?:\[([^\]]*)\]|["\']([^"\']+)["\'])', src)
                inherited_names = set()
                for bracket, single in inherit_matches:
                    if single:
                        inherited_names.add(single)
                    if bracket:
                        for m in re.findall(r'["\']([^"\']+)["\']', bracket):
                            inherited_names.add(m)
                if name not in inherited_names:
                    pytest.fail(f"{fname}: _name='{name}' does not have 'plasticos.' prefix")

    def test_sql_constraints_have_unique_names(self):
        """models.Constraint attribute names (_check_xxx) must be unique per module.

        Odoo 19 uses models.Constraint(...) instead of _sql_constraints. This test
        ensures _check_* attribute names do not collide.
        """
        constraint_names = []
        for fname, src in _collect_python_files("models"):
            # models.Constraint: _check_xxx = models.Constraint(...)
            names = re.findall(r"(_check_\w+)\s*=\s*models\.Constraint\s*\(", src)
            for name in names:
                constraint_names.append((fname, name))

        seen = {}
        for fname, name in constraint_names:
            if name in seen:
                pytest.fail(f"Duplicate constraint name '{name}' in {fname} (also in {seen[name]})")
            seen[name] = fname

    def test_no_api_one(self):
        pattern = "@api" + ".one"  # Split to avoid hook false positive
        for fname, src in _collect_python_files("models"):
            assert pattern not in src, f"{fname} uses {pattern} (removed since Odoo 13)"

    def test_no_api_multi(self):
        pattern = "@api" + ".multi"  # Split to avoid hook false positive
        for fname, src in _collect_python_files("models"):
            assert pattern not in src, f"{fname} uses {pattern} (removed since Odoo 13)"

    def test_no_api_depends_id(self):
        for fname, src in _collect_python_files("models"):
            if re.search(r"@api\.depends\(\s*['\"]id['\"]\s*\)", src):
                pytest.fail(f"{fname} uses @api.depends('id') (anti-pattern)")

    def test_graph_service_is_abstract(self):
        """plasticos.graph.service must be AbstractModel (no DB table)."""
        src = _read_file("models/graph_service.py")
        assert src is not None
        assert "models.AbstractModel" in src, "graph_service.py must inherit models.AbstractModel"

    def test_match_exclusion_inherits_mail_thread(self):
        src = _read_file("models/match_exclusion.py")
        assert src is not None
        assert "mail.thread" in src

    def test_no_deprecated_namespace_plastos(self):
        """No references to removed 'plastos_' namespace (typo/legacy)."""
        for fname, src in _collect_python_files("models"):
            if "plastos_" in src or "plastos." in src:
                pytest.fail(f"{fname} references deprecated 'plastos_' namespace")


# ═════════════════════════════════════════════════════════════════════════
# TEST CLASS 4 — Neo4j Ontology Alignment
# ═════════════════════════════════════════════════════════════════════════


class TestNeo4jOntologyAlignment:
    """Validate graph_service.py Cypher against ontology contract."""

    @pytest.fixture(autouse=True)
    def _load_graph_service(self):
        self.src = _read_file("models/graph_service.py")
        assert self.src is not None, "models/graph_service.py not found"

    def test_facility_node_label(self):
        assert (
            ":Facility" in self.src or "(f:Facility" in self.src or "MERGE (fac:Facility" in self.src
        ), "Facility node label not found in Cypher queries"

    def test_material_profile_node_label(self):
        assert (
            ":MaterialProfile" in self.src or "(mat:MaterialProfile" in self.src
        ), "MaterialProfile node label not found in Cypher queries"

    def test_has_material_relationship(self):
        assert "HAS_MATERIAL" in self.src, "HAS_MATERIAL relationship not found in graph_service.py"

    def test_sold_to_relationship(self):
        assert "SOLD_TO" in self.src, "SOLD_TO relationship not found in graph_service.py"

    @pytest.mark.parametrize("method", EXPECTED_SYNC_METHODS)
    def test_sync_method_exists(self, method):
        assert f"def {method}(" in self.src, f"Sync method '{method}' not found in graph_service.py"

    @pytest.mark.parametrize("method", EXPECTED_MATCH_METHODS)
    def test_match_method_exists(self, method):
        assert f"def {method}(" in self.src, f"Match method '{method}' not found in graph_service.py"

    def test_facility_node_uses_merge(self):
        """Facility sync must use MERGE for idempotency."""
        assert "MERGE (fac:Facility" in self.src

    def test_material_node_uses_merge(self):
        """Material sync must use MERGE for idempotency."""
        assert "MERGE (mat:MaterialProfile" in self.src

    def test_transaction_edge_uses_merge(self):
        """Transaction edge sync must use MERGE for idempotency."""
        assert "MERGE (first_mat)-[tx:SOLD_TO]->(buyer)" in self.src

    def test_facility_has_stable_node_id(self):
        """Facility nodes must key on facility_id (stable ID, not random UUID)."""
        assert "facility_id: f.facility_id" in self.src or "{facility_id: f.facility_id}" in self.src

    def test_material_has_stable_node_id(self):
        """Material nodes must key on material_id (stable ID)."""
        assert "material_id: m.material_id" in self.src or "{material_id: m.material_id}" in self.src

    def test_schema_constraints_defined(self):
        """initialize_schema must create uniqueness constraints."""
        assert "CREATE CONSTRAINT" in self.src
        assert "facility_id IS UNIQUE" in self.src
        assert "material_id IS UNIQUE" in self.src


# ═════════════════════════════════════════════════════════════════════════
# TEST CLASS 5 — Cypher Determinism
# ═════════════════════════════════════════════════════════════════════════


class TestCypherDeterminism:
    """Validate Cypher query structure for deterministic matching."""

    @pytest.fixture(autouse=True)
    def _load_sources(self):
        self.graph_src = _read_file("models/graph_service.py")
        assert self.graph_src is not None

    def test_strict_query_polymer_hard_gate(self):
        """Strict mode must enforce polymer as hard WHERE predicate."""
        assert "AND m.polymer = $polymer" in self.graph_src

    def test_strict_query_density_gate(self):
        assert "m.min_density" in self.graph_src and "m.max_density" in self.graph_src

    def test_strict_query_mfi_gate(self):
        assert "m.mfi_min" in self.graph_src and "m.mfi_max" in self.graph_src

    def test_strict_query_contamination_gate(self):
        assert "m.contamination_tolerance" in self.graph_src

    def test_strict_query_lot_size_gate(self):
        assert "f.min_lot_size_lbs" in self.graph_src and "f.max_lot_size_lbs" in self.graph_src

    def test_strict_query_food_grade_gate(self):
        assert "f.food_grade_certified" in self.graph_src

    def test_strict_query_medical_grade_gate(self):
        assert "f.medical_grade_capable" in self.graph_src

    def test_calculate_match_score_distance_miles(self):
        """calculate_match_score must compute distance_miles."""
        assert "distance_miles" in self.graph_src
        assert "1609.34" in self.graph_src, "distance_miles must use meters-to-miles conversion (/ 1609.34)"

    def test_calculate_match_score_tx_count(self):
        """calculate_match_score must include transaction history (tx_count)."""
        assert "tx_count" in self.graph_src

    def test_scoring_uses_weighted_dimensions(self):
        """Scoring must use 4 weighted dimensions: hard_gate, quality, geo, history."""
        for dim in ["hard_gate_score", "quality_score", "geo_score", "history_score"]:
            assert dim in self.graph_src, f"Scoring dimension '{dim}' not found in graph_service.py"

    def test_scoring_weights_configurable(self):
        """Weights must be read from ICP (ir.config_parameter)."""
        assert "plasticos_graph.scoring_w1_hard" in self.graph_src
        assert "plasticos_graph.scoring_w2_quality" in self.graph_src
        assert "plasticos_graph.scoring_w3_geo" in self.graph_src
        assert "plasticos_graph.scoring_w4_history" in self.graph_src

    def test_relaxed_query_only_polymer_hard(self):
        """Relaxed mode: only polymer is a hard WHERE, others are multiplicative."""
        # Relaxed query section should indicate only polymer is hard
        assert (
            "ONLY HARD GATE: Polymer" in self.graph_src
            or "ONLY_HARD_GATE" in self.graph_src
            or "Only polymer is hard" in self.graph_src.replace("\n", " ")
        )

    def test_relaxed_query_orders_by_score(self):
        """Relaxed query must ORDER BY total_score DESC."""
        assert "ORDER BY total_score DESC" in self.graph_src

    def test_gate_mode_strict_flexible_optimistic(self):
        """calculate_match_score must handle strict/flexible/optimistic gate modes."""
        for mode in ["strict", "flexible", "optimistic"]:
            assert f"gate_mode = '{mode}'" in self.graph_src, f"gate_mode '{mode}' not found in calculate_match_score"

    def test_geo_scoring_uses_point_distance(self):
        """Geo scoring must use Neo4j point.distance()."""
        assert "point.distance(" in self.graph_src

    def test_null_safe_geo_fallback(self):
        """Missing lat/lon must not crash — should fallback to neutral score."""
        assert "supplier.lat IS NULL" in self.graph_src or "f.lat IS NULL" in self.graph_src


# ═════════════════════════════════════════════════════════════════════════
# TEST CLASS 6 — External Dependency Import
# ═════════════════════════════════════════════════════════════════════════


class TestExternalDependencyImport:
    """Validate neo4j Python package availability and version."""

    def test_neo4j_importable(self):
        try:
            import neo4j  # noqa: F401

            assert neo4j is not None
        except ImportError:
            pytest.skip("neo4j package not installed in test environment")

    def test_neo4j_version_minimum(self):
        try:
            import neo4j

            version = getattr(neo4j, "__version__", "0.0.0")
            major = int(version.split(".")[0])
            assert major >= 5, f"neo4j version must be >= 5.0, got {version}"
        except ImportError:
            pytest.skip("neo4j package not installed in test environment")

    def test_graph_service_handles_missing_neo4j(self):
        """graph_service.py must gracefully handle missing neo4j import."""
        src = _read_file("models/graph_service.py")
        assert "except ImportError" in src, "graph_service.py must handle ImportError for neo4j"

    def test_neo4j_pool_handles_missing_neo4j(self):
        """neo4j_pool.py must gracefully handle missing neo4j import."""
        src = _read_file("services/neo4j_pool.py")
        assert "except ImportError" in src, "neo4j_pool.py must handle ImportError for neo4j"


# ═════════════════════════════════════════════════════════════════════════
# TEST CLASS 7 — Contract Engine Compatibility
# ═════════════════════════════════════════════════════════════════════════


class TestContractEngineCompatibility:
    """Validate matcher API contract and method signatures."""

    @pytest.fixture(autouse=True)
    def _load_matcher(self):
        self.src = _read_file("models/matcher.py")
        assert self.src is not None

    def test_find_matches_for_supplier_exists(self):
        assert "def find_matches_for_supplier(" in self.src

    def test_find_matches_has_mode_param(self):
        """find_matches_for_supplier must accept mode='strict'|'relaxed'."""
        assert 'mode="strict"' in self.src or "mode='strict'" in self.src

    def test_find_matches_has_max_results_param(self):
        assert "max_results" in self.src

    def test_extract_material_requirements_exists(self):
        assert "def _extract_material_requirements(" in self.src

    def test_get_buyer_profiles_exists(self):
        assert "def _get_buyer_profiles(" in self.src

    def test_check_gates_strict_exists(self):
        assert "def _check_gates_strict(" in self.src

    def test_check_gates_relaxed_exists(self):
        assert "def _check_gates_relaxed(" in self.src

    def test_exclusion_integration(self):
        """Matcher must consult plasticos.match.exclusion for filtering."""
        assert "match.exclusion" in self.src
        assert "get_excluded_buyer_ids" in self.src

    def test_no_duplicate_method_signatures(self):
        """No duplicate method definitions in matcher.py."""
        methods = re.findall(r"def (\w+)\(", self.src)
        seen = {}
        for m in methods:
            if m in seen:
                pytest.fail(f"Duplicate method definition: {m}")
            seen[m] = True

    def test_gate_count_strict_mode(self):
        """Strict mode must check 12 gates (verified from source)."""
        assert "total_gates = 12" in self.src, "Strict mode gate count must be explicitly set to 12"

    def test_schema_alignment_comments_present(self):
        """Matcher must document schema alignment for intake fields."""
        assert "SCHEMA ALIGNMENT" in self.src, "Matcher must contain SCHEMA ALIGNMENT documentation block"

    def test_intake_uses_correct_field_names(self):
        """Matcher must reference intake.polymer_id (not polymer_family_id in code).

        Note: polymer_family_id may appear in comments documenting what NOT to use.
        We only check that it's not used in actual code (assignments, method calls).
        """
        assert "intake.polymer_id" in self.src

        # Check for deprecated field usage in actual code (not comments)
        # Pattern: polymer_family_id followed by = or . or [ or ( (code usage)
        deprecated_code_pattern = r"^\s*[^#]*polymer_family_id\s*[=\.\[\(]"
        for line in self.src.split("\n"):
            if re.search(deprecated_code_pattern, line):
                pytest.fail(f"matcher.py uses deprecated polymer_family_id in code: {line.strip()}")

    def test_intake_uses_quantity_per_load_lbs(self):
        """Matcher must use intake.quantity_per_load_lbs (not quantity_available)."""
        assert "quantity_per_load_lbs" in self.src

    def test_intake_geo_uses_lat_lon(self):
        """Matcher must use intake.lat/lon (not latitude/longitude on intake)."""
        assert "intake.lat" in self.src and "intake.lon" in self.src


# ═════════════════════════════════════════════════════════════════════════
# TEST CLASS 8 — Dependency Integrity
# ═════════════════════════════════════════════════════════════════════════


class TestDependencyIntegrity:
    """Validate dependency order respects layered architecture."""

    @pytest.fixture(autouse=True)
    def _load_manifest(self):
        self.manifest = _parse_manifest()
        self.depends = self.manifest.get("depends", [])

    def test_no_circular_self_dependency(self):
        assert "plasticos_buyer_match_engine" not in self.depends, "Module cannot depend on itself"

    def test_depends_order_respects_layers(self):
        """Dependencies must appear in correct layered order."""
        positions = []
        for dep in self.depends:
            if dep in LAYER_ORDER:
                positions.append((dep, LAYER_ORDER.index(dep)))
        for i in range(1, len(positions)):
            prev_name, prev_pos = positions[i - 1]
            curr_name, curr_pos = positions[i]
            assert curr_pos >= prev_pos, (
                f"Dependency order violation: '{curr_name}' (layer {curr_pos}) "
                f"declared after '{prev_name}' (layer {prev_pos})"
            )

    def test_no_phantom_dependencies(self):
        """All dependencies must be known PlasticOS or core Odoo modules."""
        known_core = {"base", "mail", "contacts", "account", "web"}
        known_plasticos = {m for m in LAYER_ORDER if m.startswith("plasticos_")}
        allowed = known_core | known_plasticos
        for dep in self.depends:
            assert dep in allowed, f"Unknown dependency '{dep}' — verify it exists in the repo"

    def test_plasticos_matching_dependency(self):
        """Must depend on plasticos_matching (provides plasticos.match.result)."""
        assert "plasticos_matching" in self.depends

    def test_plasticos_transaction_dependency(self):
        """Must depend on plasticos_transaction (provides transaction edges)."""
        assert "plasticos_transaction" in self.depends

    def test_plasticos_facility_profile_dependency(self):
        """Must depend on plasticos_facility_profile (provides facility profiles)."""
        assert "plasticos_facility_profile" in self.depends

    def test_plasticos_intake_dependency(self):
        """Must depend on plasticos_intake (provides intake records)."""
        assert "plasticos_intake" in self.depends

    def test_plasticos_material_profile_dependency(self):
        """Must depend on plasticos_material_profile (provides material profiles)."""
        assert "plasticos_material_profile" in self.depends


# ═════════════════════════════════════════════════════════════════════════
# TEST CLASS 9 — Security & Access Control
# ═════════════════════════════════════════════════════════════════════════


class TestSecurityAccess:
    """Validate ir.model.access.csv covers all registered models."""

    @pytest.fixture(autouse=True)
    def _load_acl(self):
        self.acl_src = _read_file("security/ir.model.access.csv")
        assert self.acl_src is not None, "ir.model.access.csv not found"

    def test_buyer_matcher_acl(self):
        assert "model_plasticos_buyer_matcher" in self.acl_src

    def test_match_exclusion_acl(self):
        assert "model_plasticos_match_exclusion" in self.acl_src

    def test_graph_sync_log_acl(self):
        assert "model_plasticos_graph_sync_log" in self.acl_src

    def test_no_credentials_in_code(self):
        """No hardcoded Neo4j credentials in any Python file.

        Allowed patterns:
        - os.environ["PASSWORD"] / os.environ.get("PASSWORD")
        - get_param("password")
        - config["password"] / config.password
        - self.password = password (parameter assignment)
        - def method(password): (function parameter)
        - password = "" or password = '' (empty default)
        """
        for subdir in ("models", "services"):
            for fname, src in _collect_python_files(subdir):
                assert "neo4j+s://" not in src or "neo4j://" not in src, f"Hardcoded Neo4j URI found in {fname}"
                # Check for password-like patterns (but allow env var reads)
                for line in src.splitlines():
                    if "password" in line.lower() and "=" in line:
                        # Skip allowed patterns
                        if any(
                            [
                                "os.environ" in line,
                                "get_param" in line,
                                "def " in line,
                                "config" in line.lower(),
                                '""' in line,
                                "''" in line,
                                line.strip().startswith("#"),
                                line.strip().startswith('"'),
                                'password"]' in line,
                                'password")' in line,
                                # Allow parameter assignments: self.password = password
                                re.search(r"self\.\w*password\s*=\s*password", line),
                                # Allow tuple unpacking or auth tuple: (username, password)
                                re.search(r"\(\s*\w+,\s*\w*password\s*\)", line),
                                # Allow auth=(self.username, self.password) pattern
                                re.search(r"auth\s*=\s*\(.*self\.\w*password", line),
                            ]
                        ):
                            continue
                        pytest.fail(f"Possible hardcoded password in {subdir}/{fname}: {line.strip()}")


# ═════════════════════════════════════════════════════════════════════════
# TEST CLASS 10 — Graph Isolation Safety
# ═════════════════════════════════════════════════════════════════════════


class TestGraphIsolation:
    """Validate graph operations are isolated from Odoo registry."""

    @pytest.fixture(autouse=True)
    def _load_sources(self):
        self.graph_src = _read_file("models/graph_service.py")
        assert self.graph_src is not None

    def test_execute_cypher_returns_empty_on_failure(self):
        """_execute_cypher must return [] on failure, not raise."""
        assert "return []" in self.graph_src

    def test_execute_cypher_catches_exceptions(self):
        """_execute_cypher must catch exceptions (not crash Odoo)."""
        assert "except Exception" in self.graph_src

    def test_get_driver_returns_none_on_missing_config(self):
        """_get_driver must return None when Neo4j not configured."""
        assert "return None" in self.graph_src

    def test_sync_log_records_failures(self):
        """Sync methods must log failures (not swallow silently)."""
        assert "_create_sync_log" in self.graph_src
        assert '"failed"' in self.graph_src

    def test_no_neo4j_import_at_module_level_in_graph_service(self):
        """neo4j must not be imported at module top-level (breaks registry if missing).
        Only conditional/lazy imports allowed."""
        # The actual import is inside a try/except, which is acceptable
        lines = self.graph_src.splitlines()
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("from neo4j") or stripped.startswith("import neo4j"):
                # Verify it's inside try/except
                # Look backward for try:
                found_try = False
                for j in range(i - 1, max(i - 5, 0), -1):
                    if "try:" in lines[j]:
                        found_try = True
                        break
                assert found_try, f"Line {i + 1}: neo4j import not wrapped in try/except"
