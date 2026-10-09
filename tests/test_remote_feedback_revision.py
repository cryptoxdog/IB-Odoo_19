"""Remote-feedback findings apply only to the published PR head."""

from __future__ import annotations

from scripts.pr_autopilot import Issue
from scripts.pr_check_remote_feedback import decide_remote_gate, format_stale_evidence

OLD = "fd7147d2b0c34b7a4fe258a1afcf8ab81af61d76"
NEW = "8f570f1a06987f891b7a0900aacdce8e240103f7"


def _real_bug() -> Issue:
    return Issue(source="codex", kind="REAL_BUG", file="Makefile", line=138, message="old finding")


def _changes_requested() -> Issue:
    return Issue(
        source="github_review",
        kind="ADVISORY",
        message="please change this",
        raw={"state": "CHANGES_REQUESTED"},
    )


def test_matching_sha_real_bug_fails() -> None:
    result = decide_remote_gate([_real_bug()], None, 222, NEW, NEW)
    assert result.exit_code == 1
    assert result.applicability == "current"
    assert result.reasons


def test_matching_sha_failed_ci_fails() -> None:
    result = decide_remote_gate([], "failure", 222, NEW, NEW)
    assert result.exit_code == 1
    assert result.applicability == "current"
    assert any("failure" in reason for reason in result.reasons)


def test_different_sha_real_bug_is_stale_and_does_not_block() -> None:
    result = decide_remote_gate([_real_bug()], None, 222, NEW, OLD)
    assert result.exit_code == 0
    assert result.applicability == "stale"
    assert result.reasons
    text = format_stale_evidence(NEW, OLD, list(result.reasons))
    assert "STALE-TO-LOCAL-CANDIDATE" in text
    assert "remote evidence applicability = STALE" in text
    assert "not a passing remote review" in text
    assert "gate passed" not in text.lower()


def test_different_sha_changes_requested_is_stale_and_does_not_block() -> None:
    result = decide_remote_gate([_changes_requested()], None, 222, NEW, OLD)
    assert result.exit_code == 0
    assert result.applicability == "stale"
    assert any("CHANGES_REQUESTED" in reason for reason in result.reasons)
    text = format_stale_evidence(NEW, OLD, list(result.reasons))
    assert "STALE-TO-LOCAL-CANDIDATE" in text
    assert "not a passing remote review" in text


def test_missing_pr_sha_does_not_become_a_stale_pass() -> None:
    result = decide_remote_gate([_real_bug()], None, 222, NEW, "")
    assert result.exit_code == 1
    assert result.applicability == "current"


def test_explicit_pr_real_bug_fails_when_local_sha_differs() -> None:
    result = decide_remote_gate([_real_bug()], None, 222, NEW, OLD, explicit=True)
    assert result.exit_code == 1
    assert result.applicability == "current"
    assert result.reasons


def test_explicit_pr_failed_ci_fails_when_local_sha_differs() -> None:
    result = decide_remote_gate([], "failure", 222, NEW, OLD, explicit=True)
    assert result.exit_code == 1
    assert result.applicability == "current"
    assert any("failure" in reason for reason in result.reasons)


def test_explicit_pr_changes_requested_fails_when_local_sha_differs() -> None:
    result = decide_remote_gate([_changes_requested()], None, 222, NEW, OLD, explicit=True)
    assert result.exit_code == 1
    assert result.applicability == "current"
    assert any("CHANGES_REQUESTED" in reason for reason in result.reasons)


def _inline(body: str, position: int | None) -> dict:
    return {
        "user": {"login": "chatgpt-codex-connector[bot]"},
        "body": body,
        "path": "plasticos_x/models/y.py",
        "line": 10,
        "position": position,
    }


def test_outdated_inline_bot_comments_do_not_block(monkeypatch) -> None:
    """GitHub clears ``position`` once a later push removes the commented line: the finding was addressed."""
    import scripts.pr_autopilot as autopilot

    comments = [
        _inline("**![P1 Badge](x)  Still on the current diff**", 7),
        _inline("**![P1 Badge](x)  Line was changed by a later push**", None),
    ]
    monkeypatch.setattr(autopilot, "gh", lambda _path: comments)

    issues = autopilot.get_codex_issues(231)

    assert [i.kind for i in issues] == ["REAL_BUG"]
    assert "Still on the current diff" in issues[0].message
