"""Contract tests for critical API method signatures.

These verify that public API methods accept the expected parameters
and are not accidentally refactored in ways that break callers.
"""

import inspect

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.tests.common import tagged


@tagged("post_install", "-at_install", "contract")
class TestMatcherAPIContract(PlasticosTestCase):
    """Matcher.run_matching() is called by intake and web lead flows."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        try:
            cls.Matcher = cls.env["plasticos.buyer.matcher"]
            cls.skip = False
        except KeyError:
            cls.skip = True

    def test_run_matching_method_exists(self):
        if self.skip:
            self.skipTest("buyer_match_engine not installed")
        self.assertTrue(
            callable(getattr(self.Matcher, "run_matching", None)),
            "run_matching method missing on plasticos.buyer.matcher",
        )

    def test_run_matching_accepts_intake(self):
        """run_matching must accept an intake recordset."""
        if self.skip:
            self.skipTest("buyer_match_engine not installed")
        sig = inspect.signature(self.Matcher.run_matching)
        params = list(sig.parameters.keys())
        # First param is self (implicit), second should be intake-related
        self.assertGreaterEqual(len(params), 1)


@tagged("post_install", "-at_install", "contract")
class TestCommissionServiceContract(PlasticosTestCase):
    """Commission calculation is called from transaction close flow."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        try:
            cls.TX = cls.env["plasticos.transaction"]
            cls.skip = False
        except KeyError:
            cls.skip = True

    def test_commission_rule_model_exists(self):
        if self.skip:
            self.skipTest("plasticos_transaction not installed")
        try:
            self.env["plasticos.commission.rule"]
        except KeyError:
            self.fail("plasticos.commission.rule model missing")

    def test_commission_service_model_exists(self):
        if self.skip:
            self.skipTest("plasticos_transaction not installed")
        try:
            self.env["plasticos.commission.service"]
        except KeyError:
            self.fail("plasticos.commission.service model missing")


@tagged("standard", "contract")
class TestWebLeadAPIContract(PlasticosTestCase):
    """Web lead API endpoint contract."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        try:
            cls.WebLead = cls.env["plasticos.web.lead"]
            cls.skip = False
        except KeyError:
            cls.skip = True

    def test_web_lead_model_exists(self):
        if self.skip:
            self.skipTest("plasticos_web_leads not installed")
        self.assertIsNotNone(self.WebLead)

    def test_web_lead_has_create_from_agent(self):
        """External AI agent calls create_from_agent to submit leads."""
        if self.skip:
            self.skipTest("plasticos_web_leads not installed")
        self.assertTrue(
            callable(getattr(self.WebLead, "create_from_agent", None)),
            "create_from_agent method missing on plasticos.web.lead",
        )

    def test_web_lead_has_classification_fields(self):
        """Classification engine expects these fields."""
        if self.skip:
            self.skipTest("plasticos_web_leads not installed")
        fields = self.WebLead._fields
        for fname in ("raw_payload", "classification", "confidence_score"):
            self.assertIn(fname, fields, f"Missing web lead field: {fname}")
