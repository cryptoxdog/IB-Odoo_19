# Full source-owner implementation ledger (candidate, no coding grant)

Canonical machine source is `case.json` with 33 effects, owner/consumer/reachability, source blob, disposition, migration/recovery, and positive/negative proofs. This is a generated human projection. Actual code file edit commitments require `U00` closure. All EDIT/CREATE files are gathered in `PLAN/FILE_CHANGE_LEDGER.csv`; no unlisted source edit is authorized.

## E01: plasticos_gate -> Gate typed mapper, final_fields, status and allowlist [NO_CHANGE]

**Before:** Current pinned source as observed; see evidence register.

**After:** Consume current completed-state response mapper unchanged; no EIE/CEG changes. New per-field reviewer is in plasticos_enrichment.

**Source:** `plasticos_gate/services/gate_mappers.py@2dc516aa29718b4545faf67e79ca225589ac6d7f` blob `e755bc06ac51cb2d0161613e7bb46f7235290baf`

**Files:** No code changes; explicit preservation

**No-change basis:** Current mapper already projects the 8 allowlisted partner fields and source result; adding Odoo decision logic to mapper would violate ownership.

**Migration:** Do not infer installed row counts; additive migration gated by actual installed version, company/field-owner census and count-preserving backup.

**Recovery:** Review-only kill switch; restore exact DB+filestore from paired verified backup if required; preserve historical response/provenance.

**Security:** No public, portal or cross-company write. Server rechecks role/company/field and retains verified run evidence.

**Proofs:** P02, P14, P31

**Depends on:** none

## E02: plasticos_gate -> Existing dual flag default OFF [NO_CHANGE]

**Before:** Current pinned source as observed; see evidence register.

**After:** Preserve existing dual opt-in feature flag config. New Odoo enrichment run MUST take review path and not call immediate-write branch; ensure deployed flags are zero.

**Source:** `plasticos_gate/services/gate_config.py@2dc516aa29718b4545faf67e79ca225589ac6d7f` blob `e1aa6cc37f87f248f6bffeee2e1da20d0ccf9564`

**Files:** No code changes; explicit preservation

**No-change basis:** Config already requires two explicit flags; source defect is addon direct application and stale ADR-012, not Gate config.

**Migration:** Do not infer installed row counts; additive migration gated by actual installed version, company/field-owner census and count-preserving backup.

**Recovery:** Review-only kill switch; restore exact DB+filestore from paired verified backup if required; preserve historical response/provenance.

**Security:** No public, portal or cross-company write. Server rechecks role/company/field and retains verified run evidence.

**Proofs:** P01, P05, P19

**Depends on:** none

## E03: plasticos_gate -> Existing allowlist/seed/SDK [NO_CHANGE]

**Before:** Current pinned source as observed; see evidence register.

**After:** Retain existing 8-field write allowlist. Preserve signed SDK transport, request idempotency and default auto-writeback ICP 0.

**Source:** `plasticos_gate/services/gate_allowlists.py@2dc516aa29718b4545faf67e79ca225589ac6d7f` blob `782420f28650ef39f903bd06183ef11c93bd6452`

**Files:** No code changes; explicit preservation

**No-change basis:** Field list is accepted law; no change to recipient selection or source request is justified.

**Migration:** Do not infer installed row counts; additive migration gated by actual installed version, company/field-owner census and count-preserving backup.

**Recovery:** Review-only kill switch; restore exact DB+filestore from paired verified backup if required; preserve historical response/provenance.

**Security:** No public, portal or cross-company write. Server rechecks role/company/field and retains verified run evidence.

**Proofs:** P02, P14, P28

**Depends on:** none

## E04: plasticos_matching -> External consumer of Gate module [NO_CHANGE]

**Before:** Current pinned source as observed; see evidence register.

**After:** Guard matching unaffected by enrichment review; preserve Gate dependency and all matching tests.

**Source:** `plasticos_matching/__manifest__.py@2dc516aa29718b4545faf67e79ca225589ac6d7f` blob `db9f4edb74037a9a458a815d64761ac92d2c0f05`

**Files:** No code changes; explicit preservation

**No-change basis:** Independent Gate reverse dependent; no source/wiring or runtime matching effect is authorized.

**Migration:** Do not infer installed row counts; additive migration gated by actual installed version, company/field-owner census and count-preserving backup.

**Recovery:** Review-only kill switch; restore exact DB+filestore from paired verified backup if required; preserve historical response/provenance.

