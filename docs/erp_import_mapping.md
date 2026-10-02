# ERP → PlasticOS import: mapping audit

Definitive field-level matrix for the ERP historical import.

- **Source pack** — `plasticos_partner_import/erp_extracted_data/` (query definitions and frozen grids, 2026-08-07)
- **Source layer** — `plasticos_partner_import/erp/` (Odoo-free, CI-tested)
- **Import service** — `plasticos_partner_import/models/erp_import_service.py`
- **Entrypoint** — `plasticos_partner_import/scripts/run_erp_import.py`
- **Tests** — `tests/test_erp_source_layer.py`, `tests/test_erp_import_contract.py`

Every count below was measured on the tracked payload, not estimated.

---

## 0. Payload form

[ADR-021](adr/ADR-021-erp-sql-crm-api-import.md) is the contract: ERP rows
import from SQL, CRM rows import from the VanillaSoft API, and CSV is legacy.

`plasticos_partner_import/erp_extracted_data/*.sql` are the `SELECT` definitions for the ERP
extract. They do not yet contain the row payload. `reader.load_payload()`
parses `INSERT INTO … VALUES …` in preference to a grid. That statement form
is the ERP import. Do not add a new CSV mapping.

`plasticos_partner_import/erp_extracted_data/bulk/` (13 files, 17 MB) is a frozen grid from
2026-08-07. `make import-erp` can still read it until a SQL payload
replaces that call. The counts below were measured on that frozen grid. They
are not a reason to keep CSV as the architecture.

| Source table | Rows |
|---|---|
| CounterParty | 1290 |
| Address | 2950 |
| Contact | 4058 |
| ContactRoleAssignment | 3091 |
| WKSDetail | 11303 |
| GPLedger | 8220 |
| Payables | 14453 |
| Receipt | 7425 |
| ReceiptBatch | 4545 |
| WksDelivery | 8327 |

---

## 1. Identity contract

All primary keys verified unique and non-blank across the whole payload.

| Source key | Rows | Odoo target | `ir.model.data` name |
|---|---|---|---|
| `CounterParty.CpID` | 1290 | `res.partner` (company) | `plasticos_transaction.legacy_erp_cp_<CpID>` |
| `Address.AddressID` | 2950 | `res.partner` (child) | `legacy_erp_address_<AddressID>` |
| `Contact.CT_ID` | 4058 | `res.partner` (person) | `legacy_erp_contact_<CT_ID>` |
| `ContactRoleAssignment.CRA_ID` | 3091 | `res.partner.category` link | set-valued (see §5) |
| `WKSDetail.BuySellNo` | 8257 | `plasticos.transaction` | `legacy_erp_transaction_<BuySellNo>` |
| `WKSDetail.DetailID` | 11303 | `plasticos.transaction.line` | `legacy_erp_detail_<DetailID>` |

`Address`'s declared database PK is the composite `(CpID, Type)`; `AddressID`
was verified unique (2950/2950) and is used as the surrogate identity, which
also makes `Contact.Location` an exact join (§5).

Never identity: company name, e-mail, phone, address text, Odoo database id.

---

## 2. Transaction header reconstruction (the plan's step 9)

The export carries **no worksheet header table**, and `WKSDetail`'s full
104-column inventory contains **no status-like column** — verified against
`plasticos_partner_import/erp_extracted_data/diagnostics/q4_columns.csv`. Parties, date, and state are reconstructed from
accounting relationships.

| Fact | Source join | Coverage |
|---|---|---|
| Supplier | `Payables` where `ItemID` is empty → `Payables.CpID` | 6005 / 8257 |
| Buyer | `Receipt.ARBatchNo` → `ReceiptBatch.CPID` | 6488 / 8257 |
| Trade date | `min(GPLedger.TradeDt)` | 7267 / 8257 |
| Lines | `WKSDetail.BuySellNo` | 11303 lines |

**Why the supplier split works.** `Payables.ItemID` is an undeclared foreign key
into `WksDelivery.ItemID` (8054 of 8210 populated values resolve). A payable
carrying one is a freight cost for a delivery leg — its `CpID` agrees with
`WksDelivery.VendorID` on 5250 of 5524 shared `BuySellNo`. Without the split,
3849 `BuySellNo` name two distinct vendors and no supplier is determinable;
with it, 6060 of 6062 resolve to exactly one.

**Why the buyer join works.** `Receipt → ReceiptBatch.CPID` yields exactly one
customer for **all** 6938 `BuySellNo` it covers. Zero are multi-valued.

**Corroboration from `CounterParty.Role`.** The material-supplier set is
`V`/`S`-dominant and contains no `X`/`C`; the buyer set is `X`/`C`/`A`-only and
contains no `V`; carrier code `D` appears only on freight legs.

