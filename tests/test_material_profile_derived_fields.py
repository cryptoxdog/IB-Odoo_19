"""Derived material-profile fields: monthly volume, percent labels, and coordinate origins."""

import importlib.util
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[1]


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


_volume = _load("plasticos_material_profile.volume", _REPO / "plasticos_material_profile" / "volume.py")
_origin = _load("plasticos_intake.source_origin", _REPO / "plasticos_intake" / "source_origin.py")


class TestMonthlyVolume:
    def test_product_of_quantity_and_loads(self):
        assert _volume.monthly_volume_lbs(40000, 1) == pytest.approx(40000)

    def test_missing_input_is_zero(self):
        assert _volume.monthly_volume_lbs(40000, 0) == pytest.approx(0)
        assert _volume.monthly_volume_lbs(0, 1) == pytest.approx(0)
        assert _volume.monthly_volume_lbs(None, None) == pytest.approx(0)


class TestPercentPresentation:
    def test_specs_are_not_progress_bars(self):
        ux = (_REPO / "plasticos_material_profile" / "views" / "material_profile_ux.xml").read_text()
        model = (_REPO / "plasticos_material_profile" / "models" / "material_profile.py").read_text()
        assert "progressbar" not in ux
        assert 'widget="percentage"' not in ux
        assert 'string="Moisture %"' in model
        assert 'string="Contamination %"' in model
        assert "0.5 means 0.5%" in model


class TestCoordinateOrigins:
    def test_profile_follows_the_location(self):
        geo = (_REPO / "plasticos_geolocalize" / "models" / "material_profile_geo.py").read_text()
        assert 'related="partner_id.partner_latitude"' in geo
        assert 'related="partner_id.partner_longitude"' in geo
        assert "readonly=True" in geo
        assert "store=True" in geo
        assert not (_REPO / "plasticos_geolocalize" / "models" / "intake_geo.py").exists()

    def test_nonzero_snapshot_is_kept(self):
        lat, lon = _origin.snapshot_coordinates(35.2, -80.8, 40.7, -74.0)
        assert lat == pytest.approx(35.2)
        assert lon == pytest.approx(-80.8)

    def test_zero_snapshot_fills_from_the_location(self):
        lat, lon = _origin.snapshot_coordinates(0, 0, 35.2, -80.8)
        assert lat == pytest.approx(35.2)
        assert lon == pytest.approx(-80.8)
        updates = _origin.seed_blank_snapshot(0, 0, "", "", "", 35.2, -80.8, "1 Mill St", "Stanley", "28164")
        assert updates["lat"] == pytest.approx(35.2)
        assert updates["source_city"] == "Stanley"

    def test_location_with_coordinates_wins(self):
        assert (
            _origin.location_updates_from_intake(35.2, -80.8, 40.7, -74.0, "", "", "", "9 Dock", "New York", "10001")
            == {}
        )

    def test_empty_location_receives_the_intake_origin(self):
        updates = _origin.location_updates_from_intake(
            0, 0, 40.7, -74.0, "", "Stanley", "", "9 Dock", "New York", "10001"
        )
        assert updates["partner_latitude"] == pytest.approx(40.7)
        assert updates["partner_longitude"] == pytest.approx(-74.0)
        assert updates["street"] == "9 Dock"
        assert updates["zip"] == "10001"
        assert "city" not in updates

    def test_downstream_uses_the_intake_only_while_the_profile_is_zero(self):
        assert _origin.downstream_coordinates(35.2, -80.8, 40.7, -74.0) == pytest.approx((35.2, -80.8))
        assert _origin.downstream_coordinates(0, 0, 40.7, -74.0) == pytest.approx((40.7, -74.0))

    def test_web_lead_address_does_not_create_a_partner(self):
        vals = _origin.web_lead_source_address("28164", "", "Stanley, NC")
        assert vals == {"source_zip": "28164", "source_city": "Stanley, NC"}
        assert "partner_id" not in vals
        web_lead = (_REPO / "plasticos_web_leads" / "models" / "web_lead.py").read_text()
        assert "web_lead_source_address" in web_lead

    def test_crm_lead_address_copies_street_city_and_zip(self):
        assert _origin.crm_lead_source_address("9 Dock", "Stanley", "28164") == {
            "source_street": "9 Dock",
            "source_city": "Stanley",
            "source_zip": "28164",
        }
        bridge = (_REPO / "plasticos_crm_bridge" / "models" / "crm_lead.py").read_text()
        assert "crm_lead_source_address" in bridge
