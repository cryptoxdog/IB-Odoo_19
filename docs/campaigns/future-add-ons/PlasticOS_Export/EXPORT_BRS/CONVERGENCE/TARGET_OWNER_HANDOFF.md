# Target owner decisions and adoption sequence (proposal, no repository edit)

**Do not copy into an Export addon as its own authority.** This page identifies the proper existing BRS owners for acceptance.

| Owner | Minimal required scoped adoption | Source witness | What must NOT happen |
| --- | --- | --- | --- |
| `plasticos_transaction` and `plasticos_logistics` | Preserve one transaction per final physical shipment with unique `transaction.load_id`; use explicit exact association, allow many transactions to share SO/PO, and remove unsafe first-by-SO `load.create` binding | `plasticos_logistics/models/load.py` 258-299; `plasticos_logistics/models/transaction_inherit.py` | New universal transaction-to-load ledger or arbitrary auto-link |
| Logistics identity/security | Explicit stable company for load, checked against real SO/PO/stock owner; buyer optional only under valid procurement/owned-cargo movement; movement-specific dispatch authority | `load.py` 43-45, transaction bridge 54-62 | Invented buyer or company-less drayage |
| Logistics freight/scheduling | Consume Export's current booking equipment/deadlines at verified revision, keep domestic packet unaffected and support supplier-arranged freight | `freight_context.py` equipment_class None; Logistics BRS-03/04/05 | Export rate engine, mandatory drayage on supplier delivered cargo |
| PlasticOS Documents | Retain sole business verification and per-obligation typed association; remove newest-partner auto-match; make Enterprise bridge a read-only/delegating projection | `plasticos_documents/models/document.py` 166-170; `plasticos_documents_native/models/document_native.py` 118-175 | Second verification writer or partner guess |
| Logistics/Linda | Supplier PO issue and later booking send are separate authorized obligations; carrier packet only if applicable; revision and audience-safe send evidence | `plasticos_logistics/models/linda_request.py` current PO/SO purposes; BRS-05 | Export sender, surprise automatic resend |
| Export | Narrow booking identity, current source revision, requirements and native views/QWeb; report cross-booking containers and exact PO/SO quantities | BRS-EXP-01/02/08/10/13/14 | Stock, accounting, documents or freight duplicate |
| Repository constitutional owner | Maintain `INVARIANTS.md` v2.2.0 until explicit authorized v3 admission. `POS-INV-21..23` remain draft design candidates | v2.2.0 source + v3.1 working pack mapping | Claim of repository policy change from private ZIP |

**Recommended adoption sequence:** (1) owner approval of these interpretation/authority decisions, (2) source-specific Logistics/Docs BRS supersession at current revision, (3) exact Enterprise fixture with 30/4/4, booking five/four, buyerless, AI duplicate-match, (4) independent architectural/invariant review, (5) separate coded realization contract if authorized. No production activation, external sends or filings here.
