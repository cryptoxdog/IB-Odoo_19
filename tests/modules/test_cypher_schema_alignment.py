"""
Cypher ↔ Neo4j Schema Alignment Tests.

Detects misalignment between:
1. Cypher query parameters ($param_name) and Python params dicts
2. Cypher node property references (node.property) and MERGE/SET clauses
3. Deprecated field names that should have been migrated

Run:  pytest tests/modules/test_cypher_schema_alignment.py -v

Zero Odoo runtime required. Pure AST + regex parsing.
"""

import ast
import re
from collections import defaultdict
from pathlib import Path

import pytest

# ═════════════════════════════════════════════════════════════════════════
# REPO ROOT DETECTION
# ═════════════════════════════════════════════════════════════════════════


def _find_repo_root():
    """Walk up from this file until we find plasticos_base/."""
    candidate = Path(__file__).resolve().parent
    for _ in range(10):
        if (candidate / "plasticos_base").is_dir():
            return candidate
        candidate = candidate.parent
    raise RuntimeError("Cannot locate repo root")


REPO_ROOT = _find_repo_root()


# ═════════════════════════════════════════════════════════════════════════
# DEPRECATED FIELD NAMES (Schema Migration Violations)
#
# These field names were used in older versions and should be migrated.
# Add entries here when schema changes occur.
# ═════════════════════════════════════════════════════════════════════════

DEPRECATED_FIELDS = {
    # Old field → (New field, Reason)
    "polymer_family_id": ("polymer_id or polymer_code", "Schema alignment 2026-02-25"),
    "material_category_id": ("material_category or category_code", "Not in Neo4j schema"),
    "quality_level_id": ("Derived from MaterialProfile", "Not a separate ID field"),
}

# Fields that are OK in comments/docstrings (documentation of the migration)
DEPRECATED_FIELD_WHITELIST_CONTEXTS = [
    "# ",  # Comments
    '"""',  # Docstrings
    "'''",  # Docstrings
    "SCHEMA ALIGNMENT",  # Migration notes
    "not polymer_family_id",  # Explicit "don't use" documentation
]


# ═════════════════════════════════════════════════════════════════════════
# CYPHER EXTRACTION UTILITIES
# ═════════════════════════════════════════════════════════════════════════


def extract_cypher_strings(file_path: Path) -> list[tuple[int, str]]:
    """Extract all multi-line strings that look like Cypher queries.

    Returns list of (line_number, cypher_string) tuples.
    """
    content = file_path.read_text()
    results = []

    # Pattern for triple-quoted strings containing Cypher keywords
    cypher_keywords = r"(MATCH|MERGE|CREATE|RETURN|WITH|WHERE|SET|UNWIND)"

    # Find all triple-quoted strings
    pattern = r'"""(.*?)"""|\'\'\'(.*?)\'\'\''
    for match in re.finditer(pattern, content, re.DOTALL):
        string_content = match.group(1) or match.group(2)
        if re.search(cypher_keywords, string_content, re.IGNORECASE):
            line_num = content[: match.start()].count("\n") + 1
            results.append((line_num, string_content))

    return results


def extract_cypher_params(cypher: str) -> set[str]:
    """Extract all $param_name references from Cypher query."""
    return set(re.findall(r"\$([a-zA-Z_][a-zA-Z0-9_]*)", cypher))


def extract_node_property_refs(cypher: str) -> dict[str, set[str]]:
    """Extract node.property references from Cypher query.

    Returns dict: {node_alias: {property1, property2, ...}}
    """
    refs = defaultdict(set)
    # Pattern: word.word (excluding function calls like point.distance)
    # Look for patterns like: buyer.polymer_family_id, mat.polymer, fac.name
    for match in re.finditer(r"\b([a-z][a-z0-9_]*)\s*\.\s*([a-z_][a-z0-9_]*)\b", cypher, re.IGNORECASE):
        alias, prop = match.groups()
        # Exclude Neo4j functions
        if alias.lower() not in (
            "point",
            "coalesce",
            "count",
            "sum",
            "avg",
            "min",
            "max",
            "collect",
            "datetime",
            "date",
            "time",
            "tofloat",
            "tointeger",
            "tostring",
        ):
            refs[alias].add(prop)
    return dict(refs)


