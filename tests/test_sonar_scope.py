"""Declared Sonar source and test partitions stay disjoint."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.adversarial_contract

ROOT = Path(__file__).resolve().parents[1]
PROPERTY_FILES = ("sonar-project.properties", ".sonarcloud.properties")
SOURCE_EXAMPLES = (
    "scripts/audit/test_audit.py",
    "plasticos_commission/__manifest__.py",
    "plasticos_web_leads/__manifest__.py",
)


def _properties(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8").replace("\\\n", "")
    found: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        found[key.strip()] = value.strip()
    return found


def _csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _sonar_regex(pattern: str) -> str:
    parts: list[str] = []
    index = 0
    while index < len(pattern):
        if pattern.startswith("**/", index):
            parts.append("(?:.*/)?")
            index += 3
        elif pattern.startswith("**", index):
            parts.append(".*")
            index += 2
        elif pattern[index] == "*":
            parts.append("[^/]*")
            index += 1
        elif pattern[index] == "?":
            parts.append("[^/]")
            index += 1
        else:
            parts.append(re.escape(pattern[index]))
            index += 1
    return "".join(parts)


def _matches(pattern: str, path: str) -> bool:
    return re.fullmatch(_sonar_regex(pattern), path) is not None


def _class(path: str, props: dict[str, str]) -> str:
    exclusions = _csv(props["sonar.exclusions"])
    inclusions = _csv(props["sonar.test.inclusions"])
    test_roots = _csv(props["sonar.tests"])
    if any(_matches(pattern, path) for pattern in exclusions):
        return "excluded"
    under_tests = any(path == root or path.startswith(root + "/") for root in test_roots)
    if under_tests or any(_matches(pattern, path) for pattern in inclusions):
        return "test"
    sources = _csv(props["sonar.sources"])
    if sources == ["."] or any(path == root or path.startswith(root + "/") for root in sources):
        return "source"
    return "out"


def _addon_tests() -> list[str]:
    found: list[str] = []
    for path in ROOT.glob("plasticos_*/tests/**/*"):
        if path.is_file() and path.suffix in {".py", ".xml"}:
            found.append(path.relative_to(ROOT).as_posix())
    return found


def test_addon_tests_are_tests_and_production_files_stay_source() -> None:
    addon_tests = _addon_tests()
    assert addon_tests
    for name in PROPERTY_FILES:
        props = _properties(ROOT / name)
        classes = {_class(path, props) for path in addon_tests}
        assert classes == {"test"}, name
        for example in SOURCE_EXAMPLES:
            assert (ROOT / example).is_file(), example
            assert _class(example, props) == "source", (name, example)
        sampled = set(addon_tests) | set(SOURCE_EXAMPLES)
        source = {path for path in sampled if _class(path, props) == "source"}
        tests = {path for path in sampled if _class(path, props) == "test"}
        assert source.isdisjoint(tests)
