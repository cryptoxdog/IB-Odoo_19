#!/usr/bin/env bash
# Run full make pr-check against a specific PR (URL or number).
# Usage: scripts/pr_check.sh 100
#        scripts/pr_check.sh https://github.com/cryptoxdog/IB-Odoo_19/pull/100
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
cd "${ROOT}"

REF="${1:?PR number or GitHub pull URL required}"
export PR_REMOTE_REF="${REF}"
exec make pr-check
