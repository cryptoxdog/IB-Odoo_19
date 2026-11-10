# 00 | Resume here — copy in progress, 2026-11-09

Read this file first in a new chat. It records where the worksheet originals actually are. It does not authorize a Production write, and it does not mark G0–G8 passed.

## Do not do these

- Do not run `EXTRACT_BLOBS.ps1` again. The extract already finished on 2026-10-28.
- Do not disconnect the IB-PC remote session while Windows Explorer is still copying.
- Do not treat a partial `decoded/` folder as the corpus.
- Do not import into Odoo, Staging, or Production from this file alone.

## Where the files are

The finished extract is on the office file server, in the home folder that was writable when `C:` was not:

`\\ucsservers01\home\ibeylin\Desktop\SQL 10-28-26\extract`

| Path on the server | What it is |
|---|---|
| `extract\journal.csv` | 111,010-row journal. Full cohort. |
| `extract\decoded\<ImageID>.<ext>` | Opened originals. This is what Odoo attaches. |
| `extract\raw\<ImageID>.bin` | Original gzip. Stays on the server. The reconciler checks it only when `--raw-dir` is passed. |

The Mac copy is a Windows App folder redirect, not a second extract.

| Observed on this Mac | What it is |
|---|---|
| `/Users/ib-mac/Odoo-ERP-Files/journal.csv` | Journal already copied. 21 MB. Server timestamp preserved as 2026-10-28 16:20. |
| `/Users/ib-mac/Odoo-ERP-Files/decoded/` | Opened originals, copying now. Files sit directly in this folder: `<ImageID>.<ext>`. |
| the only `.bak` in `/Users/ib-mac/Odoo-ERP-Files` | October 3 ERP backup, 97,973,248 bytes. Not the document images. |

`/Users/ib-mac/Odoo-BAK-Files` does not exist. `\\tsclient\Odoo-BAK-Files` is a dead redirect. The live redirect is IB-PC (`remote.papersolve.com:3402`), Folders, name `Odoo-ERP-Files`, path `/Users/ib-mac/Odoo-ERP-Files`, Read-only off. Inside the session that share is `\\tsclient\Odoo-ERP-Files`.

A second journal, same missing column, is at `/Users/ib-mac/Dropbox/Downloads (DBOX)/journal.csv`. The working copy is the one under `Odoo-ERP-Files`.

## Copy that was running at 18:56 ET

Windows Explorer was copying 111,010 items, 38.6 GB, from the server `extract` folder into `\\tsclient\Odoo-ERP-Files\decoded`. Measured on the Mac at 18:53 ET: about 450 KB/s. At that rate the remaining 38.5 GB finishes around 7:45 PM on Tuesday 2026-11-10. The rate was moving between 300 and 500 KB/s, so the clock time is an estimate, not a receipt.

At 18:56 ET the Mac folder held 424 files and 179 MB. Recount before calling the copy finished. A finished copy has a stable file count and a stable byte size across two checks, and Explorer is no longer copying.

ImageID `633316` is the known `not_gzip` row and may have no decoded file. A decoded count of 111,009, with that image absent, still matches the journal. Confirm against the journal. Do not invent the missing file.

## Journal column the reconciler requires

The copied journal header is:

`ImageID,DocID,RefID,RefType,FileExt,BlobSize,CreatedDT,RawBytes,RawSha256,DecodedBytes,DecodedSha256,Status`

It has no `ImportScope` column. `tools/reconcile_cohort.py` rejects a journal that lacks that column. Do not re-extract to add it. After the copy is stable, add the column from `RefType` the way `EXTRACT_BLOBS.ps1` already does: `W` and `#` are `eligible`, `P` is `archive_only`, `E` and `B` are `unattached`.

When both the journal and `decoded/` are stable, the read-only check is:

```sh
python3 docs/campaigns/11-09-26/PlasticOS_Worksheet_Documents_Runbook/tools/reconcile_cohort.py \
  --journal /Users/ib-mac/Odoo-ERP-Files/journal.csv \
  --transactions <private Production export id,name,company_id> \
  --decoded-dir /Users/ib-mac/Odoo-ERP-Files/decoded \
  --output <private-receipt>
```

`--raw-dir` stays optional and points at the server `raw` folder only if that share is mounted. Omitting it records raw verification as `NOT_RUN`.

## What is still not done

G0 through G8 are `NOT_RUN`. Hosted Production was not observed. No importer exists (`make import-erp-documents` is not a target). `make import-erp` does not load these files. The next work after the copy is the gate order in `01_OPERATOR_GATES.md`, starting with a read-only Production identity check, not a bulk import.
