"""Pure tests for intake ↔ material profile delta bridge (no Odoo runtime)."""

import importlib.util
import sys
import types
import unittest
from pathlib import Path
from types import SimpleNamespace

_REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_bridge_modules():
    """Load bridge helpers without importing plasticos_material_profile.models (Odoo)."""
    if "plasticos_material_profile.intake_delta_bridge" in sys.modules:
        bridge = sys.modules["plasticos_material_profile.intake_delta_bridge"]
        features = sys.modules["plasticos_material_profile.profile_features"]
        return bridge, features

    pkg = types.ModuleType("plasticos_material_profile")
    pkg.__path__ = [str(_REPO_ROOT / "plasticos_material_profile")]
    sys.modules["plasticos_material_profile"] = pkg

    loaded = {}
    for mod_name, filename in (
        ("plasticos_material_profile.profile_features", "profile_features.py"),
        ("plasticos_material_profile.intake_delta_bridge", "intake_delta_bridge.py"),
    ):
        path = _REPO_ROOT / "plasticos_material_profile" / filename
        spec = importlib.util.spec_from_file_location(mod_name, path)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[mod_name] = mod
        assert spec.loader is not None
        spec.loader.exec_module(mod)
        loaded[mod_name] = mod

    return loaded["plasticos_material_profile.intake_delta_bridge"], loaded[
        "plasticos_material_profile.profile_features"
    ]


_bridge, _features = _load_bridge_modules()
FORBIDDEN_INTAKE_PAYLOAD_KEYS = _bridge.FORBIDDEN_INTAKE_PAYLOAD_KEYS
FORBIDDEN_PROFILE_ORM_READ_KEYS = _bridge.FORBIDDEN_PROFILE_ORM_READ_KEYS
INTAKE_TO_PROFILE_VALUE_MAP = _bridge.INTAKE_TO_PROFILE_VALUE_MAP
build_intake_to_profile_bridge_payload = _bridge.build_intake_to_profile_bridge_payload
build_material_profile_vals_from_intake = _bridge.build_material_profile_vals_from_intake
compute_has_residue_feature = _features.compute_has_residue_feature


def _fake_intake(**kwargs):
    defaults = {
        "mfi_value": 12.0,
        "density_value": 0.95,
        "moisture_pct": 0.2,
        "contamination_pct": 1.5,
        "quantity_per_load_lbs": 40000,
        "loads_per_month": 3,
        "lat": 40.7128,
        "lon": -74.0060,
        "origin_process_type": "injection",
        "filler_pct": 0.0,
        "contamination_notes": None,
        "intake_notes": None,
        "polymer_id": False,
        "form_id": False,
        "color_id": False,
        "source_type_id": False,
        "origin_form_id": False,
        "filler_type_id": False,
        "material_attribute_ids": SimpleNamespace(ids=[], mapped=lambda _f: []),
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


class TestIntakeToProfileValueMapping(unittest.TestCase):
    def test_intake_mfi_maps_to_melt_flow_index(self):
        intake = _fake_intake(mfi_value=22.5)
        vals = build_material_profile_vals_from_intake(intake)
        self.assertEqual(vals["melt_flow_index"], 22.5)
        self.assertNotIn("mfi_value", vals)

    def test_intake_density_maps_to_density(self):
        intake = _fake_intake(density_value=0.91)
        vals = build_material_profile_vals_from_intake(intake)
        self.assertEqual(vals["density"], 0.91)

    def test_intake_moisture_maps_to_moisture_percent(self):
        intake = _fake_intake(moisture_pct=0.4)
        vals = build_material_profile_vals_from_intake(intake)
        self.assertEqual(vals["moisture_percent"], 0.4)

    def test_intake_contamination_maps_to_contamination_percent(self):
        intake = _fake_intake(contamination_pct=2.0)
        vals = build_material_profile_vals_from_intake(intake)
        self.assertEqual(vals["contamination_percent"], 2.0)

    def test_shared_supply_and_geo_fields_copied(self):
        intake = _fake_intake()
        vals = build_material_profile_vals_from_intake(intake)
        self.assertEqual(vals["quantity_per_load_lbs"], 40000)
        self.assertEqual(vals["loads_per_month"], 3)
        self.assertAlmostEqual(vals["lat"], 40.7128, places=5)
        self.assertAlmostEqual(vals["lon"], -74.0060, places=5)

    def test_naming_map_documents_canonical_targets(self):
        self.assertEqual(INTAKE_TO_PROFILE_VALUE_MAP["mfi_value"], "melt_flow_index")
        self.assertEqual(INTAKE_TO_PROFILE_VALUE_MAP["contamination_pct"], "contamination_percent")


class TestDerivedHasResidueFeature(unittest.TestCase):
    def test_residue_true_from_contamination_notes(self):
        self.assertTrue(
            compute_has_residue_feature(
                contamination_percent=0,
                contamination_notes="Visible oil residue on flake",
            )
        )

    def test_residue_true_from_material_attribute(self):
        self.assertTrue(
            compute_has_residue_feature(
                material_attribute_names_or_codes=["clean", "with_residue"],
            )
        )

    def test_residue_false_when_no_signal(self):
        self.assertFalse(
            compute_has_residue_feature(
                contamination_percent=0,
                contamination_notes="Clean stream",
                material_attribute_names_or_codes=["clean"],
                freeform_notes="No issues",
            )
        )

    def test_residue_true_from_contamination_percent(self):
        self.assertTrue(compute_has_residue_feature(contamination_percent=0.1))


class TestBridgePayloadContract(unittest.TestCase):
    def test_payload_includes_derived_has_residue_not_profile_field(self):
        intake = _fake_intake(contamination_pct=0, contamination_notes="residue on drums")
        payload = build_intake_to_profile_bridge_payload(intake)
        self.assertTrue(payload["has_residue"])
        self.assertIn("source_type_id", payload)
        self.assertIn("melt_flow_index", payload)

    def test_forbidden_keys_absent(self):
        intake = _fake_intake()
        payload = build_intake_to_profile_bridge_payload(intake)
        self.assertIn("has_residue", payload)
        self.assertNotIn("target_price", payload)
        for key in FORBIDDEN_INTAKE_PAYLOAD_KEYS:
            self.assertNotIn(key, payload)