**`DesignatedCpID` is rejected as a party.** Populated on 22 of 8257
`BuySellNo`, it matches the buyer in 0 of 0 overlapping cases and the material
supplier in 0 of 15. A test asserts it never becomes either party.

**Unresolved is reported, never guessed.** 5403 transactions resolve supplier,
buyer, and date together. The rest carry an explicit reason
(`no material payable`, `no settled receipt`, `no GPLedger trade date`), and 2
ambiguous-supplier rows are left unresolved rather than picked.

### Historical state — derived, not read

The source has no status column, so state is derived from settlement evidence:

| State | Condition | Count |
|---|---|---|
| `closed` | booked in GPLedger + posted material payable + receipt | 5451 |
| `invoiced` | booked in GPLedger, not settled both sides | 1816 |
| `delivered` | delivery leg exists, never booked | 104 |
| `draft` | lines only | 886 |

This replaces the retired service's flat `state="closed"` for every row.

---

## 3. CounterParty → `res.partner`

`CounterParty.Role` semantics were proven by behaviour, not by letter, by
cross-referencing every counterparty against the material-supplier, buyer, and
freight sets.

| Code | Count | Supplier / Buyer / Freight | `company_role` | ranks |
|---|---|---|---|---|
| `V` | 543 | 330 / 0 / 101 | `supplier` | (1, 0) |
| `S` | 137 | 61 / 0 / 20 | `supplier` | (1, 0) |
| `D` | 160 | 0 / 0 / 72 | `carrier` | (0, 0) |
| `X` | 111 | 0 / 70 / 7 | `buyer` | (0, 1) |
| `C` | 30 | 0 / 16 / 0 | `buyer` | (0, 1) |
| `A` | 262 | 173 / 176 / 175 | `broker` | (1, 1) |
| `P` | 47 | 29 / 28 / 24 | `broker` | (1, 1) |

`A` and `P` trade on both sides, which single-valued `company_role` cannot
express; the multi-role truth is carried by native `supplier_rank` /
`customer_rank`, which is this repository's designated mechanism.

| Source column | Target | Disposition |
|---|---|---|
| `CpID` | `ir.model.data` | identity |
| `CompanyNm` | `name` | mapped |
| `Role` | `company_role`, `supplier_rank`, `customer_rank` | mapped |
| `ActiveStatus` | `active`, `entity_status` | mapped |
| `OurCustNo` | `ref` | mapped |
| `APEMail` | `email` | mapped |
| `WebSite` | `website` | mapped |
| `CreditLimit` | `credit_limit` | mapped when the field exists |
| `TermsCode` | `property_supplier_payment_term_id` | looked up by name; never created |
| `IndustryNm` | `industry_id` | looked up by name; never created |
| `MasterAccountID` | — | **drop: 0 of 1290 populated.** No hierarchy exists to import |
| `CustSvcRep` | — | **drop: 1289 of 1290 NULL** (single value `IB`). Not Salesperson |
| `PaymentDays` | — | **drop: 1279 zero, 11 NULL** — no signal |
| `OnHold` | — | **drop: 1287 blank, 2 NULL, 1 `N`** — no signal |
| `CurrCode` | — | **drop: 1289 USD, 1 EUR.** Single-currency payload |
| `Terms` | — | drop: free-text twin of `TermsCode`, which is mapped |
| `CpLastEdit` | — | drop: source audit metadata; Odoo keeps its own `write_date` |

---

## 4. Address → `res.partner` (child)

Parent resolution is by `CpID` **only** — never by company name.

| Source column | Target | Disposition |
|---|---|---|
| `AddressID` | `ir.model.data` | identity |
| `CpID` | `parent_id` | mapped (source key only) |
| `Type` | child `name` and `type` | site label or street. Pickup, warehouse, and delivery labels are `type='delivery'` |
| `InvoiceAddr`, `RemitToAddress`, `isBillingAddressOnly` | company address, or `type='invoice'` | the company's own remit is written on the counterparty. A second billing street is an Invoice child |
| `Addr1` | — on a child | the company name. Odoo already prefixes the company, so the child is not named with it |
| `Addr2` | `street` | mapped |
| `Addr3` | `street2` | mapped |
| `City`, `Region`, `PostalCd`, `Country` | `city`, `state_id`, `zip`, `country_id` | mapped; country/state looked up, never created |
| `Telephone`, `MobilePhone` | `phone` | mapped |
| `Email`, `BillingEmail` | `email` | mapped |
| `Fax` | — | drop: Odoo 19 `res.partner` has no fax field |

