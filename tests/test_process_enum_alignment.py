"""Drift-prevention tests for process_type enum alignment.

Ensures all layers referencing process types stay in sync:
  1. facility_profile.py     (Odoo Selection field)
  2. process_codes.py        (canonical Python registry)
  3. matcher.py              (Gate 9 MFI compatibility)
  4. graph_service.py        (Cypher process-type scoring)

Pattern follows test_form_enum_alignment.py from PR #23.
"""

import ast
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


def _get_process_codes_from_registry() -> set[str]:
    """Extract PROCESS_CODES from the canonical registry."""
    registry_path = REPO_ROOT / "plasticos_facility_profile" / "process_codes.py"
    assert registry_path.exists(), f"Registry not found: {registry_path}"

    source = registry_path.read_text()
    tree = ast.parse(source)

    for node in tree.body:
        # Handle annotated assignment: PROCESS_CODES: tuple[str, ...] = (...)
        if isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name) and node.target.id == "PROCESS_CODES":
                if isinstance(node.value, ast.Tuple):
                    return {elt.value for elt in node.value.elts if isinstance(elt, ast.Constant)}
        # Handle regular assignment: PROCESS_CODES = (...)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "PROCESS_CODES":
                    if isinstance(node.value, ast.Tuple):
                        return {elt.value for elt in node.value.elts if isinstance(elt, ast.Constant)}
    raise AssertionError("PROCESS_CODES not found in registry")


def _get_mfi_ranges_from_registry() -> set[str]:
    """Extract MFI_RANGES keys from the canonical registry."""
    registry_path = REPO_ROOT / "plasticos_facility_profile" / "process_codes.py"
    source = registry_path.read_text()
    tree = ast.parse(source)

    for node in tree.body:
        # Handle annotated assignment: MFI_RANGES: dict[...] = {...}
        if isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name) and node.target.id == "MFI_RANGES":
                if isinstance(node.value, ast.Dict):
                    return {k.value for k in node.value.keys if isinstance(k, ast.Constant)}
        # Handle regular assignment: MFI_RANGES = {...}
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "MFI_RANGES":
                    if isinstance(node.value, ast.Dict):
                        return {k.value for k in node.value.keys if isinstance(k, ast.Constant)}
    raise AssertionError("MFI_RANGES not found in registry")


class TestProcessEnumAlignment:
    """Verify process_type codes are aligned across all layers."""

    def test_registry_has_codes(self):
        """Registry must define at least the core process types."""
        registry_codes = _get_process_codes_from_registry()
        core_codes = {"injection", "extrusion", "blow_mold", "compounding"}
        assert core_codes.issubset(registry_codes), f"Missing core codes: {core_codes - registry_codes}"

    def test_mfi_ranges_cover_all_codes(self):
        """MFI_RANGES must have an entry for every PROCESS_CODE."""
        all_codes = _get_process_codes_from_registry()
        mfi_codes = _get_mfi_ranges_from_registry()
        missing = all_codes - mfi_codes
        assert not missing, f"MFI_RANGES missing entries for: {missing}"

    def test_facility_profile_imports_registry(self):
        """facility_profile.py must import PROCESS_SELECTION from registry."""
        fp_path = REPO_ROOT / "plasticos_facility_profile" / "models" / "facility_profile.py"
        assert fp_path.exists(), f"File not found: {fp_path}"

        source = fp_path.read_text()
        assert "plasticos_facility_profile.process_codes import" in source, (
            "facility_profile.py does not import from process_codes registry."
        )
        assert "PROCESS_SELECTION" in source, "facility_profile.py does not use PROCESS_SELECTION"

    def test_matcher_imports_registry(self):
        """matcher.py must import check_mfi_compatibility from registry."""
        matcher_path = REPO_ROOT / "plasticos_buyer_match_engine" / "models" / "matcher.py"
        assert matcher_path.exists(), f"File not found: {matcher_path}"

        source = matcher_path.read_text()
        assert "plasticos_facility_profile.process_codes import" in source, (
            "matcher.py does not import from process_codes registry."
        )
        assert "check_mfi_compatibility" in source, "matcher.py does not use check_mfi_compatibility"

    def test_no_hardcoded_process_literals_in_matcher(self):
        """matcher.py must not contain hardcoded process type string literals."""
        matcher_path = REPO_ROOT / "plasticos_buyer_match_engine" / "models" / "matcher.py"
        source = matcher_path.read_text()

        registry_codes = _get_process_codes_from_registry()
        for code in registry_codes:
            pattern = rf'["\']({code})["\']'
            matches = re.findall(pattern, source)
            assert not matches, (
                f"matcher.py contains hardcoded process literal '{code}'. Use process_codes registry instead."
            )

    def test_graph_service_process_alignment(self):
        """graph_service.py Cypher queries must use registry-aligned process codes."""
        gs_path = REPO_ROOT / "plasticos_buyer_match_engine" / "models" / "graph_service.py"
        if not gs_path.exists():
            pytest.skip("graph_service.py not found")

        source = gs_path.read_text()
        registry_codes = _get_process_codes_from_registry()

        cypher_pattern = r"process_type\s*=\s*['\"](\w+)['\"]"
        cypher_matches = set(re.findall(cypher_pattern, source, re.IGNORECASE))

        if cypher_matches:
            invalid = cypher_matches - registry_codes
            msg = (
                f"graph_service.py Cypher uses process codes not in registry: {invalid}. Valid codes: {registry_codes}"
            )
            assert not invalid, msg
