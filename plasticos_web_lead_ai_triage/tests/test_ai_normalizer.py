# -*- coding: utf-8 -*-
# ═══════════════════════════════════════════════════════════
# Tests: ai_normalizer — prompt building and value mapping
# ═══════════════════════════════════════════════════════════
import unittest

from odoo.addons.plasticos_web_lead_ai_triage.models.ai_normalizer import (
    build_user_prompt,
    CANONICAL_POLYMERS,
    CANONICAL_FORMS,
    CANONICAL_SOURCE_TYPES,
    CANONICAL_COLORS,
)
from odoo.addons.plasticos_web_lead_ai_triage.models.web_lead_triage import (
    _POLYMER_NORMALIZE,
    _FORM_NORMALIZE,
    _SOURCE_NORMALIZE,
    _safe_int,
)


class TestBuildUserPrompt(unittest.TestCase):
    """Tests for the prompt builder function."""

    def test_extracts_known_cognito_fields(self):
        """Known Cognito field names are extracted with labels."""
        payload = {
            "YourBusinessCompanyName": "Acme Plastics",
            "YourName": "John Doe",
            "DescribeYourMaterial": "HDPE regrind, natural color",
            "WhatIsTheQuantity": "2 truckloads per month",
        }
        prompt = build_user_prompt(payload)
        self.assertIn("Company: Acme Plastics", prompt)
        self.assertIn("Contact: John Doe", prompt)
        self.assertIn("Material Description: HDPE regrind", prompt)
        self.assertIn("Quantity: 2 truckloads", prompt)

    def test_empty_payload(self):
        """Empty payload returns a fallback message."""
        prompt = build_user_prompt({})
        self.assertEqual(prompt, "No form data provided.")

    def test_extra_fields_included(self):
        """Non-mapped fields with string values are included."""
        payload = {
            "CustomField": "Some important info",
            "ShortField": "ab",  # Too short, should be excluded
        }
        prompt = build_user_prompt(payload)
        self.assertIn("CustomField: Some important info", prompt)
        self.assertNotIn("ShortField", prompt)


class TestCanonicalValues(unittest.TestCase):
    """Verify canonical value lists are complete and consistent."""

    def test_all_polymers_in_normalize_map(self):
        """Every canonical polymer should have a normalize mapping."""
        for polymer in CANONICAL_POLYMERS:
            lower = polymer.lower().replace("-", "")
            # At least the lowercase version should be in the map
            # (some have aliases like "pa" → "nylon")
            self.assertTrue(
                lower in _POLYMER_NORMALIZE or polymer in _POLYMER_NORMALIZE,
                f"Polymer '{polymer}' missing from _POLYMER_NORMALIZE",
            )

    def test_canonical_forms_count(self):
        """We should have 12 canonical forms (including re-useable)."""
        self.assertEqual(len(CANONICAL_FORMS), 12)

    def test_canonical_source_types_count(self):
        """We should have 8 canonical source types."""
        self.assertEqual(len(CANONICAL_SOURCE_TYPES), 8)

    def test_canonical_colors_count(self):
        """We should have 5 canonical colors."""
        self.assertEqual(len(CANONICAL_COLORS), 5)


class TestMappingHelpers(unittest.TestCase):
    """Test the normalization mapping dictionaries."""

    def test_polymer_normalize_common_aliases(self):
        """Common polymer aliases map correctly."""
        self.assertEqual(_POLYMER_NORMALIZE["hdpe"], "hdpe")
        self.assertEqual(_POLYMER_NORMALIZE["pa"], "nylon")
        self.assertEqual(_POLYMER_NORMALIZE["acetal"], "pom")
        self.assertEqual(_POLYMER_NORMALIZE["ewaste"], "ewaste")
        self.assertEqual(_POLYMER_NORMALIZE["e-waste"], "ewaste")

    def test_form_normalize_plurals(self):
        """Plural forms map to singular."""
        self.assertEqual(_FORM_NORMALIZE["pellets"], "pellet")
        self.assertEqual(_FORM_NORMALIZE["flakes"], "flake")
        self.assertEqual(_FORM_NORMALIZE["lumps"], "lump")

    def test_form_normalize_reuseable_variants(self):
        """Various spellings of re-useable map correctly."""
        self.assertEqual(_FORM_NORMALIZE["re-useable"], "re_useable")
        self.assertEqual(_FORM_NORMALIZE["reuseable"], "re_useable")
        self.assertEqual(_FORM_NORMALIZE["reusable"], "re_useable")

    def test_source_normalize_hyphenated(self):
        """Hyphenated source types map to underscore versions."""
        self.assertEqual(_SOURCE_NORMALIZE["post-industrial"], "post_industrial")
        self.assertEqual(_SOURCE_NORMALIZE["post-consumer"], "post_consumer")
        self.assertEqual(_SOURCE_NORMALIZE["post-commercial"], "post_commercial")

    def test_source_normalize_ocean(self):
        """Ocean maps to ocean_recovered."""
        self.assertEqual(_SOURCE_NORMALIZE["ocean"], "ocean_recovered")
        self.assertEqual(_SOURCE_NORMALIZE["ocean_recovered"], "ocean_recovered")


class TestSafeInt(unittest.TestCase):
    """Test the _safe_int helper."""

    def test_normal_int(self):
        self.assertEqual(_safe_int(42), 42)

    def test_float_truncated(self):
        self.assertEqual(_safe_int(42.7), 42)

    def test_string_number(self):
        self.assertEqual(_safe_int("40000"), 40000)

    def test_none_returns_default(self):
        self.assertEqual(_safe_int(None, 100), 100)

    def test_invalid_string(self):
        self.assertEqual(_safe_int("not a number", 0), 0)

    def test_empty_string(self):
        self.assertEqual(_safe_int("", 0), 0)


if __name__ == "__main__":
    unittest.main()
