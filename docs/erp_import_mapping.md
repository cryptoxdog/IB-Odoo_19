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
| `WKSDetail.BuySellNo` | 8257 | not written; later `sale.order` and `purchase.order` | none |
| `WKSDetail.DetailID` | 11303 | not written; later sale and purchase lines | none |

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
| PO issue / transaction approval date | `min(GPLedger.TradeDt)` | 7267 / 8257 |
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

### Historical state — forensic reconstruction, not the live importer state authority

The table below is an archived diagnostic reconstruction only. As specified
by proposed ADR-022, every historical transaction the importer creates
starts Closed, whatever the raw worksheet status. Excluded rows are not
created. Original worksheet status is retained as provenance. A Manager may
reopen one Closed historical transaction with a reason. Neither forensic
settlement evidence nor an outstanding invoice may activate a historical trade.
Opening unpaid accounting items require a separately reconciled cutoff.

The source has no status column, so state is derived from settlement evidence:

| State | Condition | Count |
|---|---|---|
| `closed` | booked in GPLedger + posted material payable + receipt | 5451 |
| `invoiced` | booked in GPLedger, not settled both sides | 1816 |
| `delivered` | delivery leg exists, never booked | 104 |
| `draft` | lines only | 886 |

This historic derived-state model is not an active import lifecycle contract.

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
| `CustSvcRep` | — | **drop: 1289 of 1290 NULL** (single value `IB`). Not Salesperson; Salesperson comes from `SalesReps.csv` (§3a) |
| `PaymentDays` | — | **drop: 1279 zero, 11 NULL** — no signal |
| `OnHold` | — | **drop: 1287 blank, 2 NULL, 1 `N`** — no signal |
| `CurrCode` | — | **drop: 1289 USD, 1 EUR.** Single-currency payload |
| `Terms` | — | drop: free-text twin of `TermsCode`, which is mapped |
| `CpLastEdit` | — | drop: source audit metadata; Odoo keeps its own `write_date` |

---

## 3a. SalesReps → Salesperson (`res.partner.user_id`)

Salesperson is Odoo's own `res.partner.user_id` field (a `res.users` link). No
new field is added for it. The source is the ERP table `dbo.Counterparty_Referrer`
(977 rows in `erp_extracted_data/meta/census_payment_rank.txt`), projected by
`erp_extracted_data/19_salesreps.sql`; the frozen grid of it is `bulk/SalesReps.csv`.
One row per counterparty and rep, keyed by the same `CpID` as `CounterParty`.

| Source column | Target | Disposition |
|---|---|---|
| `CpID` | company `res.partner` | join on the counterparty source key only |
| `ReferrerNo` | `user_id` | rep initials, padded with trailing spaces; strip, then map through the table below |
| `IsDefault` | — | `1` marks the row that is the Salesperson |
| `Rate`, `Charge`, `ChgPer` | — | drop for the partner import: commission terms, not partner data. `Charge` is 0 on every row |

Rep initials:

| `ReferrerNo` | Salesperson | Rows |
|---|---|---|
| `IB` | Igor Beylin | 292 |
| `AA` | Arthur Akopyan | 169 |
| `RP` | Ricardo Pereira | 165 |
| `AB` | Arthur Buyanovskiy | 111 |
| `TF` | Tiffany White | 94 |
| `MM` | Mack McMurray | 85 |
| `LR` | Lindsey Malyavko | 60 |
| `DAVE` | David McLawhorn | 1 |

`MM` also carries the accounts reassigned from former reps. The frozen
`SalesReps.csv` already reads `MM` on every former `JB`, `YK`, `WC`, `RF`, `GS`,
`AK`, and `IG` row (67 rows in total, 9 of them `AB` rows whose `CpID` is missing
from `CounterParty.csv`). The restored database may still carry the former
initials, so the reassignment is a mapping rule (`mapping.SALES_REP_REASSIGNED`),
never an edit of the source: a live `JB` row maps to Mack McMurray.

Coverage: 977 rows on 975 `CpID`s. 833 of those `CpID`s are in
`CounterParty.csv`, and 738 of the 1290 counterparties have an `IsDefault=1` row.
The 142 `CpID`s missing from `CounterParty.csv` still have `Address.csv` rows
(and 136 have contacts). Those companies are missing from the extract, so
they cannot import yet.

Rules:

- A rep is matched to an existing `res.users` record by the name in the table
  above. The import never creates users. A name with no matching user leaves
  `user_id` untouched and is reported, one entry per source row.
- A company whose rows carry no `IsDefault=1` row has no Salesperson: a
  `user_id` left over from an earlier run is cleared on replay.
- Every `Counterparty_Referrer` row receives one outcome in the summary: the
  default row carries the write outcome, the company's other rows are
  `unchanged`, and rows of a company with two defaults or unknown initials are
  `rejected`.
- Igor Beylin and Arthur Buyanovskiy are seeded in
  `plasticos_base/data/admin_users.xml`. Lindsey Malyavko, Ricardo Pereira,
  Arthur Akopyan, Tiffany White, and Mack McMurray (login
  `sales2@scrapmanagement.com`) are seeded in `plasticos_base/data/sales_reps.xml`.
  David McLawhorn is not seeded. He must already exist in the database.
