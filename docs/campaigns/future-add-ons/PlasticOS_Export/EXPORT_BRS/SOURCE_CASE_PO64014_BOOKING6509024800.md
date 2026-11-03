# Case evidence: PO 64014 / Booking 6509024800 / Load 1

Status: observed supplied evidence, **not a deployed-system test**. Sources have not been published into an ERP. Files furnished by operator on October 28, 2026. Do not include original private correspondence in a redistributed public pack.

## Evidence timeline and exact provenance

| Date / source file | Direct observation | Interpretation boundary |
|---|---|---|
| 2026-09-04 `PurchaseOrder_64014.pdf` and `PurchaseOrder_64014_Email.pdf` | PO 64014 to California Waste Services LLC for **200,000 lb / five containers** MRP Grade A, **$0.04/lb**, delivery terms **FAS Port**, ship via **Supplier Delivered**, destination Long Beach; minimum **36,000 lb / 40'HQ**; pallet tare **40 lb/wooden pallet**, loading-photo sequence and docs mailbox | One commercial PO, multiple loads. Document requirements may differ from booking. PO is not 5 separate orders. |
| 2026-09-30 `BOOKING CONFIRMATION-64014.pdf` and `BOOKING CONFIRMATION-64014-Email.pdf` | Ocean booking **6509024800**, order ref **64014**, line **COSCO SHIPPING LINES**, vessel **CMA CGM JEAN GABRIEL**, voyage **MTE0**, 1 x 40'HQ, cargo cutoff **2026-10-09 16:00** (timezone not proven), ERD **2026-10-05** date-only, empty pickup **PCT Berth 246**, return loaded **APL Terminal Island**, range **36,000-44,000 lb**; POL and POD not explicitly established by supplied named fields | A booking confirmation issued by UCS; do not mislabel as steamship-line-issued original or substitute receiving terminal for POD. |
| 2026-10-06 `Universal BKG 6509024800 - PO 64014.xlsx`, Sheet1 row 3 | Booking 6509024800, container **CSNU8490558**, seal **7695652**, **20 bales**, **40,200 lb**, load **LOAD 1**, PO 64014, ticket **1728952**, loaded date **2026-10-06** | Exact per-load linkage; confirms 1 of PO's 5 only. |
| 2026-10-06 `1728952 LOAD 1.pdf` | Supplier scale ticket 1728952, PO 64014/Load 1, booking and container/seal in comment, gross **72,200 lb**, tare **32,000 lb**, net **40,200 lb**, **$0.03/lb** and **$1,206** | Source weight corroboration but scale ticket unit price differs from PO $0.04/lb. Do not recalculate/overwrite legal AP or confuse truck-scale tare with pallet tare. |
| 2026-10-08 `Email Universal BKG 6509024800 - PO 64014.pdf` | Supplier says BKG 6509024800 'now complete', attached XLSX + scale ticket, references picture link | Supplier completion assertion; not proof of port gate-in, vessel loading, or actual picture completeness. |
| 2026-10-20 `PurchaseOrder_64014_Email.pdf` page 4 | Later message says **2 x 40'HQ**, cutoff **2026-10-30**, ERD **2026-10-26**, asks supplier to confirm terminal window before dispatch; a booking PDF is referenced in email thread | **Ambiguous** whether same ocean booking amendment, extra capacity or replacement: email body does not independently establish current booking number. October 20 attached booking content not independently captured in provided September 30 booking PDF. Must compare exact attached original before supersession. |

## Human coordinator interpretation translated to AI

1. Split emails, quoted thread context, attachments and links into individually sourced evidence.
2. Classify PO / booking / amendment / completion / ticket / spreadsheet / loading-photo link.
3. Extract exact identifiers before resolving target: company, PO, booking, terminal, container, seal, load index, ticket.
4. Cross-check row-3 workbook with ticket (40200 lb net, ticket 1728952) and PO (5 containers). Preserve **price contradiction**.
5. Compare October 20 capacity/deadlines to September 30: raise material version candidate and verify whether **same booking / replacement / extra booking**.
6. Apply only verified, uniquely targeted fields under the owning domain policies; Logistics decides physical movement and window viability, Documents decides evidence verification, Native Orders/Stock own quantities and monetary facts, Linda sends external mail.
7. Require independent terminal acceptance for terminal-delivered and ocean evidence for sailed status; supplier 'booking complete' cannot bypass.

## Source limitations

- Actual photographs behind the supplier link are **not present**, and no current external retrieval or content verification has been performed.
- No actual carrier gate-in, marine B/L, vessel-departure or destination proof supplied.
- An October 20 email shows different schedule/equipment; it does **not** prove the September booking was itself rolled or cancelled. Specific causal reasons of possible rolls are user-provided operational scenarios, not established facts for this sample.
- The user refers to an additional screenshot of booking communication. The precise booking revision must still be matched to its source original; no unverified screenshot-only field is being promoted to authoritative.

## 2026-10-28 follow-up: original forwarder variants now supplied

The private fixture set now includes three PDF versions associated with the same booking number (3 x 40HC, 4 x 40HC, 5 x 40HC) and the October 5 forwarder email screenshot, as well as the earlier 1 x 40HC supplier booking summary. The precise capacity, vessel-date and cutoff comparisons are in `SOURCE_CASE_BOOKING_6509024800_REVISIONS.md`. The October 20 supplier email refers to a further two-unit instruction with October 26/30 terminal dates; **do not assume without its exact attached-source binding that this is the same event as the October 1-forwarder variants**. Independent source originals and field revisions remain necessary.

**Send-order correction:** The source PO was issued September 4 without a confirmed booking, and the booking was sent September 30. Native PO approval/issuance must not depend on prior booking existence. Subsequent booking sends must not reissue or duplicate the PO.
