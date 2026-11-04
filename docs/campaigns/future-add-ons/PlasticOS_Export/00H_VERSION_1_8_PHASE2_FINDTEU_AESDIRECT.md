# v1.8.0 Phase 2: FindTEU + ACE AESDirect integration scope

**Operator decision, 2026-10-28:** Add the following two integrations to **Phase 2 international selling** of `plasticos_export`, leaving Phase 1 unchanged.

1. **FindTEU:** provider-backed ocean container tracking and ETAs with optional API/webhook connection; source-bound per-container events and revision/conflict handling. It provides external observations, not booking, physical movement, legal delivery, credit or Odoo state authority.
2. **ACE AESDirect:** support EEI filing for applicable U.S. exports through authorized-filer identification, prepared validated data, official ACE portal / WebLink handoff or approved-format bulk upload, recording acceptance ITN/rejections/amendments. No uncertified direct filing, unsupervised submission or inferred customs clearance.

**Location in pack:** `EXPORT_BRS/RULES/BRS-EXP-12.md`, `EXPORT_BRS/SUPERSESSION_v1_4.md`, `EXPORT_BRS/PHASE2_PROVIDER_SCOPE_AND_SOURCES.md`, and indexed acceptance cases.

**Nonduplication and gates:** Reuse `plasticos_export` booking/container identity, Odoo native SO/PO/Stock/Accounting, `plasticos_documents` verification, native Documents originals, and Linda Logistics state/communication owners. Each integration is optional and tenant-configurable in operation, but is now part of the planned Phase 2 work. External credentials, live provider integration, government filing authority and acceptance remain untested/unapproved. Freightview is not added.

**Previous pack:** v1.7.0 unaffected outside the current Export BRS mirror, this addendum, readme, and manifest.
