"""Pure component tests for the provider-neutral Cognito admission seam."""

from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = ROOT / "plasticos_web_leads"

package = sys.modules.setdefault("plasticos_web_leads", types.ModuleType("plasticos_web_leads"))
package.__path__ = [str(PACKAGE_ROOT)]

from plasticos_web_leads.adapters.base import PACKET_SCHEMA_VERSION, packet_to_dict  # noqa: E402
from plasticos_web_leads.adapters.cognito import CognitoAdapter  # noqa: E402
from plasticos_web_leads.adapters.registry import get_adapter  # noqa: E402


def _payload(**overrides):
    payload = {
        "Entry": {"Number": "12345", "DateSubmitted": "2026-09-21T12:00:00Z"},
        "YourBusinessCompanyName": "Acme Plastics",
        "Name": {"First": "Alex", "Last": "Smith", "FirstAndLast": "Alex Smith"},
        "Email": "alex@example.test",
        "Phone": "555-0100",
        "LocationOfPickUpCityState": "Cleveland, OH",
        "LocationOfPickUpZip": "44101",
        "WhatIsIt": "HDPE regrind",
        "WhatMaterialIsItMadeFrom": "HDPE",
        "WhatIsTheSourceOfThisMaterial": "Manufacturing production scrap",
        "WhatIsTheQuantity": "3 loads",
        "WeightPerLoad": "40,000 lbs",
        "HowOften": "2 loads per month",
        "AreThereAnyContaminants": "none",
        "UploadPhotosOfYourScrapUpTo10": [
            {
                "Id": "file-1",
                "Name": "material.jpg",
                "File": "https://files.cognitoforms.com/material.jpg",
                "ContentType": "image/jpeg",
                "Size": 4,
            }
        ],
    }
    payload.update(overrides)
    return payload


def test_cognito_adapter_maps_current_top_level_payload_without_decision():
    packet = CognitoAdapter().to_packet(_payload())

    assert packet.schema_version == PACKET_SCHEMA_VERSION
    assert packet.provider == "cognito"
    assert packet.provider_external_id == "12345"
    assert packet.idempotency_key == "CG-12345"
    assert packet.contact_name == "Alex Smith"
    assert packet.quantity_text == "3 loads"
    assert packet.weight_per_load_text == "40,000 lbs"
    assert packet.attachments[0].attachment_index == 0
    assert packet.attachments[0].source_id == "file-1"
    assert not hasattr(packet, "decision")


def test_packet_serialization_preserves_raw_payload_and_can_omit_it():
    raw_payload = _payload()
    packet = CognitoAdapter().to_packet(raw_payload)
    raw_payload["WhatIsIt"] = "mutated after admission"

    serialized = packet_to_dict(packet)
    canonical = packet_to_dict(packet, omit_raw_payload=True)

    assert serialized["raw_payload"]["WhatIsIt"] == "HDPE regrind"
    assert serialized["attachments"][0]["filename"] == "material.jpg"
    assert "raw_payload" not in canonical


def test_adapter_accepts_no_attachments_and_compatibility_aliases():
    packet = CognitoAdapter().to_packet(
        {
            "EntryId": "legacy-id",
            "CompanyName": "Legacy Co",
            "EmailAddress": "legacy@example.test",
            "PhoneNumber": "555-0199",
            "DescribeYourMaterial": "PP purge",
            "UploadPhotosOfYourScrapUpTo10": [],
        }
    )

    assert packet.idempotency_key == "CG-legacy-id"
    assert packet.company_name == "Legacy Co"
    assert packet.contact_email == "legacy@example.test"
    assert packet.attachments == ()


@pytest.mark.parametrize(
    "attachments, message",
    [
        (
            [
                {"Id": "dup", "Name": "a.jpg", "File": "https://x/a.jpg"},
                {"Id": "dup", "Name": "b.jpg", "File": "https://x/b.jpg"},
            ],
            "Duplicate",
        ),
        ([{"Id": "one", "Name": "a.jpg", "File": "http://x/a.jpg"}], "HTTPS"),
        ([{"Id": "one", "Name": "a.jpg", "File": "https://x/a.jpg", "Size": 0}], "positive"),
    ],
)
def test_adapter_rejects_invalid_attachment_metadata(attachments, message):
    with pytest.raises(ValueError, match=message):
        CognitoAdapter().to_packet(_payload(UploadPhotosOfYourScrapUpTo10=attachments))


def test_adapter_preserves_attachment_order_and_registry_fails_closed():
    attachments = [
        {"Id": "first", "Name": "one.jpg", "File": "https://x/one.jpg", "ContentType": "image/jpeg", "Size": 1},
        {"Id": "second", "Name": "two.pdf", "File": "https://x/two.pdf", "ContentType": "application/pdf", "Size": 2},
    ]
    packet = CognitoAdapter().to_packet(_payload(UploadPhotosOfYourScrapUpTo10=attachments))

    assert [item.source_id for item in packet.attachments] == ["first", "second"]
    assert get_adapter("cognito").provider_key == "cognito"
    with pytest.raises(ValueError, match="Unsupported"):
        get_adapter("unknown")
