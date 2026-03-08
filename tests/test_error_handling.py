"""Error handling tests for PlastOS robustness.

Covers:
    - API failures (external service unavailable)
    - Invalid data (malformed imports)
    - Permission denied (ACL enforcement)
    - Concurrent edits (optimistic locking)
    - Rollback scenarios (transaction failures)

These tests validate that PlastOS handles errors gracefully:
- External service failures don't crash the system
- Invalid data is rejected with clear error messages
- Permission checks are enforced correctly
- Concurrent operations are handled safely
- Failed operations roll back cleanly
"""

from unittest.mock import patch

from psycopg2 import IntegrityError

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests.common import tagged


# ═══════════════════════════════════════════════════════════════
# API Failure Tests
# ═══════════════════════════════════════════════════════════════
@tagged("post_install", "-at_install", "plasticos", "error_handling", "api")
class TestAPIFailures(PlasticosTestCase):
    """Tests for graceful handling of external API failures."""

    def test_neo4j_unavailable_graceful(self):
        if "plasticos.graph.service" not in self.env:
            self.skipTest("Graph service not installed")
        svc = self.env["plasticos.graph.service"]
        result = svc._execute_cypher("RETURN 1")
        self.assertEqual(result, [], "Should return empty list when Neo4j unavailable")

    def test_neo4j_execute_cypher_query_raises_usererror(self):
        if "plasticos.graph.service" not in self.env:
            self.skipTest("Graph service not installed")
        svc = self.env["plasticos.graph.service"]
        with self.assertRaises(UserError):
            svc.execute_cypher_query("RETURN 1")

    def test_enrichment_api_failure_caught(self):
        if "plasticos.enrichment.run" not in self.env:
            self.skipTest("Enrichment not installed")
        run = self.env["plasticos.enrichment.run"].create({})
        if hasattr(run, "action_execute"):
            with patch.object(type(run), "_crawl_source", side_effect=Exception("API down")):
                try:
                    run.action_execute()
                except Exception:
                    pass
                self.assertIn(run.state, ("error", "draft"))

    def test_geo_backfill_api_timeout(self):
        partner = self._partner("Geo Timeout")
        us_country = self.env.ref("base.us", raise_if_not_found=False)
        partner.write({"city": "Test", "country_id": us_country.id if us_country else False})
        if hasattr(partner, "cron_geo_backfill"):
            with patch("requests.get", side_effect=Exception("Timeout")):
                partner.cron_geo_backfill()

    def test_ai_normalize_failure_sets_error_state(self):
        if "plasticos.web.lead" not in self.env:
            self.skipTest("Web leads not installed")
        import uuid

        lead = self.env["plasticos.web.lead"].create(
            {
                "lead_id": f"ERR-{uuid.uuid4().hex[:8]}",
                "decision": "cold",
                "company_name": "Fail Co",
                "state": "received",
                "raw_payload": {"test": True},
            }
        )
        with patch(
            "odoo.addons.plasticos_web_leads.models.ai_normalizer.normalize_with_llm",
            side_effect=Exception("API error"),
        ):
            lead._run_triage_pipeline()
        self.assertEqual(lead.state, "error")
        self.assertIn("API error", lead.error_message or "")


# ═══════════════════════════════════════════════════════════════
# Invalid Data Tests
# ═══════════════════════════════════════════════════════════════
@tagged("post_install", "-at_install", "plasticos", "error_handling", "validation")
class TestInvalidData(PlasticosTestCase):
    """Tests for rejection of invalid data with appropriate errors."""

    def test_intake_missing_required_fields(self):
        if "plasticos.intake" not in self.env:
            self.skipTest("plasticos.intake not installed")
        raised = False
        try:
            self.env["plasticos.intake"].create({})
        except (ValidationError, IntegrityError):
            raised = True
        self.assertTrue(raised, "Expected exception was not raised")

    def test_web_lead_duplicate_lead_id(self):
        if "plasticos.web.lead" not in self.env:
            self.skipTest("Web leads not installed")
        self.env["plasticos.web.lead"].create(
            {
                "lead_id": "DUP-001",
                "decision": "cold",
                "company_name": "Dup Co",
            }
        )
        raised = False
        try:
            self.env["plasticos.web.lead"].create(
                {
                    "lead_id": "DUP-001",
                    "decision": "cold",
                    "company_name": "Dup Co 2",
                }
            )
        except (ValidationError, IntegrityError):
            raised = True
        self.assertTrue(raised, "Expected exception was not raised")

    def test_web_lead_create_from_agent_missing_lead_id(self):
        if "plasticos.web.lead" not in self.env:
            self.skipTest("Web leads not installed")
        with self.assertRaises(UserError):
            self.env["plasticos.web.lead"].create_from_agent({})

    def test_claim_invalid_state_transition(self):
        if "plasticos.claim" not in self.env:
            self.skipTest("Claims not installed")
        tx = self.env["plasticos.transaction"].create({"name": "TX-ERR-CLM"})
        claim = self.env["plasticos.claim"].create(
            {
                "transaction_id": tx.id,
                "case_type": "buyer_claim",
                "severity": "medium",
                "state": "pending",
            }
        )
        if hasattr(claim, "action_close"):
            with self.assertRaises(UserError):
                claim.action_close()

    def test_offer_negative_price_rejected(self):
        """Negative prices should be rejected."""
        if "plasticos.offer" not in self.env:
            self.skipTest("Offer not installed")
        partner = self._create_partner()
        Offer = self.env["plasticos.offer"]
        if "price_per_lb" in Offer._fields:
            raised = False
            try:
                Offer.create({"buyer_partner_id": partner.id, "price_per_lb": -1.0})
            except (ValidationError, IntegrityError):
                raised = True
            self.assertTrue(raised, "Expected exception was not raised")

    def test_load_cancel_from_delivered_rejected(self):
        if "plasticos.load" not in self.env:
            self.skipTest("Load not installed")
        load = self.env["plasticos.load"].create({"state": "delivered"})
        if hasattr(load, "action_cancel"):
            with self.assertRaises(UserError):
                load.action_cancel()

    def test_safe_int_helper_handles_garbage(self):
        from odoo.addons.plasticos_web_leads.models.web_lead import _safe_int

        self.assertEqual(_safe_int(None), 0)
        self.assertEqual(_safe_int("garbage"), 0)
        self.assertEqual(_safe_int("123"), 123)
        self.assertEqual(_safe_int(45.6), 45)


