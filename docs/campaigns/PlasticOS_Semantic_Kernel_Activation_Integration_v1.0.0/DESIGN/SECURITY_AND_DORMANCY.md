# Security, approvals and enforceable dormancy

## Default-deny meaning

Dormant means no production inference calls, graph writes, automatic backfill, authority cutover, business records, outbound emails or paid-provider side effects. Source files may be present. An optional module may be installed in an authorized isolated fixture. Neither fact authorizes business use.

Planning flags in `PLAN/ACTIVATION_STATE.json` are a record of intent, not installed enforcement. Real enforcement must be demonstrated on every side-effect path.

## Separate permissions

| Operation | Required permission/evidence | What it does not authorize |
|---|---|---|
| Read-only census | Read access to exact environment/source | Mutation or module installation |
| Dry-run conversion | Source/tenant/family scope | Writes or inference |
| Controlled backfill | Reviewed batch, exact mapping/revision, authorized ORM adapter and recovery proof | Future scheduler or read-authority cutover |
| Inference evaluation | Approved sources, provider budget and isolated target | Confirmed supply/demand or CRM mutation |
| Current projection | Admitted source and exact revision; scoped caller permission | Generic graph writes or local authority transfer |
| Read-authority cutover | Separate family-specific contract proof and operator approval | Automatic truth promotion or migration |
| Read-only business intelligence | Current tested release and explicit tenant/operation grant | Live emails, partner/PO changes or autonomous commercial admission |
| Commercial qualification | Native campaign's role and material/approval gates | Bypass of opportunity/offer/PO controls |

Do not reuse one blanket enable flag for all these meanings. Reuse existing controls where semantics match; introduce only the smallest necessary operation scope. Proposed labels in this pack are not documented config keys until admitted and implemented.

## Server-side enforcement

All public methods, ORM create/write, import, RPC, scheduled jobs and worker retries must enforce current operation authorization. UI hiding and context booleans are not approval. Capture approver, tenant, source revision, permitted operation, time and release on the server. Recheck after queue delay and before dispatch. Disable must stop queued/retried work, not only new user requests.

Published supply/demand is derived and readonly to ordinary users. Human evidence editing uses guarded actions and creates a new reviewed revision. Database administrators are not a reason to weaken application contracts. Any maintenance escape path must be explicit, local, audited and unavailable to normal remote context injection.

## Company and privacy

Odoo ACLs and company record rules both matter; access rights alone are not sufficient. Confirm the actual `company_id` type on each model before reusing it: some older domain fields named company refer to a business partner rather than `res.company`. The integration operation and semantic row must bind the true Odoo company and tenant explicitly.

Permit minimum source fields, recipient/identity data and evidence references. Public/portal identities cannot access supplier intelligence or approve facts. Signed transport protects the boundary but does not substitute for company authorization. Test role escalation through sudo, source spoofing, attachment access and cross-company relational joins.

No secrets, live tokens or signed temporary download URLs belong in this package, reports, receipts, database ICP where disallowed, or repository commits. The evidence register contains immutable source URLs only.

## Transport and action admission

Keep Odoo a consumer. Its grant example is not proof of deployed grants and does not automatically include sync or a proposed gap action. If the existing source-publishing action cannot be safely restricted by source/tenant/record type, obtain a source-owner contract revision; do not impersonate an EIE worker or call CEG directly. Gate owner changes are narrow and versioned.

Validate signed response semantics, including failure packets carried with HTTP 200. Acknowledgement must bind intended endpoint/entities/revision/materialization. A copied query ID or candidate count is not evidence of source correctness.

## Recovery and expiry

Do not simply stop the publisher and leave active graph listings eligible forever. Each confirmed listing has source validity; graph readers reject stale/unavailable authority. Disable either stops affected use or completes an explicitly authorized invalidation path before stopping, with acknowledgement and audit. No hidden local inference fallback is permitted.

## Native guidance

Primary references checked during preparation: Odoo 19 Security in Odoo, especially ACL versus record-rule behavior; Odoo 19 Coding Guidelines, especially framework transaction ownership. Full URLs and observation limits are in EVIDENCE/SOURCE_NOTES.md. These documents do not prove the user's installed Enterprise revision.