`Address.Type` is free text — the payload uses city names such as `OMAHA, NE`
as labels — so the billing flags carry signal the label does not: **289**
addresses are `InvoiceAddr='Y'` with no invoice-like `Type`, and **88** more
carry `RemitToAddress=1`. Resolved population: 1580 invoice (1212 by label +
368 by flag), 1216 other, 110 delivery, 44 primary. Pickup, warehouse, and
delivery labels that are not an exact Type token are included in delivery.

The company's own remit is written onto that counterparty: street, city, state,
zip, country, phone, and email. An address with the same company name updates
that partner and does not create another company. A further site is a child
address, not a company, and it does not receive the remit. The person is a
Contact under the company, so Odoo copies that address onto the person. The
import does not write a street onto the person. When Country is blank and
Region is a US state code, country is United States. `facility_role` and
`partner_type_id` are left unset. Salesperson (`user_id`) is left unset: the
rep is not in the `bulk/` grids, and the superseded corporate CSV sheet is not
an import source.

A Primary contact's email and phone fill the company when those company fields
are still empty. The person remains a child contact. The company is the
commercial partner.

---

## 5. Contact and ContactRoleAssignment → `res.partner` + tags

| Source column | Target | Disposition |
|---|---|---|
| `CT_ID` | `ir.model.data` | identity |
| `CpID` | `parent_id` | the company. A person is not parented to a site |
| `Location` | — | the site join stays in the source. The person stays under the company |
| `ContactNm` | `name` | one person per counterparty and normalized name |
| `Email` | `email` | mapped |
| `PhoneBusiness` | `phone` | mapped |
| `PhoneMobile` | `mobile` if the installed registry has it, else `comment` | mapped — Odoo 19 base has no `res.partner.mobile` |
| `PhoneOther` | `comment` | mapped — Odoo has no third phone field |
| `IsActive` | `active` | mapped (`Y`/`N`, never compared to int) |
| `Notes` | `comment` | mapped |
| `RoleNm` | `category_id`, `function` | mapped |
| `CompanyNm` | — | drop: duplicate of the parent company's name |

**One person per counterparty and name.** The same name, ignoring case and
punctuation, is one `res.partner`. Different names stay two people. Every
`CT_ID` external id points at that one person. Role tags are added. `function`
holds Primary when that role is present, otherwise the first role.

**Contact roles use the existing partner-tag mechanism.** 14 distinct role
names, 510 contacts holding more than one. `res.partner.category` is this
repository's multi-valued partner classification, so roles become tags under a
`ERP Contact Role` parent, and the primary role also fills `function`. No
roles subsystem is introduced. `CRA_ID` needs no standalone record because tag
membership is set semantics — replaying an assignment is inherently
idempotent, which is exactly the replay-safety `CRA_ID` requires.

---

## 6. WKSDetail → `plasticos.transaction.line`

| Source column | Target | Disposition |
|---|---|---|
| `DetailID` | `ir.model.data` | identity |
| `BuySellNo` | `transaction_id` | mapped |
| `GradeID` | `grade_id` | mapped |
| `InvoiceDesc` | `description` | mapped |
| `SWeight`, `PWeight` | `sale_weight`, `purchase_weight` | mapped |
| `SWeightUOM`, `PWeightUOM` | `weight_uom` (shared) | mapped — see below |
| `SPrice`, `PPrice` | `sale_price`, `purchase_price` | mapped |
| `SAmount`, `PAmount` | `sale_amount`, `purchase_amount` | mapped |
| `Color` | `color` | mapped |
| `SPo`, `PPo` | `sale_po`, `purchase_po` | mapped |
| `LotNo` | `lot_no` | mapped |
| `UnitType` | `unit_type` | mapped (legacy `9` → `O`) |
| `Units` | `units` | mapped |
| `Comment` | `specifications` | mapped |
| `DesignatedCpID` | — | **drop: rejected as a party** (§2); 22 of 8257, matches neither side |
| `IsReceived`, `IsItemReceived` | — | **drop: NULL in 11303 of 11303 rows** |
| `SCurrencyCd`, `PCurrencyCd` | — | **drop: USD in 11303 of 11303 rows** |
| `SFxAmount`, `PFxAmount` | — | **drop: identical to `SAmount`/`PAmount` in 11303 of 11303 rows** — zero added information |
| `SPriceUOM`, `PUOM` | — | drop: price-basis UOM, distinct from weight UOM; no field on the line model and no business requirement identified |

`ContainerNo` and `SealNo` have model fields (`container_no`, `seal_no`) but no
column in this export, so nothing is written to them.

### Shared weight UOM