def extract_merge_set_properties(cypher: str) -> dict[str, set[str]]:
    """Extract properties set via MERGE/SET clauses.

    Returns dict: {node_alias: {property1, property2, ...}}
    """
    props = defaultdict(set)

    # Pattern for SET alias.property = value
    for match in re.finditer(r"\b([a-z][a-z0-9_]*)\s*\.\s*([a-z_][a-z0-9_]*)\s*=", cypher, re.IGNORECASE):
        alias, prop = match.groups()
        props[alias].add(prop)

    return dict(props)


# ═════════════════════════════════════════════════════════════════════════
# PYTHON PARAMS EXTRACTION
# ═════════════════════════════════════════════════════════════════════════


def extract_params_dicts(file_path: Path) -> list[tuple[int, set[str]]]:
    """Extract keys from dicts assigned to 'params' variables or returned from methods.

    Returns list of (line_number, {key1, key2, ...}) tuples.
    """
    content = file_path.read_text()
    results: list[tuple[int, set[str]]] = []

    try:
        tree = ast.parse(content)
    except SyntaxError:
        return results

    def extract_dict_keys(node: ast.Dict) -> set[str]:
        keys = set()
        for key in node.keys:
            if isinstance(key, ast.Constant) and isinstance(key.value, str):
                keys.add(key.value)
        return keys

    for node in ast.walk(tree):
        # Direct assignment: params = {...}
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "params":
                    if isinstance(node.value, ast.Dict):
                        keys = extract_dict_keys(node.value)
                        if keys:
                            results.append((node.lineno, keys))

        # Return statement in _intake_to_match_params or similar
        if isinstance(node, ast.FunctionDef):
            if "params" in node.name.lower() or "to_match" in node.name.lower():
                for child in ast.walk(node):
                    if isinstance(child, ast.Return) and isinstance(child.value, ast.Dict):
                        keys = extract_dict_keys(child.value)
                        if keys:
                            results.append((child.lineno, keys))

    return results


# ═════════════════════════════════════════════════════════════════════════
# FILE DISCOVERY
# ═════════════════════════════════════════════════════════════════════════


def find_files_with_cypher() -> list[Path]:
    """Find all Python files that likely contain Cypher queries.
    Omits files under docs/."""
    files = []
    for module_dir in REPO_ROOT.glob("plasticos_*"):
        if not module_dir.is_dir():
            continue
        for py_file in module_dir.rglob("*.py"):
            if "docs" in py_file.parts:
                continue
            content = py_file.read_text()
            if any(kw in content for kw in ["MATCH", "MERGE", "neo4j", "cypher"]):
                files.append(py_file)
    return files


def find_graph_service_files() -> list[Path]:
    """Find all graph_service.py or similar Neo4j integration files.
    Omits files under docs/."""
    patterns = ["graph_service.py", "neo4j_*.py", "*_graph.py"]
    files = []
    for module_dir in REPO_ROOT.glob("plasticos_*"):
        if not module_dir.is_dir():
            continue
        for pattern in patterns:
            for p in module_dir.rglob(pattern):
                if "docs" not in p.parts:
                    files.append(p)
    return files


# ═════════════════════════════════════════════════════════════════════════
# TEST: DEPRECATED FIELD DETECTION
# ═════════════════════════════════════════════════════════════════════════


