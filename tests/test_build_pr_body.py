"""The pull-request body is the repo template with Summary and Changes filled in."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.build_pr_body import (  # noqa: E402
    MAX_COMMIT_LIST_CHARS,
    _fallback_body,
    _section_body,
    cap_commit_list,
    fill_template,
)

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


def test_commit_list_under_the_cap_is_unchanged():
    commits = "\n".join(f"- feat: change {i}" for i in range(20))

    assert cap_commit_list(commits) == commits


def test_long_commit_list_keeps_whole_lines_and_names_the_omitted_count():
    commits = "\n".join(f"- feat: change number {i:05d} with a reasonably long subject" for i in range(2000))

    capped = cap_commit_list(commits)

    assert len(capped) <= MAX_COMMIT_LIST_CHARS
    kept = capped.splitlines()[:-1]
    assert all(line in commits.splitlines() for line in kept)
    assert kept[0] == "- feat: change number 00000 with a reasonably long subject"
    assert capped.splitlines()[-1] == f"- … and {2000 - len(kept)} more commit(s); see the pull request's Commits tab."


def test_capped_body_fits_the_github_limit():
    commits = cap_commit_list("\n".join(f"- feat: change {i:05d} " + "x" * 120 for i in range(1500)))

    body = fill_template(TEMPLATE, commits=commits, stat="")

    assert len(body) < 65_536


def test_cap_is_exact_including_the_omission_note():
    commits = "\n".join("- " + "y" * 98 for _ in range(50))

    capped = cap_commit_list(commits, limit=1000)

    assert len(capped) <= 1000
    assert capped.splitlines()[-1].startswith("- … and ")
