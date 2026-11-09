"""The pull-request body is the repo template with Summary and Changes filled in."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.build_pr_body import _fallback_body, _section_body, fill_template  # noqa: E402

TEMPLATE = (ROOT / ".github" / "pull_request_template.md").read_text(encoding="utf-8")
COMMIT_SUBJECT = "docs: retire the memory bank"


def test_filled_body_keeps_template_test_plan_and_commit_subject():
    body = fill_template(
        TEMPLATE,
        commits=f"- {COMMIT_SUBJECT}",
        stat="AGENTS.md | 2 +-",
    )

    assert _section_body(body, "Test plan") == _section_body(TEMPLATE, "Test plan")
    assert COMMIT_SUBJECT in _section_body(body, "Summary")
    assert COMMIT_SUBJECT in _section_body(body, "Changes")
    assert "AGENTS.md" not in _section_body(body, "Changes")
    assert "|" not in _section_body(body, "Changes")
    assert COMMIT_SUBJECT not in _section_body(body, "Test plan")


def test_fallback_body_keeps_sections_and_drops_the_stat():
    body = _fallback_body("Staging", f"- {COMMIT_SUBJECT}")

    assert COMMIT_SUBJECT in _section_body(body, "Summary")
    assert COMMIT_SUBJECT in _section_body(body, "Changes")
    assert "|" not in _section_body(body, "Changes")
    assert "CI Gate (`ci.yml`) green" in _section_body(body, "Test plan")
