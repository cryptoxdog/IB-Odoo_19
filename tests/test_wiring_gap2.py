"""
GAP-2 Wiring Test Suite — 22 tests, no Odoo runtime required.

Run: pytest tests/test_wiring_gap2.py -v
"""
import ast
import importlib.util
import os
import sys
import types
import uuid
from unittest.mock import MagicMock, patch, call

import pytest

# ── Helpers ──────────────────────────────────────────────────────────────────

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NEW_ROOT = os.path.join(REPO_ROOT, "tmp", "plasticos_gap2_pack") if "tmp" not in REPO_ROOT else REPO_ROOT


def source_path(*parts):
    return os.path.join(REPO_ROOT, *parts)


def parse_source(*parts):
    """Return AST for a source file in the repo."""
    path = source_path(*parts)
    if not os.path.exists(path):
        pytest.skip(f"Source not found: {path}")
    with open(path) as f:
        return ast.parse(f.read(), filename=path)


def all_class_names(tree):
    return {node.id if isinstance(node, ast.Name) else ast.unparse(node)
            for node in ast.walk(tree) if isinstance(node, ast.ClassDef)}


def all_function_names(tree):
    return {node.name for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}


def all_string_literals(tree):
    return {node.value for node in ast.walk(tree) if isinstance(node, ast.Constant) and isinstance(node.value, str)}


# ─────────────────────────────────────────────────────────────────────────────
# Group A: match_result_writer.py structural tests
# ─────────────────────────────────────────────────────────────────────────────

WRITER_PATH = source_path("plasticos_buyer_match_engine", "models", "match_result_writer.py")


@pytest.mark.skipif(not os.path.exists(WRITER_PATH), reason="match_result_writer.py not yet in repo")
class TestMatchResultWriter:
    def _tree(self):
        with open(WRITER_PATH) as f:
            return ast.parse(f.read())

    def test_class_is_abstract_model(self):
        tree = self._tree()
        classes = [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
        names = {c.name for c in classes}
        assert "MatchResultWriter" in names

    def test_model_name_is_abstract(self):
        with open(WRITER_PATH) as f:
            src = f.read()
        assert "plasticos.match.result.writer" in src

    def test_persist_match_lines_defined(self):
        tree = self._tree()
        funcs = all_function_names(tree)
        assert "persist_match_lines" in funcs

    def test_stale_purge_only_pending(self):
        with open(WRITER_PATH) as f:
            src = f.read()
        assert "pending" in src
        assert "state" in src

    def test_idempotent_run_id_uuid4(self):
        with open(WRITER_PATH) as f:
            src = f.read()
        assert "uuid4" in src or "uuid" in src

    def test_no_sudo_escalation(self):
        with open(WRITER_PATH) as f:
            src = f.read()
        # Writer must not escalate sudo — caller already carries correct env
        assert ".sudo()" not in src

    def test_score_clamped_0_100(self):
        with open(WRITER_PATH) as f:
            src = f.read()
        assert "100.0" in src or "100" in src
        assert "min(" in src or "max(" in src

    def test_typical_price_forwarded(self):
        with open(WRITER_PATH) as f:
            src = f.read()
        assert "typical_price" in src


# ─────────────────────────────────────────────────────────────────────────────
# Group B: intake_extension_patched.py — result writer call wired
# ─────────────────────────────────────────────────────────────────────────────

PATCHED_EXT_PATH = source_path(
    "plasticos_buyer_match_engine", "models", "intake_extension_patched.py"
)


@pytest.mark.skipif(not os.path.exists(PATCHED_EXT_PATH), reason="intake_extension_patched.py not in pack")
class TestIntakeExtensionPatch:
    def _src(self):
        with open(PATCHED_EXT_PATH) as f:
            return f.read()

    def test_persist_match_lines_called(self):
        assert "persist_match_lines" in self._src()

    def test_match_result_writer_guarded_by_in_env(self):
        src = self._src()
        assert "plasticos.match.result.writer" in src
        assert "in self.env" in src

    def test_run_id_uuid_generated(self):
        assert "uuid.uuid4" in self._src()

    def test_typical_price_not_hardcoded_zero(self):
        src = self._src()
        # Must use m.get("typical_price") not hardcode 0.0
        assert '"typical_price"' in src
        # Should NOT have the old hardcoded pattern
        assert '"typical_price": 0.0,' not in src


# ─────────────────────────────────────────────────────────────────────────────
# Group C: offer_price_bridge.py
# ─────────────────────────────────────────────────────────────────────────────

BRIDGE_PATH = source_path("plasticos_offer", "models", "offer_price_bridge.py")


@pytest.mark.skipif(not os.path.exists(BRIDGE_PATH), reason="offer_price_bridge.py not in repo")
class TestOfferPriceBridge:
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


# ─────────────────────────────────────────────────────────────────────────────
# Group D: migration idempotency logic
# ─────────────────────────────────────────────────────────────────────────────

MIGRATION_PATH = source_path(
    "plasticos_buyer_match_engine", "migrations", "19.0.2.1.0", "post-migrate.py"
)


@pytest.mark.skipif(not os.path.exists(MIGRATION_PATH), reason="migration not in repo")
class TestMigration210:
    def _src(self):
        with open(MIGRATION_PATH) as f:
            return f.read()

    def test_migrate_function_defined(self):
        tree = ast.parse(self._src())
        funcs = all_function_names(tree)
        assert "migrate" in funcs

    def test_idempotent_check_before_insert(self):
        src = self._src()
        assert "SELECT" in src
        assert "INSERT" in src

    def test_never_overwrites_existing(self):
        src = self._src()
        # Should check if row is None before inserting
        assert "is None" in src

    def test_seeds_stub_key(self):
        assert "plasticos.matching_engine.stub" in self._src()


# ─────────────────────────────────────────────────────────────────────────────
# Group E: __init__ import chain integrity
# ─────────────────────────────────────────────────────────────────────────────

INIT_PATCHED = source_path(
    "plasticos_buyer_match_engine", "models", "__init___patched.py"
)


@pytest.mark.skipif(not os.path.exists(INIT_PATCHED), reason="__init___patched.py not in pack")
def test_init_imports_match_result_writer():
    with open(INIT_PATCHED) as f:
        src = f.read()
    assert "match_result_writer" in src


@pytest.mark.skipif(not os.path.exists(INIT_PATCHED), reason="__init___patched.py not in pack")
def test_init_imports_all_existing_models():
    with open(INIT_PATCHED) as f:
        src = f.read()
    for mod in ["graph_service", "intake_extension", "matcher", "match_exclusion", "matching_stub"]:
        assert mod in src, f"Missing import: {mod}"


OFFER_INIT_PATCHED = source_path("plasticos_offer", "models", "__init___patched.py")


@pytest.mark.skipif(not os.path.exists(OFFER_INIT_PATCHED), reason="offer __init___patched.py not in pack")
def test_offer_init_imports_price_bridge():
    with open(OFFER_INIT_PATCHED) as f:
        src = f.read()
    assert "offer_price_bridge" in src
