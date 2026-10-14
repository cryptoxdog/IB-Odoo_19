"""F1's Docker entry refuses the wrong database and will not mint a pass receipt."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests" / "runtime_gates"))

import f1_guarded_shell as shell  # noqa: E402


def test_shell_without_an_odoo_environment_is_refused(monkeypatch):
    monkeypatch.delitem(shell.__dict__, "env", raising=False)
    with pytest.raises(SystemExit, match="no Odoo environment"):
        shell.main()


@pytest.mark.parametrize(
    "name",
    ["odoo_test_crm1r1", "odoo_test_crm1live", "c1c6_test", "odoo", "odoo_test_f1_staging", "odoo_test_f1_prod"],
)
def test_shell_refuses_integration_names_before_the_gate_body(name, monkeypatch):
    monkeypatch.setitem(shell.__dict__, "env", SimpleNamespace(cr=SimpleNamespace(dbname=name)))

    def _boom(*_args, **_kwargs):
        raise AssertionError("odoo must not load for a refused database")

    monkeypatch.setattr(shell, "_addons_path", _boom)
    with pytest.raises(SystemExit, match="refusing stub CRM gate"):
        shell.main()


def test_empty_output_is_not_an_f1_pass():
    assert shell.assertions_passed("") is False
    assert shell.assertions_passed("  PASS  something else\n") is False


def test_a_failed_row_is_not_an_f1_pass():
    text = "  PASS  F1 reached the floor\n  FAIL  F2 census\n"
    assert shell.assertions_passed(text) is False


def test_f1_table_with_only_passes_is_a_pass():
    text = "odoo log FAIL inside a sentence\n  PASS  F1 reached the floor\n  PASS  F3 provenance\n"
    assert shell.assertions_passed(text) is True


def test_receipt_is_withheld_when_the_table_did_not_pass(tmp_path):
    dest = tmp_path / "receipt.json"
    with pytest.raises(SystemExit) as caught:
        shell.write_receipt("launcher exited 0\n", "odoo_test_f1_gate", str(dest), "abc")
    assert caught.value.code == 2
    assert not dest.exists()


def test_missing_receipt_is_unproven(tmp_path):
    assert shell.accept_receipt(str(tmp_path / "missing.json"), "abc") == 2


def test_receipt_for_another_head_is_unproven(tmp_path):
    dest = tmp_path / "receipt.json"
    shell.write_receipt("  PASS  F1 reached the floor\n", "odoo_test_f1_gate", str(dest), "abc")
    assert shell.accept_receipt(str(dest), "def") == 2
    assert shell.accept_receipt(str(dest), "abc") == 0
    payload = json.loads(dest.read_text())
    assert payload["retired"] is True
    assert payload["fail_count"] == 0
    assert payload["database"] == "odoo_test_f1_gate"
