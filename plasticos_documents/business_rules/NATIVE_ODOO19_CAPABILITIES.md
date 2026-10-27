# Odoo 19-native capability binding for Documents

**Documented candidates are not installed-runtime proof.** Read exact installed Odoo 19 Enterprise `documents` and `documents_account` registries and current repository bridges before coding.

| Native feature | Intended use | Document ownership and guard |
|---|---|---|
| `documents.document` + `ir.attachment` | One original, internal folders, tags, versions, shortcuts, lock and `Linked to` | Original belongs to native; separate typed PlasticOS evidence and verification can reference it |
| Folder email alias | Incoming company document collection and Inbox triage | External sender has no viewer/editor/share rights |
| Documents `Request` / Activity view | Internal missing-file placeholders and due dates | Internal assignee only; no external Request link or built-in external reminder |
| `mail.activity` / chatter | One actionable human review per exact obligation, idempotent update | No second reminder platform or email source |
| `base.automation` + `ir.actions.server` | Safe exact on-create/on-write processing, no approval by inference | Deterministic business owner checks always apply |
| `ir.cron` / native timed actions | Distinct Documents and Linda due evaluations | Separate jobs, single external writer, actual movement event clock |
| `mail.mail`, `mail.message`, templates | Linda external requests using native queue | Preserve queued/sent/unknown, recipient confidentiality, revision identity |
| `documents_account` / Accounting journal intake | Supplier invoice PDF -> draft bill under accounting authority | No auto-post and no required paid digitization |
| Native AI auto-sort / OCR | Optional folder/tag proposal with installed/paid proof | Never verifies, writes weights or posts money |
| Native linked-record display | Navigation to one native record where applicable | Additional exact typed links must retain the one original |
| Native file PDF split/merge | Optional only with immutable retained source and provenance | Odoo docs warn some merge actions replace input originals; refuse this behavior for authoritative originals |

**Documentation checked 2026-10-26:** https://www.odoo.com/documentation/19.0/applications/productivity/documents.html . Odoo docs note that Documents folder automations require Studio (potential cost), AI Auto-sort requires AI app, built-in Request reminders can be sent, and folder email aliases are configurable. None of that is proof the current Odoo.sh Enterprise registry is installed/configured/authorized.

No custom Documents SaaS, scheduler, parallel file store, external portal or external LLM may be introduced merely because it seems convenient.
