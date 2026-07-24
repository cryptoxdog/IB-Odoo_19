---
name: CI Config Drift Cleanup
overview: "Re-verified (no content changes needed): evidence-backed plan to close 3 confirmed drift findings from the pyproject.toml / conftest.py / CI workflow audit — unpinned semgrep in l9-analysis.yml, dangling baseline-ratchet.yml references in 3 files, and stale security.yml documentation in AGENTS.md. Doc/config-only, zero behavior change, git-reversible."
todos:
  - id: PI-01-fix-l9-analysis-yml
    content: "l9-analysis.yml: pin semgrep==1.164.0 (line 89) + remove dangling baseline-ratchet.yml reference from L9_CORE_REF comment (lines 25-27)"
    status: pending
  - id: PI-02-fix-governance-readme
    content: "governance/README.md: remove dangling baseline-ratchet.yml reference (lines 37-40)"
    status: pending
  - id: PI-03-fix-agents-md
    content: "AGENTS.md: remove baseline-ratchet.yml row (line 292), rewrite security.yml row as tombstone (line 293), remove dependency-scan/trivy-scan advisory rows (lines 320-321)"
    status: pending
  - id: PI-04-verify
    content: Run verification grep sweep (baseline-ratchet, semgrep pin, dependency-scan/trivy-scan) and confirm AGENTS.md workflow table row count = 9
    status: pending
isProject: false
---

## Verification pass (2026-07-24)

Re-read all three target files plus their cross-references (`Makefile`, `ci.yml`, `.github/workflows/` directory listing) against the current working tree. Every finding, line number, and before/after text block from the original plan still matches disk exactly. No plan content changed — this is a re-confirmation, not a revision.

**Confirmed still true right now:**
- [.github/workflows/l9-analysis.yml](.github/workflows/l9-analysis.yml) line 89: `pip install --upgrade pip semgrep` (unpinned) vs. `Makefile:148` / `ci.yml:80` both pinning `semgrep==1.164.0`.
- `l9-analysis.yml` lines 25-27 and [.github/governance/README.md](.github/governance/README.md) lines 37-40 both still reference `.github/workflows/baseline-ratchet.yml`, which does not exist — confirmed exactly 9 files in `.github/workflows/`: `auto-merge.yml`, `auto-review-request.yml`, `changelog.yml`, `ci.yml`, `l9-analysis.yml`, `pr-autopilot.yml`, `release.yml`, `repo-index.yml`, `security.yml`.
- [AGENTS.md](AGENTS.md) line 292 still lists a phantom `baseline-ratchet.yml` table row.
- `AGENTS.md` line 293 still describes `security.yml` as running `pip-audit, Trivy, Gitleaks` on push/PR/weekly, but the file on disk is confirmed a tombstone (`workflow_dispatch` only, single `placeholder` job, header comment "REMOVED — all checks duplicated by ci.yml").
- `AGENTS.md` lines 320-321 still list `dependency-scan`/`trivy-scan` advisory rows against that tombstoned workflow.

Note: `git status` shows `AGENTS.md` and `ci.yml` as modified-but-uncommitted, and `l9-analysis.yml` + `.github/governance/` as untracked, on branch `docs/agent-docs-refresh-and-repo-index`. This doesn't affect any line number or text block targeted below — all edits remain local/unpushed as the plan already assumed.

## Plan Items (unchanged from prior draft)

### PI-01 — l9-analysis.yml: pin semgrep, drop dead sibling-workflow comment
- Line 89: `pip install --upgrade pip semgrep` → `pip install --upgrade pip "semgrep==1.164.0"`
- Lines 25-27 env comment: remove `# Keep in lockstep with .github/workflows/baseline-ratchet.yml's core-revision.` → replace with a comment describing what `L9_CORE_REF` pins (no baseline-ratchet mention), value `d81a06ed821106a487df2e5ad06d93e347392af6` unchanged.
- Acceptance: `grep -n 'semgrep==1.164.0'` matches; `grep -n 'baseline-ratchet'` returns zero matches in this file.

### PI-02 — governance/README.md: remove dangling baseline-ratchet.yml reference
- Lines 37-40: rewrite the "Pin" section prose so it no longer claims `baseline-ratchet.yml` trusts the same commit — keep the SHA and the "bump deliberately" guidance, drop the sibling-workflow claim.
- Acceptance: `grep -n 'baseline-ratchet'` returns zero matches; SHA string unchanged.

### PI-03 — AGENTS.md: correct workflow and advisory tables
- Line 292: delete the `baseline-ratchet.yml` row entirely.
- Line 293: rewrite `security.yml` row to `| \`security.yml\` | manual only (\`workflow_dispatch\`) | Tombstone — disabled; all checks moved to \`ci.yml\`'s \`secret-scan\` job |`.
- Lines 320-321: delete the `dependency-scan` and `trivy-scan` advisory rows.
- Acceptance: zero `baseline-ratchet`/`dependency-scan`/`trivy-scan` matches; active-workflow table body row count = 9.

### PI-04 — Verification sweep (after PI-01–PI-03)
- `grep -rn "baseline-ratchet" .` → zero results.
- `grep -n "semgrep" .github/workflows/l9-analysis.yml` → shows `semgrep==1.164.0`.
- `grep -rn "dependency-scan|trivy-scan" .` → zero results.
- Manual row count of `AGENTS.md`'s active-workflow table = 9, matching `ls .github/workflows/*.yml | wc -l`.

## Execution waves
Wave 1 (parallel, independent files): PI-01, PI-02, PI-03. Wave 2 (sequential): PI-04.

## Risk / rollback
Low risk — comment/prose/version-pin only, no behavior change. Each item reverts independently via `git checkout -- <path>`. Commit and push each remain separate, explicit user instructions per `99-no-auto-commit.mdc` / `01-git-push-prohibition.mdc` — this plan stops at file edits.