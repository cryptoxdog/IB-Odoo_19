# Go-live ERP source chain — SM-CIETRADE-DOCUMENT-RECOVERY-001

**Recorded:** 2026-10-28  
**Use this on go-live day.** The October 3 restore in `01_SOURCE_DISCOVERY.md` and `09_OPERATOR_HANDOFF.md` is the historical proof. Go-live uses a new backup, current as of that day, in `/Users/ib-mac/Odoo-ERP-Files`.

`docs/campaigns/PlasticOS_Plan_Graph` publishes with this pack. It is the planning graph for the same go-live. It is not an implementation contract and it does not change the running extractor.

## Historical chain, already applied

On 2026-10-03, `UCSCIETRADE` backed up live `cieTrade_SM` to `cieTrade_SM_2026-10-03.bak`. On 2026-10-18 that file was restored from `/Users/ib-mac/sql-backup-proof/cieTrade_SM_2026-10-03.bak` into Docker `cie-sql-proof` as database `cieTrade_SM`. `make import-erp` read that restored database through `ERP_SQL_SERVER` and `ERP_SQL_DATABASE`. The import reads the database. The `.bak` path is the restore input that selects which snapshot the database contains.

That October 3 file is one backup with four copies:

| Path | Role |
|---|---|
| `/Users/ib-mac/sql-backup-proof/cieTrade_SM_2026-10-03.bak` | Restore input for the 2026-10-18 proof |
| `/Users/ib-mac/sql-backup-lab/cieTrade_SM_2026-10-03.bak` | Extra copy of the same file |
| `plasticos_partner_import/erp_extracted_data/bulk/cieTrade_SM_2026-10-03.bak` | Regression fixture of the same file |
| `/Users/ib-mac/Odoo-ERP-Files/cieTrade_SM_2026-10-03.bak` | Same file, after `Odoo-BAK-Files` was renamed on 2026-10-28 |

Worksheet activity in that restore stops at 2026-10-02. The file does not contain `cieTrade_Documents`.

## Go-live chain

Go-live repeats the same chain with data current as of that day. The restore input is a new full backup of live `cieTrade_SM`, placed in `/Users/ib-mac/Odoo-ERP-Files/`.

| Step | Go-live path |
|---|---|
| Backup file, dated that day | `/Users/ib-mac/Odoo-ERP-Files/` |
| Remote Desktop copy path, after the IB-PC folder redirect is updated | `\\tsclient\Odoo-ERP-Files` |
| Restore input | The new file in `/Users/ib-mac/Odoo-ERP-Files/` |
| Import | `make import-erp` with `ERP_SQL_SERVER` and `ERP_SQL_DATABASE` pointed at the database restored from that file |

The October 3 file may stay in the same folder beside the new file. The go-live file is a new name dated that day. `sql-backup-proof`, `sql-backup-lab`, and `erp_extracted_data/bulk/` remain the October 3 copies.

Document images are not inside the `cieTrade_SM` backup. Their expanded copies also land in `/Users/ib-mac/Odoo-ERP-Files`. The extractor that is running now still writes to `\\ucsservers01\home\ibeylin\Desktop\SQL 10-28-26\extract` until that copy is made.
