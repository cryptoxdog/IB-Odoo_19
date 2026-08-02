"""Contract tests for critical API surfaces and M7 retirement guards."""

from __future__ import annotations

from pathlib import Path

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.tests.common import tagged

ROOT = Path(__file__).resolve().parents[2]

RETIRED_MODULE_DIRS = (
    ROOT / "plasticos_buyer_match_engine",
    ROOT / "plasticos_inference_engine",
)

RETIRED_FALLBACK_TESTS = (
    ROOT / "tests" / "test_gate_matcher_fallback.py",
    ROOT / "tests" / "test_gate_enrichment_fallback.py",
)


def test_m7_retired_local_intelligence_modules_absent():
    """M7: physical delete — legacy matcher/inference addons must not remain on disk."""
    for path in RETIRED_MODULE_DIRS:
        assert not path.exists(), f"retired module directory still present: {path.relative_to(ROOT)}"


def test_m7_superseded_fallback_tests_absent():
    for path in RETIRED_FALLBACK_TESTS:
        assert not path.exists(), f"superseded fallback test still present: {path.relative_to(ROOT)}"


def test_m7_requirements_exclude_neo4j_driver():
    text = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    assert "neo4j>=" not in text


def test_m7_env_example_excludes_neo4j_variables():
    text = (ROOT / ".env.example").read_text(encoding="utf-8")
    assert "NEO4J_URL" not in text
    assert "NEO4J_PASSWORD" not in text


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
