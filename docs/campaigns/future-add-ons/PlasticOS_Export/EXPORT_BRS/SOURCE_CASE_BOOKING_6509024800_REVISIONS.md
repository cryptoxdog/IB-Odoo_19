# Same-number ocean booking: extracted version candidates and coordinator decisions

**Status:** direct readings of user-supplied files and screenshot on 2026-10-28; not a chronology certification, regulatory statement, source-owner approval or live Odoo test. These sources are private fixtures. They were removed from the repository on 2026-11-12 by operator decision and are held privately; repository history was not rewritten.

| Source | Booking reference | Capacity | Cargo cutoff | ERD / terminal | Sail/ETA | Other |
|---|---|---|---|---|---|---|
| `6509024800-LAS-SEA2-UCS.pdf` | 6509024800 | 3 x 40HC | 2026-10-09 16:00 | 2026-10-03 stated in Special Instructions | 2026-10-16 / 2026-11-09 | POL Los Angeles, POD Port Kelang; vessel CMA CGM JEAN GABRIEL / MTE0 |
| `6509024800-R_1.pdf` | 6509024800 | 4 x 40HC | 2026-10-09 16:00 | 2026-10-03 stated in Special Instructions | 2026-10-16 / 2026-11-09 | Same visible booking and voyage family |
| `6509024800-RR_1.pdf` | 6509024800 | 5 x 40HC | 2026-10-12 16:00 | 2026-10-03 stated in Special Instructions | 2026-10-18 / 2026-11-09 | Master reference present in this PDF; capacity and schedule changed |
| `64014-Email From Sherry With Booking.png` | 6509024800 | Email says increased by 1 to 5 x 40HC | 2026-10-12 | Different terminals cited: FMS/APL ERD 2026-10-03 and TML ERD 2026-10-07 (reported as-of email) | Not established by email alone | Email dated 2026-10-05; empty pickup PCT; return FMS/APL TML |
| Earlier `BOOKING CONFIRMATION-64014.pdf` | 6509024800 | 1 x 40HC | 2026-10-09 16:00 | 2026-10-05 in its own document | No authoritative voyage update from this original alone | Separate supplier-facing booking summary linked to PO 64014 |

**Reading boundary:** The three later PDF artifacts have a booking date of 2026-10-01, but a file suffix alone does not authenticate sender order, actual issuance timestamps, carrier acceptance, or unambiguous scope of every supplier's allocated container. The October 5 email provides a separate attributed update. Do not impose a fabricated globally consistent ERD: the sources reference different terminal contexts and roles. The supplier-facing booking summary from September 30 also differs from the forwarder documents; store each original independently, reconcile the current authorized booking field values and their applicability before release.

**AI Documents positive case:** Extract exact source fields and dates; connect by company + booking number + verified parties/subject + relevant PO/container identities; show a source-backed field-level comparison, a capacity history, terminal-specific ERD, changed cutoff and sailing date, and exceptions for ambiguous revision precedence or terminal applicability. Once an authorized version is accepted, publish only affected booking requirements to Logistics and leave unaffected movements/mail/PO approvals unchanged.

**Negative controls:** No automatic claim that PDF naming alone proves chronological sequence, no merge of competing terminal ERDs, no assumption that a 5-container booking comprises PO 64014's five supplier loads, no shipment-state transition from the email, and no duplicate PO/booking/scale-ticket originals.

**Relevant existing requirements:** `BRS-EXP-02-R001..R005`, `BRS-EXP-09-R002..R008`, `BRS-EXP-10-R001/R004`, `BRS-EXP-11-R003..R006/R011`, `BRS-EXP-13-R002/R003/R005/R008`, `BRS-EXP-14-R002/R003`. These implement candidate `POS-INV-04/06/07/16/21/22/23` without creating a new AI or dispatch engine.
