# Owner map: export must never become a shadow subsystem

| Business fact / action | Writer / owner | Export's permitted role | Explicit non-ownership |
|---|---|---|---|
| Original booking PDF, gate receipt, marine B/L, versions | Native Odoo Documents / approved attachment fallback | Typed read-only links and useful UI | No second file store, no external sharing portal |
| Evidence type, exact record mapping, verification and override | `plasticos_documents` and authorized actor | Declare export applicability and read operation-scoped verdict | No duplicate verification field/action or rule evaluator |
| Export booking number, steamship line, POL, POD, ERD, cargo cutoff, amendments | Suitable existing owner if present, otherwise a narrow `plasticos_export` context | Own only the true missing export facts and source/version context | No unnecessary duplicate order, load or material fields |
| Supplier/buyer contracting, price, formal Incoterms | Native Sale/Purchase with existing PlasticOS transaction links | Show contract and industry-quote terminology separately | No order or price rewrite from shipment status |
| Freight quotes, actual costs, dispatch, physical communication | `plasticos_logistics` / Linda | Reference, project and request existing owner action | No second dispatch state machine or mail sender |
| Mail queue/sent result/replies | Native Odoo Mail via approved Linda owner | Render outgoing artifact; action routed to sender | No SMTP client, blind retry or separate chase cron |
| Physical receipt, reserve, load and ship inventory | Native Odoo Stock, approved scan/dock workflow | Link exact container/packages, derive manifest from actuals | No new quant, lot, movement or weight ledger |
| File due/exception tracking and internal follow-up | `plasticos_documents`, native Request/Activity; Linda external reminders | Show scoped missing evidence, schedule risks | No external reminder owner or independent scheduler |
| Financial posting, AR/AP, reconciliation | Native Odoo Accounting and approved bank/cutover authority | Read actual commercial state | No invoice auto-post, payment, ledger |
| Export booking/packing/SI *report layout* | `plasticos_export` QWeb layout, native report engine | Generate source-derived, audience-safe drafts | No claimed third-party issued B/L or filings |
| AES/customs/waste-import filing and release decision | Authorized filer/regulator, retained verified evidence | Show required/reported decision and proof | No assumed filing or auto-clearance |

**Integration invariant:** One source original may support several exact typed business links. The same linked fact must not acquire a second writer because it appears on an export screen.

## v1.2 precise order/booking/AI extensions

| Concern | Authoritative writer | Export role / forbidden shortcut |
|---|---|---|
| Buyer may be unassigned before sale; late/on-water sale | Native Sale/Purchase, custody/Stock and authorized Logistics | Exact allocation/read; no dummy buyer, no auto SO or order rewrite |
| PO 4 loads; SO 30 loads; partial receipts/delivery | Native Purchase/Sale/Stock | Typed many-side reference, not a second quantity/backorder ledger |
| Four weekly bookings, one per actual shipment | Export booking context, real carrier originals in Documents | Link exact load/booking and revision; not one-to-one PO/booking |
| AI extraction candidate/source | Native Odoo 19 AI Documents / Documents original owner | Consume typed proposal after exact review; no competing OCR, parser or original file storage |
| Verify binding/auto match | PlasticOS Documents and authorized reviewer | Reject most-recent-partner heuristic for export books |
| Authorized state transition | Existing Transaction/Logistics/Stock owner | Propose required evidence only; no direct state writes |
| PO PDF + booking PDF | Native PO/QWeb, export booking QWeb, Linda sender | Distinct PDF artifacts, no repeat commercial PO issuance per booking |
| Carrier work order and appointment | Logistics/Linda | Export provides time/equipment constraints only; no dispatcher clone |

## v1.4 Phase 2 external adapter ownership (additive)

| Outside feed / regulated action | Writer/authority | Allowed Export role | Explicit prohibition |
|---|---|---|---|
| FindTEU ocean milestones | Carrier/provider supplies external observations; Export only links/summarizes | Consume exact container observations, provenance, revisions and ETA | Cannot set native delivery, dispatch, stock, booking issuance or posted finance status |
| EEI filing applicability and filer role | Authorized exporter/USPPI/agent and applicable rules | Gather evidence and show accountable filing case | Cannot guess exemptions, roles, valuation or regulatory classification |
| AESDirect filing | Authorized filer via official portal/WebLink/bulk submission | Prepare validated packet, connect to permitted filing UI and retain official response | No uncertified direct transmission, autopost or fake ITN |
| Official filing acceptance evidence | AES official response held in native Documents and verified by existing compliance owner | Read/expose exact acceptance/ITN/rejection and correction status | No invented accepted/clearance state |
