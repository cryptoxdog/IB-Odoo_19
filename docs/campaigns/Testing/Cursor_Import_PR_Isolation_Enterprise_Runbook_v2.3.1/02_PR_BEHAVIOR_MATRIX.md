# 02. Trees and the single behavior list

`BEHAVIOR_CATALOG.csv` names every behavior. This file says which tree each lane uses. Do not invent a second set of IDs.

## Trees

| Catalog lane | Test this tree | Do not substitute |
|---|---|---|
| `Staging` (`S-*`) | Current `Staging` | A historical PR head for an already-merged import |
| `M301` (`301-*`) | Merge of current `Staging` and PR #301 | PR #301's raw tip, when that tip does not contain `Staging` |
| `M303` (`303-*`, `303-DIAG-*`) | Merge of current `Staging` and PR #303 | The older executable baseline `702ebaf` when the PR head has moved |
| `BOTH` | Merge of the M301 tree and the M303 tree | A claim that M301's pass plus M303's pass is the combined result |

Re-resolve the SHAs at run time. Record `git rev-parse HEAD` and `git rev-parse HEAD^{tree}` for each worktree. A dirty worktree is `BLOCKED_SOURCE_DIRTY`.

## Rows to repeat on BOTH

Run these catalog rows again on the BOTH tree, and keep the same IDs. Add `tree=BOTH` on the evidence row.

- Every `301-*` row. Both PRs touch `plasticos_transaction`.
- `303-C`, `303-F`, `303-G`, and `303-DIAG-E`. These are the import-facing transaction, document, and worksheet behaviors on #303.
- `S-10`, `S-11`, `S-12`, `S-13`, `S-14`. These are the commercial behaviors a transaction-module merge can disturb.

`303-DIAG-A1` through `303-DIAG-C3`, `303-DIAG-UNLINK`, and `303-DIAG-POST` stay visible. Run one only when its owning addon is already in the authorized module list below. Do not add a claims, offer, commission, matching, or logistics module run in order to turn a Community report green.

## Authorized Enterprise modules

| Tree | `make test-module` modules |
|---|---|
| M301 | `plasticos_transaction` |
| M303 | `plasticos_transaction`, `plasticos_partner_import` |
| BOTH | `plasticos_transaction`, `plasticos_documents` |

One fresh owned clone per invocation. The runner upgrades the full PlasticOS roster on that clone and limits tests to `m=`. Logistics code that #303 already contains may load. That load is not a logistics test and not a logistics acceptance.

## Retired v2.3.1 matrix letters

The old matrix reused `301-A` through `301-H` for a different sequence. Use the catalog meaning.

| Retired matrix letter | Catalog ID that actually matches it |
|---|---|
| Matrix `301-A` (header, plus a row-fallback test) | `301-A` covers the header. The row-fallback pure test is extra evidence on that same ID, not a new ID. |
| Matrix `301-B` (matched and unmatched terms together) | `301-B` and `301-C` |
| Matrix `301-C` (undated vendor bill) | `301-D` |
| Matrix `301-D` (earliest trade date) | `301-E` |
| Matrix `301-E` (Delivered is not FAS) | `301-F` |
| Matrix `301-F` (no stock picking) | `301-G` |
| Matrix `301-G` (missing customer invoice date) | `301-H` |
| Matrix `301-H` (draft, no payment) | `301-I` |
| `S-C1` | `S-02` and `S-03` |
| `S-C2` | `S-05` |
| `S-C3` | `S-04` |
| `S-C4` | `S-06` |
| `S-C5` | `S-07` |
| `S-C6` | `S-08` |
| `S-M1` | `S-09` |
| `S-E1` | `S-10` |
| `S-E2` | `S-12` |
| `S-E3` | `S-13` |

`S-01`, `S-11`, and `S-14` had no matrix ID. They stay in the catalog.

## How to score

A behavior passes only when its named test ran on the tree in the table and the assertion held. A green module count does not pass a behavior whose method is absent from the log. A pure-test pass does not pass the ORM column. M301 does not prove M303. M303 does not prove M301. BOTH is the only combined score.

`303-DIAG-*` owners in the catalog are the owners on the #303 tree after the test move: claims recovery and `TestOfferBridge` live in `plasticos_claims`, `TestOfferActions` lives in `plasticos_security_base`, and the ACL classes live in `plasticos_commission`. Those paths are wrong if read against current `Staging`, where the same classes are still under root `tests/`.

Technical verdict and business-fidelity verdict stay separate. Draft historical bills can be implementation-correct and still be a business-fidelity decision. Write the proposed remediation. Do not apply it.
