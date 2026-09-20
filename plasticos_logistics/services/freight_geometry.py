"""Validated, deterministic Haversine geometry for freight features only."""

from __future__ import annotations

import math

EARTH_RADIUS_MILES = 3958.7613


class FreightCoordinateError(ValueError):
    """Raised for missing, non-finite, or out-of-range coordinates."""


def _coordinate(value, *, name: str, lower: float, upper: float) -> float:
    if value is None or value is False or value == "":
        raise FreightCoordinateError(f"{name} is missing")
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise FreightCoordinateError(f"{name} is not numeric") from exc
    if not math.isfinite(parsed):
        raise FreightCoordinateError(f"{name} must be finite")
    if not lower <= parsed <= upper:
        raise FreightCoordinateError(f"{name} must be between {lower} and {upper}")
    return parsed


def haversine_miles(lat1, lon1, lat2, lon2) -> float:
    """Return great-circle miles; never treat this feature as road mileage."""
    lat1 = _coordinate(lat1, name="origin latitude", lower=-90, upper=90)
    lon1 = _coordinate(lon1, name="origin longitude", lower=-180, upper=180)
    lat2 = _coordinate(lat2, name="destination latitude", lower=-90, upper=90)
    lon2 = _coordinate(lon2, name="destination longitude", lower=-180, upper=180)
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = math.sin(delta_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    a = min(1.0, max(0.0, a))
    return EARTH_RADIUS_MILES * 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
