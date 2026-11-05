# Open Decisions, No Accidental Defaults

Unresolved details are deliberately NOT_RUN or UNKNOWN. The BRS records the safe negative boundary and does not automatically approve a code change.

| Boundary | Still unproven/open | Safe rule until evidence |
|---|---|---|
| Odoo Enterprise Documents | Installed Request model/schema, internal-only activity, folder alias, permissions, shortcut, version and historical original behavior | No guessed fields/actions; exact native API census before coding |
| PO-only attachment mapping | Existing typed `plasticos.document` relation to a native PO/picking without SO/load | No fabricated `plasticos.load`/transaction or partner-recency attribution; propose minimum schema gap later |
| Multi-link original | Native bridge's one `plasticos_doc_id` pointer versus multiple business evidence rows | One original with typed rows; derive bridge after source proof, no duplicated attachments |
| Verification and compliance | Existing multiple writers, expiry/supersession logic, `account.move.action_post` in compute | Safety correction (side-effect-free compute) **before active intake**; only authorized verification writer |
| Receiving sufficiency | Accepted Receiving format, full vs partial net/quantity and per-load coverage | No blanket close, preserve per-quantity unknown |
| CST sufficiency | Certification evidence and $150 penalty deadline/cure/reversal | No automatic carrier penalty or AR block; remain an independent obligation |
| Business-day calendar | Mon–Fri basis; holidays and company/recipient timezone quiet-hour policy | Do not guess holidays; no external reminders before authorization |
| Native Activity reminders | Built-in Documents Request reminder buttons/batch tool and any scheduled sends | Internal-only, do not activate separate external send |
| Studio / paid OCR / AI | Actual entitlement and integration requirements | Never require new paid feature for basic intake; no AI authority transfer |
| Document -> finance | Buyer AR, vendor bills, credit/debit, QuickBooks cutover | No auto-post, dunning or bank transactions from Documents events |
| Automation stage | Existing crons and Linda send ownership, duplicated actions | Manual verified flow first; separate runtime proof and activation approval |
| Repository admission | Accepted ADR overlap, actual new PR ancestry and BRS status | Stop on conflict; BRS install PR is candidate until operator-reviewed merge |

Original fine-grained campaign open gates live in the frozen source `GOVERNANCE/OPEN_DECISIONS.md` and Primary Rev008. Never silently promote source plan assumptions to runtime proof.

## Branch integration status (2026-10-27)

Pull request #318's non-documentation blobs match pull request #316 head `53b18fd90046696e946a0d8e1e60e88595a5e143`. That match keeps the Linda runtime already carried by #316. This Documents overlay remains `CANDIDATE_UNTIL_OPERATOR_APPROVED_MERGE`. Native Documents Requests, native AI, mail, cron, and financial posting stay `NOT_RUN` on this installation. The open rows above are the future implementation gaps. Publish this branch only after #316 is the integrated Staging base, so the published diff stays the Documents chapters, the logistics alignment overlay, and these status records.
