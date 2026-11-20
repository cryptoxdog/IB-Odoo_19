#!/usr/bin/env python3
"""Run the Odoo-free ``pytest tests/`` suite for the Staging nightly workflow.

The guard refuses every event other than schedule or workflow_dispatch, every
ref other than ``refs/heads/Staging``, and a repository whose default branch is
not Staging. Refusal happens before pytest. This file is not a pull-request job.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

NIGHTLY_PYTEST = [
    "python3",
    "-m",
    "pytest",
    "tests/",
    "-v",
    "--cov=.",
    "--cov-report=term-missing:skip-covered",
    "--junitxml=artifacts/pytest/pure-python.xml",
]

_STAGING_REF = "refs/heads/Staging"
_ALLOWED_EVENTS = {"schedule", "workflow_dispatch"}
_FORBIDDEN_ENV = ("PYTEST_ADDOPTS", "PYTEST_DISABLE_PLUGIN_AUTOLOAD", "PLASTICOS_SMOKE_SOURCE")
_JUNIT = Path("artifacts/pytest/pure-python.xml")
_REVISION = Path("artifacts/pytest/revision.json")


def refuse(event: str, ref: str, default_branch: str, head: str, github_sha: str) -> None:
    """Raise ``SystemExit`` when this process must not start the full suite."""
    if event not in _ALLOWED_EVENTS:
        raise SystemExit(f"nightly refused event {event or '(missing)'}")
    if ref != _STAGING_REF:
        raise SystemExit(f"nightly refused ref {ref or '(missing)'}")
    if default_branch != "Staging":
        raise SystemExit(f"nightly refused default branch {default_branch or '(missing)'}")
    if not head or head != github_sha:
        raise SystemExit("nightly checkout SHA does not match github.sha")
    for key in _FORBIDDEN_ENV:
        if os.environ.get(key):
            raise SystemExit(f"nightly refused {key}")
    if os.environ.get("PLASTICOS_CONTRACT_CI") != "1":
        raise SystemExit("nightly requires PLASTICOS_CONTRACT_CI=1")
    if os.environ.get("PLASTICOS_CI_TIER") != "nightly_full":
        raise SystemExit("nightly requires PLASTICOS_CI_TIER=nightly_full")


def fetch_default_branch() -> str:
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    if not repo or "/" not in repo:
        raise SystemExit("nightly cannot resolve the repository default branch")
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "plasticos-nightly-full-python",
    }
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if not token:
        raise SystemExit("nightly requires GITHUB_TOKEN to read the default branch")
    headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(f"https://api.github.com/repos/{repo}", headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.load(response)
    except (OSError, TimeoutError, UnicodeError, json.JSONDecodeError, urllib.error.URLError) as exc:
        raise SystemExit(f"nightly cannot read the default branch: {exc}") from exc
    branch = payload.get("default_branch")
    if not isinstance(branch, str) or not branch:
        raise SystemExit("nightly default branch response is empty")
    return branch


def git_head() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise SystemExit(f"nightly cannot read HEAD: {exc}") from exc


def write_revision(event: str, ref: str, head: str, default_branch: str) -> None:
    _REVISION.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "event": event,
        "ref": ref,
        "default_branch": default_branch,
        "tested_checkout_sha": head,
        "github_sha": os.environ.get("GITHUB_SHA", ""),
        "run_id": os.environ.get("GITHUB_RUN_ID", ""),
        "run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT", ""),
        "tier": "nightly_full",
        "suite": "odoo-free pytest tests/",
    }
    _REVISION.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")


def main(fetch_default=fetch_default_branch, launch=subprocess.call, head: str | None = None) -> int:
    event = os.environ.get("GITHUB_EVENT_NAME", "")
    ref = os.environ.get("GITHUB_REF", "")
    github_sha = os.environ.get("GITHUB_SHA", "")
    observed = head if head is not None else git_head()
    default_branch = fetch_default()
    refuse(event, ref, default_branch, observed, github_sha)
    write_revision(event, ref, observed, default_branch)
    code = int(launch(NIGHTLY_PYTEST))
    if not _JUNIT.is_file():
        print("nightly missing JUnit evidence", file=sys.stderr)
        return code or 1
    return code


if __name__ == "__main__":
    sys.exit(main())
