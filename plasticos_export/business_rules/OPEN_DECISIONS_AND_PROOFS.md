# Export BRS | open decisions and proofs

These items are still open. They are proof obligations at the owner named, not permission for Export to invent a system. The full reasoning is in the campaign pack: `docs/campaigns/future-add-ons/PlasticOS_Export/EXPORT_BRS/DECISION_FRONTIER.md` and `EXPORT_BRS/INTEROP/SOURCE_BOUND_CHANGE_PLAN_v2.7.5.md` (decisions C01 to C09).

## Owner decisions

| # | Item | Owner | State |
| --- | --- | --- | --- |
| 1 | One business verification writer: `plasticos_documents` and `plasticos_documents_native` both expose `verified`. Correct it at Documents, never in Export (`BRS-POS-03-R004`). | Documents | Open (S3) |
| 2 | Whether Documents requirement rules can express booking + stage + operation applicability, or need a generalized Documents-owner extension. | Documents | Open (S3) |
| 3 | Booking identity: the narrowest missing Export context, many containers per booking, stock packages kept distinct from ocean containers. | Export | Open (S5 models) |
| 4 | FOB pickup and FAS inland-to-port/rail are industry quote terms, not formal ICC Incoterms. Each contract sets responsibilities. | Commercial | Ruling kept |
| 5 | Terminal or rail acceptance needs independent evidence; a QR scan or dock loading does not prove it. | Logistics / Documents | Open |
| 6 | Carrier, terminal and local time zones, source revision, date versus timestamp: data sources and follow-up owner. | Export / Logistics | Open |
| 7 | Enterprise `documents`, `documents_account` and `stock_barcode` installed versions and interfaces. | S1 census | Settled by the S1 receipt; runtime proofs open |
| 8 | Destination-specific filings, VGM and carrier-issued B/L in Phase 2. | Authorized filer / provider | Phase 2 |
| 9 | Which Linda workflow sends ocean booking and forwarder messages. | Logistics / Linda | Open (S4) |
| 10 | Commercial pickup, document eligibility, stock delivery and finance readiness stay independent; none becomes a global close blocker. | All owners | Ruling kept |
| 11 | Cardinality: one transaction or SO to many loads, one supplier PO to many receipts, several bookings. | Logistics / native | Open (S2) |
| 12 | Buyerless movement path that does not require `sale_order_id`, with sale guards and company isolation kept. | Logistics | Open (S2) |
| 13 | Unit of measure and line-level allocation for a 30-load SO and a 4-load PO, with partial receipts. | Native Sales/Purchase/Stock | Open |
| 14 | Installed Odoo 19 AI Documents extraction and server-tool hooks; exact match abstains on ambiguity. | Native Documents / Documents | Open |
| 15 | Which evidence-backed owner transitions are allowed. Never auto-promote booking received to delivered, invoiced or closed. | State owners | Open |
| 16 | Supplier PO copy policy: weekly booking notices do not reissue the PO; a controlled reference copy may be allowed. | Purchase / Linda | Open |
| 17 | In-transit resale: custody, title, insurance, exporter of record and B/L instructions change only through an authorized process. | Commercial / Phase 2 | Phase 2 |

## Proofs not run

- Every one of the 120 acceptance cases in `ACCEPTANCE.json` is `NOT_RUN`.
- The smallest Phase 1 walkthrough (an FAS shipment linked to its order and Linda load, a corrected cutoff notice, a verified gate receipt, one party-safe Linda send) is `NOT_RUN`.
- The discriminating cardinality proof (a 30-load SO, a 4-load PO, two weekly bookings, a buyerless load sold on the water) is `NOT_RUN`.
- Phase 2 providers (FindTEU, ACE AESDirect) are not connected and not in this campaign.

## Scaffold limit (S5A)

At S5A the addon is installable and empty: no model, view, report, mail rule or data record. Installing it proves the dependency graph and the roster entry only. It is not acceptance of any rule above.