**Security:** No public, portal or cross-company write. Server rechecks role/company/field and retains verified run evidence.

**Proofs:** P21, P23

**Depends on:** none

## E05: plasticos_enrichment -> Audit model state and server methods [EDIT]

**Before:** Current pinned source as observed; see evidence register.

**After:** Replace weak write/unlink/state guards with service-owned transition policy; deny state-plus-evidence edits, add current Odoo company/owner validation without restoring local engine.

**Source:** `plasticos_enrichment/models/enrichment_run.py@2dc516aa29718b4545faf67e79ca225589ac6d7f` blob `7307232d4abce258874b272d6a95e4dbb42560c2`

**Files:** `plasticos_enrichment/models/enrichment_run.py` (EDIT)

**No-change basis:** n/a

**Migration:** Do not infer installed row counts; additive migration gated by actual installed version, company/field-owner census and count-preserving backup.

**Recovery:** Review-only kill switch; restore exact DB+filestore from paired verified backup if required; preserve historical response/provenance.

**Security:** No public, portal or cross-company write. Server rechecks role/company/field and retains verified run evidence.

**Proofs:** P04, P09, P11, P29

**Depends on:** E01

## E06: plasticos_enrichment -> Security groups and ACLs [EDIT]

**Before:** Current pinned source as observed; see evidence register.

**After:** Remove broad base.group_user full CRUD from run/source/extraction/provenance. Restrict proposal decisions to explicit enrichment user/manager and system-owner methods; no public/portal rights.

**Source:** `plasticos_enrichment/security/ir.model.access.csv@2dc516aa29718b4545faf67e79ca225589ac6d7f` blob `054061fbf09df792c9e61545c613e54891265bc9`

**Files:** `plasticos_enrichment/security/ir.model.access.csv` (EDIT), `plasticos_enrichment/security/security.xml` (EDIT)

**No-change basis:** n/a

**Migration:** Do not infer installed row counts; additive migration gated by actual installed version, company/field-owner census and count-preserving backup.

**Recovery:** Review-only kill switch; restore exact DB+filestore from paired verified backup if required; preserve historical response/provenance.

**Security:** No public, portal or cross-company write. Server rechecks role/company/field and retains verified run evidence.

**Proofs:** P04, P10, P11, P23

**Depends on:** E05

## E07: plasticos_enrichment -> Retired system cron manager grant [EDIT]

**Before:** Current pinned source as observed; see evidence register.

**After:** Remove default enrichment-manager grant to inactive cron user when no proved authorized consumer; preserve other group memberships. Revocation of already-installed grant is a separate scoped migration.

**Source:** `plasticos_enrichment/hooks.py@2dc516aa29718b4545faf67e79ca225589ac6d7f` blob `d6aa4367a8eeea18bcc77de82a8bfd06416ae91d`

**Files:** `plasticos_enrichment/hooks.py` (EDIT)

**No-change basis:** n/a

**Migration:** Do not infer installed row counts; additive migration gated by actual installed version, company/field-owner census and count-preserving backup.

**Recovery:** Review-only kill switch; restore exact DB+filestore from paired verified backup if required; preserve historical response/provenance.

**Security:** No public, portal or cross-company write. Server rechecks role/company/field and retains verified run evidence.

**Proofs:** P04, P19, P20

**Depends on:** E06

## E08: plasticos_enrichment -> Retired local inference service and material injector [EDIT]

**Before:** Current pinned source as observed; see evidence register.

**After:** Remove unreachable executable local engine helper paths after dynamic-consumer census; keep the historical service owner and explicit fail-closed/no-op APIs required by tests. No local material profile create.

**Source:** `plasticos_enrichment/models/enrichment_service.py@2dc516aa29718b4545faf67e79ca225589ac6d7f` blob `79ae6e5a6200a5f987bf72cc121fee976ea206af`

**Files:** `plasticos_enrichment/models/enrichment_service.py` (EDIT)

**No-change basis:** n/a

**Migration:** Do not infer installed row counts; additive migration gated by actual installed version, company/field-owner census and count-preserving backup.

**Recovery:** Review-only kill switch; restore exact DB+filestore from paired verified backup if required; preserve historical response/provenance.

**Security:** No public, portal or cross-company write. Server rechecks role/company/field and retains verified run evidence.

**Proofs:** P03, P08, P19, P23

**Depends on:** E05

## E09: plasticos_enrichment -> Retired historical cron definitions [NO_CHANGE]

**Before:** Current pinned source as observed; see evidence register.

