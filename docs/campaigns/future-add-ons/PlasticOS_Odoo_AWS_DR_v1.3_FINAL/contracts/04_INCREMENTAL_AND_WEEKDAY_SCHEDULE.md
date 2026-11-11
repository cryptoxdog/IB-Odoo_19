```yaml
repository_access:
  writable:
    - https://github.com/cryptoxdog/IB-Odoo_19
  read_only:
    - https://github.com/Quantum-L9/.github
    - https://github.com/Quantum-L9/Cursor-Governance
  unlisted_repositories: no_access
```


# CONTRACT 04 | Changed-data economy, fresh weekday source checkpoints and cold archival

**Mission:** SM-DR-04-INCREMENTAL | **Owner:** source capture, byte reuse, scheduler, monitoring, incremental recovery and archive lifecycle. **Prerequisite:** 03 has a fully restored real Odoo production checkpoint in AWS; 05 has deposited and proved the baseline operator pack; and 00/01 have authorized a supported *fresh* source acquisition path. The already protected daily baseline must remain recoverable during all optimization tests. Never convert a daily archive re-download into a new recovery point.

## Source feasibility gate

- First demonstrate at least TWO genuinely distinct, consistent **real Production** source timestamps with exact DB state, matching filestore and independent restore result. **Never create/modify/delete Production business records to stage a test.** Use naturally observed production changes where available; perform deterministic changed transaction/dependent rows, deleted record, added/replaced/deleted attachment and race tests in an isolated Odoo fixture through the same implemented snapshot/restore mechanism. Production fidelity tests and fixture mutation semantics are separately identified; neither substitutes for the other. Source mechanism must be vendor-supported and provider-authorized, with measured CPU/network/IO impact; no undocumented platform API, production daemon, new Odoo cron, app module, PostgreSQL setting change or unauthorized binary-copy race.
- If provider-native completed daily backup is the only supported source, keep daily independent copies protected and restored, but **leave this contract BLOCKED_EXTERNAL**. Submit the exact official Odoo.sh plan/API/backup capability request, identify potential provider-approved service tier or access change, and do not enable misleading four-times-a-day jobs. Do not simply rename snapshots or redefine DONE.
- Source state must include complete transactional database semantics, deletion and sequence semantics and matching original filestore. A change-event stream, `write_date` records or standalone `pg_dump` + concurrent file copy is not sufficient without proved full point-in-time closure.

## Efficient content and immutable dependency design

- Baseline from 03 becomes first approved source; use verified content-addressing/cryptographic digest and versioned checkpoint manifests. Identical file bytes and database chunks MUST be reused when lawful/possible; preserve exact file identity and metadata. Measure network bytes **from Odoo.sh** as well as S3 bytes; dedup storage-only does not make repeated 40GB downloads disappear.
- No mutating/pruning a WORM-protected dedup repository from routine writer. Each manifest must capture the exact S3 version IDs, hash and retention expiration of every parent/chunk/dependency, and every shared object must remain protected through newest dependent checkpoint. A new snapshot can reference an existing object only with proven retention extension/re-protection or equivalent safe published immutable object version.
- Preserve multiple historical snapshots and true deletion behavior (restore older shows old state; restore later excludes deleted record). Use isolated fixtures for corruption/missing chunk, partial upload/worker crash, concurrent jobs, permission loss, poisoned/source stale artifact and change in code/Enterprise dependencies.
- Restore at least two different real fresh source timestamps, with a later deletion/new document and an unchanged historical attachment; verify observed read-back hash and relational integrity. Snapshot admission atomic: commit only when all verification and locks succeed; prior last-good remains if failed.

## Weekday schedule, metrics and alarms

