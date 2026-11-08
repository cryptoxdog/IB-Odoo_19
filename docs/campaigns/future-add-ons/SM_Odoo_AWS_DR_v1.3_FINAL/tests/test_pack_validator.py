"""Negative validation proofs for packaging; not real-world DR conformance."""

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from validate_campaign_pack import validate

SRC = Path(__file__).resolve().parents[1]


class PackValidatorTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "pack"
        shutil.copytree(SRC, self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def test_pristine(self):
        self.assertIn("PASS", validate(self.root))

    def assert_rejected(self, rel, original, changed):
        p = self.root / rel
        s = p.read_text("utf-8")
        self.assertIn(original, s)
        p.write_text(s.replace(original, changed, 1), encoding="utf-8")
        with self.assertRaises(AssertionError):
            validate(self.root)

    def test_tampered_bytes(self):
        self.assert_rejected("policy/INVARIANTS.md", "DR-001 Native", "DR-001 NATIVE TAMPER")

    def test_missing_trace_row(self):
        p = self.root / "coordination/INVARIANT_TRACEABILITY.csv"
        s = p.read_text("utf-8").splitlines(keepends=True)
        p.write_text("".join(s[:-1]))
        with self.assertRaises(AssertionError):
            validate(self.root)

    def test_broken_access_header(self):
        self.assert_rejected(
            "contracts/00_FEASIBILITY_AND_BLAST_RADIUS.md",
            "unlisted_repositories: no_access",
            "unlisted_repositories: any",
        )

    def test_unscheduled_5th_slot(self):
        self.assert_rejected("policy/LOCKED_POLICY.yaml", "- '17:00'", "- '19:00'")

    def test_missing_file(self):
        (self.root / "contracts/02_AWS_VAULT_AND_IDENTITY.md").unlink()
        with self.assertRaises(AssertionError):
            validate(self.root)

    def test_unresolved_reference_even_when_hashes_are_rebuilt(self):
        # The structural validator must reject an explicit link to an absent file
        # *even if an attacker repackages changed files and recalculates hashes*.
        import json
        from hashlib import sha256

        p = self.root / "README.md"
        p.write_text(p.read_text("utf-8") + "\n`contracts/MISSING_FILE.md`\n")
        manifest_p = self.root / "MANIFEST.json"
        manifest = json.loads(manifest_p.read_text("utf-8"))
        for rec in manifest["files"]:
            if rec["path"] == "README.md":
                b = p.read_bytes()
                rec["bytes"] = len(b)
                rec["sha256"] = sha256(b).hexdigest()
        manifest_p.write_text(json.dumps(manifest))
        (self.root / "CHECKSUMS.sha256").write_text("".join(f"{r['sha256']}  {r['path']}\n" for r in manifest["files"]))
        with self.assertRaisesRegex(AssertionError, "unresolved bundled references"):
            validate(self.root)


if __name__ == "__main__":
    unittest.main()
