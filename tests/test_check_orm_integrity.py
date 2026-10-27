"""ORM integrity scanner: required test fixtures are not production defects.

Test modules call ``env.ref()`` without ``raise_if_not_found=False`` because a
missing group, seed, or view must fail the test. Production lookups stay
critical. Unguarded search access stays reported in both contexts.
"""

from __future__ import annotations

import importlib.util
import sys
import textwrap
from pathlib import Path

CHECKER_PATH = Path(__file__).parents[1] / "ci" / "check_orm_integrity.py"
SPEC = importlib.util.spec_from_file_location("check_orm_integrity", CHECKER_PATH)
assert SPEC and SPEC.loader
checker_module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = checker_module
SPEC.loader.exec_module(checker_module)

_ENV_REF = """
def load(self):
    return self.env.ref("base.group_user")
"""

_OPTIONAL_REF = """
def load(self):
    return self.env.ref("base.group_user", raise_if_not_found=False)
"""

_UNGUARDED_SEARCH = """
def load(self):
    return self.env["res.partner"].search([("customer_rank", ">", 0)]).id
"""


def _scan(root: Path, relative: str, source: str) -> list[dict]:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(source), encoding="utf-8")
    return checker_module.scan_file(str(path))


def test_test_file_env_ref_generates_no_warning(tmp_path: Path):
    issues = _scan(tmp_path, "plasticos_base/tests/test_groups.py", _ENV_REF)
    assert issues == []


def test_production_env_ref_is_critical(tmp_path: Path):
    issues = _scan(tmp_path, "plasticos_base/models/groups.py", _ENV_REF)
    assert len(issues) == 1
    assert issues[0]["type"] == "UNPROTECTED_ENV_REF"
    assert issues[0]["severity"] == "CRITICAL"
    assert issues[0]["message"] == "env.ref('base.group_user') without raise_if_not_found=False"


def test_optional_env_ref_is_accepted(tmp_path: Path):
    issues = _scan(tmp_path, "plasticos_base/models/groups.py", _OPTIONAL_REF)
    assert issues == []


def test_unguarded_search_access_still_reported(tmp_path: Path):
    production = _scan(tmp_path, "plasticos_base/models/groups.py", _UNGUARDED_SEARCH)
    tests = _scan(tmp_path, "plasticos_base/tests/test_groups.py", _UNGUARDED_SEARCH)
    assert [issue["type"] for issue in production] == ["UNGUARDED_SEARCH_ACCESS"]
    assert production[0]["severity"] == "HIGH"
    assert [issue["type"] for issue in tests] == ["UNGUARDED_SEARCH_ACCESS"]
    assert tests[0]["severity"] == "MEDIUM"


def test_critical_production_finding_fails_the_scanner(tmp_path: Path, monkeypatch):
    production = tmp_path / "plasticos_base" / "models" / "groups.py"
    production.parent.mkdir(parents=True)
    production.write_text(textwrap.dedent(_ENV_REF), encoding="utf-8")
    monkeypatch.setattr(checker_module, "find_python_files", lambda: [str(production)])
    assert checker_module.main() == 1


def test_test_file_refs_do_not_fail_the_scanner(tmp_path: Path, monkeypatch):
    test_file = tmp_path / "plasticos_base" / "tests" / "test_groups.py"
    test_file.parent.mkdir(parents=True)
    test_file.write_text(textwrap.dedent(_ENV_REF), encoding="utf-8")
    monkeypatch.setattr(checker_module, "find_python_files", lambda: [str(test_file)])
    assert checker_module.main() == 0
