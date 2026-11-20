"""Odoo.sh fails a build when install.log contains ERROR.

Enterprise l10n_cl_edi and l10n_cl_edi_stock log an ERROR if pdf417gen is
missing, and those modules install with Accounting on a fresh database.
requirements.txt is the file Odoo.sh installs. The pin stays exact.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PIN = "pdf417gen==0.8.1"


def test_odoo_sh_requirements_pin_pdf417gen() -> None:
    lines = [
        line.strip()
        for line in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    assert lines.count(PIN) == 1
    assert not any(line.startswith("pdf417gen") and line != PIN for line in lines)