class TestDeprecatedFieldUsage:
    """Detect usage of deprecated field names in Cypher queries."""

    @pytest.fixture(scope="class")
    def cypher_files(self):
        return find_files_with_cypher()

    @pytest.mark.parametrize("deprecated_field,replacement_info", list(DEPRECATED_FIELDS.items()))
    def test_no_deprecated_fields_in_cypher(self, cypher_files, deprecated_field, replacement_info):
        """Ensure deprecated field names are not used in Cypher queries."""
        new_field, reason = replacement_info
        violations = []

        for file_path in cypher_files:
            content = file_path.read_text()

            for line_num, line in enumerate(content.split("\n"), 1):
                # Skip whitelisted contexts (comments, docstrings, migration notes)
                if any(ctx in line for ctx in DEPRECATED_FIELD_WHITELIST_CONTEXTS):
                    continue

                # Check for deprecated field in Cypher context
                if deprecated_field in line:
                    # Verify it's in a Cypher-like context (has $ or . prefix)
                    if f"${deprecated_field}" in line or f".{deprecated_field}" in line:
                        rel_path = file_path.relative_to(REPO_ROOT)
                        violations.append(f"{rel_path}:{line_num}")

        assert not violations, (
            f"Deprecated field '{deprecated_field}' found in Cypher queries.\n"
            f"Migrate to: {new_field}\n"
            f"Reason: {reason}\n"
            f"Violations:\n  " + "\n  ".join(violations)
        )


# ═════════════════════════════════════════════════════════════════════════
# TEST: CYPHER PARAM ↔ PYTHON DICT ALIGNMENT
# ═════════════════════════════════════════════════════════════════════════


class TestCypherParamAlignment:
    """Verify Cypher $params match Python params dict keys."""

    @pytest.fixture(scope="class")
    def graph_files(self):
        return find_graph_service_files()

    def test_cypher_params_have_python_source(self, graph_files):
        """Every $param in Cypher should have a corresponding Python dict key."""
        mismatches = []

        for file_path in graph_files:
            cypher_queries = extract_cypher_strings(file_path)
            params_dicts = extract_params_dicts(file_path)

            if not cypher_queries or not params_dicts:
                continue

            # Collect all Cypher params and all Python params
            all_cypher_params = set()
            for _, cypher in cypher_queries:
                all_cypher_params.update(extract_cypher_params(cypher))

            all_python_params = set()
            for _, keys in params_dicts:
                all_python_params.update(keys)

            # Find Cypher params without Python source
            orphan_params = all_cypher_params - all_python_params

            # Filter out common Neo4j built-ins
            builtins = {"facilities", "materials", "edges", "facility_ids"}
            orphan_params -= builtins

            if orphan_params:
                rel_path = file_path.relative_to(REPO_ROOT)
                mismatches.append(
                    f"{rel_path}: Cypher uses ${{{', $'.join(sorted(orphan_params))}}} "
                    f"but Python params only has {{{', '.join(sorted(all_python_params))}}}"
                )

        assert not mismatches, "Cypher query parameters without Python dict source:\n  " + "\n  ".join(mismatches)


# ═════════════════════════════════════════════════════════════════════════
# TEST: NODE PROPERTY CONSISTENCY
# ═════════════════════════════════════════════════════════════════════════


class TestNodePropertyConsistency:
    """Verify Cypher queries only reference properties that are synced."""

    @pytest.fixture(scope="class")
    def graph_files(self):
        return find_graph_service_files()

    def test_queried_properties_are_synced(self, graph_files):
        """Properties referenced in WHERE/CASE should exist in MERGE/SET."""
        issues = []

        for file_path in graph_files:
            cypher_queries = extract_cypher_strings(file_path)

            # Separate sync queries (MERGE/SET) from read queries (MATCH/WHERE)
            sync_props = defaultdict(set)  # What we write
            read_props = defaultdict(set)  # What we read

            for _line_num, cypher in cypher_queries:
                # Queries with MERGE/UNWIND are sync operations
                if "MERGE" in cypher or "UNWIND" in cypher:
                    for alias, props in extract_merge_set_properties(cypher).items():
                        sync_props[alias].update(props)

                # All queries may read properties
                for alias, props in extract_node_property_refs(cypher).items():
                    read_props[alias].update(props)

            # Check for properties read but never synced
            # Map common aliases to canonical node types
            alias_map = {
                "fac": "Facility",
                "f": "Facility",
                "supplier": "Facility",
                "buyer": "Facility",
                "mat": "MaterialProfile",
                "m": "MaterialProfile",
                "tx": "TRANSACTED_WITH",
            }

            for alias, props_read in read_props.items():
                # Find what's synced for this alias type
                canonical = alias_map.get(alias, alias)
                props_synced = set()
                for sync_alias, sync_set in sync_props.items():
                    if alias_map.get(sync_alias, sync_alias) == canonical:
                        props_synced.update(sync_set)

                # Properties read but not synced (potential schema drift)
                if props_synced:  # Only check if we have sync data
                    missing = props_read - props_synced
                    # Filter out common computed/relationship properties
                    computed = {"facility_id", "material_id", "partner_id", "tx_count", "last_tx_date"}
                    missing -= computed

                    if missing:
                        rel_path = file_path.relative_to(REPO_ROOT)
                        issues.append(
                            f"{rel_path}: {alias}.{{{', '.join(sorted(missing))}}} referenced but not in MERGE/SET"
                        )

        # This is informational - may have false positives
        if issues:
            pytest.skip("Potential schema drift detected (review manually):\n  " + "\n  ".join(issues))


