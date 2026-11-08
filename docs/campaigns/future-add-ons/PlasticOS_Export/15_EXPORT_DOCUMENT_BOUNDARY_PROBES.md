# Document/Export boundary acceptance scenarios

**All scenario executions: NOT_RUN.** These are precise checks for a future separately authorized implementation. Negative tests must fail closed without mutating business facts.

| ID | Positive expectation | Negative control / prohibited result |
| --- | --- | --- |
| EX-DOC-01 | One original booking PDF is received via authorized native alias, linked to exact company/booking and shown on export view | Export saves a second authoritative copy or creates a parallel file repository |
| EX-DOC-02 | One same original terminal receipt can support two independently verified typed associations where justified | One file upload instantly verifies every load using the same booking/customer |
| EX-DOC-03 | Authorized Documents business verification writes once; native view projects that same verdict | Clicking native `action_verify` independently changes its own `verified` without authoritative `plasticos_documents` verification |
| EX-DOC-04 | `plasticos_export` declares that this FAS booking needs a current terminal receipt and reads operation-scoped compliance | Export implements second `verified` or `all_docs_complete` field whose verdict disagrees with Documents |
| EX-DOC-05 | Carrier/forwarder cutoff revision retains original email, replaced source and true active date/time zone | New booking email from wrong party overwrites Cut Off/ERD or corrupts earlier evidence |
| EX-DOC-06 | User generates a booking/packing report whose values are native source-derived and audience-safe | Export writes a new physical weight, pretends cargo was accepted, or leaks buyer/supplier economics |
| EX-DOC-07 | Linda sends one currently approved export report using Odoo Mail; receipt/sent status is unambiguous | Export separately sends a second PDF/email or interprets queued as sent |
| EX-DOC-08 | Missing or mismatched port/rail gate receipt stays pending, with at most one appropriate native Activity | Upload alone marks FAS commercial handoff completed, stock shipped or invoices posted |
| EX-DOC-09 | Phase 2 adds document requirements (SI, issued ocean B/L, VGM evidence) using same Docs and booking identities | Ocean phase requires migrating Phase 1 files to a competing document store |
| EX-DOC-10 | No Enterprise Documents features assumed before installation/licensing proof; safe native attachment fallback if authorized | Phase 1 becomes unusable because an unlicensed Documents AI/Enterprise feature was silently required |
| EX-DOC-11 | A PO-only shipment's evidence attaches to its real PO/picking with exact company | Export invents a load/SO solely to satisfy its own document links |
| EX-DOC-12 | An export document affecting more than one party preserves role-specific confidentiality and access rights | A forwarder receives internal supplier economics through a generic attached native report |
| EX-DOC-13 | No export-specific scheduler is required where native `ir.cron`/mail.activity and Linda owner cover due reminders | Both Export and Linda send overdue-document reminders for the same obligation |
| EX-DOC-14 | Physical QR/container scan and document verification remain separate actions and independent authorities | Scan triggers financial posting, regulatory clearance, or marks B/L issued |

## Required pre-implementation source comparison

- Compare actual current `plasticos_documents`, `plasticos_documents_native`, and `plasticos_logistics` code against the separately frozen Native-First BRS. Resolve duplicate verification-authority risk at its existing owner before adding Export consumers.
- Audit whether `plasticos.document.rule` and `plasticos.document.validation.matrix` already support exact export scope; if not, add the smallest generalized extension in Documents, with export declaring contextual requirements through a supported interface. No new duplicate rule engine.
- Verify whether export Booking/Schedule fields already have authoritative homes; extend only uncovered facts. One booking may have many containers; export views must not conflate identities.
- Verify active Odoo Enterprise Documents licensing and actual `documents.document` interface on the deployment, not just addon declarations in a repository.
- Confirm external correspondence operation owner and report audience/privacy rule before enabling outbound export messages.
- Check future implementation with both positive and prohibited negative controls. All above NOT_RUN now.
