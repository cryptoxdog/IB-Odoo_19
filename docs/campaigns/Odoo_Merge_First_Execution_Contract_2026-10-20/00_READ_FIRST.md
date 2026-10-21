# Odoo 19 Merge-First Campaign | Cold Start

**Primary mission:** converge and merge all ready, currently open `Staging` PRs (#260 through #266) in `cryptoxdog/IB-Odoo_19` as quickly as safely possible, then resolve the independent `Development` PR #197. This is a release-integration campaign, **not** another open-ended audit or a new CI architecture campaign.

**Read in this order:** `MERGE_EXECUTION_CONTRACT.md` -> `PR_BINDINGS.json` -> `WORK_STATE.yaml` -> `MANIFEST.json`.

**Executor:** a fresh, user-invoked Claude Code session with GitHub access, using the existing `l9-pr-remediation` skill and its `pr_fleet.py`, `pr_board.py`, `stack_safe_merge.py`, and review-thread machinery in `Quantum-L9/Cursor-Governance`. Do not assume the capability is available until checked. The operator can paste `START_CLAUDE_CODE.md` as their actual instruction.

**Authority order:** actual user instruction > target Odoo repository's governing law > relevant Cursor-Governance skill's merge gates > this handoff > stale audits or PR prose. **Odoo's own existing `make pr` plumbing is the publishing exception**; do not apply the L9 SSOT Makefile publishing doctrine to Odoo. Merge execution remains subject to GitHub protection and the governance stack-safe merge authority.

**Freshness rule:** all PR SHAs in `PR_BINDINGS.json` are a discovery snapshot, not an instruction to merge a stale head. Re-fetch immediately before every edit/merge, then bind the exact live head. Do not reuse old green CI after a head moves.

**Critical distinction:** This ZIP is a bounded execution contract and skill-routed handoff, not a validated canonical `l9-pr-audit` bundle and not a merge authorization by itself. Human authorization must be obtained from the operator's actual message or a valid GitHub approval record under the host merge gate. **Nothing has been merged by creation of this ZIP.**
