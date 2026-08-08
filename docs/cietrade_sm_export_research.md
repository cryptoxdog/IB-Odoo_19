# cieTrade `SM_EXPORT` — extract runbook

**Status (2026-08-07):** P0 data on Mac as CSVs. PlasticOS import not wired.  
**SSOT** — re-run extracts with zero chat context.

| | |
|--|--|
| Server | `UCSCIETRADE` |
| Database | **`cieTrade_SM_EXPORT`** (not `cieTrade_SM`) |
| Login | `UCSINC\ibeylin` (Windows auth in SSMS) |
| Client | SSMS on **Windows App → IB-PC** |
| Mac SQL | No `sqlcmd`; `:1433` unreachable from Mac |
| Tracked pack | `data/cietrade_sm_export/` |
| SQL (canonical) | `data/cietrade_sm_export/sql/` — see §3 |
| Golden CSVs | `data/cietrade_sm_export/bulk/*.csv` |
| WIP land / Excel | gitignored `Current Work - IGNORE/CieTrade Data Extraction/excel files/` |
| Control plane | `~/.cursor-governance/tools/l9_agent_ui_control` |
| Odoo partner import | [README_plasticos_partner_import.md](./README_plasticos_partner_import.md) — different CSV shape |

---

## 1. Paths

```bash
REPO="${CURSOR_PROJECT_DIR:-$HOME/IB-Odoo_19 (LOCAL)/IB-Odoo_19}"
LIVE="$REPO/data/cietrade_sm_export"
SQL="$LIVE/sql"
BULK="$LIVE/bulk"
EXTRACT="$REPO/Current Work - IGNORE/CieTrade Data Extraction"  # WIP Excel land only
PACK="$HOME/.cursor-governance/tools/l9_agent_ui_control"
PY="$HOME/.cursor-governance/.venv/bin/python"
[ -x "$PY" ] || PY="$(command -v python3)"
```

---

## 2. Hard rules

1. Toolbar DB = **`cieTrade_SM_EXPORT`**. Results to **Grid** only.
2. **Never** Windows App drag / Save Results `.rpt` → Mac (null-byte files).
3. **Do** Copy with Headers (`Ctrl+Shift+C`) → Mac file, **or** Excel `.xlsx` on IB-PC → copy bytes to Mac → convert (§6).
4. Accept only if `size > 0` **and** `nonzero_bytes > 0` **and** row 1 is a real header.
5. Never `CREATE TABLE` / writes in extract scripts (Msg 262 on `master`).
6. Agent GUI: raise **`IB-PC`**. No Cmd/Ctrl+N. Prefer `pbcopy` + human paste/Execute.
7. Data is **CSV/XLSX**; `.sql` files are SELECT-only.

```bash
"$PY" "$PACK/integrity_check.py" "$BULK"
```

---

## 3. SQL catalog (`$SQL/`)

| File | Purpose |
|------|---------|
| `00_probe.sql` | Confirm DB / login / server |
| `01_census.sql` | Table size rank |
| `02_columns.sql` | P0 column inventory |
| `03_diagnostic.sql` | PK / FK / distributions |
| `04_counts.sql` | Exact row counts |
| **`05_extract_all.sql`** | **Full reload — 14 result grids** |
| `06_extract_remaining.sql` | Batches / roles / delivery / docs only |
| `10_counterparty.sql` … `17_prepayledger.sql` | Single-table full extracts |
| `archive/` | Legacy explore scripts — do not use |

---

## 4. Re-run procedure

```text
1. Windows App → IB-PC → SSMS → UCSCIETRADE
2. New query → toolbar DB = cieTrade_SM_EXPORT → Results to Grid
3. Mac: pbcopy < "$SQL/<file>.sql"
4. Paste into SSMS (replace all) → Execute
5. Transfer each grid:
   A) Ctrl+A → Ctrl+Shift+C → paste Mac $BULK/<Name>.csv
   B) Or Excel on IB-PC → .xlsx → $EXTRACT/excel files/ → §6
6. Integrity check (§2)
```

### Full reload (preferred)

```bash
pbcopy < "$SQL/00_probe.sql"           # expect cieTrade_SM_EXPORT
pbcopy < "$SQL/05_extract_all.sql"     # 14 grids
# Each tab → Copy with Headers → $BULK/<name from SQL comment>.csv
"$PY" "$PACK/integrity_check.py" "$BULK"
```

| Grid | Save as |
|------|---------|
| 1 | `CounterParty.csv` |
| 2 | `Address.csv` |
| 3 | `Contact.csv` |
| 4 | `ContactRoleAssignment.csv` |
| 5 | `Payables.csv` |
| 6 | `PayablesBatch.csv` |
| 7 | `Receipt.csv` |
| 8 | `ReceiptBatch.csv` |
| 9 | `GPLedger.csv` |
| 10 | `UACashLedger.csv` |
| 11 | `PrepayLedger.csv` |
| 12 | `WKSDetail.csv` |
| 13 | `WksDelivery.csv` |
| 14 | `WksDocument.csv` (slim — no `Field*` blobs) |

### Single table / gap fill

```bash
pbcopy < "$SQL/10_counterparty.sql"
pbcopy < "$SQL/11_address.sql"
pbcopy < "$SQL/12_contact.sql"        # no IsActive filter
pbcopy < "$SQL/13_payables.sql"
pbcopy < "$SQL/14_receipt.sql"
pbcopy < "$SQL/15_gpledger.sql"
pbcopy < "$SQL/16_wksdetail.sql"
pbcopy < "$SQL/17_prepayledger.sql"   # not landed yet
```

### Remaining-only (7 grids)

