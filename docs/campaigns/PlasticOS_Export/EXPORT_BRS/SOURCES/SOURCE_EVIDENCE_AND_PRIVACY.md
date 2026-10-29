# Source evidence, protection and epistemic status

**Context:** Operator provided legacy legacy ERP screenshots and booking report on 2026-10-28 for internal requirements only; not redistribution or marketing assets.

| Source | SHA-256 | Observation |
|---|---|---|
| `Screenshot 2026-10-28 at 12.39.46 PM.png` | `5b9fbff45504872c8d36ac95276bab81a84c4e9c3fa48070fa1b254deaa49367` | Booking form with multiple deadlines and shipment tabs |
| `legacy ERP container report.png` | `322efa729218e3993bba7a9b3ea304fd46f3274c95de7800c9a9661625ed5f23` | Five-container mixed-PO reservation and legacy search screen |
| `booking report.xlsx` | `b5e47176e34d89a70210039da8336c76517b8dc9d301a65ba897f0aef7f2a92f` | 372 data rows, 43 headings, 172 booking IDs |

These files are originals from the user and are included as **private design fixtures**, not authoritative current Odoo database snapshots. Names and prices may be commercially sensitive. Tests should use synthetic/approved sanitized fixtures.

The screenshot showing booking 6509024800 has five containers across POs 64014, 64036, 63999 and 63992. The workbook independently corroborates all five container IDs and four PO references.

Do NOT infer carrier confirmation, completed gate-in, customs filing, official BL, invoice posting or actual voyage arrival from a screenshot row.

## What remains unknown

- Exact available native Odoo 19 fields, installed Enterprise modules, configured AI Documents, and test fixtures on current running Staging.
- Whether every legacy workbook column has an exact, currently accessible corresponding production Odoo owner.
- Whether old legacy values contain duplicated, incorrect, overwritten or missing data. They are conformance fixtures only.


## v1.6.0 supplemental private fixture set

- `PRIVATE_OPERATOR_CASE_PO64014/` preserves eleven exact user-provided originals (emails, original booking PDFs, three later same-number booking variants, scale ticket, load spreadsheet, forwarding email screenshot). This directory **MUST NOT be committed to the repository** or published.
- Same-booking version evidence: `SOURCE_CASE_BOOKING_6509024800_REVISIONS.md` and the case-specific original hashes in `PRIVATE_OPERATOR_CASE_PO64014/SOURCE_INVENTORY.json`.
- The historical image previously named as the forbidden legacy vendor plus ` container report.png` is now `legacy_container_report.png`; raw binary SHA-256 remains `322efa729218e3993bba7a9b3ea304fd46f3274c95de7800c9a9661625ed5f23`. This is a neutral source label, not falsification of the original artwork.
- Any future generated CI fixtures must be sanitized, approved and distinct from the originals; source file presence is not live-Odoo evidence.
