"""Security and human-authority hardening of web-lead admission (PR 187 audit F187-01..07).

These run against the real ORM under ``odoo --test-enable --test-tags /plasticos_web_leads``.
External AI/vision providers are never called: the relevant seams are patched
with deterministic fakes, and DNS resolution is injected so no test touches the
network.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from lxml import etree

from odoo.exceptions import AccessError, ConcurrencyError, UserError, ValidationError
from odoo.tests import TransactionCase, tagged

from ..models.review_snapshot import snapshot_content_hash
from .test_broker_one_pass import economic_assessment_patch

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
            economic_assessment_patch(return_value=dict(_ASSESSED)),
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

        result = lead.action_approve_for_commercial_preparation()
        # The broker stays on the lead: the action opens no snapshot screen.
        self.assertIs(result, True)
        snapshot = lead.review_snapshot_ids
        self.assertEqual(len(snapshot), 1)

        self.assertEqual(lead.review_status, "approved")
        self.assertEqual(snapshot.web_lead_id, lead)
        self.assertEqual(snapshot.intake_id, lead.intake_id)
        self.assertEqual(snapshot.revision, 1)
        self.assertEqual(snapshot.approved_by_id, self.env.user)
        self.assertTrue(snapshot.approved_at)
        self.assertEqual(snapshot.content_hash, snapshot_content_hash(snapshot.snapshot_payload))
        self.assertEqual(snapshot.snapshot_payload["lead"]["lead_id"], lead.lead_id)
        self.assertEqual(snapshot.snapshot_payload["review_notes"], "Verified with the seller.")
        # A replayed or double-clicked approval is a no-op; it never mints a duplicate.
        again = lead.action_approve_for_commercial_preparation()
        self.assertIs(again, True)
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
class TestSilentApprovalEvidence(_WebLeadCase):
    """Approval is one business action; its evidence is recorded without any snapshot interaction."""

    _APPROVAL_MESSAGE = "is broker-approved only through its Approve action"

    def test_reapproval_after_a_new_review_decision_mints_the_next_revision(self):
        lead = self._approved_hot_lead("HARD-SILENT-REAPPROVE-001")
        lead.action_approve_for_commercial_preparation()
        first = lead.review_snapshot_ids
        first_hash, first_payload = first.content_hash, dict(first.snapshot_payload)

        lead.action_request_clarification()
        self.assertEqual(lead.review_status, "clarification_required")
        self.assertEqual(lead.review_snapshot_ids, first, "clarification records no approval evidence")
        lead.write({"review_notes": "Seller confirmed the corrected weight."})
        lead.action_approve_for_commercial_preparation()

        self.assertEqual(lead.review_status, "approved")
        self.assertEqual(sorted(lead.review_snapshot_ids.mapped("revision")), [1, 2])
        self.assertEqual(first.content_hash, first_hash, "the earlier revision is unchanged")
        self.assertEqual(dict(first.snapshot_payload), first_payload)
        latest = lead.review_snapshot_ids.filtered(lambda snap: snap.revision == 2)
        self.assertEqual(latest.snapshot_payload["review_notes"], "Seller confirmed the corrected weight.")

    def test_reject_records_no_approval_evidence(self):
        lead = self._approved_hot_lead("HARD-SILENT-REJECT-001")
        lead.action_reject_after_review()
        self.assertEqual(lead.review_status, "rejected")
        self.assertFalse(lead.review_snapshot_ids)

    def test_direct_status_write_cannot_approve(self):
        lead = self._approved_hot_lead("HARD-SILENT-BYPASS-001")
        with self.assertRaisesRegex(AccessError, self._APPROVAL_MESSAGE):
            lead.write({"review_status": "approved"})
        with self.assertRaisesRegex(AccessError, self._APPROVAL_MESSAGE):
            lead.sudo().write({"review_status": "approved"})
        with self.assertRaisesRegex(AccessError, self._APPROVAL_MESSAGE):
            lead.with_user(self.internal_user).sudo().write({"review_status": "approved"})
        lead.invalidate_recordset()
        self.assertNotEqual(lead.review_status, "approved")
        self.assertFalse(lead.review_snapshot_ids)

    def test_rpc_context_cannot_forge_the_approval_token(self):
        lead = self._approved_hot_lead("HARD-SILENT-RPC-001")
        # A JSON-RPC client can send only JSON values in a context; none is the token.
        for forged in (True, 1, "token", {"token": True}):
            with self.assertRaisesRegex(AccessError, self._APPROVAL_MESSAGE):
                lead.with_context(plasticos_web_leads_approval_status_write=forged).write({"review_status": "approved"})
        with self.assertRaisesRegex(AccessError, self._APPROVAL_MESSAGE):
            self.WebLead.create({"lead_id": "HARD-SILENT-RPC-CREATE-001", "review_status": "approved"})
        lead.invalidate_recordset()
        self.assertNotEqual(lead.review_status, "approved")
        self.assertFalse(lead.review_snapshot_ids)

    def test_rewriting_approved_on_an_approved_lead_is_not_a_transition(self):
        lead = self._approved_hot_lead("HARD-SILENT-REPLAY-001")
        lead.action_approve_for_commercial_preparation()
        lead.write({"review_status": "approved"})  # e.g. a triage replay keeps the existing status
        self.assertEqual(lead.review_status, "approved")
        self.assertEqual(len(lead.review_snapshot_ids), 1)

    def test_failed_evidence_leaves_no_approval(self):
        lead = self._approved_hot_lead("HARD-SILENT-EVIDENCE-FAIL-001")
        with (
            patch.object(
                type(self.Snapshot), "_record_broker_approval", side_effect=ValidationError("evidence refused")
            ),
            self.assertRaises(ValidationError),
        ):
            lead.action_approve_for_commercial_preparation()
        lead.invalidate_recordset()
        self.assertNotEqual(lead.review_status, "approved")
        self.assertFalse(lead.review_snapshot_ids)

    def test_failure_after_evidence_rolls_back_the_evidence_too(self):
        lead = self._approved_hot_lead("HARD-SILENT-ATOMIC-001")
        # Odoo's assertRaises runs its block in a savepoint, standing in for the
        # request transaction: a failure after the snapshot was minted must take
        # both the snapshot and the approved status with it.
        with (
            patch.object(type(lead), "message_post", side_effect=UserError("late failure")),
            self.assertRaises(UserError),
        ):
            lead.action_approve_for_commercial_preparation()
        self.env.invalidate_all()
        self.assertNotEqual(lead.review_status, "approved")
        self.assertEqual(self.Snapshot.search_count([("web_lead_id", "=", lead.id)]), 0)

    def test_composed_form_has_no_snapshot_interaction(self):
        arch = etree.fromstring(self.WebLead.get_views([(False, "form")])["views"]["form"]["arch"])
        approve = arch.xpath("//button[@name='action_approve_for_commercial_preparation']")
        self.assertEqual(len(approve), 1)
        self.assertEqual(approve[0].get("string"), "Approve")
        self.assertIsNone(approve[0].get("confirm"), "approval asks no snapshot confirmation")
        self.assertFalse(arch.xpath("//button[@name='action_view_review_snapshots']"))
        self.assertFalse(arch.xpath("//field[@name='review_snapshot_count']"))
        self.assertFalse(arch.xpath("//field[@name='review_snapshot_ids']"))
        self.assertNotIn("Snapshot", etree.tostring(arch, encoding="unicode"))
        status_fields = arch.xpath("//field[@name='review_status']")
        self.assertTrue(status_fields)
        for node in status_fields:
            self.assertIn(node.get("readonly"), ("1", "True", "true"), "approval status is not hand-editable")


@tagged("post_install", "-at_install", "plasticos", "web_lead", "hardening")
class TestAcquisitionSecretsAndDestinations(_WebLeadCase):
    """F187-02 / F187-03 / F187-05 through the real pipeline."""

    def test_signed_url_never_reaches_storage_prompt_or_snapshot_but_bytes_are_retained(self):
        captured = {}

        def _fake_structured_text(_provider, *, system_prompt, user_prompt, **_kwargs):
            captured["prompt"] = user_prompt
            return {"polymer": "HDPE", "confidence": 0.9}, {"tokens": 1}

        previous_text_provider = self.config.text_inference_provider
        self.config.write(
            {"ai_enabled": True, "openai_api_key": "test-key-not-real", "text_inference_provider": "openai"}
        )
        try:
            with patch(
                "odoo.addons.plasticos_web_leads.models.ai_normalizer.call_structured_text", _fake_structured_text
            ):
                lead = self._approved_hot_lead("HARD-SECRET-001", [_image_attachment()])
        finally:
            self.config.write(
                {"ai_enabled": False, "openai_api_key": False, "text_inference_provider": previous_text_provider}
            )

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

        lead.action_approve_for_commercial_preparation()
        snapshot = lead.review_snapshot_ids
        self.assertEqual(len(snapshot), 1)
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
        self.assertIn("no web-lead reviewer is configured", lead.mack_review_reason.lower())
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


@tagged("post_install", "-at_install", "plasticos", "web_lead", "hardening")
class TestRejectedInboundIdempotency(_WebLeadCase):
    """A repeated invalid delivery with a stable provider identity never adds a second rejection row."""

    def _invalid_body(self, number):
        return {
            "Entry": {"Number": number, "DateSubmitted": "2026-09-21T12:00:00Z"},
            "YourBusinessCompanyName": "Rejected Co",
            "UploadPhotosOfYourScrapUpTo10": [
                {"Id": "dup", "Name": "a.jpg", "File": "https://www.cognitoforms.com/fa/a"},
                {"Id": "dup", "Name": "b.jpg", "File": "https://www.cognitoforms.com/fa/b"},
            ],
        }

    def test_repeated_rejected_delivery_updates_the_one_row(self):
        body = self._invalid_body("7001")
        first = self.WebLead.record_rejected_inbound("cognito", body, "Duplicate Cognito attachment source ID: dup.")
        second = self.WebLead.record_rejected_inbound("cognito", body, "Duplicate Cognito attachment source ID: dup.")
        self.assertEqual(first.id, second.id)
        self.assertEqual(first.lead_id, "REJ-cognito-7001")
        self.assertEqual(first.provider_external_id, "7001")
        self.assertEqual(first.state, "error")
        self.assertEqual(self.WebLead.search_count([("provider_external_id", "=", "7001")]), 1)

    def test_repeated_rejected_delivery_refreshes_the_reason(self):
        body = self._invalid_body("7002")
        first = self.WebLead.record_rejected_inbound("cognito", body, "first reason")
        again = self.WebLead.record_rejected_inbound("cognito", body, "second reason")
        self.assertEqual(first.id, again.id)
        self.assertEqual(again.error_message, "second reason")

    def test_rejection_identity_does_not_capture_a_later_valid_resubmission(self):
        body = self._invalid_body("7003")
        rejected = self.WebLead.record_rejected_inbound("cognito", body, "bad attachments")
        valid = dict(body)
        valid["UploadPhotosOfYourScrapUpTo10"] = []
        valid["WhatIsIt"] = "HDPE regrind"
        admitted = self.WebLead.create_from_cognito(valid)
        self.assertNotEqual(admitted.id, rejected.id)
        self.assertEqual(admitted.lead_id, "CG-7003")
        self.assertNotEqual(admitted.state, "error")

    def test_delivery_without_a_stable_identity_gets_a_server_identity_each_time(self):
        body = {"YourBusinessCompanyName": "No Entry Co"}
        first = self.WebLead.record_rejected_inbound("cognito", body, "no identity")
        second = self.WebLead.record_rejected_inbound("cognito", body, "no identity")
        self.assertNotEqual(first.id, second.id)
        self.assertFalse(first.provider_external_id)
        self.assertTrue(first.lead_id.startswith("WL-") or first.lead_id)


@tagged("post_install", "-at_install", "plasticos", "web_lead", "hardening")
class TestDefaultProviderField(_WebLeadCase):
    """The required default-provider field: its default, its backfill, and the fallback that reads it."""

    def test_config_default_is_cognito_and_the_field_is_required(self):
        field = self.config._fields["inbound_default_provider_key"]
        self.assertTrue(field.required)
        fresh = self.env["plasticos.web.lead.config"].new({})
        self.assertEqual(fresh.inbound_default_provider_key, "cognito")
        self.assertEqual(self.config.inbound_default_provider_key, "cognito")

    def test_lead_without_a_provider_key_falls_back_to_the_configured_default(self):
        lead = self.WebLead.create(
            {"lead_id": "FALLBACK-1", "source": "web_lead", "decision": "cold", "raw_payload": {}, "state": "received"}
        )
        self.assertFalse(lead.provider_key)
        hosts = lead._attachment_allowed_hosts(self.config)
        self.assertIn("cognitoforms.com", hosts)
        self.config.write({"inbound_default_provider_key": "no-such-provider"})
        self.assertEqual(lead._attachment_allowed_hosts(self.config), self.config.get_attachment_allowed_hosts(()))

    def test_admitted_lead_records_its_own_provider_key(self):
        lead = self.WebLead.create_from_cognito(
            {"Entry": {"Number": "7100"}, "YourBusinessCompanyName": "Keyed Co", "WhatIsIt": "HDPE regrind"}
        )
        self.assertEqual(lead.provider_key, "cognito")

    def test_migration_backfills_null_provider_keys_and_an_empty_default(self):
        import importlib.util
        from pathlib import Path

        lead = self.WebLead.create(
            {"lead_id": "BACKFILL-1", "source": "web_lead", "decision": "cold", "raw_payload": {}, "state": "received"}
        )
        self.env.cr.execute("UPDATE plasticos_web_lead SET provider_key = NULL WHERE id = %s", (lead.id,))
        self.env.cr.execute(
            "UPDATE plasticos_web_lead_config SET inbound_default_provider_key = '' WHERE id = %s", (self.config.id,)
        )
        path = Path(__file__).resolve().parents[1] / "migrations" / "19.0.2.8.0" / "post-migrate.py"
        spec = importlib.util.spec_from_file_location("web_lead_provider_backfill", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.migrate(self.env.cr, "19.0.2.7.2")
        lead.invalidate_recordset(["provider_key"])
        self.config.invalidate_recordset(["inbound_default_provider_key"])
        self.assertEqual(lead.provider_key, "cognito")
        self.assertEqual(self.config.inbound_default_provider_key, "cognito")