# ═══════════════════════════════════════════════════════════════
# Permission / ACL Tests
# ═══════════════════════════════════════════════════════════════
@tagged("post_install", "-at_install", "plasticos", "error_handling", "security")
class TestPermissionDenied(PlasticosTestCase):
    """Tests for ACL enforcement and permission denied scenarios."""

    def test_non_admin_cannot_write_config(self):
        """Regular users cannot modify system config."""
        if "plasticos.web.lead.config" not in self.env:
            self.skipTest("Web lead config not installed")
        demo_user = self.env.ref("base.user_demo", raise_if_not_found=False)
        if not demo_user:
            self.skipTest("Demo user not available")
        Config = self.env["plasticos.web.lead.config"].with_user(demo_user)
        with self.assertRaises(AccessError):
            Config.create({"name": "Unauthorized"})

    def test_non_admin_cannot_delete_intake(self):
        """Regular users should not be able to delete intakes."""
        if "plasticos.intake" not in self.env:
            self.skipTest("plasticos.intake not installed")
        partner = self._create_partner()
        polymer = self._get_or_create_polymer()
        form = self._get_or_create_form()
        intake = self._create_intake(partner=partner, polymer=polymer, form=form)
        demo_user = self.env.ref("base.user_demo", raise_if_not_found=False)
        if not demo_user:
            self.skipTest("Demo user not available")
        with self.assertRaises(AccessError):
            intake.with_user(demo_user).unlink()


# ═══════════════════════════════════════════════════════════════
# Concurrent Edit Tests
# ═══════════════════════════════════════════════════════════════
@tagged("post_install", "-at_install", "plasticos", "error_handling", "concurrency")
class TestConcurrentEdits(PlasticosTestCase):
    """Tests for concurrent edit handling and idempotency."""

    def test_advisory_lock_prevents_double_cron(self):
        """Advisory lock pattern prevents concurrent cron runs."""
        if "plasticos.graph.service" not in self.env:
            self.skipTest("Graph service not installed")
        svc = self.env["plasticos.graph.service"]
        with patch.object(self.env.cr, "execute"), patch.object(self.env.cr, "fetchone", return_value=(False,)):
            result = svc._cron_nightly_graph_sync()
            self.assertIn("Skipped", result)

    def test_idempotent_web_lead_creation(self):
        if "plasticos.web.lead" not in self.env:
            self.skipTest("Web leads not installed")
        payload = {
            "lead_id": "IDEMP-001",
            "decision": "cold",
            "raw_payload": {"test": True},
        }
        lead1 = self.env["plasticos.web.lead"].create_from_agent(payload)
        lead2 = self.env["plasticos.web.lead"].create_from_agent(payload)
        self.assertEqual(lead1.id, lead2.id, "Should return same record on duplicate")


# ═══════════════════════════════════════════════════════════════
# Rollback / Transaction Tests
# ═══════════════════════════════════════════════════════════════
@tagged("post_install", "-at_install", "plasticos", "error_handling", "rollback")
class TestRollbackScenarios(PlasticosTestCase):
    """Tests for atomic operations and rollback on failure."""

    def test_intake_creation_atomic(self):
        """Failed intake creation does not leave partial records."""
        if "plasticos.intake" not in self.env:
            self.skipTest("plasticos.intake not installed")
        count_before = self.env["plasticos.intake"].search_count([])
        try:
            self.env["plasticos.intake"].create(
                {
                    "partner_id": False,  # Should fail validation
                }
            )
        except Exception:
            pass
        count_after = self.env["plasticos.intake"].search_count([])
        self.assertEqual(count_before, count_after, "Failed create should not leave partial records")

    def test_web_lead_triage_error_state(self):
        """Pipeline error sets state=error, does not leave inconsistent data."""
        if "plasticos.web.lead" not in self.env:
            self.skipTest("Web leads not installed")
        import uuid

        lead = self.env["plasticos.web.lead"].create(
            {
                "lead_id": f"ROLL-{uuid.uuid4().hex[:8]}",
                "decision": "cold",
                "company_name": "Rollback Co",
                "state": "received",
                "raw_payload": {"test": True},
            }
        )
        with patch.object(type(lead), "_merge_ai_and_vision", side_effect=Exception("Merge failed")):
            lead._run_triage_pipeline()
        self.assertEqual(lead.state, "error")
        self.assertFalse(lead.intake_id)
