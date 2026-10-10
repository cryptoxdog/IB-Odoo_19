#!/usr/bin/env bash
# Usage: run_import.sh <run-name> [ERP_REQUIRE_EMPTY]
# Launches the real importer (odoo shell + import_erp_shell.py) detached against erp_import_proof.
set -euo pipefail
name="$1"; require_empty="${2:-}"
cd "/Users/ib-mac/IB-Odoo_19 (LOCAL)/IB-Odoo_19"
docker rm -f "erp_proof_${name}" >/dev/null 2>&1 || true
docker compose -p odoo19 run -d --name "erp_proof_${name}" -w /mnt/extra-addons \
  -e ERP_DRY= -e ERP_LIMIT= -e ERP_PAYLOAD_ROOT= -e ERP_REQUIRE_EMPTY="${require_empty}" -e ERP_PARTNERS_ONLY= -e ERP_LAYER= \
  -e ERP_REPORT_PATH="/mnt/extra-addons/.l9/pr/erp-import-${name}-summary.json" \
  -e ERP_TARGET_DB=erp_import_proof \
  -e ERP_SQL_SERVER=host.docker.internal -e ERP_SQL_PORT=1433 -e ERP_SQL_USER=sa -e ERP_SQL_DRIVER= \
  -e ERP_SQL_DATABASE="$ERP_SQL_DATABASE" -e ERP_SQL_PASSWORD="$ERP_SQL_PASSWORD" \
  odoo sh -c 'odoo shell -d erp_import_proof --no-http --log-level=info < /mnt/extra-addons/plasticos_partner_import/scripts/import_erp_shell.py'
