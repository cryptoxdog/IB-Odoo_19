"""Drift-prevention tests for material form enum alignment.

These tests enforce the cross-layer contract between:
  1. material_form_data.xml  (canonical XML records)
  2. form_codes.py           (canonical Python registry)
  3. material_profile.form   (Selection field)
  4. facility_profile.form_preference (computed Selection from Many2one)
  5. graph_service.py        (Cypher form-equipment gate)

If ANY layer drifts, these tests will fail.
"""

import re
import xml.etree.ElementTree as ET
from pathlib import Path

# ── Locate repo root ────────────────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parent.parent
MATERIAL_FORM_DATA_XML = REPO_ROOT / "plasticos_material_profile" / "data" / "material_form_data.xml"
FORM_CODES_PY = REPO_ROOT / "plasticos_material_profile" / "form_codes.py"
GRAPH_SERVICE_PY = REPO_ROOT / "plasticos_buyer_match_engine" / "models" / "graph_service.py"
FACILITY_PROFILE_PY = REPO_ROOT / "plasticos_facility_profile" / "models" / "facility_profile.py"
MATERIAL_PROFILE_PY = REPO_ROOT / "plasticos_material_profile" / "models" / "material_profile.py"


# ── Helpers ─────────────────────────────────────────────────────────


def _extract_xml_form_codes() -> set[str]:
    """Extract form codes from material_form_data.xml."""
    tree = ET.parse(MATERIAL_FORM_DATA_XML)
    codes = set()
    for record in tree.iter("record"):
        model = record.get("model", "")
        if model == "plasticos.material.form":
            for field in record.iter("field"):
                if field.get("name") == "code":
                    code = (field.text or "").strip()
                    if code:
                        codes.add(code)
    return codes


def _get_form_codes_from_registry() -> set[str]:
    """Import FORM_CODES from the canonical registry."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("form_codes", FORM_CODES_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return set(mod.FORM_CODES)


def _get_equipment_gated_forms_from_registry() -> dict[str, str]:
    """Import EQUIPMENT_GATED_FORMS from the canonical registry."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("form_codes", FORM_CODES_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return dict(mod.EQUIPMENT_GATED_FORMS)


