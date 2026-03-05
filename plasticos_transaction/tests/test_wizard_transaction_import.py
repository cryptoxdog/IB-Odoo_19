"""Tests for Transaction Import Wizard."""

import base64

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase


class TestTransactionImportWizard(TransactionCase):
    """Test plasticos.transaction.import.wizard."""

    SAMPLE_CSV = (
        "BuySellNo,DetailID,GradeID,InvoiceDesc,SWeight,SPrice,SAmount,"
        "PWeight,PPrice,PAmount,Color,ContainerNo,SealNo,SPo,PPo,"
        "Specifications,Condition,UnitType,Units\n"
        "TX-IMP-001,D001,G001,HDPE Natural,40000,0.25,10000.00,"
        "40000,0.20,8000.00,Natural,CONT001,SEAL001,SPO1,PPO1,"
        "Spec A,Good,LB,1\n"
        "TX-IMP-001,D002,G002,HDPE Blue,20000,0.30,6000.00,"
        "20000,0.22,4400.00,Blue,CONT001,SEAL001,SPO1,PPO1,"
        "Spec B,Fair,LB,1\n"
        "TX-IMP-002,D003,G001,PP Clear,35000,0.28,9800.00,"
        "35000,0.21,7350.00,Clear,CONT002,SEAL002,SPO2,PPO2,"
        "Spec C,Good,LB,2\n"
    )

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.csv_b64 = base64.b64encode(cls.SAMPLE_CSV.encode("utf-8"))

    # ------------------------------------------------------------------
    # Preview / dry-run
    # ------------------------------------------------------------------
    def test_preview_counts_transactions(self):
        """Preview should count unique BuySellNo references."""
        wiz = self.env["plasticos.transaction.import.wizard"].create(
            {
                "use_default_file": False,
                "csv_file": self.csv_b64,
                "csv_filename": "test.csv",
                "dry_run": True,
            }
        )
        wiz.action_preview()
        self.assertEqual(wiz.state, "preview")
        self.assertEqual(wiz.preview_tx_count, 2)  # TX-IMP-001, TX-IMP-002
        self.assertEqual(wiz.preview_line_count, 3)  # 3 CSV rows

    def test_preview_skip_existing(self):
        """Preview should mark existing transactions as skip."""
        self.env["plasticos.transaction"].create({"name": "TX-IMP-001"})
        wiz = self.env["plasticos.transaction.import.wizard"].create(
            {
                "use_default_file": False,
                "csv_file": self.csv_b64,
                "csv_filename": "test.csv",
                "dry_run": True,
            }
        )
        wiz.action_preview()
        self.assertEqual(wiz.preview_skip_count, 1)
        self.assertEqual(wiz.preview_tx_count, 1)  # only TX-IMP-002

    # ------------------------------------------------------------------
    # Import execution
    # ------------------------------------------------------------------
    def test_import_creates_transactions(self):
        """Full import should create transaction + line records."""
        wiz = self.env["plasticos.transaction.import.wizard"].create(
            {
                "use_default_file": False,
                "csv_file": self.csv_b64,
                "csv_filename": "test.csv",
                "dry_run": False,
                "skip_existing": True,
            }
        )
        wiz.with_context(force_import=True).action_import()
        self.assertEqual(wiz.state, "done")
        tx1 = self.env["plasticos.transaction"].search([("name", "=", "TX-IMP-001")])
        self.assertTrue(tx1)
        self.assertEqual(len(tx1.line_ids), 2)

    def test_import_skips_existing(self):
        """Import with skip_existing should not duplicate."""
        self.env["plasticos.transaction"].create({"name": "TX-IMP-001"})
        wiz = self.env["plasticos.transaction.import.wizard"].create(
            {
                "use_default_file": False,
                "csv_file": self.csv_b64,
                "csv_filename": "test.csv",
                "dry_run": False,
                "skip_existing": True,
            }
        )
        wiz.with_context(force_import=True).action_import()
        count = self.env["plasticos.transaction"].search_count([("name", "=", "TX-IMP-001")])
        self.assertEqual(count, 1)

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------
    def test_no_file_raises(self):
        """Creating wizard without file and use_default=False should raise on read."""
        wiz = self.env["plasticos.transaction.import.wizard"].create(
            {
                "use_default_file": False,
            }
        )
        with self.assertRaises(UserError):
            wiz.action_preview()

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------
    def test_action_back_resets_state(self):
        """action_back should return to draft state."""
        wiz = self.env["plasticos.transaction.import.wizard"].create(
            {
                "use_default_file": False,
                "csv_file": self.csv_b64,
                "csv_filename": "test.csv",
            }
        )
        wiz.action_preview()
        self.assertEqual(wiz.state, "preview")
        wiz.action_back()
        self.assertEqual(wiz.state, "draft")

    def test_action_close_returns_window_close(self):
        """action_close should return act_window_close."""
        wiz = self.env["plasticos.transaction.import.wizard"].create(
            {
                "use_default_file": False,
                "csv_file": self.csv_b64,
                "csv_filename": "test.csv",
            }
        )
        result = wiz.action_close()
        self.assertEqual(result["type"], "ir.actions.act_window_close")

    # ------------------------------------------------------------------
    # Helper methods
    # ------------------------------------------------------------------
    def test_parse_float_handles_null(self):
        """_parse_float should return 0.0 for NULL/empty."""
        wiz = self.env["plasticos.transaction.import.wizard"].create(
            {
                "use_default_file": False,
                "csv_file": self.csv_b64,
                "csv_filename": "test.csv",
            }
        )
        self.assertEqual(wiz._parse_float("NULL"), 0.0)
        self.assertEqual(wiz._parse_float(""), 0.0)
        self.assertEqual(wiz._parse_float("42.5"), 42.5)

    def test_parse_string_handles_null(self):
        """_parse_string should return False for NULL/(none)."""
        wiz = self.env["plasticos.transaction.import.wizard"].create(
            {
                "use_default_file": False,
                "csv_file": self.csv_b64,
                "csv_filename": "test.csv",
            }
        )
        self.assertFalse(wiz._parse_string("NULL"))
        self.assertFalse(wiz._parse_string("(none)"))
        self.assertEqual(wiz._parse_string("  Hello  "), "Hello")