**After:** Keep both cron records inactive and their methods as no-ops; noupdate data may not reset installed state, so migration needs explicit DB check.

**Source:** `plasticos_enrichment/data/cron.xml@2dc516aa29718b4545faf67e79ca225589ac6d7f` blob `305e4339c678fcc08614e4ebf005c080564816e3`

**Files:** No code changes; explicit preservation

**No-change basis:** Retirement is accepted ADR; never reactivate or replace with an Odoo scorer.

**Migration:** Do not infer installed row counts; additive migration gated by actual installed version, company/field-owner census and count-preserving backup.

**Recovery:** Review-only kill switch; restore exact DB+filestore from paired verified backup if required; preserve historical response/provenance.

**Security:** No public, portal or cross-company write. Server rechecks role/company/field and retains verified run evidence.

**Proofs:** P19, P20

**Depends on:** none

## E10: plasticos_enrichment -> Field review data owner [CREATE]

**Before:** Current pinned source as observed; see evidence register.

**After:** Add one narrow proposal-line model in the existing addon: unique (run,field) for Gate response, immutable target and source snapshot, separate review decision state and reviewer metadata; committed provenance remains separate.

**Source:** `plasticos_enrichment/models/enrichment_proposal_line.py@2dc516aa29718b4545faf67e79ca225589ac6d7f` (PROPOSED NEW source)

**Files:** `plasticos_enrichment/models/enrichment_proposal_line.py` (CREATE)

**No-change basis:** n/a

**Migration:** Do not infer installed row counts; additive migration gated by actual installed version, company/field-owner census and count-preserving backup.

**Recovery:** Review-only kill switch; restore exact DB+filestore from paired verified backup if required; preserve historical response/provenance.

**Security:** No public, portal or cross-company write. Server rechecks role/company/field and retains verified run evidence.

**Proofs:** P06, P07, P12, P16, P30

**Depends on:** E05, E06

## E11: plasticos_enrichment -> Gate response storage and proposal projection [EDIT]

**Before:** Current pinned source as observed; see evidence register.

**After:** Store EIE completed response snapshot/digest and aggregate evidence; on success enter review, create lines for eligible and evidence-only values; all partner writes deferred; no-eligible-fields becomes explicit no-action/evidence-only state, not fabricated failure.

**Source:** `plasticos_enrichment/models/enrichment_run.py@2dc516aa29718b4545faf67e79ca225589ac6d7f` blob `7307232d4abce258874b272d6a95e4dbb42560c2`

**Files:** `plasticos_enrichment/models/enrichment_run.py` (EDIT)

**No-change basis:** n/a

**Migration:** Do not infer installed row counts; additive migration gated by actual installed version, company/field-owner census and count-preserving backup.

**Recovery:** Review-only kill switch; restore exact DB+filestore from paired verified backup if required; preserve historical response/provenance.

**Security:** No public, portal or cross-company write. Server rechecks role/company/field and retains verified run evidence.

**Proofs:** P02, P05, P06, P15, P17, P31

**Depends on:** E10, E01, E02, E03

## E12: plasticos_enrichment -> Original provenance semantics [EDIT]

**Before:** Current pinned source as observed; see evidence register.

**After:** Keep records as committed write/effect lineage, optionally add nullable reviewed_line_id for new changes; never reclassify old provenance as pending proposals. No fake aggregate confidence=1.0.

**Source:** `plasticos_enrichment/models/enrichment_provenance.py@2dc516aa29718b4545faf67e79ca225589ac6d7f` blob `19ddaea78e3126807df51713c1885dfcc7ff1ee2`

**Files:** `plasticos_enrichment/models/enrichment_provenance.py` (EDIT)

**No-change basis:** n/a

**Migration:** Do not infer installed row counts; additive migration gated by actual installed version, company/field-owner census and count-preserving backup.

**Recovery:** Review-only kill switch; restore exact DB+filestore from paired verified backup if required; preserve historical response/provenance.

**Security:** No public, portal or cross-company write. Server rechecks role/company/field and retains verified run evidence.

**Proofs:** P07, P15, P16, P20

**Depends on:** E10

## E13: plasticos_enrichment -> Historic crawl/extraction evidence [NO_CHANGE]

**Before:** Current pinned source as observed; see evidence register.

**After:** Preserve existing source, extraction and governance evidence. New Gate results are projected to proposal lines, not falsely inserted as AI material extractions.

