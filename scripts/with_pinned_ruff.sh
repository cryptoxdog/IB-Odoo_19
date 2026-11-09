#!/usr/bin/env bash
# Exec the ruff version this repo pins, then replace this process with it.
#
# make pr reaches ruff through `make lint` / `make format` in the audit wave.
# requirements-dev.txt (`ruff==X`) is that pin, the same one `make venv`,
# ci.yml, and .pre-commit-config.yaml install. pyproject.toml
# required-version rejects every other ruff. A linked worktree has no .venv,
# so a PATH fallback runs whatever ruff is installed and the audit wave dies
# before it lints. This wrapper never execs that binary.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PIN=""

pin_from_requirements() {
  local req="$ROOT/requirements-dev.txt"
  local pin
  if [[ ! -f "$req" ]]; then
    echo "FAIL: $req is missing; cannot pin ruff" >&2
    exit 1
  fi
  pin="$(
    sed -nE 's/^[[:space:]]*ruff[[:space:]]*==[[:space:]]*([^[:space:];#,]+).*/\1/p' "$req" |
      awk 'NR == 1 { print; exit }'
  )"
  if [[ -z "$pin" || "$pin" == *"*"* ]]; then
    echo "FAIL: $req has no exact ruff== pin" >&2
    exit 1
  fi
  printf '%s\n' "$pin"
}

pyproject_pin() {
  local spec=""
  if [[ -f "$ROOT/pyproject.toml" ]]; then
    spec="$(
      sed -nE 's/^required-version[[:space:]]*=[[:space:]]*"==([^"*]+)".*/\1/p' "$ROOT/pyproject.toml" |
        awk 'NR == 1 { print; exit }'
    )"
  fi
  printf '%s\n' "$spec"
}

# True when $1 is an executable ruff whose --version equals PIN.
matches() {
  local bin="$1" got
  [[ -x "$bin" ]] || return 1
  got="$("$bin" --version 2>/dev/null | awk 'NR == 1 { print $2; exit }')" || return 1
  [[ -n "$got" && "$got" == "$PIN" ]]
}

# Exec $1 with the remaining args when it is the pinned ruff.
try_exec() {
  local bin="$1"
  shift
  if matches "$bin" ; then
    exec "$bin" "$@"
  fi
}

# A linked worktree does not carry .venv. The primary checkout's venv does.
search_worktrees() {
  local line wt wt_phys root_phys toplevel
  command -v git >/dev/null 2>&1 || return 0
  # --show-toplevel walks parents. A checkout that merely sits inside another
  # repo is not that repo's worktree, and must not borrow its .venv.
  toplevel="$(git -C "$ROOT" rev-parse --show-toplevel 2>/dev/null || true)"
  [[ -n "$toplevel" ]] || return 0
  root_phys="$(cd "$ROOT" && pwd -P)"
  [[ "$(cd "$toplevel" && pwd -P)" == "$root_phys" ]] || return 0
  while IFS= read -r line || [[ -n "$line" ]]; do
    case "$line" in
      worktree\ *)
        wt="${line#worktree }"
        [[ -d "$wt" ]] || continue
        wt_phys="$(cd "$wt" && pwd -P)" || continue
        [[ "$wt_phys" == "$root_phys" ]] && continue
        try_exec "$wt/.venv/bin/ruff" "$@"
        ;;
    esac
  done < <(git -C "$ROOT" worktree list --porcelain)
}

fail_unavailable() {
  local path_ruff path_version
  echo "FAIL: ruff==${PIN} is required (requirements-dev.txt)." >&2
  echo "      ${ROOT}/.venv/bin/ruff is missing or is not ${PIN}." >&2
  path_ruff="$(command -v ruff 2>/dev/null || true)"
  if [[ -n "$path_ruff" ]]; then
    path_version="$("$path_ruff" --version 2>/dev/null | awk 'NR == 1 { print $2; exit }' || true)"
    echo "      PATH ruff (${path_ruff}) is ${path_version:-unknown}, which is not ${PIN}." >&2
  fi
  echo "      Run: make venv" >&2
  echo "      Or install uv so this gate can run ruff==${PIN}." >&2
  exit 1
}

PIN="$(pin_from_requirements)"
py_pin="$(pyproject_pin)"
if [[ -n "$py_pin" && "$py_pin" != "$PIN" ]]; then
  echo "FAIL: requirements-dev.txt pins ruff==${PIN} but pyproject.toml required-version is ==${py_pin}" >&2
  exit 1
fi

try_exec "$ROOT/.venv/bin/ruff" "$@"
search_worktrees "$@"
path_ruff="$(command -v ruff 2>/dev/null || true)"
if [[ -n "$path_ruff" ]]; then
  try_exec "$path_ruff" "$@"
fi
if command -v uv >/dev/null 2>&1; then
  exec uv tool run --from "ruff==${PIN}" ruff "$@"
fi
fail_unavailable
