#!/usr/bin/env bash
# Claude Code remote-environment setup script for IB-Odoo_19.
#
# WHERE THIS GOES: this file is documentation, not something the repo executes.
# Paste it as the environment's setup script (claude.ai/code -> the environment
# used for this repo). The container runs it at session start, so a session
# begins able to run the real-runtime launch gates instead of spending six
# minutes building a runtime first.
#
# WHY IT EXISTS: the launch gates in tests/runtime_gates/ need a live Odoo 19
# registry and a live PostgreSQL server. Docker is the usual way to get that,
# and in a sandbox it is often the hard way -- the daemon is not started, the
# registry pull goes through a TLS-inspecting proxy, and IPv4 forwarding is
# disabled so compose has no bridge network. The no-Docker path in
# docs/runbooks/C1_C6_LOCAL_RUNTIME.md has none of those dependencies.
#
# WHAT IT COSTS: about six minutes cold, seconds warm. Everything it builds is
# idempotent and cached, so re-running is cheap and safe.
set -euo pipefail

REPO="${REPO:-/home/user/IB-Odoo_19}"
cd "$REPO"

# 1. Toolchain the builder needs. Skip whatever the image already carries.
need=""
command -v python3.12  >/dev/null || need="$need python3.12 python3.12-venv"
[ -x /usr/lib/postgresql/16/bin/initdb ] || need="$need postgresql-16"
command -v psql        >/dev/null || need="$need postgresql-client-16"
if [ -n "$need" ]; then
  apt-get update -qq
  # shellcheck disable=SC2086
  DEBIAN_FRONTEND=noninteractive apt-get install -y -qq $need
fi

# 2. Repo tooling, pinned. pyproject pins ruff EXACTLY, so a mismatched binary
#    aborts every invocation -- install the pin, not "latest".
python3 -m pip install -q --upgrade pip
python3 -m pip install -q "ruff==0.16.0" "semgrep==1.164.0" pytest pytest-timeout pytest-cov

# 3. The Odoo 19 + PostgreSQL 16 runtime. Idempotent; seconds on a warm cache.
bash scripts/setup_local_runtime.sh

# 4. Verify, and fail the setup loudly rather than leaving a half-built runtime
#    that only shows up as a confusing gate error later.
bash scripts/setup_local_runtime.sh --check

cat <<'READY'

  Runtime ready. Useful entrypoints:

    make runtime-gates      real-runtime launch gates (C1-C6, F1-F3, S1-S3)
    make test-odoo-local    Odoo module tests, no Docker
    make test              pure-python suite (no runtime needed)
    make pr-check           full local gate before pushing

READY
