```yaml
repository_access:
  writable:
    - https://github.com/cryptoxdog/IB-Odoo_19
  read_only:
    - https://github.com/Quantum-L9/Cursor-Governance
    - https://github.com/Quantum-L9/.github
  unlisted_repositories: no_access
```

# PlasticOS | One Production ERP/CRM Import Seam | One PR | Hardened v1.1, amended v1.2

**Read this first, then execute `C00` through `C05` as a single bounded coding campaign.**
**Amendment v1.2:** `13_AMENDMENT_v1.2_OPERATOR_DECISIONS.md` records operator decisions D1–D4 (2026-10-30) and prevails over any conflicting v1.1 text below.
**Publication authorization:** exactly one repository-local `make pr` against `Staging` (D1); no merge, deployment or Production data write is authorized by this pack.

## Frozen objective

Enable an *operator-authorized* Odoo.sh Production ERP SQL import followed by historical VanillaSoft CRM + live delta, using current Odoo 19 services. First implement and validate on one isolated branch, then publish one PR. User defers worksheet images and attachment-to-transaction imports. User defers full AWS DR rollout, broad business UAT and Production migration rehearsal, **not** a native pre-change Production restore checkpoint.

## Source coordinates and correction to predecessor

- Current observed source: [`IB-Odoo_19` Staging@`42556d2e5e7434be43f2ff7f89e66b1c8ee6c15a`](https://github.com/cryptoxdog/IB-Odoo_19/commit/42556d2e5e7434be43f2ff7f89e66b1c8ee6c15a), PR #345 index-only and #346 sale/load both **OPEN** on 2026-10-30. Create `feat/production-erp-crm-bootstrap` from the actual verified clean `Staging` head. **Do not wait for #346 to merge** as a ceremonial dependency; rebind/rebase/inspect overlap and rerun tests if Staging changes.
- `Cursor-Governance` observed main@`f47c256b2c282b51a22b416f28466d60018e299f` and `.github` observed main@`3dcdeaae355b6de08562993f705084d7a3714bfd`. These observations are **not canonical projection admission or publication proof**. The publication chain and actual command must be source-verified again at the terminal publication step. L9 semantic projection receipts = **UNKNOWN**, not PASSED.
- Working cutover graph: `PlasticOS_Plan_Graph_Overnight_Cutover_2026-10-30.zip` files `26_OPERATOR_OVERNIGHT_CUTOVER_DECISION.md` and `27_OVERNIGHT_CUTOVER_EXECUTION_GRAPH.json`. Earlier `23_RELEASE_CHECKPOINT_2026-10-30.md` contains the pre-decision rehearsal/DR blockers; the operator's later deferral in 26 controls this working cutover plan, without granting admitted L9 authority.
- Owner docs: `docs/adr/ADR-021-erp-sql-crm-api-import.md` and full-cohort contract `docs/campaigns/PlasticOS_ERP_Then_Full_VanillaSoft_Cursor_Delegation_v2_2026-10-21/CURSOR_EXECUTION_CONTRACT.md`. Reconcile historical pack stale assumptions against currently bound source. Never use frozen CSV as runtime importer.
- Supplied schema: `REFERENCE_OPERATOR_SCHEMA_v1.1.0.md` is an unedited reference copy; six YAML contracts are the executable planning instructions and use the required fields. This package is **not** code or actual GAR delegation-compilation proof.

## One dependency path, not six PRs

| Phase | Source owner / outcome | Can complete locally without Production credentials? |
|---|---|---|
| C00 | Bind worktree, exact SHA, import dependency/side-effect census, classify live unknowns | Yes, if relevant local source readable |
| C01 | Production permit on `validate_partner_layer` and its owner; negative tests | Yes, simulated production target only |
| C02 | Existing `import_erp_shell` Odoo.sh native adapter and restart-safe replay | Yes for code; host transport proof still cutover-blocking |
| C03 | Import disposition and financial state truth; no unapproved posting | Yes for current supported semantics; source actual-status admission separate |
| C04 | Existing `plasticos_crm_sync` per-ID history runner, durable identity-aware checkpoint | Yes for code; live provider proof still cutover-blocking |
| C05 | Integrated Enterprise baseline diff, exact-owner CI/gates, **one** `make pr` | Yes only when required code-side checks passed; no import-ready claim without live proofs |

**All changes, tests, and fixes accumulate on the SAME branch.** No phase authorizes an interim PR. Stop only the affected slice if the real source owner/authority or a security/accounting design choice is unresolved. No invented new ETL, service, authentication provider, source credential, API, ERP mapping, native posting status or arbitrary scope expansion.

## Hard import safety law

1. Production is **default DENY**. A deliberate bounded operator permit binds actual DB identity (not name alone), Odoo.sh build/stage, release SHA, immutable ERP source snapshot, import phase and expiry/run identity. Missing/mismatched/replayed permit or contaminated first-import target is DENY. Operator must approve one planned overnight workflow; the agent cannot generate authorization by checking its own box. Keep scratch/staging tests denied unless explicitly target-simulated.
2. Phase sequence: active-only ERP partners -> full ERP native SO/PO/draft invoice/bill reconstruction + compiled transactions -> one exact-ID VanillaSoft 4,876 snapshot cohort -> current API delta -> read-only reconciliation. The historic 4,876 cohort does **not** establish all-current contacts; report absent source-total proof as UNKNOWN.
3. `ERP_LIMIT` is for diagnostics only. Never use `25%` as a completion claim or a chunk cursor. Source and destination snapshots must remain fixed across sessions. Crash after commit and before checkpoint must replay without duplicate invoices, payables or provider refs. If no genuinely bounded restart-safe hosted execution path exists, do not authorize the overnight import.
4. Historical source accounting status remains UNRESOLVED where no approved status/booking mapping exists. Existing `account.move` draft creation is a code fact, **not proof of source-accurate actual status**. Do not post bills/invoices or manufacture payments to get a green suite. This blocks *accounting data acceptance*, not honest coding PR publication.
5. Keep `import_mode`, `skip_procurement`, mail/Linda non-release and disabled overlapping CRM cron. DNC remains a contact restriction and excluded inactive ERP aliases remain excluded. Source ID crosswalk: 763 YES, 18 NO, 4,095 PENDING; 759 actual crosswalk ContactIDs and four omitted duplicate YES IDs, exact input hashes reverified before any run. *(v1.2: runtime crosswalk is the packaged pin `9aa6fcd0…72c1`; private inputs are external runtime inputs, D3.)*
6. Do not open SQL Server publicly, transfer legacy grids into Odoo.sh as alternative runtime source, write to source ERP, wipe Production data, or activate customer notifications. Worksheet images/documents remain excluded from all gates.

## Four independent readiness verdicts

| Verdict | When allowed | What it does NOT imply |
|---|---|---|
| **PR_PUBLISHABLE** | Bounded code, local proof, current test differential, publisher source checked | Not merge/Production/import ready |
| **MERGE_PROMOTION_READY** | Required ten-test closure, immutable integrated Enterprise suite green, release code + approvals | Not ERP SQL reachable nor CRM history complete |
| **HOSTED_IMPORT_READY** | Operator approval + actual Odoo.sh target/source/driver/API reachability, current snapshot, clean-target and restart probe, native checkpoint | Not that imported data is accepted |
| **POST_IMPORT_DATA_ACCEPTED** | Actual ERP+CRM disposition receipts, clear unresolved exceptions, accepted status semantics, current delta accounted | Not inferred from shell exit=0 or imported snapshot size |

If live runtime is inaccessible, produce code and PR with `HOSTED_IMPORT_READY=NOT_RUN/BLOCKED`, never call it a successful cutover. **For a same-night promotion and import event, prove hosted source/CRM connectivity and current SQL/ID source readiness before the Production promotion begins**, even though code-only PR publication need not wait on those operational probes. Report blockers by owner. DO NOT run the actual import under this delegation.

## One publication interface

*(Amended v1.2 D1.)* Before publication, verify the **repository-local** chain: the `IB-Odoo_19` `Makefile` target `pr` -> `scripts/make_push_pipeline.sh` (clean-tree preflight, `pr-check`, L4, single push, PR into `Staging`). Run `make pr` once from the exact clean feature worktree. Do not call raw `git push`, `gh pr create`, or API publication. When any source owner or path is UNKNOWN, block publication without inventing a substitute.

## How to proceed and hand off

1. Load `C00_EXACT_BIND_AND_PREFLIGHT.yaml`; perform source and optional read-only host discovery, classify UNKNOWN by proof stage, pin revision and owner graph. No source-absent assertions.
2. Run C01 -> C02 -> C03 -> C04 sequentially in same worktree, with each phase reporting changed files, validation evidence, negative controls and remaining UNKNOWN. Allow only local implementation discretion that preserves the locked semantic envelope; if public authority changes, escalate.
3. Execute C05 after a single integrated code census. Compare full Enterprise suite with an independently observed, same-fixture base. If historical ten failures are still present, record `PR_PUBLISHABLE` separately from `MERGE_PROMOTION_READY` and refrain from hiding baseline red.
4. Terminal publication only once through verified `make pr` and read back actual PR number/head/base/check status. A command's existence is not publication evidence. Do not merge or deploy.
5. Handoff the short post-merge operator gating plan. A Production run needs new human authorization, current ERP source and the real hosted proof. No customer-impacting side effect during this coding campaign.

**Read:** `07_SOURCE_AND_ACCEPTANCE.md`, `09_EXECUTION_GATE_MATRIX.md`, `10_HARDENING_AND_DIFFERENTIAL.md` and all six C00-C05 YAML contracts. `08_VALIDATION.json` is package-level structural proof only.