The shared `weight_uom` field is accepted as the intended model. Resolution:
both sides agree → that code; one side populated → the populated code; both
populated and different → **flagged as a source-data anomaly, never resolved**.

Measured on 11303 lines: **161** genuine sale/purchase disagreements and **2**
lines where both sides agree on a code outside the model's `L`/`S`/`E`
selection. 163 total, all reported. None is silently defaulted to `L` — which
is precisely what the retired service did.

---

## 7. Unresolved references

725 source rows cannot participate, all reported, none orphan-created:

| Kind | Count | Cause |
|---|---|---|
| `unresolved_counterparty` | 698 | child of a counterparty the export never carried |
| `missing_parent_key` | 19 | blank parent key on the source row |
| `unresolved_contact` | 8 | role assignment for a contact not in the export |

The export intentionally carries only active counterparties (a locked business
decision), so these are the expected consequence of that scope, not a defect.
Roughly 65 transaction parties fall in the same category and are nulled with a
named reason rather than linked to an invented partner.

---

## 8. Evidenced new-field candidate

**One** field is proposed, and it is not created by this change.

`plasticos.transaction` has **no trade/transaction date field**. Verified across
the base model and every module that inherits it (`plasticos_logistics`,
`plasticos_claims`, `plasticos_documents`, `plasticos_commission`,
`plasticos_transaction`): the only date fields are
`expected_pickup_date`, `actual_pickup_date`, `expected_delivery_date`,
`actual_delivery_date` — all Datetime, none meaning "when the trade was
booked". Writing the trade date into a delivery field would be worse than
dropping it.

| Test | Result |
|---|---|
| Business concept required? | Yes — 7267 transactions carry an authoritative `GPLedger.TradeDt`, spanning 2019-01-05 to 2026-08-07 |
| Current field represents it? | No |
| Current relation represents it? | No |
| Standard Odoo field represents it? | No |
| Dropping it acceptable? | No — a historical trade with no date cannot be reported on |

The importer already reconstructs and reports the date, and writes it **only if
`transaction_date` exists** on the model. Adding that field is a separate,
approved change; until then no data path is invented, and adding it later
requires no importer change — a re-run backfills it.

---

## 9. Relationship to the retired CSV path

`plasticos_transaction/models/transaction_import_service.py` remains in the
tree; this pipeline does not call it, import it, or depend on it, which a test
asserts. For the record, what it did differently:

| Behaviour | Retired service | This pipeline |
|---|---|---|
| Source | one root `ERP.WksDetail.csv` sample | the full tracked export (10 tables) |
| Parties | none — no `supplier_id`, no `buyer_id` | reconstructed from proven joins |
| Date | none | `min(GPLedger.TradeDt)` |
| State | hardcoded `closed` for every row | derived from settlement evidence |
| Partners / contacts / roles | not imported | imported deterministically |
| Atomicity | `cr.commit()` every 100 records | one savepoint per `BuySellNo` |
| Unknown UOM | silently defaulted to `L` | flagged as an anomaly |
| Unparsable number | silently `0.0` | flagged as an anomaly |
| Re-run | skipped existing, never updated | deterministic upsert |

Removing it is a separate cleanup; it is simply irrelevant to this import.

---

## 10. Acceptance status

Closed by this change, each with a test:

- [x] authoritative payload parsed directly, no manual preprocessing
- [x] no dependency on the retired CSV architecture
- [x] `CpID` / `AddressID` / `CT_ID` / `CRA_ID` / `BuySellNo` / `DetailID` deterministic
- [x] facilities attached by `CpID`, contacts by `CpID`/`Location`, roles by `CT_ID`
- [x] all contact roles handled, multiple roles per contact preserved
- [x] supplier and buyer source relationships proven from data
- [x] transaction date and historical state proven
- [x] all material line fields mapped or dropped with measured evidence
- [x] shared weight UOM validated; mismatches flagged
- [x] existing Odoo fields maximized; **no field added to any model**
- [x] one `BuySellNo` is atomic; no partial transaction, no stale marker
- [x] upsert-only writes, so a re-run creates no duplicate identity

Requires a database, and therefore an operator run — this container has no Odoo
instance:

- [ ] first full import against a clean test database (plan step 16)
- [ ] identical second import proving zero duplicates (plan step 17)
- [ ] forced mid-transaction failure and retry against a live database (step 15)
- [ ] operator decision on the `transaction_date` field (§8)

Run it with:

```python
from plasticos_partner_import.scripts.run_erp_import import run
run(env, dry_run=True)   # resolve and map, persist nothing
run(env)                 # full import
run(env)                 # again — must report created=0 across the board
```
