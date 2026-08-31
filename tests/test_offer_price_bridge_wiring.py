"""Structural wiring tests for plasticos_offer/models/offer_price_bridge.py.

No Odoo runtime required — this is a source-level contract check.

Architecture note (2026-08 reconciliation): this file was ``test_wiring_gap2.py``,
a 24-case "GAP-2 pack" suite. 19 of those cases were permanently dead:

  * ``TestMatchResultWriter``, ``TestIntakeExtensionPatch``, ``TestMigration210``
    and the ``__init___patched`` cases pointed into
    ``plasticos_buyer_match_engine/``, physically retired in M7 / TASK-051
    (docs/adr/ADR-003-single-external-intelligence-authority.md). Reintroducing
    that directory is blocked by ci/check_no_local_intelligence.py, and
    tests/contracts/test_no_local_intelligence.py asserts it stays absent — so
    those ``skipif(not os.path.exists(...))`` guards could never become live again.
  * The ``*_patched.py`` targets were scratch files from a staging pack that was
    never merged; no such path has ever existed in this repository.

Only the offer price bridge group bound to a file that exists, so that is what
this module now is. Deleted coverage was for retired code, not lost behavior.
"""

import os

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BRIDGE_PATH = os.path.join(REPO_ROOT, "plasticos_offer", "models", "offer_price_bridge.py")


@pytest.mark.skipif(not os.path.exists(BRIDGE_PATH), reason="offer_price_bridge.py not in repo")
class TestOfferPriceBridge:
    """offer_price_bridge.py must back-fill offer price from intake match data."""

    def _src(self):
        with open(BRIDGE_PATH) as f:
            return f.read()

    def test_inherit_plasticos_offer(self):
        assert '"plasticos.offer"' in self._src()

    def test_create_multi_override(self):
        assert "model_create_multi" in self._src()
        assert "def create" in self._src()

    def test_only_fills_when_price_zero(self):
        src = self._src()
        assert "price_per_lb" in src
        assert "== 0.0" in src or "or 0.0" in src

    def test_searches_intake_match_for_typical_price(self):
        src = self._src()
        assert "plasticos.intake.match" in src
        assert "typical_price" in src

    def test_calls_super_create(self):
        assert "super().create" in self._src()