- 103 `CpID`s have only `IsDefault=0` rows. They get no Salesperson. 95 of them
  are in `CounterParty.csv`, and none is a carrier (`D`). By role: 46 `V`, 24 `A`,
  16 `S`, 4 `P`, 4 `X`, 1 `C`.

The `salesreps` stage runs after `roles` in every applied run (full,
`PARTNERS_ONLY=1`, or `make import-erp LAYER=salesreps`). A `CpID` with more than one `IsDefault=1`
row, or with initials missing from the table, is reported and left without a
Salesperson. `Rate`, `Charge`, and `ChgPer` are commission terms and are not
imported.

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
| `Email`, `BillingEmail` | `email` | mapped; the brokerage's own staff mailboxes (`mapping.INTERNAL_MAILBOX_DOMAINS`) are dropped by the mapping, the source row is not edited |
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
`partner_type_id` are left unset. Salesperson (`user_id`) comes from
`SalesReps.csv` (§3a), not from an address row. The superseded corporate CSV
sheet is not an import source.

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

**One real human, one partner (C1, 2026-11-17).** The ERP stores the same person
again under a first name, a role word, or the mailbox prefix. Those rows fold into
the person; role mailboxes stay; sales-rep mailboxes never reach Odoo.

- **R1 weak name.** A `ContactNm` is weak when it is blank, a single word, a role
  word (a key of `mapping.CONTACT_ROLE_TAGS`, any case: `BILLING`, `COLLECTIONS`),
  or an e-mail prefix (one word equal to the local part of one of the row's own
  external addresses, such as `todd.antonick`). Any other title of two or more
  words is a full name. A multi-person title such as `A B & C D` is one full-name
  person and is never split. `mapping.weak_name_kind`.
- **R2 fold.** A weak row folds into the full-name person of the same counterparty
  when its phone digits (`PhoneBusiness` or `PhoneMobile`; digits only, eleven
  digits starting with `1` drop the `1`) or one of its external addresses
  (case-folded) match exactly one full-name person. A plain first name (not a role
  word, not an e-mail prefix) is only checked against persons whose first word is
  that name. A folded row's `CT_ID` aliases the person, its channels join the
  person's, its `Location` becomes one of the person's sites, and its roles land
  on the person through the roles stage. The person's name and anchor `CT_ID`
  (the lowest `CT_ID` of the full-name rows) never come from a folded row.
- **R3 never.** Two different full names never merge, even on a shared phone or
  mailbox. Zero or several candidates report `alias ambiguous`; phone to one person
  and address to another reports `alias conflict`. Neither folds. A non-blank weak
  name that does not fold is its own person, as before; an e-mail prefix written in
  lower case is title-cased (`todd.antonick` → `Todd Antonick`), and a title
  typed with capitals (`AP`) keeps its spelling. A blank name that does not fold is
  rejected; a blank name that folds is not.
- **Tie-breaks before "ambiguous" (probe 3, 2026-11-17).** (a) a plain first name
  only counts persons whose first word is that name; (b) an e-mail prefix with
  several candidates folds into the one whose name produces the local part
  (`first.last`, `firstlast`, `flast`, `firstl`, `first`, `last`; case-folded,
  alphanumeric only); (c) a role word whose own address has a generic local part
  (`ap`, `ar`, `accounting`, `accounts`, `invoices`, `invoice`, `billing`,
  `payables`, `receivables`, `office`, `orders`, `customerservice`, `info`,
  `sales`, `purchasing`, `shipping`, `receiving`) never becomes or joins a person:
  its phone and e-mail go to the one site of the company they match, else to the
  company, and its role tags stay with the person who already holds them (nothing
  is added); (d) phone to one person and e-mail to another does not fold. What
  remains is listed under NEEDS REVIEW.
- **R2b — one matching site.** A weak row that matches no person but exactly one
  site of the same company by phone or e-mail: a blank, role-word or e-mail-prefix
  row creates no person and puts its phone and e-mail on that site (filling empty
  fields, as for a site mailbox); a plain first name stays a person and gets that
  site among its sites. Several matching sites: as before, listed under NEEDS
  REVIEW.
- **Phone match key.** Two numbers match when their digits match, or, when the
  `phonenumbers` library is installed (it ships with Odoo), when their E.164 forms
  (with `x<extension>`) match. The region is the partner's country, else its
  company's, else `US`, so `+44 20 …` and `020 …` of a UK company match. The same
  keys decide whether a phone line is already present.
- **NEEDS REVIEW.** Every ERP import ends with an always-present review block, ids
  only, every entry in full: contact rows left ambiguous (CT_ID, kind, reason,
  candidate CT_IDs and partner ids), rows matching several sites, phones the parser
  could not read (partner id, digit-masked shape), and people the retire rule kept
  visible. Its last line, `NEEDS REVIEW: <n>`, is the last line of
  `make import-erp`. These are diagnostics: the balance equation is unchanged.
