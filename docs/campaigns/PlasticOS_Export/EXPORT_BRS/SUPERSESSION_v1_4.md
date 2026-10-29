# Phase 2 provider scope addition: v1.4.0

Effective date: 2026-10-28. Operator authorization: add FindTEU and ACE AESDirect to **Phase 2** planning scope only. This is not permission to code, subscribe, submit filings, certify or release.

## Changed boundaries

- BRS-EXP-12-R001..R005: FindTEU container milestone tracking, exact binding, actual-vs-estimated events, replays/rolls and provider availability. The Phase 2 feature is planned; provider behavior is unproved at runtime.
- BRS-EXP-12-R006..R010: ACE AESDirect applicability, prepared EEI filing packets, authorized portal/WebLink/bulk handoff, official receipt/ITN or exemption evidence, amendments, and prohibition of uncertified direct transmission.
- Both connectors are external, optional *at runtime*, and non-blocking for Phase 1. Their provider integrations are explicitly included in Phase 2 scope, without changing native ownership.
- No Freightview integration is added to the committed Phase 2 scope by this revision.

## Preservation

All earlier rule statements BRS-EXP-01..11, their 78 acceptance cases, original booking evidence, and unrelated RecycleOS decisions are preserved byte-for-byte. The current authoritative Export BRS is the same 78 rules plus ten new BRS-EXP-12 requirements. References to earlier version counts in historical files remain historical only.

## Non-negotiable semantic boundaries

- **FindTEU:** observation-only; not an ocean carrier booking or Customs authority; no setting financial, physical delivery or freight states from event names.
- **AESDirect:** authorized-filed regulatory workflow; prepared is not submitted, submitted is not accepted, ITN is not necessarily cargo customs clearance, exemption is not a guess.
- **Evidence:** Documents retains originals, PlasticOS Documents retains verification; Export consumes evidence; Logistics remains the carrier/dispatch authority; Stock/Accounting remain native.

## Verification and activation

Structural integrity and registry/acceptance consistency are checked in the packaged artifact. Live FindTEU provider calls, authentication/security proof, AES filing handoff and regulatory acceptance are NOT_RUN. No external adoption or repository change.
