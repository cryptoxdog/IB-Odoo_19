"""Pure-Python regression tests for freight Haversine features."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

SERVICE_PATH = Path(__file__).parents[1] / "plasticos_logistics" / "services" / "freight_geometry.py"
SPEC = importlib.util.spec_from_file_location("freight_geometry_service", SERVICE_PATH)
freight_geometry = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = freight_geometry
SPEC.loader.exec_module(freight_geometry)


def test_identical_coordinates_are_zero_miles():
    assert freight_geometry.haversine_miles(0, 0, 0, 0) == pytest.approx(0.0)


def test_equatorial_degree_matches_reference_vector():
    assert freight_geometry.haversine_miles(0, 0, 0, 1) == pytest.approx(69.093419, abs=0.0001)


def test_antipodal_reference_vector_matches():
    assert freight_geometry.haversine_miles(0, 0, 0, 180) == pytest.approx(12436.815417, abs=0.0001)


def test_antimeridian_pair_is_short_route():
    assert freight_geometry.haversine_miles(0, 179.9, 0, -179.9) < 20


def test_zero_is_valid_coordinate_not_missing_evidence():
    assert freight_geometry.haversine_miles(0, 0, 1, 1) > 0


@pytest.mark.parametrize("values", [(91, 0, 0, 0), (0, 181, 0, 0), (float("nan"), 0, 0, 0), (None, 0, 0, 0)])
def test_invalid_coordinates_raise_classified_error(values):
    with pytest.raises(freight_geometry.FreightCoordinateError):
        freight_geometry.haversine_miles(*values)