**Source:** `plasticos_enrichment/models/enrichment_extraction.py@2dc516aa29718b4545faf67e79ca225589ac6d7f` blob `c3a3deb8535e50a9aa2d274ec0ea84f1c960da63`

**Files:** No code changes; explicit preservation

**No-change basis:** Historic extraction table has its own old meaning; no schema rewrite or silent orphan removal.

**Migration:** Do not infer installed row counts; additive migration gated by actual installed version, company/field-owner census and count-preserving backup.

**Recovery:** Review-only kill switch; restore exact DB+filestore from paired verified backup if required; preserve historical response/provenance.

**Security:** No public, portal or cross-company write. Server rechecks role/company/field and retains verified run evidence.

**Proofs:** P08, P20

**Depends on:** none

## E14: plasticos_enrichment -> Per-line review and CAS apply [EDIT]

**Before:** Current pinned source as observed; see evidence register.

**After:** Server-side approve/reject/skip; apply only approved, still-empty, currently allowlisted partner fields under row lock, exact source snapshot comparison and company check. One partner.write with per-field provenance in same transaction; accurate partial statuses.

**Source:** `plasticos_enrichment/models/enrichment_run.py@2dc516aa29718b4545faf67e79ca225589ac6d7f` blob `7307232d4abce258874b272d6a95e4dbb42560c2`

**Files:** `plasticos_enrichment/models/enrichment_run.py` (EDIT), `plasticos_enrichment/models/enrichment_proposal_line.py` (EDIT)

**No-change basis:** n/a

**Migration:** Do not infer installed row counts; additive migration gated by actual installed version, company/field-owner census and count-preserving backup.

**Recovery:** Review-only kill switch; restore exact DB+filestore from paired verified backup if required; preserve historical response/provenance.

**Security:** No public, portal or cross-company write. Server rechecks role/company/field and retains verified run evidence.

**Proofs:** P07, P09, P12, P13, P14, P16, P29

**Depends on:** E11, E12

## E15: plasticos_enrichment -> Legacy Inject and local profile write bypass [EDIT]

**Before:** Current pinned source as observed; see evidence register.

**After:** Keep action_inject as guarded compatibility route: require explicit line decisions, never auto-approve all, never execute retired local material injection. Legacy validated runs remain read-only.

**Source:** `plasticos_enrichment/models/enrichment_run.py@2dc516aa29718b4545faf67e79ca225589ac6d7f` blob `7307232d4abce258874b272d6a95e4dbb42560c2`

**Files:** `plasticos_enrichment/models/enrichment_run.py` (EDIT)

**No-change basis:** n/a

**Migration:** Do not infer installed row counts; additive migration gated by actual installed version, company/field-owner census and count-preserving backup.

**Recovery:** Review-only kill switch; restore exact DB+filestore from paired verified backup if required; preserve historical response/provenance.

**Security:** No public, portal or cross-company write. Server rechecks role/company/field and retains verified run evidence.

**Proofs:** P07, P08, P09, P20

**Depends on:** E14

## E16: plasticos_enrichment -> Gate retry/rollback and durable failure state [EDIT]

**Before:** Current pinned source as observed; see evidence register.

**After:** Preserve attempt identity, fail-closed typed exception, and separately committed failure evidence only after safe rollback. No leaked approval between attempts or unsafe commit of partner fields.

**Source:** `plasticos_enrichment/models/enrichment_run.py@2dc516aa29718b4545faf67e79ca225589ac6d7f` blob `7307232d4abce258874b272d6a95e4dbb42560c2`

**Files:** `plasticos_enrichment/models/enrichment_run.py` (EDIT)

**No-change basis:** n/a

**Migration:** Do not infer installed row counts; additive migration gated by actual installed version, company/field-owner census and count-preserving backup.

**Recovery:** Review-only kill switch; restore exact DB+filestore from paired verified backup if required; preserve historical response/provenance.

**Security:** No public, portal or cross-company write. Server rechecks role/company/field and retains verified run evidence.

**Proofs:** P16, P18, P29

**Depends on:** E14

## E17: plasticos_enrichment -> Run native form/list/button and evidence [EDIT]

**Before:** Current pinned source as observed; see evidence register.

**After:** Add native one2many proposed changes with per-line decisions, known-vs-unknown confidence/source and Apply Approved. Remove naked Inject bulk approval; status and audit views remain.

**Source:** `plasticos_enrichment/views/enrichment_run_views.xml@2dc516aa29718b4545faf67e79ca225589ac6d7f` blob `5aa91814c53a3eed7cef25e9206ece6447c8470a`

