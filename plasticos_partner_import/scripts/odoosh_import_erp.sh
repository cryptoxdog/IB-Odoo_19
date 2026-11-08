#!/usr/bin/env bash
# Odoo.sh entrypoint for the ERP historical import: the same driver as
# `make import-erp`, run through the host's own `odoo-bin shell`, with no
# Docker and no virtualenv.
#
#   ERP_TARGET_DB=<odoo.sh database> ERP_SQL_SERVER=... ERP_SQL_DATABASE=... \
#   ERP_SQL_USER=... ERP_SQL_PASSWORD=... [ERP_PRODUCTION_PERMIT=<permit.json>] \
#   bash plasticos_partner_import/scripts/odoosh_import_erp.sh <mode>
#
# Modes:
#   probe-partners | probe-commercial  print target identity + source fingerprint; writes nothing
#   partners                           ERP_PARTNERS_ONLY=1 on an empty target
#   commercial                         full run on the imported partners (ERP_REQUIRE_EMPTY=0)
#
# Production (ODOO_STAGE=production) refuses every applied mode unless
# ERP_PRODUCTION_PERMIT names a one-use operator permit for that phase.
# Reports, verdicts, permit receipts and the console log land in
# ERP_RUN_DIR (default: $HOME/data/plasticos_import), never in git.
set -euo pipefail

usage() {
	sed -n '2,17p' "$0" >&2
	exit 2
}

mode="${1:-}"
case "$mode" in
probe-partners) export ERP_PROBE=erp_partners ;;
probe-commercial) export ERP_PROBE=erp_commercial ;;
partners)
	export ERP_PARTNERS_ONLY=1
	unset ERP_REQUIRE_EMPTY
	;;
commercial)
	export ERP_REQUIRE_EMPTY=0
	unset ERP_PARTNERS_ONLY
	;;
*) usage ;;
esac

: "${ERP_TARGET_DB:?set ERP_TARGET_DB to the Odoo.sh database name}"
: "${ERP_SQL_SERVER:?set ERP_SQL_SERVER (direct SQL is the only production source)}"
: "${ERP_SQL_DATABASE:?set ERP_SQL_DATABASE}"
for name in ERP_LIMIT ERP_PAYLOAD_ROOT ERP_LAYER ERP_DRY; do
	if [[ -n "${!name:-}" ]]; then
		echo "refusing: $name is set; the hosted import runs the complete source" >&2
		exit 2
	fi
done
command -v odoo-bin >/dev/null || {
	echo "refusing: odoo-bin is not on PATH (run on the Odoo.sh shell)" >&2
	exit 2
}

run_dir="${ERP_RUN_DIR:-$HOME/data/plasticos_import}"
mkdir -p "$run_dir"
chmod 700 "$run_dir"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
export ERP_REPORT_PATH="${ERP_REPORT_PATH:-$run_dir/erp-$mode-$stamp.json}"
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "→ ERP $mode on $ERP_TARGET_DB (stage ${ODOO_STAGE:-unset}); report $ERP_REPORT_PATH"
set +e
odoo-bin shell -d "$ERP_TARGET_DB" --no-http <"$here/import_erp_shell.py" 2>&1 | tee "$run_dir/erp-$mode-$stamp.log"
status="${PIPESTATUS[0]}"
set -e
echo "→ ERP $mode exit $status"
exit "$status"
