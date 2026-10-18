#!/usr/bin/env bash
# Push the current HEAD only after live L4 check-remote allows this worktree.
# Prove origin's branch ref matches local HEAD. Does not open the PR.
set -euo pipefail

refuse() {
  echo "refusing to publish: $*" >&2
  exit 1
}

require_l4_release() {
  # These switches make upstream release_allows_remote() return success.
  # They are not authorization for this publication.
  local l4_switch="${L9_L4_LOCAL_AUTONOMY-1}"
  case "${l4_switch}" in
    0|false|False|no)
      refuse "L9_L4_LOCAL_AUTONOMY=${l4_switch} is not release authorization"
      ;;
  esac
  if [[ -n "${L9_LOCAL_PUSH_AUTHORIZED:-}" ]]; then
    refuse "L9_LOCAL_PUSH_AUTHORIZED is not release authorization"
  fi

  local resolver="${HOME}/.cursor-governance/ops/scripts/resolve_governance_paths.sh"
  if [[ ! -f "${resolver}" ]]; then
    refuse "L4 provider is not available (no governance resolver at \$HOME/.cursor-governance)"
  fi
  # shellcheck disable=SC1090
  source "${resolver}"
  if ! resolve_governance_paths; then
    refuse "L4 provider is not available at \$HOME/.cursor-governance"
  fi
  local l4_py="${GOV_ROOT}/ops/autonomy/l4_local.py"
  if [[ ! -f "${l4_py}" ]]; then
    refuse "L4 check-remote provider is missing"
  fi

  local worktree gov_real l4_out l4_rc
  worktree="$(git rev-parse --show-toplevel)"
  worktree="$(python3 -c 'import os,sys; print(os.path.realpath(sys.argv[1]))' "${worktree}")"
  gov_real="$(python3 -c 'import os,sys; print(os.path.realpath(sys.argv[1]))' "${GOV_ROOT}")"
  if [[ "${worktree}" == "${gov_real}" ]]; then
    refuse "L4 workspace resolved to the governance checkout"
  fi

  set +e
  l4_out="$(python3 "${l4_py}" check-remote --workspace "${worktree}")"
  l4_rc=$?
  set -e
  printf '%s\n' "${l4_out}"
  if [[ "${l4_rc}" -ne 0 ]]; then
    refuse "L4 check-remote denied release for ${worktree} (exit ${l4_rc})"
  fi
  printf '%s' "${l4_out}" | python3 -c '
import json, sys
data = json.load(sys.stdin)
if data.get("allowed") is not True or not isinstance(data.get("reason"), str) or not data["reason"]:
    raise SystemExit("L4 check-remote did not return release authorization")
'
}

if [[ "${1:-}" == "--check-l4" ]]; then
  require_l4_release
  exit 0
fi

TARGET="${1:?target branch required}"
case "${TARGET}" in
  Staging|Production|staging|production)
    refuse "${TARGET} is a protected branch"
    ;;
esac

require_l4_release

status="$(git status --porcelain)"
if [[ -n "${status}" ]]; then
  echo "refusing to publish: working tree, index, or untracked files are not clean" >&2
  printf '%s\n' "${status}" >&2
  exit 1
fi
LOCAL_SHA="$(git rev-parse HEAD)"

push_urls=()
while IFS= read -r push_url; do
  [[ -n "${push_url}" ]] && push_urls+=("${push_url}")
done < <(git remote get-url --push --all origin 2>/dev/null || true)
if [[ "${#push_urls[@]}" -ne 1 ]]; then
  refuse "origin must have exactly one push URL"
fi
python3 - "${push_urls[0]}" <<'PY'
import sys

url = sys.argv[1].removesuffix(".git")
allowed = {
    "https://github.com/cryptoxdog/IB-Odoo_19",
    "git://github.com/cryptoxdog/IB-Odoo_19",
    "git@github.com:cryptoxdog/IB-Odoo_19",
    "ssh://git@github.com/cryptoxdog/IB-Odoo_19",
}
if url not in allowed:
    raise SystemExit(f"refusing to publish: origin push URL is not cryptoxdog/IB-Odoo_19 ({sys.argv[1]})")
PY

export GH_REPO="cryptoxdog/IB-Odoo_19"
case "${PR_CHECK_SKIP_REMOTE:-0}" in
  1|true|True|yes) refuse "PR_CHECK_SKIP_REMOTE is set" ;;
esac
case "${PR_CHECK_SKIP_SMOKE:-0}" in
  1|true|True|yes) refuse "PR_CHECK_SKIP_SMOKE is set" ;;
esac
case "${PR_CHECK_FORCE_SMOKE:-0}" in
  1|true|True|yes) refuse "PR_CHECK_FORCE_SMOKE is set" ;;
esac

if ! command -v gitleaks >/dev/null 2>&1; then
  refuse "gitleaks is not on PATH"
fi
if ! gitleaks detect --config .gitleaks.toml --redact --exit-code 2; then
  refuse "gitleaks detect failed"
fi

if ! bash scripts/install_smoke.sh --resolve; then
  refuse "install-smoke --resolve rejected the effective module lists"
fi

if ! make pr-check; then
  refuse "make pr-check failed"
fi

if [[ "$(git rev-parse HEAD)" != "${LOCAL_SHA}" ]] || [[ -n "$(git status --porcelain)" ]]; then
  refuse "HEAD or the worktree changed during validation"
fi
if ! bash scripts/install_smoke.sh --recheck; then
  refuse "install-smoke --recheck rejected the live evidence"
fi

if ! git push --no-verify -u origin "HEAD:${TARGET}"; then
  echo "git push failed for origin/${TARGET} (local HEAD ${LOCAL_SHA})" >&2
  echo "Publication stays on make pr. An API push is not a fallback ceremony." >&2
  exit 1
fi

REMOTE_SHA="$(git ls-remote --heads origin "${TARGET}" | awk 'NR == 1 { print $1 }')"
if [[ -z "${REMOTE_SHA}" ]]; then
  echo "remote refs/heads/${TARGET} is missing after push; local HEAD is ${LOCAL_SHA}" >&2
  exit 1
fi
if [[ "${REMOTE_SHA}" != "${LOCAL_SHA}" ]]; then
  echo "remote refs/heads/${TARGET} is ${REMOTE_SHA}; local HEAD is ${LOCAL_SHA}" >&2
  exit 1
fi
echo "✅ Push complete → origin/${TARGET} (${LOCAL_SHA})"
