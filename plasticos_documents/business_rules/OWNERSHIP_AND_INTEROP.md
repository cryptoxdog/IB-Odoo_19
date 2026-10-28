# Documents business-rule ownership and integration boundary

**Rule source:** BRS-POS-02 (native Originals), BRS-POS-03 (verification), BRS-POS-09 (Requests/automation). Their 44 verbatim rules are local. Other BRS-POS IDs remain owned by their respective domains and appear only as references in `ALL_170_RULES_SCOPE.csv`.

| Fact / responsibility | One authoritative owner | Documents consumer obligation | Forbidden duplicate |
|---|---|---|---|
| Original file, internal folder, alias, versions and shortcuts | Odoo Enterprise `documents.document` / its `ir.attachment`, accessed via `plasticos_documents_native` | Retain exact original and provenance for one or many links | Second authoritative PDF/binary for convenience |
| Document type/category, typed transaction/load/PO/picking reference, verified status and override | `plasticos_documents` business policy | Only authorized verification action writes; expose read-only projection in native bridge | Native and legacy model independently verifying |
| Native Documents Request placeholder / internal Activity | Native Documents / Odoo Activities | Track one exact missing obligation; verification closes business obligation, file receipt alone does not | External Documents sharing, duplicate reminder writer |
| External supplier/carrier/buyer request or reminder | `plasticos_logistics` (Linda), via Odoo `mail.mail` / `mail.message` | Supply approved missing/verified/superseded state and SLA evidence | `plasticos_documents` cron, native Request reminder and Linda all emailing |
| Physical pickup/delivery or 3PL stock receipt | Native `stock.picking` and verified movement/load owner | Use truthful actual event time as business clock; PO-only receipt remains PO/picking scoped | `assigned` treated as READY/dispatch, invented load |
| Buyer Receiving net/quantity and supplier settlement weight | Commercial/Accounting business owner and documentary evidence; see BRS-POS-04/-06 | Verify provenance and quantity/load coverage, never auto-write weights from OCR | One ambiguous report clearing all loads or bill weights |
| Carrier CST / certification | Verified business evidence and carrier obligation | Certificate sufficiency distinct from `SCALE` tag; missing CST does not block buyer AR | Carrier penalty booked from missing tag alone |
| Claim, debit/credit, invoice/bill and payment | Native Accounting after authorized operation; QuickBooks settlement until cutover | Read-only eligibility/evidence; no auto-post side effects | `account.move.action_post` in a compute, auto-dunning before QB exit |
| AI classification | Installed Odoo AI only when independently approved | Candidate tag / routing only, human verifier remains authority | OCR/AI changing liability, weights or payments |

## Exact-file association

One original may support multiple explicit typed evidence rows (e.g., two loads) while retaining separate company, reference, revision, party and quantity coverage. No recency/partner-only allocation. For PO-only inbound and 3PL warehouse deliveries, associate the real native PO/picking even when there is no PlasticOS transaction/load; if current schema cannot do so, declare a bounded representation gap under the authorized later coding contract. **Do not invent missing business records or a new field without a proper schema decision.**

## Native Objects

`documents.document` owns files but its native `Linked to` is not proof of all multiple business links; `plasticos.document` owns verified typed evidence on the PlasticOS side. The exact installed Enterprise API and ACLs must be inspected before implementation. Native folder aliases can ingest from external email without external folder grants. Native Documents Request can send reminders, so it must remain **internal-only** and not become a parallel sender.

## Scheduling and business clocks

Supplier doc +1/+5 business days from **actual pickup**; carrier doc +2/+6 from **actual pickup**; buyer Receiving +1/+5 from **actual delivery**. Working calendar Mon–Fri; holiday policy remains OPEN, do not infer. Only Linda sends approved external chasers, with one party/day/obligation identity and quiet-hour compliance. `ir.cron` is the native platform; separate owner-specific jobs may coexist. The planned Linda `_cron_linda_tick` is not a universal scheduler. Automation activation is the final separately approved stage, after the side-effect-free compliance safety seam and native evidence workflow are proven.

## Acceptance boundary

At this installation stage all runtime tests are **NOT_RUN**. The installation makes rule text discoverable to agents; it does not prove Odoo Documents Request, native AI, QWeb, Accounting or stock behavior. Tests must be executed separately against the installed Odoo 19 Enterprise fixture before implementation acceptance.
