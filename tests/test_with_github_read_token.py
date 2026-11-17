"""The Gate SDK install helper authenticates git without handing the token to the child."""

from __future__ import annotations

import base64
import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "ci" / "with_github_read_token.py"

_spec = importlib.util.spec_from_file_location("with_github_read_token", SCRIPT)
assert _spec is not None and _spec.loader is not None
helper = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(helper)


def test_auth_env_sets_a_git_header_and_drops_the_raw_token() -> None:
    token = "org-read-example"
    env = helper.auth_env(token, {"PATH": "/usr/bin", "L9_GITHUB_READ_TOKEN": token})
    assert "L9_GITHUB_READ_TOKEN" not in env
    assert env["GIT_CONFIG_COUNT"] == "1"
    assert env["GIT_CONFIG_KEY_0"] == "http.https://github.com/.extraheader"
    encoded = env["GIT_CONFIG_VALUE_0"].removeprefix("AUTHORIZATION: basic ")
    assert base64.b64decode(encoded).decode() == f"x-access-token:{token}"


def test_empty_token_does_not_run_the_command() -> None:
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--", sys.executable, "-c", "raise SystemExit(0)"],
        env={"PATH": "/usr/bin"},
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 1
    assert "L9_GITHUB_READ_TOKEN is empty" in completed.stderr
