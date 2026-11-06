"""Census source identity for the ERP import, and the rehearsal gate that reads it.

Pure-python tier. ``_write_census`` lives on the import runner, whose parent
package imports Odoo, so the runner is loaded with that parent stubbed.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PACKAGE = "plasticos_partner_import"
RUNNER = ROOT / PACKAGE / "scripts" / "run_erp_import.py"
README = ROOT / "tests" / "production-rehearsal" / "README.md"
GATE = ROOT / "tests" / "production-rehearsal" / "erp_slice.sh"


def _load_write_census():
    names = (
        PACKAGE,
        f"{PACKAGE}.erp",
        f"{PACKAGE}.erp.summary",
        f"{PACKAGE}.scripts",
        f"{PACKAGE}.scripts.run_erp_import",
    )
    saved = {name: sys.modules.get(name) for name in names}
    parent = types.ModuleType(PACKAGE)
    parent.__path__ = [str(ROOT / PACKAGE)]
    parent.__package__ = PACKAGE
    erp = types.ModuleType(f"{PACKAGE}.erp")
    erp.__path__ = [str(ROOT / PACKAGE / "erp")]
    erp.__package__ = f"{PACKAGE}.erp"
    summary = types.ModuleType(f"{PACKAGE}.erp.summary")
    erp.summary = summary
    scripts = types.ModuleType(f"{PACKAGE}.scripts")
    scripts.__path__ = [str(ROOT / PACKAGE / "scripts")]
    scripts.__package__ = f"{PACKAGE}.scripts"
    for module in (parent, erp, summary, scripts):
        sys.modules[module.__name__] = module
    try:
        spec = importlib.util.spec_from_file_location(f"{PACKAGE}.scripts.run_erp_import", RUNNER)
        module = importlib.util.module_from_spec(spec)
        module.__package__ = f"{PACKAGE}.scripts"
        sys.modules[spec.name] = module
        assert spec.loader is not None
        spec.loader.exec_module(module)
        return module._write_census
    finally:
        for name, previous in saved.items():
            if previous is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = previous


def test_census_records_payload_kind_and_origin(tmp_path):
    write_census = _load_write_census()
    path = tmp_path / "05-erp-summary-census.json"
    write_census(
        str(path),
        {
            "payload_kind": "database",
            "source_origin": "erp-host/erp_SM",
            "census": {"payables": 1},
            "anomalies": [],
            "unresolved": [],
        },
    )
    written = json.loads(path.read_text(encoding="utf-8"))
    assert written["payload_kind"] == "database"
    assert written["source_origin"] == "erp-host/erp_SM"
    assert written["census"] == {"payables": 1}
    assert "records_seen" not in written


def test_rehearsal_refuses_the_frozen_grid():
    readme = README.read_text(encoding="utf-8")
    gate = GATE.read_text(encoding="utf-8")
    assert "CSV grid by default" not in readme
    assert "payload_kind" in gate
    assert "database" in gate
    assert 'kind != "database"' in gate