**Files:** `plasticos_enrichment/views/enrichment_run_views.xml` (EDIT)

**No-change basis:** n/a

**Migration:** Do not infer installed row counts; additive migration gated by actual installed version, company/field-owner census and count-preserving backup.

**Recovery:** Review-only kill switch; restore exact DB+filestore from paired verified backup if required; preserve historical response/provenance.

**Security:** No public, portal or cross-company write. Server rechecks role/company/field and retains verified run evidence.

**Proofs:** P06, P07, P22

**Depends on:** E14, E15

## E18: plasticos_enrichment -> Native contact Enrichment tab [EDIT]

**Before:** Current pinned source as observed; see evidence register.

**After:** Show pending review count and native read-only run/decision navigation on partner form; no new CRM or portal/website.

**Source:** `plasticos_enrichment/views/res_partner_enrichment.xml@2dc516aa29718b4545faf67e79ca225589ac6d7f` blob `53079c057d5bf149c92e5a85df37c2fba9021a63`

**Files:** `plasticos_enrichment/views/res_partner_enrichment.xml` (EDIT), `plasticos_enrichment/models/res_partner.py` (EDIT)

**No-change basis:** n/a

**Migration:** Do not infer installed row counts; additive migration gated by actual installed version, company/field-owner census and count-preserving backup.

**Recovery:** Review-only kill switch; restore exact DB+filestore from paired verified backup if required; preserve historical response/provenance.

**Security:** No public, portal or cross-company write. Server rechecks role/company/field and retains verified run evidence.

**Proofs:** P21, P22

**Depends on:** E17

## E19: plasticos_enrichment -> Company record rules and method permissions [CREATE]

**Before:** Current pinned source as observed; see evidence register.

**After:** Declare company-scoped rules for run/source/proposal/provenance, including shared-partner policy; enforce Odoo role checks at action/write/confirm. Handle existing rows without company safely in migration.

**Source:** `plasticos_enrichment/security/record_rules.xml@2dc516aa29718b4545faf67e79ca225589ac6d7f` (PROPOSED NEW source)

**Files:** `plasticos_enrichment/security/record_rules.xml` (CREATE), `plasticos_enrichment/security/ir.model.access.csv` (EDIT)

**No-change basis:** n/a

**Migration:** Do not infer installed row counts; additive migration gated by actual installed version, company/field-owner census and count-preserving backup.

**Recovery:** Review-only kill switch; restore exact DB+filestore from paired verified backup if required; preserve historical response/provenance.

**Security:** No public, portal or cross-company write. Server rechecks role/company/field and retains verified run evidence.

**Proofs:** P10, P11, P12, P13, P23

**Depends on:** E06, E10

## E20: plasticos_enrichment -> Addon import/manifest/registry/data order [EDIT]

**Before:** Current pinned source as observed; see evidence register.

**After:** Version bump above source 19.0.2.5.5 after installed-version evidence; load rules/proposal UI/ACL/test exports with correct Odoo 19 ordering. No new dependency on CRM bridge or Gate peers.

**Source:** `plasticos_enrichment/__manifest__.py@2dc516aa29718b4545faf67e79ca225589ac6d7f` blob `636647aaea9397a1125d76e7b7d894cc68b484f8`

**Files:** `plasticos_enrichment/__manifest__.py` (EDIT), `plasticos_enrichment/models/__init__.py` (EDIT), `plasticos_enrichment/tests/__init__.py` (EDIT)

**No-change basis:** n/a

**Migration:** Do not infer installed row counts; additive migration gated by actual installed version, company/field-owner census and count-preserving backup.

**Recovery:** Review-only kill switch; restore exact DB+filestore from paired verified backup if required; preserve historical response/provenance.

**Security:** No public, portal or cross-company write. Server rechecks role/company/field and retains verified run evidence.

**Proofs:** P19, P22, P23, P24

**Depends on:** E10, E19

## E21: plasticos_enrichment -> Upgrade/migration owner [NO_CHANGE]

**Before:** Current pinned source as observed; see evidence register.

**After:** Preserve original mothball migration and all old audit. Plan a NEW versioned 19.0.2.5.6 migration candidate only after installed version census; close broad rights and retire actual installed crons with evidenced source refs.

**Source:** `plasticos_enrichment/migrations/19.0.2.0.0/post-migrate.py@2dc516aa29718b4545faf67e79ca225589ac6d7f` blob `1f85d74778ed0a511a4c164cca8e5c5431cf18dd`

