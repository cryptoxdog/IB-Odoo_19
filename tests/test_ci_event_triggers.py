"""CI Gate runs once per relevant event."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_feature_branch_pushes_do_not_start_a_second_ci_gate() -> None:
    text = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "branches: [Staging, Production]" in text
    assert "pull_request:" in text
    assert "workflow_dispatch:" in text
    for job in (
        "lint:",
        "static-checks:",
        "pure-python-tests:",
        "gate-sdk-tests:",
        "secret-scan:",
        "audit-baseline:",
        "ci-gate-result:",
    ):
        assert job in text
    assert "name: CI Gate Result" in text
