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

LOCAL_SHA="$(git rev-parse HEAD)"

if ! git push -u origin "HEAD:${TARGET}"; then
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
