#!/usr/bin/env bash
# Usage: collect.sh <run-name>  — snapshot + normalized dump + container log summary for a finished run.
set -uo pipefail
name="$1"; out=/tmp/erp_proof
docker inspect "erp_proof_${name}" --format 'status={{.State.Status}} exit={{.State.ExitCode}} started={{.State.StartedAt}} finished={{.State.FinishedAt}}' > "$out/${name}_container.txt"
docker logs "erp_proof_${name}" 2>&1 | grep -v "docutils\|(ERROR/3)\|unknown parameter 'tracking'\|PyJWT\|pdf417gen" > "$out/${name}_log.txt"
docker exec -i odoo19-db-1 psql -U odoo -d erp_import_proof -f - < "$out/snapshot.sql" > "$out/${name}_snapshot.txt" 2>&1
docker exec -i odoo19-db-1 psql -U odoo -d erp_import_proof -f - < "$out/dump.sql" > "$out/${name}_dump.txt" 2>&1
cp "/Users/ib-mac/IB-Odoo_19 (LOCAL)/IB-Odoo_19/.l9/pr/erp-import-${name}-summary.json" "$out/${name}_summary.json" 2>/dev/null || echo "no summary json"
cat "$out/${name}_container.txt"; wc -l "$out/${name}_dump.txt" "$out/${name}_log.txt"
