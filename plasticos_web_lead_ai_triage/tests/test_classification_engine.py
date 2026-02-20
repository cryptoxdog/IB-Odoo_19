# -*- coding: utf-8 -*-
# ═══════════════════════════════════════════════════════════
# Tests: classification_engine — deterministic HOT/COLD rules
# ═══════════════════════════════════════════════════════════
import unittest

from odoo.addons.plasticos_web_lead_ai_triage.models.classification_engine import (
    classify_lead,
    ClassificationResult,
)

# Default reject lists (matching triage_config defaults)
_REJECT_MATERIALS = frozenset([
    "vinyl siding", "appliances", "conduit", "pvc pipe",
    "pet bottles", "carpet", "mattress", "tire",
])
_REJECT_SOURCES = frozenset([
    "residential", "individual", "homeowner", "drop-off", "drop off",
])


class TestClassificationEngine(unittest.TestCase):
    """Unit tests for the deterministic classification engine.

    These tests run without Odoo — pure Python logic.
    """

    # ── HOT Lead Tests ───────────────────────────────────────

    def test_hot_lead_all_qualifiers(self):
        """A lead with >= 10k lbs, identified polymer, commercial source → HOT."""
        result = classify_lead(
            polymer="hdpe",
            material_description="HDPE regrind from manufacturing plant",
            estimated_lbs=40000,
            source_description="Industrial manufacturing facility",
            source_type="post_industrial",
            reject_materials=_REJECT_MATERIALS,
            reject_sources=_REJECT_SOURCES,
        )
        self.assertEqual(result.decision, "hot")
        self.assertGreaterEqual(len(result.hot_qualifiers_met), 3)

    def test_hot_lead_exact_threshold(self):
        """Exactly 10,000 lbs should qualify as HOT."""
        result = classify_lead(
            polymer="pp",
            material_description="PP pellets from factory",
            estimated_lbs=10000,
            source_description="Commercial warehouse",
            source_type="post_commercial",
            reject_materials=_REJECT_MATERIALS,
            reject_sources=_REJECT_SOURCES,
        )
        self.assertEqual(result.decision, "hot")

    # ── COLD Lead Tests — Gate Triggers ──────────────────────

    def test_cold_pvc_material(self):
        """PVC polymer → auto-COLD regardless of weight."""
        result = classify_lead(
            polymer="pvc",
            material_description="PVC pipe scrap",
            estimated_lbs=50000,
            source_description="Commercial building demolition",
            source_type="post_commercial",
            reject_materials=_REJECT_MATERIALS,
            reject_sources=_REJECT_SOURCES,
        )
        self.assertEqual(result.decision, "cold")
        self.assertIn("pvc_material", result.cold_gates_triggered)

    def test_cold_below_minimum_weight(self):
        """Below 8,000 lbs → auto-COLD."""
        result = classify_lead(
            polymer="hdpe",
            material_description="HDPE buckets",
            estimated_lbs=5000,
            source_description="Commercial facility",
            source_type="post_commercial",
            reject_materials=_REJECT_MATERIALS,
            reject_sources=_REJECT_SOURCES,
        )
        self.assertEqual(result.decision, "cold")
        self.assertTrue(
            any("below_8000_lbs" in g for g in result.cold_gates_triggered)
        )

    def test_cold_residential_source(self):
        """Residential source → auto-COLD."""
        result = classify_lead(
            polymer="hdpe",
            material_description="HDPE containers",
            estimated_lbs=20000,
            source_description="Residential neighborhood cleanup",
            source_type="post_consumer",
            reject_materials=_REJECT_MATERIALS,
            reject_sources=_REJECT_SOURCES,
        )
        self.assertEqual(result.decision, "cold")
        self.assertTrue(
            any("residential" in g for g in result.cold_gates_triggered)
        )

    def test_cold_reject_material_vinyl_siding(self):
        """Vinyl siding in description → auto-COLD."""
        result = classify_lead(
            polymer="pvc",
            material_description="Vinyl siding from house renovation",
            estimated_lbs=30000,
            source_description="Construction company",
            source_type="post_commercial",
            reject_materials=_REJECT_MATERIALS,
            reject_sources=_REJECT_SOURCES,
        )
        self.assertEqual(result.decision, "cold")
        # PVC gate fires first, but vinyl siding would also trigger
        self.assertIn("pvc_material", result.cold_gates_triggered)

    def test_cold_reject_material_appliances(self):
        """Appliances in description → auto-COLD."""
        result = classify_lead(
            polymer=None,
            material_description="Old appliances and electronics",
            estimated_lbs=20000,
            source_description="Commercial warehouse",
            source_type="post_commercial",
            reject_materials=_REJECT_MATERIALS,
            reject_sources=_REJECT_SOURCES,
        )
        self.assertEqual(result.decision, "cold")
        self.assertTrue(
            any("appliances" in g for g in result.cold_gates_triggered)
        )

    def test_cold_drop_off_request(self):
        """Drop-off source → auto-COLD."""
        result = classify_lead(
            polymer="hdpe",
            material_description="HDPE buckets",
            estimated_lbs=15000,
            source_description="I want to drop-off at your facility",
            source_type=None,
            reject_materials=_REJECT_MATERIALS,
            reject_sources=_REJECT_SOURCES,
        )
        self.assertEqual(result.decision, "cold")
        self.assertTrue(
            any("drop-off" in g for g in result.cold_gates_triggered)
        )

    def test_cold_non_plastic_material(self):
        """Non-plastic material (metal) → auto-COLD."""
        result = classify_lead(
            polymer=None,
            material_description="Scrap steel and aluminum from factory",
            estimated_lbs=40000,
            source_description="Industrial plant",
            source_type="post_industrial",
            reject_materials=_REJECT_MATERIALS,
            reject_sources=_REJECT_SOURCES,
        )
        self.assertEqual(result.decision, "cold")
        self.assertTrue(
            any("non_plastic" in g for g in result.cold_gates_triggered)
        )

    # ── COLD Lead Tests — Insufficient Qualifiers ────────────

    def test_cold_no_commercial_source(self):
        """Good weight + polymer but unknown source → COLD."""
        result = classify_lead(
            polymer="pp",
            material_description="PP regrind",
            estimated_lbs=20000,
            source_description="",
            source_type=None,
            reject_materials=_REJECT_MATERIALS,
            reject_sources=_REJECT_SOURCES,
        )
        self.assertEqual(result.decision, "cold")
        self.assertTrue(
            any("Insufficient" in r for r in result.reasons)
        )

    def test_cold_no_polymer_identified(self):
        """Good weight + commercial source but no polymer → COLD."""
        result = classify_lead(
            polymer=None,
            material_description="Some plastic material",
            estimated_lbs=20000,
            source_description="Commercial warehouse",
            source_type="post_commercial",
            reject_materials=_REJECT_MATERIALS,
            reject_sources=_REJECT_SOURCES,
        )
        self.assertEqual(result.decision, "cold")

    # ── Edge Cases ───────────────────────────────────────────

    def test_custom_thresholds(self):
        """Custom hot_min_lbs and cold_max_lbs work correctly."""
        result = classify_lead(
            polymer="hdpe",
            material_description="HDPE film from factory",
            estimated_lbs=5000,
            source_description="Manufacturing plant",
            source_type="post_industrial",
            reject_materials=_REJECT_MATERIALS,
            reject_sources=_REJECT_SOURCES,
            hot_min_lbs=5000,
            cold_max_lbs=3000,
        )
        self.assertEqual(result.decision, "hot")

    def test_empty_reject_lists(self):
        """Empty reject lists should not trigger COLD gates."""
        result = classify_lead(
            polymer="hdpe",
            material_description="HDPE vinyl siding",  # would normally be rejected
            estimated_lbs=20000,
            source_description="Industrial facility",
            source_type="post_industrial",
            reject_materials=frozenset(),
            reject_sources=frozenset(),
        )
        self.assertEqual(result.decision, "hot")

    def test_ewaste_polymer(self):
        """E-Waste as polymer type should be treated as plastic."""
        result = classify_lead(
            polymer="ewaste",
            material_description="E-waste plastics from electronics recycler",
            estimated_lbs=25000,
            source_description="Commercial electronics recycler",
            source_type="post_commercial",
            reject_materials=_REJECT_MATERIALS,
            reject_sources=_REJECT_SOURCES,
        )
        self.assertEqual(result.decision, "hot")

    def test_result_dataclass_fields(self):
        """ClassificationResult has all expected fields."""
        result = classify_lead(
            polymer="pp",
            material_description="PP pellets",
            estimated_lbs=40000,
            source_description="Factory",
            source_type="post_industrial",
            reject_materials=_REJECT_MATERIALS,
            reject_sources=_REJECT_SOURCES,
        )
        self.assertIsInstance(result, ClassificationResult)
        self.assertIn(result.decision, ("hot", "cold"))
        self.assertIsInstance(result.reasons, list)
        self.assertIsInstance(result.cold_gates_triggered, list)
        self.assertIsInstance(result.hot_qualifiers_met, list)

    def test_agricultural_source_is_commercial(self):
        """Agricultural source should count as commercial."""
        result = classify_lead(
            polymer="ldpe",
            material_description="LDPE film from farm",
            estimated_lbs=20000,
            source_description="Agricultural operation",
            source_type="agricultural",
            reject_materials=_REJECT_MATERIALS,
            reject_sources=_REJECT_SOURCES,
        )
        self.assertEqual(result.decision, "hot")


if __name__ == "__main__":
    unittest.main()
