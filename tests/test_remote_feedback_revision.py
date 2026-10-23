"""Remote-feedback findings apply only to the published PR head."""

from __future__ import annotations

from pathlib import Path

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


def _inline(body: str, line: int | None, comment_id: int = 1) -> dict:
    return {
        "id": comment_id,
        "user": {"login": "chatgpt-codex-connector[bot]"},
        "body": body,
        "path": "plasticos_x/models/y.py",
        "line": line,
        "original_line": 10,
        "position": 1,
    }


def test_outdated_or_resolved_inline_bot_comments_do_not_block(monkeypatch) -> None:
    """GitHub clears ``line`` once a later push removes the commented line; a resolved thread is answered."""
    import scripts.pr_autopilot as autopilot

    comments = [
        _inline("**![P1 Badge](x)  Still on the current diff**", 7, comment_id=1),
        _inline("**![P1 Badge](x)  Line was changed by a later push**", None, comment_id=2),
        _inline("**![P1 Badge](x)  Thread resolved by a reviewer**", 9, comment_id=3),
    ]
    monkeypatch.setattr(autopilot, "gh", lambda _path: comments)
    monkeypatch.setattr(autopilot, "_resolved_review_comment_ids", lambda _pr: {3})

    issues = autopilot.get_codex_issues(231)

    assert [i.kind for i in issues] == ["REAL_BUG"]
    assert "Still on the current diff" in issues[0].message


def test_resolved_thread_lookup_fails_open_to_no_resolution(monkeypatch) -> None:
    import scripts.pr_autopilot as autopilot

    def boom(*_args, **_kwargs):
        raise OSError("offline")

    monkeypatch.setattr(autopilot, "_http", boom)
    assert autopilot._resolved_review_comment_ids(231) == set()


def test_resolved_thread_ids_come_from_the_ccr_rest_route(monkeypatch) -> None:
    """Resolution state is read from ``ccr/review_threads`` over REST; only resolved threads count."""
    import scripts.pr_autopilot as autopilot

    calls: list[str] = []

    def fake_gh(path: str):
        calls.append(path)
        return [
            {"resolved": True, "outdated": True, "path": "a.py", "line": None, "comment_ids": [11, 12]},
            {"resolved": False, "outdated": False, "path": "b.py", "line": 4, "comment_ids": [13]},
            {"resolved": True, "outdated": False, "path": "c.py", "line": 9, "comment_ids": [14, "x", None]},
            "not-a-thread",
        ]

    monkeypatch.setattr(autopilot, "gh", fake_gh)
    assert autopilot._resolved_review_comment_ids(231) == {11, 12, 14}
    assert calls == [f"/repos/{autopilot.REPO}/pulls/231/ccr/review_threads"]


def test_resolved_thread_lookup_error_payload_resolves_nothing(monkeypatch) -> None:
    """An HTTP error (``gh`` returns ``{"_error": ...}``) or a non-list body resolves no thread."""
    import scripts.pr_autopilot as autopilot

    for payload in ({"_error": 404, "_msg": "Not Found"}, "<html>proxy</html>", None):
        monkeypatch.setattr(autopilot, "gh", lambda _path, payload=payload: payload)
        assert autopilot._resolved_review_comment_ids(231) == set()


def test_pr_autopilot_never_calls_graphql() -> None:
    """GraphQL is disabled on the cloud surface by design; no code path may call it."""
    source = (Path(__file__).resolve().parents[1] / "scripts" / "pr_autopilot.py").read_text(encoding="utf-8")
    code = "\n".join(line for line in source.splitlines() if not line.lstrip().startswith("#"))
    assert "/graphql" not in code
    assert "reviewThreads" not in code