- **Replay.** A partner an earlier run created for a now-folded `CT_ID` has that
  marker re-pointed to the person. It is archived, never deleted, once no other
  `legacy_erp_contact_%` marker still points at it. Before that, what names it moves
  to the person: `crm.lead.partner_id`, `plasticos.material.profile.partner_id`,
  `plasticos.facility.profile.partner_id` (each only when that model is installed),
  and its linked sites (`location_partner_ids`). A profile the person already holds
  (one facility profile per partner; one material profile per polymer, form and
  grade) is not moved, and the old partner then stays visible. Moves and refusals
  are reported as `fold re-pointed …` / `fold kept … visible` anomalies.
- **Retire without a survivor.** A person archived because its rows are now
  inactive, or because its title turned out to be a number or a site mailbox, has no
  person to receive its records. Before it is archived, `crm.lead.partner_id` moves
  to its company; material and facility profiles move to its single linked site, or,
  with no linked site, to its company when that company has no site. With several
  linked sites, or company sites and no link, or a profile the target already holds,
  the person stays visible and the report says `retire kept … visible`. A profile
  never ends on a person (ADR in #530).
- **Sites are added, never removed.** A person's `location_partner_ids` gains the
  sites its rows name; a site linked by hand, or carried over from a folded card,
  stays on replay.

**E-mail cells.** Every importer e-mail write (counterparty `APEMail`, address
`Email` / `BillingEmail`, contact `Email`, site mailbox, company fill) goes through
one cleaner, `mapping.email_cell`:

1. drop the brokerage's own mailboxes (`mapping.INTERNAL_MAILBOX_DOMAINS`) — an
   import rule only, the source row is not edited;
2. split on `;` or `,`, trim, drop empty entries and entries not shaped
   `local@domain.tld`, lower-case, de-duplicate keeping the first occurrence;
3. join with `, `.

A person's own first address stays first. A cell left with no address writes no
e-mail. Fold matching uses the same cleaned addresses, so an internal mailbox is
never a match.

**Contact roles use the existing partner-tag mechanism.** 14 distinct role
names, 510 contacts holding more than one. `res.partner.category` is this
repository's multi-valued partner classification, so roles become tags under a
`ERP Contact Role` parent, and the primary role also fills `function`. No
roles subsystem is introduced. `CRA_ID` needs no standalone record because tag
membership is set semantics — replaying an assignment is inherently
idempotent, which is exactly the replay-safety `CRA_ID` requires.

---

## 6. WKSDetail — not written to `plasticos.transaction.line`

This table is retired as an import target. The import does not create one `plasticos.transaction` per worksheet or one `plasticos.transaction.line` per detail.

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

## 8. Native date authority: `GPLedger.TradeDt` → purchase order approval

The business meaning is now resolved. Under current PlasticOS rules,
`GPLedger.TradeDt` is the date the purchase order was issued and the transaction
was approved.

Odoo 19 already has native purchase-order date semantics:

- `purchase.order.date_approve` — **Confirmation Date**; this is the target for
  the historical PO issue/approval event.
- `purchase.order.date_order` — RFQ / order deadline; this is not the chosen
  target for `TradeDt`.

`plasticos.transaction` already relates to native purchase orders through
`purchase_order_ids`, so the date belongs on the historical PO rather than on a
new transaction field.

**Locked mapping rule:**

```text
GPLedger.TradeDt
        ↓
PO issued / transaction approved
        ↓
purchase.order.date_approve
```

No `plasticos.transaction.transaction_date` field is authorized. Do not copy
`TradeDt` into pickup/delivery dates or another semantically unrelated field.

The import does not create `plasticos.transaction` or `plasticos.transaction.line`
records. Until the historical purchase order is realized, the reconstructed
`TradeDt` remains source evidence. It is not written onto a transaction field.

---

## 9. Relationship to the retired CSV path

`plasticos_transaction/models/transaction_import_service.py` remains in the
tree; this pipeline does not call it, import it, or depend on it, which a test
asserts. For the record, what it did differently:

| Behaviour | Retired service | This pipeline |
|---|---|---|
| Source | one root `ERP.WksDetail.csv` sample | the full tracked export (10 tables) |
| Parties | none — no `supplier_id`, no `buyer_id` | reconstructed from proven joins |
| PO approval date | none | reconstructed from `min(GPLedger.TradeDt)`; persists to native `purchase.order.date_approve` when historical PO realization exists |
| State | formerly hardcoded `closed` | created historical trades start Closed; raw status is provenance; settlement is independently reconciled at cutoff |
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
- [x] operator decision on date ownership: `GPLedger.TradeDt` → native `purchase.order.date_approve`; no custom transaction date (§8)
- [ ] historical PO realization that persists the resolved approval date without creating a source-mirroring transaction field

Run it with:

```python
from plasticos_partner_import.scripts.run_erp_import import run
run(env, dry_run=True)   # resolve and map, persist nothing
run(env)                 # full import
run(env)                 # again — must report created=0 across the board
```
