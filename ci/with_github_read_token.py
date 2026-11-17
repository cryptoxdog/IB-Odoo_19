#!/usr/bin/env python3
"""Run a command whose git can read private Quantum-L9 repositories.

``L9_GITHUB_READ_TOKEN`` is the organization secret: a fine-grained token with
contents and metadata read on the organization's repositories. ``GITHUB_TOKEN``
is scoped to this repository, so ``pip install`` of private ``Gate_SDK`` fails
with ``could not read Username`` when the clone is anonymous.

The token reaches git only as a per-command ``http.extraheader`` through
``GIT_CONFIG_COUNT`` / ``GIT_CONFIG_KEY_*`` / ``GIT_CONFIG_VALUE_*`` (git >= 2.31),
the same contract as ``l9-ci-core`` ``provision-sdk``. It is never placed in
argv, a URL, or a file, and the child environment does not keep the raw token.
"""

from __future__ import annotations

import base64
import os
import subprocess
import sys

TOKEN_ENV = "L9_GITHUB_READ_TOKEN"


def auth_env(token: str, base: dict[str, str] | None = None) -> dict[str, str]:
    """Return a child environment whose git sends ``token`` and does not inherit it."""
    env = dict(os.environ if base is None else base)
    env.pop(TOKEN_ENV, None)
    basic = base64.b64encode(f"x-access-token:{token}".encode()).decode()
    index = int(env.get("GIT_CONFIG_COUNT", "0") or "0")
    env[f"GIT_CONFIG_KEY_{index}"] = "http.https://github.com/.extraheader"
    env[f"GIT_CONFIG_VALUE_{index}"] = f"AUTHORIZATION: basic {basic}"
    env["GIT_CONFIG_COUNT"] = str(index + 1)
    return env


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args[:1] == ["--"]:
        args = args[1:]
    if not args:
        print("usage: with_github_read_token.py -- COMMAND ...", file=sys.stderr)
        return 2
    token = os.environ.get(TOKEN_ENV, "").strip()
    if not token:
        print(
            f"{TOKEN_ENV} is empty. Gate_SDK is private, and GITHUB_TOKEN cannot "
            "read Quantum-L9 repositories. Pass the organization read secret into this step.",
            file=sys.stderr,
        )
        return 1
    completed = subprocess.run(args, env=auth_env(token), check=False)  # noqa: S603
    return completed.returncode


if __name__ == "__main__":
    sys.exit(main())
