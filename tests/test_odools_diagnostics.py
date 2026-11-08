"""Normalizer for odoo_ls_server --parse. Does not invoke the language server."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import odools_diagnostics as odools  # noqa: E402

PARTNER_MESSAGE = "Invalid search domain field: partner_id is not a member of PlasticosTransaction"


def _diagnostic(start, end, severity, message, code="OLS03011"):
    body = {
        "range": {"start": {"line": start[0], "character": start[1]}, "end": {"line": end[0], "character": end[1]}},
        "severity": severity,
        "source": "Odoo",
        "message": message,
    }
    if code is not None:
        body["code"] = code
    return body


def _payload():
    partner = ROOT / "plasticos_documents_native/models/document_native.py"
    community = odools.COMMUNITY / "odoo/addons/base/__manifest__.py"
    return {
        "events": [
            {"type": "log", "severity": 3, "message": "Adding sys.path"},
            {
                "type": "diagnostic",
                "uri": partner.as_uri(),
                "version": None,
                "diagnostics": [
                    _diagnostic((162, 17), (162, 29), 1, PARTNER_MESSAGE, "OLS03011"),
                    _diagnostic((0, 0), (0, 1), 2, "missing code", None),
                ],
            },
            {
                "type": "diagnostic",
                "uri": community.as_uri(),
                "version": None,
                "diagnostics": [_diagnostic((0, 0), (0, 1), 1, "upstream", "OLS00000")],
            },
        ]
    }


def test_normalizer_spans_code_and_drops_community():
    rows = odools.rows_from_payload(_payload(), ROOT, include_all=False)
    assert len(rows) == 2
    assert [row["path"] for row in rows] == [
        "plasticos_documents_native/models/document_native.py",
        "plasticos_documents_native/models/document_native.py",
    ]
    assert odools.format_row(rows[0]) == (
        "plasticos_documents_native/models/document_native.py:163:18-163:30 "
        f"[error] [OLS03011] {PARTNER_MESSAGE} (Odoo)"
    )
    assert rows[0]["start"] == {"line": 163, "character": 18}
    assert rows[0]["end"] == {"line": 163, "character": 30}
    assert rows[1]["code"] is None
    assert odools.format_row(rows[1]).endswith("[warning] [-] missing code (Odoo)")
    assert all(odools.COMMUNITY.as_posix() not in row["path"] for row in rows)
    assert all("odoo-enterprise" not in row["path"] for row in rows)