**Files:** No code changes; explicit preservation

**No-change basis:** Historical data migration is executed history; not safe to edit in place. Add a successor upgrade if necessary.

**Migration:** Do not infer installed row counts; additive migration gated by actual installed version, company/field-owner census and count-preserving backup.

**Recovery:** Review-only kill switch; restore exact DB+filestore from paired verified backup if required; preserve historical response/provenance.

**Security:** No public, portal or cross-company write. Server rechecks role/company/field and retains verified run evidence.

**Proofs:** P01, P19, P20, P26

**Depends on:** none

## E22: plasticos_enrichment -> Future versioned migration candidate [CREATE]

**Before:** Current pinned source as observed; see evidence register.

**After:** Additive schema/data reconciliation: identify/harden broad ACLs and old cron grant, ensure company scope only when unambiguous, leave historic Gate/local runs without fabricated review decisions; quarantines reported. Candidate path requires installed-version validation.

**Source:** `plasticos_enrichment/migrations/19.0.2.5.6/post-migrate.py@2dc516aa29718b4545faf67e79ca225589ac6d7f` (PROPOSED NEW source)

**Files:** `plasticos_enrichment/migrations/19.0.2.5.6/post-migrate.py` (CREATE)

**No-change basis:** n/a

**Migration:** Do not infer installed row counts; additive migration gated by actual installed version, company/field-owner census and count-preserving backup.

**Recovery:** Review-only kill switch; restore exact DB+filestore from paired verified backup if required; preserve historical response/provenance.

**Security:** No public, portal or cross-company write. Server rechecks role/company/field and retains verified run evidence.

**Proofs:** P01, P11, P19, P20, P26

**Depends on:** E20, E07, E09, E21

## E23: Odoo ADR owner -> CRM writeback ADR default contradiction [EDIT]

**Before:** Current pinned source as observed; see evidence register.

**After:** Append narrowly scoped supersession: old 1-switch auto default is historical; current code 2-switch OFF; new Gate enrichment runs always need field-level review until separately authorized. Keep eight-field allowlist and provenance.

**Source:** `docs/adr/ADR-012-crm-writeback-allowlist-provenance.md@2dc516aa29718b4545faf67e79ca225589ac6d7f` blob `0c0e0e51ff84d068489bade09295d8f84dfaf891`

**Files:** `docs/adr/ADR-012-crm-writeback-allowlist-provenance.md` (EDIT)

**No-change basis:** n/a

**Migration:** Do not infer installed row counts; additive migration gated by actual installed version, company/field-owner census and count-preserving backup.

**Recovery:** Review-only kill switch; restore exact DB+filestore from paired verified backup if required; preserve historical response/provenance.

**Security:** No public, portal or cross-company write. Server rechecks role/company/field and retains verified run evidence.

**Proofs:** P05, P14, P25, P28

**Depends on:** E11, E14

## E24: Odoo ADR owner -> Proposed successor for per-field approval [CREATE]

**Before:** Current pinned source as observed; see evidence register.

**After:** Proposed ADR for one source of truth, line review states, Gate-only fields, operator attestation, CAS, native ACL, audit and no auto-writeback; source owner assigns final numeric ADR ID.

**Source:** `docs/adr/PROPOSED-enrichment-granular-approval.md@2dc516aa29718b4545faf67e79ca225589ac6d7f` (PROPOSED NEW source)

**Files:** `docs/adr/PROPOSED-enrichment-granular-approval.md` (CREATE)

**No-change basis:** n/a

**Migration:** Do not infer installed row counts; additive migration gated by actual installed version, company/field-owner census and count-preserving backup.

**Recovery:** Review-only kill switch; restore exact DB+filestore from paired verified backup if required; preserve historical response/provenance.

**Security:** No public, portal or cross-company write. Server rechecks role/company/field and retains verified run evidence.

**Proofs:** P07, P14, P28

**Depends on:** E23

## E25: plasticos_enrichment -> Module README and version docs [EDIT]

**Before:** Current pinned source as observed; see evidence register.

**After:** Align frontmatter module version to target, replace false fallback/old default wording and document native review-only flow, disabled cron and external intelligence ownership.

**Source:** `plasticos_enrichment/README.md@2dc516aa29718b4545faf67e79ca225589ac6d7f` blob `3adf8424a7d5bd9c4326e84f6307ab7927fa394d`

**Files:** `plasticos_enrichment/README.md` (EDIT)

**No-change basis:** n/a