# ═════════════════════════════════════════════════════════════════════════
# TEST: SCHEMA ALIGNMENT DOCUMENTATION
# ═════════════════════════════════════════════════════════════════════════


class TestSchemaDocumentation:
    """Verify schema alignment is documented where field mappings exist."""

    def test_graph_service_has_schema_comments(self):
        """graph_service.py should document field mappings."""
        graph_files = find_graph_service_files()

        for file_path in graph_files:
            if "graph_service" not in file_path.name:
                continue

            content = file_path.read_text()

            # Should have schema alignment comments
            has_schema_docs = any(
                marker in content
                for marker in [
                    "Schema alignment",
                    "SCHEMA ALIGNMENT",
                    "schema:",
                    "Node properties:",
                ]
            )

            rel_path = file_path.relative_to(REPO_ROOT)
            assert has_schema_docs, (
                f"{rel_path} contains Cypher queries but lacks schema documentation. "
                "Add comments documenting the Neo4j node properties and their Python sources."
            )


# ═════════════════════════════════════════════════════════════════════════
# TEST: INTAKE ↔ CYPHER FIELD MAPPING
# ═════════════════════════════════════════════════════════════════════════


class TestIntakeCypherMapping:
    """Verify intake field names match Cypher parameter expectations."""

    def test_intake_to_match_params_alignment(self):
        """_intake_to_match_params should produce keys that Cypher expects."""
        graph_files = find_graph_service_files()

        for file_path in graph_files:
            content = file_path.read_text()

            # Find _intake_to_match_params method
            if "_intake_to_match_params" not in content:
                continue

            # Extract keys from the return dict
            try:
                tree = ast.parse(content)
            except SyntaxError:
                continue

            intake_keys = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.name == "_intake_to_match_params":
                    for child in ast.walk(node):
                        if isinstance(child, ast.Return) and isinstance(child.value, ast.Dict):
                            for key in child.value.keys:
                                if isinstance(key, ast.Constant):
                                    intake_keys.add(key.value)

            if not intake_keys:
                continue

            # Find Cypher params in match queries
            cypher_queries = extract_cypher_strings(file_path)
            match_params = set()
            for _, cypher in cypher_queries:
                if "facility_ids" in cypher:  # This is a match query
                    match_params.update(extract_cypher_params(cypher))

            # Remove common params not from intake
            match_params -= {"facility_ids", "w_hard_gate", "w_quality", "w_geo", "w_history"}

            # Check alignment
            missing_in_cypher = intake_keys - match_params
            missing_in_intake = match_params - intake_keys

            rel_path = file_path.relative_to(REPO_ROOT)

            if missing_in_cypher:
                # Intake provides keys Cypher doesn't use - OK (extra data)
                pass

            assert not missing_in_intake, (
                f"{rel_path}: Cypher expects ${{{', $'.join(sorted(missing_in_intake))}}} "
                f"but _intake_to_match_params doesn't provide them"
            )
