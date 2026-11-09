"""Instruction-set alignment with the admitted INVARIANTS.md constitution."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RULES = ROOT / ".cursor" / "rules"
CLAUDE_RULES = ROOT / ".claude" / "rules"
FIXTURES = ROOT / "tests" / "fixtures" / "agent_rule_alignment"

ALWAYS_ON = {"00-plasticos-master-context.mdc", "01-cursor-governance-law.mdc"}
DESCRIPTION_ONLY = {
    "02-context7-auto-invoke.mdc",
    "36-plasticos-docker-test-fixture.mdc",
    "70-github-api-commit.mdc",
    "87-plasticos-code-graph-rag.mdc",
    "88-plasticos-odoo-python-tooling.mdc",
}
PROHIBITION = re.compile(r"(?i)\b(do\s*\**\s*not|don't|never|must\s+not)\b")
BANNED = (
    re.compile(r"test_depends_order_respects_layers"),
    re.compile(r"5 layers"),
    re.compile(r"Layer Isolation"),
    re.compile(r"Integer not Many2one"),
    re.compile(r"local matcher fallback is acceptable", re.IGNORECASE),
    re.compile(r"18 invariants"),
    re.compile(r"architectural draft", re.IGNORECASE),
    re.compile(r"wrap all reference data in noupdate", re.IGNORECASE),
    re.compile(r"make update-all"),
    re.compile(r"36099032"),
    re.compile(r"(?i)read\s+`?(?:plasticos_logistics/business_rules/|SUPERSESSION\.md)"),
)


def _frontmatter(text: str) -> dict[str, str]:
    match = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    if not match:
        return {}
    fields: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" not in line or line.startswith(" "):
            continue
        key, value = line.split(":", 1)
        fields[key.strip()] = value.strip()
    return fields


def doctrine_hits(text: str) -> list[str]:
    hits: list[str] = []
    for line in text.splitlines():
        if PROHIBITION.search(line):
            continue
        for pattern in BANNED:
            if pattern.search(line):
                hits.append(pattern.pattern)
    return hits


def _instruction_texts() -> list[tuple[str, str]]:
    paths = sorted(RULES.glob("*.mdc"))
    paths.append(ROOT / "AGENTS.md")
    paths.append(ROOT / "CLAUDE.md")
    paths.extend(sorted(CLAUDE_RULES.glob("*.md")))
    return [(str(path.relative_to(ROOT)), path.read_text(encoding="utf-8")) for path in paths]


def test_activation_table() -> None:
    for name in ALWAYS_ON:
        fields = _frontmatter((RULES / name).read_text(encoding="utf-8"))
        assert fields.get("alwaysApply") == "true", name
    for name in DESCRIPTION_ONLY:
        fields = _frontmatter((RULES / name).read_text(encoding="utf-8"))
        assert fields.get("alwaysApply") == "false", name
        assert "globs" not in fields, name
    version_bump = _frontmatter((RULES / "89-plasticos-odoo-version-bump.mdc").read_text(encoding="utf-8"))
    assert version_bump.get("alwaysApply") == "false"
    assert "plasticos_*/**/*" in version_bump.get("globs", "")


def test_rule_00_names_the_constitution() -> None:
    text = (RULES / "00-plasticos-master-context.mdc").read_text(encoding="utf-8")
    assert "INVARIANTS.md" in text


def test_constitution_status_is_active() -> None:
    text = (ROOT / "INVARIANTS.md").read_text(encoding="utf-8")
    assert "**Status:** ACTIVE" in text


def test_instruction_set_has_no_retired_doctrine() -> None:
    failures = [(path, hits) for path, text in _instruction_texts() if (hits := doctrine_hits(text))]
    assert failures == []


def test_negative_fixtures_fail_the_same_checker() -> None:
    for path in sorted(FIXTURES.glob("*.md")):
        assert doctrine_hits(path.read_text(encoding="utf-8")), path.name
