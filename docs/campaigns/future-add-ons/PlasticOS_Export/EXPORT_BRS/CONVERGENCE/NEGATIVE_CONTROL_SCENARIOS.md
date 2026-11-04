# Architecture discriminators: negative-control and integrated proof plan

**All results: NOT_RUN.** These are future proofs, not assertions of implemented behavior.

1. **30/4/4:** One real customer SO for 30 load-equivalents, one supplier PO for 4, four distinct physical shipment transactions, four loads/bookings over four weeks. Week 1 actual movement does not mark three future loads received/delivered or change the remaining SO/PO quantities incorrectly.
2. **Mixed booking:** One ocean booking with five different ISO container numbers, four legitimate supplier POs, independent quantities, scales, seals, and documents. The query returns all five, without choosing the first arbitrary transaction from the SO/booking.
3. **Buyer unassigned:** Real PO or owned cargo supports company-scoped load with no SO or buyer; arbitrary company/no approved source cannot. Later buyer allocation retains original movement and source evidence.
4. **Supplier delivered:** PO 64014 is supplier delivered FAS port; no Linda drayage award, work order, trucking cost or carrier ACK is fabricated. An independently carrier-managed drayage case requires its actual carrier commitments.
5. **Booking revisions:** Same booking number with 3->4->5x40HC and divergent ERD/cutoff/ETD; preserve all source originals, select authorized effective revision, invalidate only pending affected Logistics commitments, and never auto-reissue the unchanged PO.
6. **Ambiguous AI:** Two open transactions share supplier/PO/booking but differ in container. Inbound attachment lacks container ID; match remains unresolved. No latest-partner or first-sale fallback, no direct `state` write.
7. **One original/multiple obligations:** One native original supports two typed obligations independently; one verified, one unverified. Native bridge cannot create a second conflicting verified truth.
8. **Commercial price conflict:** Supplier ticket 1728952 reports $0.03/lb while PO 64014 reports $0.04/lb. No automatic PO modification, accounting posting or invoice recalculation.
9. **Separate milestones:** Supplier 'booking complete' email does not prove gate-in; terminal gate-in does not prove vessel sailing/foreign receipt; a completed load cannot close the whole multi-load order.
10. **One send authority:** Supplier gets issued PO, later authorized booking; carrier gets Work Order only if company-managed. A queued/unknown SMTP outcome does not lead to duplicate send. Domestic three-PDF carrier packet remains applicable to domestic loads.
11. **No false stock:** Supplier delivery to port or resale afloat uses native routes/actual ownership without pretending stock was received into a company warehouse or duplicating quantities.
12. **Company security:** Two companies share booking-like numbers and partner identities; no cross-company document, rate, order or container link or supplier-to-buyer leakage.
13. **Cyclic dependencies:** `plasticos_export` can install alongside Enterprise Documents and Logistics under an acyclic module graph. Native Documents owner does not import Export to compute generic verification. Provider integrations remain optional Phase 2.
14. **Multi-origin stress:** If one actual container requires two distinct trucking pickups and final port drayage, preserve separate real Logistics moves and one final export shipment; if this loses order/weight/identity truth, STOP and raise a new cardinality decision rather than forging a one-to-one.
