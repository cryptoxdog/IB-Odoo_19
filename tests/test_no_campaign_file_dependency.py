"""Repo tests must not read docs/campaigns."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SELF = Path(__file__).resolve()
CAMPAIGN_PATH = "docs" + "/campaigns"


def _test_files():
    bases = [ROOT / "tests", *ROOT.glob("plasticos_*/tests")]
    for base in bases:
        if base.is_dir():
            yield from base.rglob("*.py")


def test_repo_tests_do_not_read_campaign_files():
    offenders = []
    for path in _test_files():
        if path.resolve() == SELF:
            continue
        text = path.read_text(encoding="utf-8")
        reads_campaign = CAMPAIGN_PATH in text or ('"docs"' in text and '"campaigns"' in text)
        if reads_campaign:
            offenders.append(str(path.relative_to(ROOT)))
    assert offenders == []