**Migration:** Do not infer installed row counts; additive migration gated by actual installed version, company/field-owner census and count-preserving backup.

**Recovery:** Review-only kill switch; restore exact DB+filestore from paired verified backup if required; preserve historical response/provenance.

**Security:** No public, portal or cross-company write. Server rechecks role/company/field and retains verified run evidence.

**Proofs:** P19, P23, P25

**Depends on:** E23

## E26: Odoo accepted ADR owners -> Existing external authority and trigger division [NO_CHANGE]

**Before:** Current pinned source as observed; see evidence register.

**After:** Preserve ADR-003/009/010/013/017 decisions: CEG ranks, EIE enriches, Gate routes, Odoo owns manual review; no CEG nightly queue adoption or new Odoo local selector.

**Source:** `docs/adr/ADR-009-enrichment-selection-ranking-not-in-odoo.md@2dc516aa29718b4545faf67e79ca225589ac6d7f` blob `9addd94c6afe4ce4305bc6c28326b29d292208e2`

**Files:** No code changes; explicit preservation

**No-change basis:** Existing ADRs already assert proper separation; avoid unnecessary constitutional churn. ADR-012 is the actual needed correction.

**Migration:** Do not infer installed row counts; additive migration gated by actual installed version, company/field-owner census and count-preserving backup.

**Recovery:** Review-only kill switch; restore exact DB+filestore from paired verified backup if required; preserve historical response/provenance.

**Security:** No public, portal or cross-company write. Server rechecks role/company/field and retains verified run evidence.

**Proofs:** P21, P28

**Depends on:** none

## E27: plasticos_enrichment -> Existing runtime Gate review tests [EDIT]

**Before:** Current pinned source as observed; see evidence register.

**After:** Replace tests asserting automatic live mode and one-click Inject with review-only even if config toggled, per-line identity/roles/CAS/idempotency and truthful no-eligible-fields, preserving transport failure tests.

**Source:** `plasticos_enrichment/tests/test_gate_enrichment_fallback.py@2dc516aa29718b4545faf67e79ca225589ac6d7f` blob `997638c340e78d1e1d36a6347535909d44e16d64`

**Files:** `plasticos_enrichment/tests/test_gate_enrichment_fallback.py` (EDIT)

**No-change basis:** n/a

**Migration:** Do not infer installed row counts; additive migration gated by actual installed version, company/field-owner census and count-preserving backup.

**Recovery:** Review-only kill switch; restore exact DB+filestore from paired verified backup if required; preserve historical response/provenance.

**Security:** No public, portal or cross-company write. Server rechecks role/company/field and retains verified run evidence.

**Proofs:** P05, P07, P16, P17, P18, P25

**Depends on:** E14, E15, E11

## E28: plasticos_enrichment -> New Odoo 19 Enterprise runtime tests [CREATE]

**Before:** Current pinned source as observed; see evidence register.

**After:** Add real ORM/Enterprise tests: 2 of 3 approval, source metadata, stale conflict, role/company, invalid fields, race, legacy history, disabled cron, install+upgrade. Register through tests/__init__.py.

**Source:** `plasticos_enrichment/tests/test_field_proposal_review.py@2dc516aa29718b4545faf67e79ca225589ac6d7f` (PROPOSED NEW source)

**Files:** `plasticos_enrichment/tests/test_field_proposal_review.py` (CREATE)

**No-change basis:** n/a

**Migration:** Do not infer installed row counts; additive migration gated by actual installed version, company/field-owner census and count-preserving backup.

**Recovery:** Review-only kill switch; restore exact DB+filestore from paired verified backup if required; preserve historical response/provenance.

**Security:** No public, portal or cross-company write. Server rechecks role/company/field and retains verified run evidence.

**Proofs:** P05, P06, P07, P10, P11, P12, P13, P14, P15, P16, P20, P22, P24

**Depends on:** E20, E27

## E29: plasticos_security_base -> Upstream security action-method regression consumer [EDIT]

**Before:** Current pinned source as observed; see evidence register.

**After:** Update test_action_inject to assert no old bulk bypass, then make new explicit review flow positive. Preserve all unrelated security-base tests.

**Source:** `plasticos_security_base/tests/test_action_methods.py@2dc516aa29718b4545faf67e79ca225589ac6d7f` blob `7215d3af74a2099e2736ef35c39f3dc8acea90ce`

**Files:** `plasticos_security_base/tests/test_action_methods.py` (EDIT)

**No-change basis:** n/a

