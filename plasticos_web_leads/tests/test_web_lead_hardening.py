"""Security and human-authority hardening of web-lead admission (PR 187 audit F187-01..07).

These run against the real ORM under ``odoo --test-enable --test-tags /plasticos_web_leads``.
External AI/vision providers are never called: the relevant seams are patched
with deterministic fakes, and DNS resolution is injected so no test touches the
network.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from odoo.exceptions import AccessError, ConcurrencyError, UserError, ValidationError
from odoo.tests import TransactionCase, tagged

from ..models.review_snapshot import snapshot_content_hash

_ATTACHMENT_PROCESSOR = "odoo.addons.plasticos_web_leads.models.attachment_processor"
_WEB_LEAD = "odoo.addons.plasticos_web_leads.models.web_lead"
_SIGNED_URL = "https://www.cognitoforms.com/files/material.jpg?sig=SECRET-SIGNED-TOKEN"
_PUBLIC_IP = ["93.184.216.34"]
_ASSESSED = {"status": "assessed", "assessment": {"recommendation": "broker_review", "clarifications": []}}


def _hot_payload(external_id, attachments=None):
    return {
        "Entry": {"Number": external_id},
        "YourBusinessCompanyName": "HOT Co",
        "DescribeYourMaterial": "HDPE pellets",
        "WhatIsTheSourceOfThisMaterial": "Manufacturing production scrap",
        "WhatIsTheQuantity": "2 loads per month",
        "WeightPerLoad": "40000 lbs",
        "AreThereAnyContaminants": "none",
        "UploadPhotosOfYourScrapUpTo10": list(attachments or []),
    }


def _image_attachment(url=_SIGNED_URL, source_id="file-1"):
    return {"Id": source_id, "Name": "material.jpg", "File": url, "ContentType": "image/jpeg", "Size": 12}


def _image_response():
    response = MagicMock()
    response.status_code = 200
    response.headers = {"Content-Type": "image/jpeg"}
    response.raise_for_status.return_value = None
    response.iter_content.return_value = [b"legacy-image"]
    response.content = b"legacy-image"
    return response


class _WebLeadCase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.WebLead = cls.env["plasticos.web.lead"]
        cls.Snapshot = cls.env["plasticos.web.lead.review.snapshot"]
        cls.Attachment = cls.env["ir.attachment"]
        cls.config = cls.env["plasticos.web.lead.config"].sudo().get_config()
        # The test env user is the inactive OdooBot, which is deliberately not an
        # eligible reviewer; route to a real, active internal user instead.
        cls.reviewer = cls.env.ref("base.user_admin")
        cls.config.write(
            {
                "ai_enabled": False,
                "vision_enabled": False,
                "hot_intake_reviewer_id": cls.reviewer.id,
                "attachment_allowed_hosts": False,
            }
        )
        cls.internal_user = cls.env["res.users"].create(
            {
                "name": "Ordinary Internal User",
                "login": "web-lead-ordinary-user",
                "group_ids": [(6, 0, [cls.env.ref("base.group_user").id])],
            }
        )

    def _approved_hot_lead(self, external_id, attachments=None):
        """A HOT lead whose economic assessment completed, so it is approvable."""
        with (
            patch(f"{_WEB_LEAD}.evaluate_economic_opportunity", return_value=dict(_ASSESSED)),
            patch(f"{_ATTACHMENT_PROCESSOR}.requests.get", return_value=_image_response()),
            patch(f"{_ATTACHMENT_PROCESSOR}.resolve_host_addresses", return_value=_PUBLIC_IP),
        ):
            lead = self.WebLead.create_from_cognito(_hot_payload(external_id, attachments))
        self.assertEqual(lead.decision, "hot")
        self.assertTrue(lead.intake_id)
        return lead


@tagged("post_install", "-at_install", "plasticos", "web_lead", "hardening")
class TestSnapshotApprovalAuthority(_WebLeadCase):
    """F187-01: approved evidence is minted only by the server-owned approval path."""

    def _forged_vals(self, lead):
        payload = {"schema_version": "forged", "lead": {"lead_id": lead.lead_id}}
        return {
            "name": "forged",
            "web_lead_id": lead.id,
            "intake_id": lead.intake_id.id,
            "revision": 99,
            "approved_by_id": self.internal_user.id,
            "approved_at": "2020-01-01 00:00:00",
            "snapshot_payload": payload,
            "content_hash": snapshot_content_hash(payload),
        }

    def test_ordinary_internal_user_cannot_create_snapshot(self):
        lead = self._approved_hot_lead("HARD-SNAP-ACL-001")
        with self.assertRaises(AccessError):
            self.Snapshot.with_user(self.internal_user).create(self._forged_vals(lead))
        self.assertFalse(lead.review_snapshot_ids)

    def test_generic_create_with_forged_provenance_is_rejected_even_for_admin(self):
        lead = self._approved_hot_lead("HARD-SNAP-FORGE-001")
        forged = self._forged_vals(lead)
        with self.assertRaises(AccessError):
            self.Snapshot.create(forged)
        with self.assertRaises(AccessError):
            self.Snapshot.sudo().create(forged)
        # A JSON-RPC caller can send a string/boolean context key; it is not the token.
        with self.assertRaises(AccessError):
            self.Snapshot.with_context(plasticos_web_leads_broker_approval=True).create(forged)
        self.assertFalse(lead.review_snapshot_ids)

    def test_approval_action_derives_every_provenance_fact_server_side(self):
        lead = self._approved_hot_lead("HARD-SNAP-ACTION-001")
        lead.write({"review_notes": "Verified with the seller."})

        action = lead.action_approve_for_commercial_preparation()
        snapshot = self.env[action["res_model"]].browse(action["res_id"])

        self.assertEqual(lead.review_status, "approved")
        self.assertEqual(snapshot.web_lead_id, lead)
        self.assertEqual(snapshot.intake_id, lead.intake_id)
        self.assertEqual(snapshot.revision, 1)
        self.assertEqual(snapshot.approved_by_id, self.env.user)
        self.assertTrue(snapshot.approved_at)
        self.assertEqual(snapshot.content_hash, snapshot_content_hash(snapshot.snapshot_payload))
        self.assertEqual(snapshot.snapshot_payload["lead"]["lead_id"], lead.lead_id)
        self.assertEqual(snapshot.snapshot_payload["review_notes"], "Verified with the seller.")
        # Re-approving an approved lead opens the existing evidence; it never mints a duplicate.
        again = lead.action_approve_for_commercial_preparation()
        self.assertEqual(again["res_model"], snapshot._name)
        self.assertEqual(len(lead.review_snapshot_ids), 1)
        with self.assertRaises(UserError):
            snapshot.write({"content_hash": "tamper"})
        with self.assertRaises(UserError):
            snapshot.unlink()

    def test_approval_requires_internal_user_with_write_access_and_hot_intake(self):
        lead = self._approved_hot_lead("HARD-SNAP-GUARD-001")
        with self.assertRaises(AccessError):
            self.Snapshot.with_user(self.internal_user)._record_broker_approval(lead.with_user(self.internal_user))
        cold = self.WebLead.create({"lead_id": "HARD-SNAP-COLD-001", "decision": "cold", "company_name": "Cold Co"})
        with self.assertRaises(UserError):
            cold.action_approve_for_commercial_preparation()
        self.assertFalse(lead.review_snapshot_ids)
        self.assertFalse(cold.review_snapshot_ids)

    def test_hash_must_match_payload_even_on_the_server_path(self):
        lead = self._approved_hot_lead("HARD-SNAP-HASH-001")
        vals = self._forged_vals(lead)
        vals["content_hash"] = "0" * 64
        from ..models import web_lead_review_snapshot as module

        token_ctx = {module._APPROVAL_CONTEXT_KEY: module._APPROVAL_TOKEN}
        with self.assertRaises(ValidationError):
            self.Snapshot.sudo().with_context(**token_ctx).create(vals)


@tagged("post_install", "-at_install", "plasticos", "web_lead", "hardening")
class TestAcquisitionSecretsAndDestinations(_WebLeadCase):
    """F187-02 / F187-03 / F187-05 through the real pipeline."""

    def test_signed_url_never_reaches_storage_prompt_or_snapshot_but_bytes_are_retained(self):
        captured = {}

        def _fake_structured_text(_provider, *, system_prompt, user_prompt, **_kwargs):
            captured["prompt"] = user_prompt
            return {"polymer": "HDPE", "confidence": 0.9}, {"tokens": 1}

        self.config.write({"ai_enabled": True, "openai_api_key": "test-key-not-real"})
        try:
            with patch(
                "odoo.addons.plasticos_web_leads.models.ai_normalizer.call_structured_text", _fake_structured_text
            ):
                lead = self._approved_hot_lead("HARD-SECRET-001", [_image_attachment()])
        finally:
            self.config.write({"ai_enabled": False, "openai_api_key": False})

        self.assertIn("prompt", captured, "text normalization ran")
        self.assertNotIn("SECRET-SIGNED-TOKEN", captured["prompt"])
        self.assertNotIn("SECRET-SIGNED-TOKEN", json.dumps(lead.canonical_payload))
        self.assertNotIn("source_url", json.dumps(lead.canonical_payload["attachments"]))
        self.assertNotIn("SECRET-SIGNED-TOKEN", json.dumps(lead.evidence_bundle))

        row = lead.evidence_bundle["attachments"][0]
        self.assertEqual(row["acquisition_status"], "success")
        self.assertTrue(row["ir_attachment_id"])
        self.assertEqual(
            self.Attachment.search_count([("res_model", "=", "plasticos.web.lead"), ("res_id", "=", lead.id)]), 1
        )

        action = lead.action_approve_for_commercial_preparation()
        snapshot = self.env[action["res_model"]].browse(action["res_id"])
        serialized = json.dumps(snapshot.snapshot_payload)
        self.assertNotIn("SECRET-SIGNED-TOKEN", serialized)
        self.assertNotIn("source_url", serialized)
        self.assertEqual(snapshot.snapshot_payload["evidence"]["attachments"][0]["source_id"], "file-1")

    def test_private_destination_is_never_fetched_and_lead_is_still_admitted(self):
        with (
            patch(f"{_ATTACHMENT_PROCESSOR}.requests.get") as download,
            patch(f"{_ATTACHMENT_PROCESSOR}.resolve_host_addresses", return_value=["10.0.0.5"]),
        ):
            lead = self.WebLead.create_from_cognito(
                _hot_payload(
                    "HARD-SSRF-001",
                    [
                        _image_attachment("https://10.0.0.8/internal.jpg", "ip-literal"),
                        _image_attachment("https://www.cognitoforms.com/files/x.jpg", "dns-private"),
                        _image_attachment("https://evil.example.test/x.jpg", "unlisted"),
                    ],
                )
            )

        download.assert_not_called()
        self.assertNotEqual(lead.state, "error")
        rows = {row["source_id"]: row for row in lead.evidence_bundle["attachments"]}
        self.assertEqual(rows["ip-literal"]["error"]["code"], "destination_host_not_allowed")
        self.assertEqual(rows["dns-private"]["error"]["code"], "destination_address_rejected")
        self.assertEqual(rows["unlisted"]["error"]["code"], "destination_host_not_allowed")
        self.assertEqual(
            self.Attachment.search_count([("res_model", "=", "plasticos.web.lead"), ("res_id", "=", lead.id)]), 0
        )

    def test_redirect_to_private_target_is_rejected_after_public_first_hop(self):
        redirect = MagicMock()
        redirect.status_code = 302
        redirect.headers = {"Location": "https://169.254.169.254/latest/meta-data"}
        with (
            patch(f"{_ATTACHMENT_PROCESSOR}.requests.get", return_value=redirect) as download,
            patch(f"{_ATTACHMENT_PROCESSOR}.resolve_host_addresses", return_value=_PUBLIC_IP),
        ):
            lead = self.WebLead.create_from_cognito(_hot_payload("HARD-SSRF-REDIRECT-001", [_image_attachment()]))

        self.assertEqual(download.call_count, 1)
        self.assertFalse(download.call_args.kwargs["allow_redirects"])
        row = lead.evidence_bundle["attachments"][0]
        self.assertEqual(row["acquisition_status"], "failed")
        self.assertEqual(row["error"]["code"], "destination_host_not_allowed")

    def test_operator_allowlist_extends_provider_default(self):
        self.config.write({"attachment_allowed_hosts": "files.partner.example"})
        try:
            with (
                patch(f"{_ATTACHMENT_PROCESSOR}.requests.get", return_value=_image_response()),
                patch(f"{_ATTACHMENT_PROCESSOR}.resolve_host_addresses", return_value=_PUBLIC_IP),
            ):
                lead = self.WebLead.create_from_cognito(
                    _hot_payload("HARD-ALLOW-001", [_image_attachment("https://files.partner.example/a.jpg")])
                )
        finally:
            self.config.write({"attachment_allowed_hosts": False})
        self.assertEqual(lead.evidence_bundle["attachments"][0]["acquisition_status"], "success")

    def test_error_shaped_vision_result_is_failed_evidence_requiring_review(self):
        self.config.write({"vision_enabled": True, "openai_api_key": "test-key-not-real"})
        try:
            with (
                patch(f"{_ATTACHMENT_PROCESSOR}.requests.get", return_value=_image_response()),
                patch(f"{_ATTACHMENT_PROCESSOR}.resolve_host_addresses", return_value=_PUBLIC_IP),
                patch(
                    f"{_WEB_LEAD}.image_analyzer.analyze_image_with_provider",
                    return_value={"error": "provider_inference_failed", "provider": {"provider": "openai"}},
                ),
            ):
                lead = self.WebLead.create_from_cognito(_hot_payload("HARD-VISION-ERR-001", [_image_attachment()]))
        finally:
            self.config.write({"vision_enabled": False, "openai_api_key": False})

        row = lead.evidence_bundle["attachments"][0]
        self.assertEqual(row["acquisition_status"], "success", "stored evidence is preserved")
        self.assertEqual(row["analysis_status"], "failed")
        self.assertEqual(row["error"]["code"], "image_analysis_error")
        self.assertFalse(lead.ai_vision_results, "no error-shaped result is stored as a vision result")
        self.assertEqual(lead.evidence_bundle["vision"], [])
        self.assertEqual(lead.decision, "hot")
        self.assertEqual(lead.review_status, "clarification_required")
        self.assertIn("no visual analysis succeeded", lead.review_required_reason)
        self.assertTrue(lead.decision_reasons["review_required"])


@tagged("post_install", "-at_install", "plasticos", "web_lead", "hardening")
class TestHotReviewerRouting(_WebLeadCase):
    """F187-06: a HOT handoff reaches only the explicitly configured internal reviewer."""

    def test_missing_reviewer_produces_blocked_handoff_not_technical_assignment(self):
        self.config.write({"hot_intake_reviewer_id": False})
        try:
            # The webhook path runs under sudo after token auth: the technical
            # actor must never become the reviewer.
            lead = self.WebLead.sudo().create_from_cognito(_hot_payload("HARD-REVIEW-NONE-001"))
        finally:
            self.config.write({"hot_intake_reviewer_id": self.reviewer.id})

        self.assertTrue(lead.intake_id)
        self.assertEqual(lead.state, "intake_created")
        self.assertEqual(lead.mack_review_state, "blocked")
        self.assertIn("not configured", lead.mack_review_reason.lower())
        self.assertFalse(lead.intake_id.activity_ids)
        self.assertFalse(
            self.env["mail.activity"].search_count(
                [("res_model", "=", "plasticos.intake"), ("res_id", "=", lead.intake_id.id)]
            )
        )

        lead.action_route_hot_review()
        self.assertEqual(lead.mack_review_state, "queued")
        self.assertEqual(lead.intake_id.activity_ids.user_id, self.reviewer)

    def test_configured_reviewer_receives_the_activity_exactly_once(self):
        lead = self.WebLead.sudo().create_from_cognito(_hot_payload("HARD-REVIEW-SET-001"))
        activities = lead.intake_id.activity_ids
        self.assertEqual(len(activities), 1)
        self.assertEqual(activities.user_id, self.reviewer)
        self.assertNotEqual(activities.user_id, self.env.user, "the ingestion actor is never the reviewer")
        self.assertEqual(lead.mack_review_state, "queued")
        lead.action_route_hot_review()
        self.assertEqual(len(lead.intake_id.activity_ids), 1, "routing is idempotent")

    def test_inactive_or_portal_reviewer_is_not_eligible(self):
        portal_group = self.env.ref("base.group_portal", raise_if_not_found=False)
        if not portal_group:
            self.skipTest("portal group unavailable")
        portal = self.env["res.users"].create(
            {"name": "Portal Reviewer", "login": "web-lead-portal-reviewer", "group_ids": [(6, 0, [portal_group.id])]}
        )
        self.config.write({"hot_intake_reviewer_id": portal.id})
        try:
            lead = self.WebLead.sudo().create_from_cognito(_hot_payload("HARD-REVIEW-PORTAL-001"))
        finally:
            self.config.write({"hot_intake_reviewer_id": self.reviewer.id})
        self.assertEqual(lead.mack_review_state, "blocked")
        self.assertFalse(lead.intake_id.activity_ids)


@tagged("post_install", "-at_install", "plasticos", "web_lead", "hardening")
class TestIdentityAndIdempotency(_WebLeadCase):
    """F187-04 / F187-07 at the model level."""

    def test_legacy_agent_payload_without_lead_id_gets_server_identity(self):
        lead = self.WebLead.create_from_agent({"decision": "cold", "raw_payload": {"CompanyName": "Legacy Co"}})
        self.assertTrue(lead.lead_id.startswith("WL-"))
        self.assertEqual(lead.company_name, "Legacy Co")
        self.assertNotEqual(lead.state, "error")

    def test_legacy_agent_payload_identity_is_idempotent(self):
        payload = {"lead_id": "HARD-AGENT-IDEMP-001", "decision": "cold", "raw_payload": {}}
        first = self.WebLead.create_from_agent(payload)
        second = self.WebLead.create_from_agent(payload)
        self.assertEqual(first, second)

    def test_unique_collision_is_treated_as_replay_and_returns_prior_receipt(self):
        payload = _hot_payload("HARD-RACE-001")
        winner = self.WebLead.create_from_cognito(payload)
        WebLeadClass = type(self.WebLead)

        # Simulate the concurrent window: the pre-check search misses, so the
        # loser reaches the unique constraint and must recover.
        with patch.object(WebLeadClass, "_find_existing_lead", side_effect=[self.WebLead.browse(), winner]):
            with patch.object(WebLeadClass, "_run_triage_pipeline") as triage:
                loser = self.WebLead.create_from_cognito(payload)

        self.assertEqual(loser, winner)
        triage.assert_not_called()
        self.assertEqual(self.WebLead.search_count([("lead_id", "=", "CG-HARD-RACE-001")]), 1)
        # The transaction is still usable after the savepoint recovery.
        self.assertTrue(self.WebLead.create({"lead_id": "HARD-RACE-AFTER-001", "decision": "cold"}))

    def test_invisible_winner_escalates_to_a_request_replay(self):
        """Under REPEATABLE READ the loser cannot see the winner; it must ask for a fresh transaction."""
        payload = _hot_payload("HARD-RACE-002")
        self.WebLead.create_from_cognito(payload)
        WebLeadClass = type(self.WebLead)

        with patch.object(WebLeadClass, "_find_existing_lead", return_value=self.WebLead.browse()):
            with patch.object(WebLeadClass, "_run_triage_pipeline") as triage:
                with self.assertRaises(ConcurrencyError):
                    self.WebLead.create_from_cognito(payload)

        triage.assert_not_called()
        self.assertEqual(self.WebLead.search_count([("lead_id", "=", "CG-HARD-RACE-002")]), 1)
        self.assertTrue(self.WebLead.create({"lead_id": "HARD-RACE-AFTER-002", "decision": "cold"}))

    def test_replay_with_different_provider_submission_is_rejected(self):
        winner = self.WebLead.create_from_cognito(_hot_payload("HARD-RACE-MISMATCH-001"))
        # Provider identity is immutable through the ORM once an intake exists;
        # simulate a stored row bound to a different provider submission directly.
        self.env.cr.execute(
            "UPDATE plasticos_web_lead SET provider_external_id = %s WHERE id = %s", ("OTHER", winner.id)
        )
        winner.invalidate_recordset(["provider_external_id"])
        with self.assertRaises(UserError):
            self.WebLead.create_from_cognito(_hot_payload("HARD-RACE-MISMATCH-001"))
