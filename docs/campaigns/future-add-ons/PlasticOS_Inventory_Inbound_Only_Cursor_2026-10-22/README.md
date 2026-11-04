# PlasticOS: Inventory-bound worksheet import, one concern only

Target: https://github.com/cryptoxdog/IB-Odoo_19
Observed origin/Staging: e78af874604890f8adb6b049694f93c48311eab4
Overnight evidence checkout (local-only; verify): 607a64b897cb73b19adeea1b867990c5bf556189
Date: 2026-10-22

## Locked objective

Repair only historical worksheets where `BuySell.CustID` is exactly `(INV)` and the second Sold To field identifies the destination inventory warehouse. These are inventory inbound movements, not sales to an absent customer.

Preserve the valid vendor-side purchase document and the warehouse's source identity. Do not fabricate a customer, a customer sale, a sales invoice, or a sale-linked commercial transaction. Verify the exact source field that selects the warehouse before changing the importer. Reuse native existing stock/location capabilities where evidence proves their meaning; do not create today's stock/valuation from historical source activity without a documented safe reconciliation.

## Package contents

- `CURSOR_EXECUTION_CONTRACT.md`: executable, bounded local implementation delegation, acceptance and stop conditions.
- `READ_ONLY_SOURCE_PROBE.sql`: exact source probes for the representative worksheet and warehouse relationship; SELECT only.
- `EVIDENCE_AND_FINDINGS.md`: evidence census and pinned code observations.
- `ACCEPTANCE_MATRIX.md`: positive, negative and replay conditions.
- `RECEIPT_TEMPLATE.json`: short, explicit local evidence receipt.

## No scope creep

No invoice, vendor bill, accounting-status, due-date, payment-term, sales-rep, CRM, outbound-inventory, broad transaction import, or production work. No GitHub push, PR, merge, or deploy in this delegation. One selective Enterprise Docker verification, not a full import or replay campaign.

The exact warehouse selector column on the worksheet has NOT yet been verified. The source Address row is evidence of the destination vocabulary, not proof of the selector's database key. The source probe is a prerequisite for a reliable implementation.
