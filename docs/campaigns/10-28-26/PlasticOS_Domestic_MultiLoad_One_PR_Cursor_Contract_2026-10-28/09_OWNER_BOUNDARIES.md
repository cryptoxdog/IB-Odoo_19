# One authoritative owner per concern

| Capability/fact | Owner | This PR can do | Explicitly forbidden |
| --- | --- | --- | --- |
| Physical domestic load, state, rate, dispatch, actual freight evidence | `plasticos_logistics` | Fix load to transaction FK and affected workflow consumers | New freight product, shipment booking, Export engine, mail writer, state guard bypass |
| Transaction aggregation, SO/PO relationship, amounts | `plasticos_transaction` and native Sale/Purchase | Preserve/update exact link read only when causally needed | Rewrite worksheet identities, accounting values or order authorization |
| Native PO-only inbound and real stock moves | Odoo Purchase/Stock | Prove no regression against genuine PO and `stock.picking` | Invent buyer, SO, PlasticOS load, booking or receipt action |
| Document originals, attachments, versions | Native `documents.document` / `ir.attachment` | Use prior PR's exact file identity for linking tests | Duplicate binary, change original, add secondary Documents store |
| Verified business evidence, operation-scoped compliance | `plasticos_documents` | Repair exact load consumer only, preserve previous PR | Second verifier, recency-based link, document-triggered account posting |
| Claims and per-load source claim attribution | `plasticos_claims` | Optional exact load association and old-record preservation | Default to tx's first load or create new financial recovery |
| Accounting invoice/bill, financial posting, commission | Native Accounting and existing owning PlasticOS modules | Compare immutable before/after snapshots only | Recompute source economics, post invoices, create payments or penalties |
| External supplier/buyer/carrier communications | `plasticos_logistics` Linda via native Mail | Preserve existing approved send guards and timing behavior | New sends, chaser automation or duplicate sender |
| Identity/security and user access | Existing native Odoo/PlasticOS security owners | Require existing access to remain functional and company-safe | ACL policy redesign or unapproved `sudo`/superuser bypass |
| Canonical constitutional invariants and L9 projections | Existing authority owners | Read and obey admitted revisions | Promote draft v3.3.0 or rewrite invariant/ADR to make code pass |

## Bounded ambiguity disposition

1. A physical load may remain **unlinked** until proven and still have its own legal physical record when the actual source flow permits it. A PO-only native Stock receipt is not automatically a PlasticOS load.
2. `sale.order.transaction_id` can be a useful correlation, but historical worksheet compilation can associate multiple transactions with one SO; never use ambiguous shared SO identity to pick a transaction by order.
3. Historical `claim.load_id` derived from `tx.load_id` is not sufficient evidence for a *per-load* claim on transactions with more than one load. Require original source evidence or retain transaction-only attribution.
4. The old `transaction.load_id` can remain as a guarded compatibility API for one-load transactions; it cannot remain a second authoritative writer or pick arbitrary first/last when there are two loads.
5. If existing accepted source contracts contradict the design, return the exact conflict to the semantic owner. Do not reinterpret the owner within the coding PR.
