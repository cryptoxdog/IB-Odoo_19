# Q4 deep diagnosis summary
Source: `/Users/ib-mac/IB-Odoo_19 (LOCAL)/IB-Odoo_19/Current Work - IGNORE/CieTrade Data Extraction/cieTrade_export_20260807_183800/deep diagnosis.md` → copied to `/Users/ib-mac/IB-Odoo_19 (LOCAL)/IB-Odoo_19/Current Work - IGNORE/CieTrade Data Extraction/cieTrade_export_20260807_181433_live/diagnostics/q4_deep_diagnosis.md`
Integrity: ACCEPT

## Identity
- DB: `cieTrade_SM_EXPORT`
- Login: `UCSINC\\ibeylin`

## Value distributions
### Role
- `V`: 505
- `S`: 252
- `A`: 243
- `D`: 186
- `X`: 110
- `P`: 55
- `C`: 44
### ActiveStatus
- `A`: 1195
- `I`: 200
### OnHold
- `(blank)`: 1387
- `NULL`: 7
- `N`: 1
### PostingType
- `CRE`: 6069
- `UAC`: 361
- `OFF`: 107
### CurrencyCd
- `USD`: 12746

## Primary keys found (INFORMATION_SCHEMA)
- `Address.CpID` (PK_Address)
- `Address.Type` (PK_Address)
- `Contact.CT_ID` (PK_Contact)
- `ContactRoleAssignment.CRA_ID` (PK_ContactRoleAssignment)
- `PrepayLedger.PrepayID` (PK_PrepayLedger)
- `ReceiptBatch.ARBatchNo` (pk_ReceiptBatch)
- `UACashLedger.LedgerID` (PK_UACashLedger)

## Foreign keys
- None returned for P0 set (empty FK result grid).

## Column inventory
- Full CSV: `diagnostics/q4_columns.csv`
- **Address**: 56 columns
- **Contact**: 14 columns
- **ContactRoleAssignment**: 3 columns
- **CounterParty**: 106 columns
- **GPLedger**: 61 columns
- **Payables**: 32 columns
- **PayablesBatch**: 22 columns
- **PrepayLedger**: 16 columns
- **Receipt**: 30 columns
- **ReceiptBatch**: 15 columns
- **UACashLedger**: 28 columns
- **WKSDetail**: 104 columns
- **WksDelivery**: 29 columns