```bash
pbcopy < "$SQL/06_extract_remaining.sql"
# ContactRoleAssignment, PayablesBatch, ReceiptBatch, UACashLedger,
# PrepayLedger, WksDelivery, WksDocument(slim)
```

### Diagnostics (optional)

```bash
pbcopy < "$SQL/01_census.sql"
pbcopy < "$SQL/02_columns.sql"
pbcopy < "$SQL/03_diagnostic.sql"     # artifacts: $LIVE/diagnostics/
pbcopy < "$SQL/04_counts.sql"
```

---

## 5. Landed inventory

Under `$BULK/` (and extract-root mirrors). Row counts ≈ data rows.

| File | Rows | Notes |
|------|------|-------|
| `CounterParty.csv` | ~1290 | Active; drop synthetic `CpID` |
| `Address.csv` | ~2950 | |
| `Contact.csv` | ~4058 | |
| `ContactRoleAssignment.csv` | ~3091 | |
| `Payables.csv` | 14453 | |
| `PayablesBatch.csv` | 11872 | |
| `Receipt.csv` | 7425 | |
| `ReceiptBatch.csv` | 4545 | |
| `GPLedger.csv` | 8220 | |
| `UACashLedger.csv` | 174 | |
| `WKSDetail.csv` | 11303 | |
| `WksDelivery.csv` | 8327 | |
| `WksDocument.csv` | 87297 | Slim |
| `PrepayLedger.csv` | — | **Gap** — run `17_prepayledger.sql` |

Join keys: **`CpID`** (partners) · **`BuySellNo`** (trade/payment lines).

**Reject:**

- `$EXTRACT/cieTrade_export_20260807_183800/` (null CSVs)
- `$EXTRACT/8-7-26*.rpt` (all `\x00`)
- Any file with `nonzero_bytes == 0`

---

## 6. Schema notes

| Fact | Detail |
|------|--------|
| Payment history | **Payables + Receipt** (not empty `AccountingPayment` / `Checks`) |
| `Contact.IsActive` | `char(1)` `Y`/`N` — never compare to int |
| `CounterParty.Role` | V / S / A / D / X / P / C |
| `CounterParty.ActiveStatus` | `A` / `I` |
| `Receipt.PostingType` | CRE / UAC / OFF |
| Clipboard dates | `CONVERT(varchar(19), col, 120)` in SELECTs |
| `WksDocument` | Extract **slim** only (skip `Field*` blobs) |

Role → PlasticOS ranks/tags: draft mapping only — not implemented.

---

## 7. Excel → CSV (Mac)

When results land as `$EXTRACT/excel files/Book*.xlsx`:

```bash
"$PY" -m pip install -q openpyxl
export EXTRACT  # from §1
"$PY" - <<'PY'
from pathlib import Path
import csv, re, os
from openpyxl import load_workbook

excel_dir = Path(os.environ["EXTRACT"]) / "excel files"
out_dir = excel_dir / "csv"
out_dir.mkdir(exist_ok=True)

def guess(headers):
    h = {str(x).strip() for x in headers if x is not None}
    if "AddressID" in h and "CpID" in h: return "Address"
    if "PayableID" in h: return "Payables"
    if "ReceiptID" in h: return "Receipt"
    if "CRA_ID" in h: return "ContactRoleAssignment"
    if "CT_ID" in h and "ContactNm" in h: return "Contact"
    if "PrepayID" in h: return "PrepayLedger"
    if "DocumentID" in h: return "WksDocument"
    if "DetailID" in h and "SWeight" in h: return "WKSDetail"
    if "ItemID" in h and "TrailerNo" in h: return "WksDelivery"
    if "LedgerID" in h and "GrossProfit" in h: return "GPLedger"
    if "LedgerID" in h and "CustID" in h: return "UACashLedger"
    if "APBatchNo" in h and "NumofItems" in h: return "PayablesBatch"
    if "ARBatchNo" in h and "PostType" in h: return "ReceiptBatch"
    if "CpID" in h and "CompanyNm" in h and "Role" in h: return "CounterParty"
    return "Unknown"

for xlsx in sorted(excel_dir.glob("*.xlsx")):
    wb = load_workbook(xlsx, read_only=True, data_only=True)
    ws = wb[wb.sheetnames[0]]
    it = ws.iter_rows(values_only=True)
    header = list(next(it))
    while header and header[-1] is None:
        header.pop()
    name = guess(header)
    out = out_dir / f"{xlsx.stem}__{name}.csv"
    with out.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow([("" if c is None else c) for c in header])
        for row in it:
            if row is None or all(v is None or str(v).strip() == "" for v in row):
                continue
            vals = list(row[: len(header)]) + [None] * max(0, len(header) - len(row))
            w.writerow([("" if v is None else v) for v in vals[: len(header)]])
    print(out.name)
    wb.close()
PY
# Promote newest Book per table into $BULK as needed
```

---

## 8. Import into Odoo (not built for this dump)

| Step | Action |
|------|--------|
| 1 | Golden CSVs live under `$BULK/` (`data/cietrade_sm_export/bulk/`) |
| 2 | Transform offline: `CounterParty`+`Address`+`Contact` → shape for `plasticos.partner.import.service` (`CpID` → `ref`) |
| 3 | Headless load via shell / ICP — not Contacts wizard UI |
| 4 | Payables / Receipt / WKS need a **new** staging path |

See [README_plasticos_partner_import.md](./README_plasticos_partner_import.md).

---

## 9. Checklist — full reload

```bash
pbcopy < "$SQL/00_probe.sql"
pbcopy < "$SQL/05_extract_all.sql"
# SSMS Execute → Copy with Headers each grid → $BULK/<Name>.csv
"$PY" "$PACK/integrity_check.py" "$BULK"
# Optional gap:
pbcopy < "$SQL/17_prepayledger.sql"
```
