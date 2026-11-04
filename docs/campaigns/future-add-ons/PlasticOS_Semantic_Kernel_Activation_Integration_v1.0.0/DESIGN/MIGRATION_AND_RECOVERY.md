# Data conversion, migration, historical compatibility and recovery

## 1. Pre-mutation census

Read exact module states/versions, model/field registry, native/Enterprise versions, supply/demand/spec/observation/facility/capacity rows, material/facility ownership, company assignments, UUIDs/external references, graph labels/edges and consumer identifiers. Include archived data. Inspect DB server actions, cron, automated actions, mail/aliases/templates, views, import jobs and custom integrations. Identify owners of every trigger. This is read-only until separately authorized.

Report counts by family, source classification and migration disposition: reusable as-is, needs mapping, ambiguous/quarantined, conflicting, referenced externally, and out of scope. Unknown installed state must not be rephrased as empty database.

## 2. No bulk truth inflation

Backfill is source-to-representation conversion, not an inference engine and not confirmation. A material profile, an imported historical invoice or a facility process does not prove available stock or present demand. Supply admission requires the source contract in DESIGN/DATA_CONTRACT.md; demand requires explicit buyer evidence. Historical rows lacking current validity remain nonmarketable regardless of apparent material fit.

The old `BLOCKED_AUTOMATIC` rule is relaxed only for the exact admitted source/family/batch and operation. Blanket automatic conversion of ambiguous records remains blocked permanently. Removing a guard is not a sufficient patch.

## 3. Adapter and truthful receipts

The current CLI is fixture-only and forces dry-run; the planner's non-dry branch increments a counter without ORM persistence. The new execution adapter must return actual durable outcomes. A report must reconcile:

`attempted = committed creates + committed updates + reused + rejected + conflicted + failed + unknown`

Distinguish planned work and committed effects. A timed-out external write is unknown/pending until acknowledged or read back, not an automatic failure or success. Mapping-level identity lookup must be durable, not an in-memory set that disappears after restart.

The logical business key is independent of mapping version; the operation key includes the exact source revision/mapping/digest. Replaying unchanged input reuses the existing business row. A newer approved revision updates/supersedes it. Replaying an older revision cannot resurrect expired or withdrawn facts.

## 4. Transaction and resume behavior

Source admission and its local operation record are atomic. External dispatch occurs after commit through the governed worker, never while a source rollback could invalidate the fact. The framework owns normal RPC transactions; do not add ad hoc commits. A separately owned batch cursor, when required and admitted, commits a bounded batch and records an exact checkpoint only after durable completion.

Resume cursor denotes last durably processed source record, not the last item originally fetched when stop-on-conflict broke early. Use deterministic sortable keys and snapshot bounds. Concurrent runs need uniqueness/locking at the actual owner. Record mapping/source revisions and input digests; reruns after mappings change must not double-count loads.

## 5. Existing semantic rows

Preserve UUIDs and native IDs when still valid. Existing public entity references get an explicit retained alias or migration mapping, not silent string replacement. Rows with no native commercial source are diagnostic-only until reconciled. Conflicting owner/material evidence stays preserved and quarantined. Do not autolink by company name.

Material/facility reconciliation must retain observations, specifications, supply relations, attachments and existing graph source identities. Run the optional CRM collision suite with the optional module actually installed. Keep all historic approved snapshots unchanged.

## 6. Schema migration

Plan additive fields and constraints first, data reconciliation second, and tightening constraints only after audited completeness. Record exact installed version and choose the migration folder accordingly. Existing null/invalid rows cannot be hidden by new defaults or backfilled approval flags. No install/upgrade hook may create tradable supply, call paid inference, emit graph writes or activate cron.

The passive kernel and optional bridge each have their own versioning/wiring. Installation is not activation. Default app dependencies must not pull the bridge into the primary MVP.

## 7. Graph publication

Persist exact native source lineage, evidence state, quantity units, validity and version. Verify required nodes and typed edges, including relation updates and removals. Current-row update and tombstone ordering must be monotonic per source key. A successful node count without the required material relation does not prove queryable supply.

Backfill and ongoing changes use the same admitted mapper and source policy. Do not let backfill construct one identity while the live event path constructs another.

## 8. Recovery sequence

1. Stop authorizing new affected operations; pause queued work and prevent stale listings from being treated as current.
2. Preserve the operation journal, receipts and exact source revisions. Classify ambiguous external outcomes by readback.
3. Reconcile the last confirmed graph watermark against authoritative Odoo facts; apply explicit withdrawn/stale states when authorized.
4. Restore the known-good code/config release, preserving compatible additive data. Restore database and filestore only when necessary using a tested paired backup; avoid destroying unrelated concurrent business changes.
5. Rebuild projections from the preserved source snapshot through the approved mapper, then prove counts, identities, edges and eligibility before resuming.

If disable cannot protect against stale availability, use of the affected intelligence must stop completely. Never restore retired local matching or inference as a recovery shortcut.

## 9. Required receipts

Before any live batch: backup identity, database/filestore pairing, restore test, exact release and installed versions, source/batch digest, authorization, planned counts, rejected/conflict report and rollback boundaries. After: actual committed counts, mapping table, source/graph readback, failures/unknowns, replay test and disable test. Every receipt is evidence of its demonstrated operation only.
