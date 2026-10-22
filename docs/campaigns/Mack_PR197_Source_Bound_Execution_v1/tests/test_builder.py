"""Offline synthetic tests. They never assert live GitHub or Odoo validation."""

import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("mack_builder", HERE / "scripts" / "build_repair.py")
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)

MODEL_SOURCE = """_SHA256_RE = None
class TestModel:
    def _check_request_shape(self):
        for record in self:
            if not _SHA256_RE.fullmatch((record.decision_snapshot_hash or "").strip()):
                raise ValueError('invalid')
"""
MANIFEST_SOURCE = '{\n    "version": "19.0.1.1.0",\n}\n'
TEST_SOURCE = """class TestMack:
    def test_identical_retry_returns_prior_receipt_without_second_activity(self):
        return True
"""


def git(root, *argv, check=True):
    p = subprocess.run(["git", *argv], cwd=root, capture_output=True, text=True)
    if check and p.returncode:
        raise AssertionError(f"git {argv!r}: {p.stderr}")
    return p.stdout.strip()


class BuilderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "repo"
        self.root.mkdir()
        git(self.root, "init", "-b", "mack")
        for rel, body in (
            (builder.MODEL, MODEL_SOURCE),
            (builder.TEST, TEST_SOURCE),
            (builder.MANIFEST, MANIFEST_SOURCE),
        ):
            dest = self.root / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(body)
        (self.root / "tests" / "runtime_gates").mkdir(parents=True)
        git(self.root, "add", ".")
        git(self.root, "-c", "user.name=Fixture", "-c", "user.email=fixture@example.org", "commit", "-m", "fixture")
        git(self.root, "remote", "add", "origin", "git@github.com:cryptoxdog/IB-Odoo_19.git")
        builder.HEAD = git(self.root, "rev-parse", "HEAD")
        builder.MODEL_SHA = git(self.root, "hash-object", builder.MODEL)
        builder.TEST_SHA = git(self.root, "hash-object", builder.TEST)
        builder.MANIFEST_SHA = git(self.root, "hash-object", builder.MANIFEST)

    def test_exact_fixture_generates_applyable_patch(self):
        builder.ensure_target(self.root)
        patch = builder.make_patch(self.root)
        path = Path(self.temp.name) / "repair.patch"
        path.write_text(patch)
        git(self.root, "apply", "--check", str(path))
        git(self.root, "apply", str(path))
        self.assertIn('fullmatch(record.decision_snapshot_hash or "")', (self.root / builder.MODEL).read_text())
        self.assertIn(
            "test_snapshot_hash_requires_exact_lowercase_sha256_without_whitespace",
            (self.root / builder.TEST).read_text(),
        )
        self.assertIn("def bind_config(config)", (self.root / builder.HELPER).read_text())
        self.assertIn("mack_owned_disposable=1", (self.root / builder.HELPER).read_text())
        self.assertIn("19.0.1.1.1", (self.root / builder.MANIFEST).read_text())
        import py_compile

        for rel in (builder.MODEL, builder.TEST, builder.MANIFEST, builder.HELPER):
            py_compile.compile(str(self.root / rel), doraise=True)

    def test_wrong_branch_is_rejected(self):
        git(self.root, "checkout", "-b", "Staging")
        with self.assertRaisesRegex(RuntimeError, "Wrong source branch"):
            builder.ensure_target(self.root)

    def test_dirty_worktree_is_rejected(self):
        (self.root / "dirty.txt").write_text("untracked\n")
        with self.assertRaisesRegex(RuntimeError, "not clean"):
            builder.ensure_target(self.root)

    def test_changed_remote_is_rejected(self):
        git(self.root, "remote", "set-url", "origin", "git@github.com:other/IB-Odoo_19.git")
        with self.assertRaisesRegex(RuntimeError, "Wrong origin"):
            builder.ensure_target(self.root)

    def test_lookalike_host_is_rejected(self):
        git(self.root, "remote", "set-url", "origin", "https://evilgithub.com/cryptoxdog/IB-Odoo_19.git")
        with self.assertRaisesRegex(RuntimeError, "Wrong origin"):
            builder.ensure_target(self.root)

    def test_https_origin_is_accepted(self):
        git(self.root, "remote", "set-url", "origin", "https://github.com/cryptoxdog/IB-Odoo_19.git")
        builder.ensure_target(self.root)

    def test_stale_head_is_rejected(self):
        (self.root / "README.md").write_text("new commit\n")
        git(self.root, "add", "README.md")
        git(self.root, "-c", "user.name=Fixture", "-c", "user.email=fixture@example.org", "commit", "-m", "changed")
        with self.assertRaisesRegex(RuntimeError, "Stale PR source"):
            builder.ensure_target(self.root)

    def test_missing_model_anchor_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "Exact model validation anchor"):
            builder.replacements(MODEL_SOURCE.replace(builder.BAD_VALIDATOR, "if True:"), TEST_SOURCE)

    def test_duplicate_test_anchor_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "Exact test anchor"):
            builder.replacements(MODEL_SOURCE, TEST_SOURCE + builder.TEST_ANCHOR)

    def test_existing_helper_is_rejected(self):
        (self.root / builder.HELPER).write_text("already present\n")
        with self.assertRaises(RuntimeError):
            builder.ensure_target(self.root)


if __name__ == "__main__":
    unittest.main()


# The pack also tests the GENERATED helper's safety boundary in isolation:
# fake psycopg2 means these tests make no database connection at all.
class RuntimeBindingSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        helper = self.root / "repo" / "tests" / "runtime_gates" / "_runtime_env.py"
        helper.parent.mkdir(parents=True)
        helper.write_text(builder.HELPER_BODY)
        self.helper = helper
        self.src = self.root / "src" / "odoo" / "addons"
        self.src.mkdir(parents=True)

    def _run_binding(self, *, db="odoo_test_mack_fixture", host="/tmp", marker="role=clone owner=mack", expect=None):
        import os
        import sys
        import types
        from unittest.mock import patch

        called = []

        class Cursor:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                pass

            def execute(self, statement):
                called.append(statement)

            def fetchone(self):
                return (marker,)

        class Conn:
            def cursor(self):
                return Cursor()

            def close(self):
                pass

        def connect(**kwargs):
            called.append(kwargs)
            return Conn()

        fake_psycopg2 = types.SimpleNamespace(connect=connect)
        env = {"SEAM_DB": db, "SEAM_PG_HOST": host, "SEAM_ODOO_SRC": str(self.src.parents[1])}
        with patch.dict(os.environ, env, clear=True), patch.dict(sys.modules, {"psycopg2": fake_psycopg2}):
            spec = importlib.util.spec_from_file_location("mack_fixture_runtime", self.helper)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            config = {}
            if expect is not None:
                with self.assertRaisesRegex(SystemExit, expect):
                    module.bind_config(config)
                return called
            module.bind_config(config)
            self.assertEqual(config["db_host"], host)
            self.assertEqual(config["db_port"], 5433)
            self.assertIn("odoo/addons", config["addons_path"])
            return called

    def test_owned_disposable_allows_binding(self):
        self.assertTrue(self._run_binding())

    def test_refuses_non_disposable_db_before_any_connection(self):
        self.assertEqual(self._run_binding(db="Production", expect="explicit SEAM_DB"), [])

    def test_refuses_remote_host_before_any_connection(self):
        self.assertEqual(self._run_binding(host="production.example.com", expect="local PostgreSQL"), [])

    def test_refuses_database_without_ownership_marker(self):
        self.assertTrue(self._run_binding(marker="", expect="not an owner-marked disposable"))