**Migration:** Do not infer installed row counts; additive migration gated by actual installed version, company/field-owner census and count-preserving backup.

**Recovery:** Review-only kill switch; restore exact DB+filestore from paired verified backup if required; preserve historical response/provenance.

**Security:** No public, portal or cross-company write. Server rechecks role/company/field and retains verified run evidence.

**Proofs:** P07, P09, P25

**Depends on:** E15

## E30: Odoo test/release owner -> Source-level writeback regression and audit baseline [EDIT]

**Before:** Current pinned source as observed; see evidence register.

**After:** Update source assertions for current class and guard semantics, keep convergence and allowlist proofs; do not reset tech-debt baseline or create unaudited skip.

**Source:** `tests/test_enrichment_gate_writeback.py@2dc516aa29718b4545faf67e79ca225589ac6d7f` blob `539a32813d62ef7e3dfdedaa003d72d4cfffea28`

**Files:** `tests/test_enrichment_gate_writeback.py` (EDIT)

**No-change basis:** n/a

**Migration:** Do not infer installed row counts; additive migration gated by actual installed version, company/field-owner census and count-preserving backup.

**Recovery:** Review-only kill switch; restore exact DB+filestore from paired verified backup if required; preserve historical response/provenance.

**Security:** No public, portal or cross-company write. Server rechecks role/company/field and retains verified run evidence.

**Proofs:** P25, P32

**Depends on:** E27

## E31: Odoo module owner -> Historical source and extract models [NO_CHANGE]

**Before:** Current pinned source as observed; see evidence register.

**After:** Keep source URLs, crawl status, extractions, source row UUIDs/IDs and attached evidence unchanged; no backfill from EIE to retired local extraction models.

**Source:** `plasticos_enrichment/models/enrichment_source.py@2dc516aa29718b4545faf67e79ca225589ac6d7f` blob `8879b9a8692313a896d29b4a825378de6a419576`

**Files:** No code changes; explicit preservation

**No-change basis:** No active crawl/extract owner left; model remains needed to interpret old evidence.

**Migration:** Do not infer installed row counts; additive migration gated by actual installed version, company/field-owner census and count-preserving backup.

**Recovery:** Review-only kill switch; restore exact DB+filestore from paired verified backup if required; preserve historical response/provenance.

**Security:** No public, portal or cross-company write. Server rechecks role/company/field and retains verified run evidence.

**Proofs:** P20, P26

**Depends on:** none

## E32: Odoo module owner -> Existing material profile/partnerless CRM seam [NO_CHANGE]

**Before:** Current pinned source as observed; see evidence register.

**After:** No enrichment-initiated supplier partner, material profile creation or CRM/Won effect; only allowlisted existing partner fields.

**Source:** `plasticos_material_profile/__manifest__.py@2dc516aa29718b4545faf67e79ca225589ac6d7f` blob `3f590b923e579c68382b1361bcdf3242a62312f6`

**Files:** No code changes; explicit preservation

**No-change basis:** Different commercial data owner; per-field CRM enrichment cannot become opportunity/material promotion.

**Migration:** Do not infer installed row counts; additive migration gated by actual installed version, company/field-owner census and count-preserving backup.

**Recovery:** Review-only kill switch; restore exact DB+filestore from paired verified backup if required; preserve historical response/provenance.

**Security:** No public, portal or cross-company write. Server rechecks role/company/field and retains verified run evidence.

**Proofs:** P08, P21, P28

**Depends on:** none

## E33: Odoo primary operation owner -> Existing run sequence and retired scheduler independence [NO_CHANGE]

**Before:** Current pinned source as observed; see evidence register.

**After:** Retain original run sequence, no new enrichment job or autonomous ranking scheduler; installed runtime safety must still be verified.

**Source:** `plasticos_enrichment/data/sequence.xml@2dc516aa29718b4545faf67e79ca225589ac6d7f` blob `4555e93dbbba4c0815f40f98be886df888a8caef`

**Files:** No code changes; explicit preservation

**No-change basis:** Sequence is not a scheduled job and needs no new numbering semantics. No additional module should own ranking or duplicate enrichment state.

**Migration:** Do not infer installed row counts; additive migration gated by actual installed version, company/field-owner census and count-preserving backup.

**Recovery:** Review-only kill switch; restore exact DB+filestore from paired verified backup if required; preserve historical response/provenance.

**Security:** No public, portal or cross-company write. Server rechecks role/company/field and retains verified run evidence.

**Proofs:** P01, P19, P24

**Depends on:** none
