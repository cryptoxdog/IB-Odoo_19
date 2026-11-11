"""Where an intake's address and coordinates come from.

A location's coordinates stay on the location. An intake born from another
source keeps that source's address and coordinates. A zero snapshot may be
filled from the location later. A non-zero snapshot is left alone.
"""


def has_coordinates(latitude, longitude):
    """True when either value is a real coordinate. Zero is the empty sentinel."""
    return bool(latitude) or bool(longitude)


def snapshot_coordinates(current_lat, current_lon, origin_lat, origin_lon):
    """Keep a non-zero snapshot. Fill a zero snapshot from the origin."""
    if has_coordinates(current_lat, current_lon):
        return current_lat, current_lon
    if has_coordinates(origin_lat, origin_lon):
        return origin_lat or 0.0, origin_lon or 0.0
    return current_lat or 0.0, current_lon or 0.0


def seed_blank_snapshot(
    current_lat,
    current_lon,
    current_street,
    current_city,
    current_zip,
    origin_lat,
    origin_lon,
    origin_street,
    origin_city,
    origin_zip,
):
    """Values to write onto an intake. Set keys are left unchanged."""
    updates = {}
    lat, lon = snapshot_coordinates(current_lat, current_lon, origin_lat, origin_lon)
    if has_coordinates(lat, lon) and not has_coordinates(current_lat, current_lon):
        updates["lat"] = lat
        updates["lon"] = lon
    if not current_street and origin_street:
        updates["source_street"] = origin_street
    if not current_city and origin_city:
        updates["source_city"] = origin_city
    if not current_zip and origin_zip:
        updates["source_zip"] = origin_zip
    return updates


def web_lead_source_address(pickup_postal_code, pickup_place, pickup_location_text):
    """Pickup text from a web lead. This does not create a partner."""
    city = pickup_place or pickup_location_text or False
    vals = {}
    if pickup_postal_code:
        vals["source_zip"] = pickup_postal_code
    if city:
        vals["source_city"] = city
    return vals


def crm_lead_source_address(street, city, zip_code):
    """Street, city, and ZIP copied from a CRM lead onto an intake."""
    vals = {}
    if street:
        vals["source_street"] = street
    if city:
        vals["source_city"] = city
    if zip_code:
        vals["source_zip"] = zip_code
    return vals


def downstream_coordinates(profile_lat, profile_lon, intake_lat, intake_lon):
    """Profile coordinates win. The intake snapshot is used only while those are zero."""
    if has_coordinates(profile_lat, profile_lon):
        return profile_lat or 0.0, profile_lon or 0.0
    if has_coordinates(intake_lat, intake_lon):
        return intake_lat or 0.0, intake_lon or 0.0
    return 0.0, 0.0


def location_updates_from_intake(
    location_lat,
    location_lon,
    intake_lat,
    intake_lon,
    location_street,
    location_city,
    location_zip,
    source_street,
    source_city,
    source_zip,
):
    """Partner writes for a location that has no coordinates yet.

    A location that already has coordinates is left alone. The profile then
    follows that location.
    """
    if has_coordinates(location_lat, location_lon):
        return {}
    updates = {}
    if has_coordinates(intake_lat, intake_lon):
        updates["partner_latitude"] = intake_lat or 0.0
        updates["partner_longitude"] = intake_lon or 0.0
    if source_street and not location_street:
        updates["street"] = source_street
    if source_city and not location_city:
        updates["city"] = source_city
    if source_zip and not location_zip:
        updates["zip"] = source_zip
    return updates
