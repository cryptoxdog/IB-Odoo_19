"""Derive a web lead's Location from its pickup ZIP. The seller's words are not an input."""

from __future__ import annotations

import gzip
import json
from collections.abc import Mapping
from pathlib import Path

ANCHOR_ZIP = "28277"
ANCHOR_PLACE = "Charlotte, NC"
_FIVE_DIGIT_ZIP = 5
_NINE_DIGIT_ZIP = 9

# USPS abbreviations for the states, DC, and the populated territories this table can name.
USPS_STATE_CODES = frozenset(
    {
        "AL",
        "AK",
        "AZ",
        "AR",
        "CA",
        "CO",
        "CT",
        "DE",
        "DC",
        "FL",
        "GA",
        "HI",
        "ID",
        "IL",
        "IN",
        "IA",
        "KS",
        "KY",
        "LA",
        "ME",
        "MD",
        "MA",
        "MI",
        "MN",
        "MS",
        "MO",
        "MT",
        "NE",
        "NV",
        "NH",
        "NJ",
        "NM",
        "NY",
        "NC",
        "ND",
        "OH",
        "OK",
        "OR",
        "PA",
        "RI",
        "SC",
        "SD",
        "TN",
        "TX",
        "UT",
        "VT",
        "VA",
        "WA",
        "WV",
        "WI",
        "WY",
        "AS",
        "GU",
        "MP",
        "PR",
        "VI",
    }
)

_TABLE_PATH = Path(__file__).with_name("data") / "us_zip_places.json.gz"
_LOADED: tuple[dict[str, str], bool] | None = None


def zip_key(value: str) -> str | None:
    """Return the exact 5-digit key, or None when the text is not a US ZIP or ZIP+4."""
    digits = "".join(character for character in value if character.isdigit())
    if len(digits) == _FIVE_DIGIT_ZIP or len(digits) == _NINE_DIGIT_ZIP:
        return digits[:_FIVE_DIGIT_ZIP]
    return None


def _row_place(key: object, value: object) -> str:
    """Accept one preferred-city row. Anything else is a miss, not a guess."""
    if not isinstance(key, str) or not isinstance(value, str):
        return ""
    if len(key) != _FIVE_DIGIT_ZIP or not key.isdigit():
        return ""
    city, separator, state = value.partition(", ")
    if not separator or not city or "," in city or state not in USPS_STATE_CODES:
        return ""
    place = f"{city}, {state}"
    if place != value:
        return ""
    return place


def validated_places(mapping: Mapping[object, object]) -> dict[str, str]:
    """Keep only rows whose city and state match the Location grammar."""
    places: dict[str, str] = {}
    for key, value in mapping.items():
        place = _row_place(key, value)
        if place and isinstance(key, str):
            places[key] = place
    return places


def table_is_anchored(places: Mapping[str, str]) -> bool:
    """A table that cannot prove the Charlotte anchor must not name any city."""
    return bool(places) and places.get(ANCHOR_ZIP) == ANCHOR_PLACE


def location_for_zip(postal_code: str, places: Mapping[str, str]) -> str:
    """Exact ZIP match. A missing anchor, a short key, or an unknown ZIP returns empty."""
    if not table_is_anchored(places):
        return ""
    key = zip_key(postal_code)
    if key is None:
        return ""
    return places.get(key, "")


def _load_places() -> tuple[dict[str, str], bool]:
    global _LOADED
    if _LOADED is not None:
        return _LOADED
    try:
        with gzip.open(_TABLE_PATH, "rt", encoding="utf-8") as handle:
            raw = json.load(handle)
    except (OSError, json.JSONDecodeError, UnicodeError):
        _LOADED = ({}, False)
        return _LOADED
    if not isinstance(raw, dict):
        _LOADED = ({}, False)
        return _LOADED
    places = validated_places(raw)
    _LOADED = (places, table_is_anchored(places))
    return _LOADED


def resolve_pickup(postal_code: str, location_text: str) -> tuple[str, str, str]:
    """Return the trimmed ZIP, the seller's words, and Location. Location ignores the words."""
    postal = postal_code.strip() if isinstance(postal_code, str) else ""
    text = location_text.strip() if isinstance(location_text, str) else ""
    places, anchored = _load_places()
    place = location_for_zip(postal, places) if anchored else ""
    return postal, text, place


def _payload_text(payload: object, key: str) -> str:
    if not isinstance(payload, dict):
        return ""
    value = payload.get(key)
    return value.strip() if isinstance(value, str) else ""


def sources_from_payloads(canonical: object, raw: object) -> tuple[str, str]:
    """Prefer the canonical packet, then the Cognito keys still sitting on older leads."""
    postal = _payload_text(canonical, "pickup_postal_code") or _payload_text(raw, "LocationOfPickUpZip")
    text = _payload_text(canonical, "pickup_location_text") or _payload_text(raw, "LocationOfPickUpCityState")
    if not text:
        text = _payload_text(raw, "WhereIsItLocated")
    return postal, text


def resolve_payloads(canonical: object, raw: object) -> tuple[str, str, str]:
    """The backfill calls the same Location writer as a new admission."""
    postal, text = sources_from_payloads(canonical, raw)
    return resolve_pickup(postal, text)