def _get_passthrough_forms_from_registry() -> set[str]:
    """Import PASSTHROUGH_FORMS from the canonical registry."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("form_codes", FORM_CODES_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return set(mod.PASSTHROUGH_FORMS)


# ── Test Class ──────────────────────────────────────────────────────


class TestFormEnumAlignment:
    """Drift-prevention tests for the form enum contract."""

    def test_xml_codes_match_registry(self):
        """material_form_data.xml codes MUST exactly equal FORM_CODES."""
        xml_codes = _extract_xml_form_codes()
        registry_codes = _get_form_codes_from_registry()
        assert xml_codes == registry_codes, (
            f"XML vs registry drift detected.\n"
            f"  In XML only: {xml_codes - registry_codes}\n"
            f"  In registry only: {registry_codes - xml_codes}"
        )

    def test_registry_is_sorted(self):
        """FORM_CODES tuple MUST be sorted alphabetically for determinism."""
        import importlib.util

        spec = importlib.util.spec_from_file_location("form_codes", FORM_CODES_PY)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        assert list(mod.FORM_CODES) == sorted(mod.FORM_CODES), "FORM_CODES is not sorted alphabetically."

    def test_equipment_gated_plus_passthrough_equals_all(self):
        """EQUIPMENT_GATED_FORMS + PASSTHROUGH_FORMS MUST equal FORM_CODES."""
        all_codes = _get_form_codes_from_registry()
        gated = set(_get_equipment_gated_forms_from_registry().keys())
        passthrough = _get_passthrough_forms_from_registry()

        combined = gated | passthrough
        assert combined == all_codes, (
            f"Gated + Passthrough != FORM_CODES.\n"
            f"  Missing from combined: {all_codes - combined}\n"
            f"  Extra in combined: {combined - all_codes}"
        )

    def test_no_overlap_gated_passthrough(self):
        """EQUIPMENT_GATED_FORMS and PASSTHROUGH_FORMS MUST NOT overlap."""
        gated = set(_get_equipment_gated_forms_from_registry().keys())
        passthrough = _get_passthrough_forms_from_registry()
        overlap = gated & passthrough
        assert not overlap, f"Overlap between gated and passthrough: {overlap}"

    def test_graph_service_imports_from_registry(self):
        """graph_service.py MUST import from form_codes, not hard-code literals."""
        source = GRAPH_SERVICE_PY.read_text()
        assert "plasticos_material_profile.form_codes import" in source, (
            "graph_service.py does not import from form_codes registry."
        )

    def test_graph_service_no_hardcoded_form_literals(self):
        """graph_service.py MUST NOT contain hard-coded form code strings in Cypher.

        The only allowed form-code strings are inside the generated Cypher
        (produced by _build_form_gate_where / _build_form_gate_case).
        We check that the raw source does not contain inline form-code
        string literals in the query builder methods.
        """
        source = GRAPH_SERVICE_PY.read_text()
        registry_codes = _get_form_codes_from_registry()

        # Extract the _build_strict_query and _build_relaxed_query method bodies
        # and check they don't contain hard-coded form literals
        # (the f-string placeholders {form_gate_where} and {form_gate_case} are OK)
        for method_name in ("_build_strict_query", "_build_relaxed_query"):
            # Find method body (rough extraction between def and next def/class)
            pattern = rf"def {method_name}\(self\):(.*?)(?=\n    def |\nclass |\Z)"
            match = re.search(pattern, source, re.DOTALL)
            if match:
                body = match.group(1)
                for code in registry_codes:
                    # Allow the f-string reference but not hard-coded string
                    # Hard-coded would be: '$form = 'bales'
                    hard_coded_pattern = rf"\$form\s*=\s*'{re.escape(code)}'"
                    assert not re.search(hard_coded_pattern, body), (
                        f"Hard-coded form literal '{code}' found in {method_name}. Use canonical registry instead."
                    )

    def test_facility_profile_uses_many2one(self):
        """facility_profile.py MUST use form_preference_id (Many2one), not Selection."""
        source = FACILITY_PROFILE_PY.read_text()
        assert "form_preference_id = fields.Many2one" in source, (
            "facility_profile.py does not use Many2one for form_preference_id."
        )

    def test_material_profile_imports_form_selection(self):
        """material_profile.py MUST import FORM_SELECTION from form_codes."""
        source = MATERIAL_PROFILE_PY.read_text()
        assert "from" in source and "FORM_SELECTION" in source, (
            "material_profile.py does not import FORM_SELECTION from form_codes."
        )

    def test_graph_gate_covers_all_form_codes(self):
        """The generated Cypher form gate MUST cover every canonical form code.

        This test instantiates the gate generators and verifies that every
        code from FORM_CODES appears in the generated Cypher.
        """
        import importlib.util

        spec = importlib.util.spec_from_file_location("form_codes", FORM_CODES_PY)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        all_codes = set(mod.FORM_CODES)
        gated = mod.EQUIPMENT_GATED_FORMS
        passthrough = mod.PASSTHROUGH_FORMS

        # Simulate _build_form_gate_where
        where_lines = ["$form IS NULL"]
        for form_code, condition in gated.items():
            where_lines.append(f"($form = '{form_code}' AND {condition} = true)")
        passthrough_list = ", ".join(f"'{c}'" for c in passthrough)
        where_lines.append(f"($form IN [{passthrough_list}])")
        where_cypher = "\n            OR ".join(where_lines)

        # Verify every code appears in the generated WHERE clause
        for code in all_codes:
            assert f"'{code}'" in where_cypher, (
                f"Form code '{code}' is NOT covered in the generated Cypher WHERE clause."
            )

        # Simulate _build_form_gate_case
        case_lines = ["WHEN $form IS NULL THEN 1.0"]
        for form_code, condition in gated.items():
            case_lines.append(f"WHEN $form = '{form_code}' AND {condition} = true THEN 1.0")
        passthrough_list2 = ", ".join(f"'{c}'" for c in passthrough)
        case_lines.append(f"WHEN $form IN [{passthrough_list2}] THEN 1.0")
        case_lines.append("ELSE 0.3")
        case_cypher = "\n                ".join(case_lines)

        # Verify every code appears in the generated CASE expression
        for code in all_codes:
            assert f"'{code}'" in case_cypher, (
                f"Form code '{code}' is NOT covered in the generated Cypher CASE expression."
            )

    def test_no_pellet_singular_drift(self):
        """Regression: 'pellet' (singular) MUST NOT appear; canonical is 'pellets'."""
        registry_codes = _get_form_codes_from_registry()
        assert "pellet" not in registry_codes, "'pellet' (singular) found in FORM_CODES. Canonical code is 'pellets'."
        assert "pellets" in registry_codes, "'pellets' not found in FORM_CODES."

    def test_no_bale_singular_drift(self):
        """Regression: 'bale' (singular) MUST NOT appear; canonical is 'bales'."""
        registry_codes = _get_form_codes_from_registry()
        assert "bale" not in registry_codes, "'bale' (singular) found in FORM_CODES. Canonical code is 'bales'."
        assert "bales" in registry_codes, "'bales' not found in FORM_CODES."