- Only after real fresh source proof, provision EventBridge Scheduler (or verified equivalent) **11:00, 13:00, 15:00, 17:00 on Monday-Friday**, zone `America/New_York`, DST safe, no overlap, one execution per slot. No independent starts nights/weekends; the 17:00 run can finish after 17:00; native Odoo.sh daily backup continues every day.
- Record source checkpoint and completed/upload/admitted times separately, source age and transfer latency. Measure RPO as **operating elapsed time** under the actual business clock 09:00-17:00; note a snapshot starting at 11:00 is not yet available at 11:00 if it takes time. Include 09-11 and Friday-Monday windows and overnight mutations, no unconditional two-hour guarantee.
- Independently test failure/late/stale/no-op/failed checksum/partial upload/missed or concurrent job, source clock skew and retry; an overdue run raises an actual alarm to the independent company recipient and does not advance last-good. Reconcile observable AWS schedule and the code configuration; test one real point from the deployed scheduler (not only manual trigger), plus a four-slot weekday cycle where feasible without additional unauthorized jobs.
- Measure full baseline bytes, dedup inventory bytes, changed source transfer bytes, S3 growth, execution time, restore duration, running cost and practical business RPO. If observed RPO >120 operating minutes, report target missed even if source checkpoints started on schedule. Investigate within this slice and retest; no invented green.

## Cold archive and lifetime

- Configure and test a version-controlled, age-based archival process that only considers **selected complete, self-contained recovery bundles >365 days old, which have actually been retained online during the prior year**. Test against synthetic aged fixture and independent restore; never force fresh object to cold, delete original business records, shorten legal retention or move objects required by hot/latest restore. The archive must include code/DB/filestore/manifest/key dependencies and retrieval-cost/time handling. All S3 Object Lock and KMS controls from 02 remain effective.
- A 90-day immutable protection period is a minimum deletion lock, NOT the total archive retention policy. Do not silently prune selected month-end/year-end points before 365 days. Until time-based eligibility is met, the policy can be installed/tested with fixtures and report `NOT_YET_ELIGIBLE`, not manufacture a year-old production archive.

## Exit receipts and closure

`PASS` requires REAL fresh distinct source points, tested and observed two-hour weekday scheduling, dedup with measured source and S3 savings, changed/deleted restore correctness, alarm evidence, full immutable dependency closure, cold archive proof and one actual scheduled point independently restored. No open in-scope issue allowed. Tests, secrets, runbooks, code/config and operator access must be closed and handed to 05. If source access blocked, leave this workstream `BLOCKED_EXTERNAL`, finish only safe daily S3 protection and label campaign NOT_DONE. Do not edit previously locked policy or weaken RPO goal to pass.

## Post-change operator custody and implementation durability

- As soon as any worker, IAM/KMS resource, retention, native source mechanism, executable image or recovery command changes, invalidate the related protected release manifest and 1Password references; produce a new frozen release bundle and hand it to Contract 05 for independent retrieval/repair before 06 can close. Preserve the previously usable baseline until the new version is fully proven. No destructive in-place upgrade of the sole known-good restore implementation.
- The fixed 11/13/15/17 starts create a **mathematical gap whenever a checkpoint finishes later than its start**. The exact 120 operating-minute number is a TARGET, not a platform SLA. Evaluate the worst observed business-minute age including the 09-11 period, job completion, misses, overnight changes, and weekend recovery; do not mask >120-minute windows by averaging. If the user later needs a hard guaranteed two-hour RPO, request an explicit architecture/schedule revision rather than adding an unauthorized 09:00 job.
- Require a protected, source-true *new* checkpoint to have a different actual data capture point, not merely a changed manifest hash. If no documented provider-supported method produces it, leave 04 BLOCKED_EXTERNAL; do not add an undocumented Odoo script or declare a fake four-per-day schedule.

## Verifier must be independent of the scheduled writer

Do not give the scheduled backup runner credentials or an assume-role trust path allowing it to publish the `admitted` index, change last-good or hide alarms. The independent verifier validates every scheduled candidate against the actual source and immutable S3 object versions and either promotes it or fails closed, preserving the previous known-good. Negative-test a forged candidate and attempted writer-driven self-promotion, including the case where the scheduler fires correctly but integrity verification fails.
