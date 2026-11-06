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

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = "plasticos_partner_import"
RUNNER = ROOT / PACKAGE / "scripts" / "run_erp_import.py"
KIT = Path(__file__).resolve().parent
README = KIT / "README.md"
GATE = KIT / "erp_slice.sh"
RUN = KIT / "run.sh"


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
    run = RUN.read_text(encoding="utf-8")
    assert "CSV grid by default" not in readme
    assert "If either is unset, Gate 6 is blocked" not in readme
    assert "erp-proof/database" in readme
    assert "erp_extracted_data" in readme
    # The payload_kind rule lives in the kit helper erp_slice.sh calls; the
    # behaviour (grid / statements / missing kind fail) is exercised in
    # test_rehearsal_kit_lib.py::test_erp_fails_closed.
    lib = (KIT / "rehearsal_lib.py").read_text(encoding="utf-8")
    assert "rehearsal_lib.py" in (KIT / "rehearsal_common.sh").read_text(encoding="utf-8")
    assert "rlib check-erp" in gate
    assert "payload_kind" in lib
    assert 'kind != "database"' in lib
    assert "host.docker.internal" in gate
    assert "erp-proof/database" in gate or "PROOF_DB" in gate
    assert "14330" in gate
    assert "reader.pw" in gate
    banned = bytes([99, 105, 101, 116, 114, 97, 100, 101]).decode("ascii")
    for path in (README, GATE, RUN, ROOT / "tests" / "production-rehearsal" / "SPEC.md"):
        assert banned not in path.read_text(encoding="utf-8").lower()
    assert "make import-erp" in gate
    assert "make -C /mnt/extra-addons import-erp" not in gate
    make_args = gate.split("make import-erp", 1)[1].split("2>&1", 1)[0]
    assert "ERP_SQL_PASSWORD" not in make_args
    assert "make import-vanillasoft" in run
    assert "test_env.sh" in run
    assert "VANILLASOFT_CONTACT_FLOOR" in run
