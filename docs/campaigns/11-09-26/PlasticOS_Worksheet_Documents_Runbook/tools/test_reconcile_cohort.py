"""Synthetic negative controls. No live data or Odoo required."""
import csv
import hashlib
import tempfile
import unittest
from pathlib import Path

from reconcile_cohort import analyze


def h(b):
    return hashlib.sha256(b).hexdigest()


def write(path, fields, rows):
    with path.open("w", newline="", encoding="utf8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


class CohortTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.decoded = self.root / "decoded"
        self.decoded.mkdir()
        self.raw = self.root / "raw"
        self.raw.mkdir()
        self.j = self.root / "journal.csv"
        self.t = self.root / "transactions.csv"
        self.i = self.root / "imports.csv"
        self.rows = []
        for image, ref, typ, status in [("1", "1001", "W", "ok"), ("2", "1002", "W", "ok"), ("3", "1003", "W", "ok"), ("4", "1004-X", "#", "ok"), ("5", "1005", "W", "not_gzip"), ("6", "2001", "P", "ok")]:
            content = f"fake-image-{image}".encode()
            (self.raw / f"{image}.bin").write_bytes(content)
            if status == "ok":
                (self.decoded / f"{image}.pdf").write_bytes(content)
            self.rows.append({"ImageID": image, "DocID": str(100 + int(image)), "RefID": ref, "RefType": typ, "FileExt": "pdf", "BlobSize": len(content), "RawBytes": len(content), "RawSha256": h(content), "DecodedBytes": len(content) if status == "ok" else 0, "DecodedSha256": h(content) if status == "ok" else "", "Status": status, "ImportScope": "eligible" if typ in {"W", "#"} else "archive_only"})
        self.transactions = [
            {"id": "11", "name": "1001", "company_id": "1"},
            {"id": "33", "name": "1003", "company_id": "1"},
            {"id": "34", "name": "1003", "company_id": "2"},
            {"id": "44", "name": "1004-X", "company_id": "1"},
        ]
        self.imports = [
            {"ImageID": "1", "odoo_document_id": "501", "odoo_transaction_id": "11", "status": "imported", "decoded_sha256": h(b"fake-image-1"), "reason": ""},
            {"ImageID": "4", "odoo_document_id": "504", "odoo_transaction_id": "44", "status": "imported", "decoded_sha256": h(b"fake-image-4"), "reason": ""},
        ]
        self.save()

    def save(self):
        write(self.j, list(self.rows[0]), self.rows)
        write(self.t, ["id", "name", "company_id"], self.transactions)
        write(self.i, list(self.imports[0]), self.imports)

    def test_expected_closed_partition_and_replay(self):
        one = analyze(self.j, self.t, self.i, self.decoded, self.raw)
        self.assertEqual(one["verdict"], "STRUCTURAL_PASS_NOT_PRODUCTION_ATTESTATION")
        self.assertEqual(one["counts"]["eligible"], 5)
        for key, expected in {"unique_match": 2, "missing_transaction": 1, "ambiguous_transaction": 1, "integrity_failure": 1, "successfully_imported": 2, "archive_only_P": 1}.items():
            self.assertEqual(one["counts"][key], expected)
        two = analyze(self.j, self.t, self.i, self.decoded, self.raw)
        self.assertEqual(one, two)

    def test_wrong_target_detected(self):
        self.imports[0]["odoo_transaction_id"] = "999"
        self.save()
        self.assertEqual(analyze(self.j, self.t, self.i)["verdict"], "STRUCTURAL_FAIL")

    def test_duplicate_image_detected(self):
        self.rows.append(dict(self.rows[0]))
        self.save()
        self.assertEqual(analyze(self.j, self.t, self.i)["verdict"], "STRUCTURAL_FAIL")

    def test_excluded_import_detected(self):
        self.imports.append({"ImageID": "6", "odoo_document_id": "506", "odoo_transaction_id": "11", "status": "imported", "decoded_sha256": h(b"fake-image-6"), "reason": ""})
        self.save()
        self.assertEqual(analyze(self.j, self.t, self.i)["verdict"], "STRUCTURAL_FAIL")

    def test_missing_blob_detected(self):
        (self.decoded / "1.pdf").unlink()
        out = analyze(self.j, self.t, self.i, self.decoded, self.raw)
        self.assertEqual(out["counts"]["integrity_failure"], 2)
        self.assertEqual(out["verdict"], "STRUCTURAL_FAIL")

    def test_duplicate_original_receipt_detected(self):
        self.imports[1]["odoo_document_id"] = "501"
        self.save()
        self.assertEqual(analyze(self.j, self.t, self.i)["verdict"], "STRUCTURAL_FAIL")


if __name__ == "__main__":
    unittest.main()
