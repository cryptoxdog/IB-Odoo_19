"""Submission date, cold-lead photos, and stored-evidence replay."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from odoo.tests import TransactionCase, tagged

_ATTACHMENT_PROCESSOR = "odoo.addons.plasticos_web_leads.models.attachment_processor"
_PUBLIC_IP = ["93.184.216.34"]


def _image_response():
    payload = MagicMock()
    payload.status_code = 200
    payload.headers = {"Content-Type": "image/jpeg"}
    payload.raise_for_status.return_value = None
    payload.iter_content.return_value = [b"legacy-image"]
    payload.content = b"legacy-image"
    return payload


@tagged("post_install", "-at_install", "plasticos", "web_lead", "date_photos")
class TestWebLeadDatePhotos(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.WebLead = cls.env["plasticos.web.lead"]
        cls.config = cls.env["plasticos.web.lead.config"].sudo().get_config()
        cls.config.write({"ai_enabled": False, "vision_enabled": False, "attachment_allowed_hosts": False})

    def _admit(self, number, **overrides):
        payload = {
            "Entry": {"Number": number, "DateSubmitted": "2026-09-21T12:00:00Z"},
            "YourBusinessCompanyName": "Photo Co",
            "DescribeYourMaterial": "mixed plastic",
            "WhatIsTheQuantity": "1",
            "WeightPerLoad": "",
            "UploadPhotosOfYourScrapUpTo10": [
                {
                    "Id": "file-1",
                    "Name": "material.jpg",
                    "File": "https://www.cognitoforms.com/files/material.jpg?sig=SECRET",
                    "ContentType": "image/jpeg",
                    "Size": 12,
                }
            ],
        }
        payload.update(overrides)
        with (
            patch(f"{_ATTACHMENT_PROCESSOR}.requests.get", return_value=_image_response()),
            patch(f"{_ATTACHMENT_PROCESSOR}.resolve_host_addresses", return_value=_PUBLIC_IP),
        ):
            return self.WebLead.create_from_cognito(payload)

    def test_submitted_date_is_stored_and_a_cold_lead_keeps_its_photo(self):
        lead = self._admit("DATE-PHOTO-001")

        self.assertEqual(str(lead.submitted_at), "2026-09-21 12:00:00")
        self.assertEqual(lead.state, "skipped")
        self.assertEqual(lead.decision, "cold")
        stored = self.env["ir.attachment"].search(
            [("res_model", "=", "plasticos.web.lead"), ("res_id", "=", lead.id), ("mimetype", "=like", "image/%")]
        )
        self.assertTrue(stored)
        self.assertEqual(lead.lead_image_ids, stored)
        self.assertNotIn("[IMG] SKIPPED", lead.triage_log or "")

    def test_missing_seller_date_uses_the_receipt_time(self):
        lead = self._admit("DATE-PHOTO-002", Entry={"Number": "DATE-PHOTO-002"})

        self.assertEqual(lead.submitted_at, lead.create_date)

    def test_stored_tons_and_polymer_become_hot_without_a_new_model_call_or_activity(self):
        lead = self.WebLead.create(
            {
                "lead_id": "REPLAY-100-TON",
                "decision": "cold",
                "state": "skipped",
                "company_name": "Comproremex",
                "quantity_text": "100 ton",
                "estimated_lbs_per_load": 0,
                "ai_analysis": {"polymer": "PP"},
            }
        )

        lead._reclassify_from_stored_evidence()

        self.assertEqual(lead.decision, "hot")
        self.assertEqual(lead.estimated_lbs_per_load, 200_000)
        self.assertTrue(lead.intake_id)
        activities = self.env["mail.activity"].search(
            [("res_model", "=", "plasticos.intake"), ("res_id", "=", lead.intake_id.id)]
        )
        self.assertFalse(activities)
        lead._reclassify_from_stored_evidence()
        self.assertEqual(self.env["plasticos.intake"].search_count([("source_lead_id", "=", lead.id)]), 1)

    def test_stored_area_and_small_weight_stay_cold(self):
        area = self.WebLead.create(
            {
                "lead_id": "REPLAY-SQFT",
                "decision": "cold",
                "state": "skipped",
                "company_name": "TGS",
                "quantity_text": "65,000 sqft",
                "estimated_lbs_per_load": 65_000,
                "ai_analysis": {"polymer": "PP"},
            }
        )
        small = self.WebLead.create(
            {
                "lead_id": "REPLAY-7200",
                "decision": "cold",
                "state": "skipped",
                "company_name": "Clean Management",
                "quantity_text": "7200",
                "estimated_lbs_per_load": 7_200,
                "ai_analysis": {"polymer": "HDPE"},
            }
        )

        area._reclassify_from_stored_evidence()
        small._reclassify_from_stored_evidence()

        self.assertEqual(area.decision, "cold")
        self.assertEqual(area.estimated_lbs_per_load, 0)
        self.assertFalse(area.intake_id)
        self.assertEqual(small.decision, "cold")
        self.assertFalse(small.intake_id)
