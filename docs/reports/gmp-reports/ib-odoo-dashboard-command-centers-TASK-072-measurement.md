# TASK-072 — Auto-Sort measurement against the v2.0 targets (synthetic part)

Campaign `ib-odoo-dashboard-command-centers`, LANE-E. Unknowns UNK-005 and UNK-007. Requirements: Document AI Prompt Requirements v2.0, section E. Model: DeepSeek Flash, non-thinking (DEC-016).

**Outcome: no target is measured yet.** No model output exists for any document. Every target below is UNKNOWN. That is not a failure and not a pass.

## Status of each measurement input

| Input | Status | Why |
|---|---|---|
| Harness (TASK-074, `plasticos_documents_ai/eval/harness.py`) | Built, tested offline | Scores recorded outputs: the six v2.0 metrics, the confusion matrix, the regression replay, and since TASK-073 the benefit of each specialist |
| Synthetic labeled set `synthetic_v1` (dataset 1.0.0) | 57 cases | Written descriptions of fictional documents. 1 is human-corrected and counts only toward overwrites. 2 have no defensible type. 56 are classification cases. |
| Recorded P1 output on the synthetic set | **NOT RUN** | The UNK-006 live probe has not run: no DeepSeek key on this host, and the operator's key is set only on Staging |
| Recorded P2–P7 output | **NOT RUN** | Same reason. Every specialist stays inactive (TASK-073) |
| Operator's labeled Staging set (UNK-007) | **PENDING** | Behind GATE-005. Size: UNKNOWN |
| Invoice learning runtime tests | Written, **NOT RUN** here | `plasticos_documents_native/tests/test_invoice_learning.py`. They run under `odoo --test-enable` (the `make pr` smoke stage on a host with Docker and the Enterprise fixture). A cloud session skips that stage. |
| Staging repeat-upload protocol (3 vendors × 3 bills) | **PENDING** | Behind GATE-005 |

The checked-in recordings (`eval/recorded/harness_fixture_*.py`) are hand-written to test the scorer. No number computed from them describes any model. This report quotes none of them.

## v2.0 targets

| Metric | Provisional target | Synthetic set | Labeled Staging set |
|---|---|---|---|
| Auto-routed share | ≥ 80 % | UNKNOWN (no recorded output) | UNKNOWN (GATE-005) |
| Primary-family accuracy among routed | ≥ 90 % | UNKNOWN | UNKNOWN |
| Human classification intervention | ≤ 20 % | UNKNOWN | UNKNOWN |
| Unnecessary review | measured and minimized | UNKNOWN | UNKNOWN |
| Unauthorized business actions | 0 | UNKNOWN as a model measurement. Enforced by the application regardless of the model; see below | UNKNOWN |
| Human-correction overwrites | 0 | UNKNOWN as a model measurement. Enforced by the TASK-070 bridge | UNKNOWN |

A target is claimed met only after a representative labeled set has been measured. That set is the operator's Staging set after GATE-005, and its size goes in this table. A synthetic recording measures the prompt on fictional descriptions only. It says nothing about real documents.

### What holds without a measurement

These are code properties, not model results. Their tests are listed. The Odoo runtime tests were NOT RUN on this host.

- **Tools.** P1 carries only move-in-folder and add-tags. P2–P7 carry add-tags only. No bill, invoice, activity, code or webhook tool. Tests: `test_autosort_p1.py`, `test_autosort_specialists.py`.
- **Tags.** A Plasticos rule adds only its prompt's tags and never Verified. A specialist adds a type from another family only together with Needs Review, and cannot move a document even when its rule is edited. Code: `models/documents_document.py`.
- **No chaining.** No AI action starts another AI action, because Enterprise runs Auto-Sort tools under `ai_documents_skip_autosort`. The tests count every rule run across all seven rules.
- **Human precedence.** A human-set `doc_type` is never overwritten by a tag. Code: TASK-070, `plasticos_documents_native`.

## Specialist benefit (TASK-073)

**Post-P1 refinement is not provided** (CTO decision, 2026-11-21). Enterprise runs every Auto-Sort tool under `ai_documents_skip_autosort`, so a P1 move never starts the destination folder's rule. No code here starts one AI action from another. A specialist refines only three entry paths:

- a direct upload into its folder;
- a person's move into its folder;
- a manual *AI Sort*.

GATE-006 benefit is measured on those entry paths only. If measurement later shows that P1 alone misroutes enough to need refinement, that is a new operator decision outside this campaign.

`harness.score_specialist` compares a specialist with P1 alone on the labeled cases of its family. Each case is read as a document arriving in the folder untyped. Benefit requires all of:

- strictly higher exact-type accuracy than P1;
- no unauthorized action;
- no more unnecessary review than P1.

Missing outputs or an empty family make the verdict unknown, never a benefit.

| Specialist | Family cases in `synthetic_v1` | Verdict | Activation |
|---|---|---|---|
| P2 Bills of Lading | 8 | UNKNOWN (no recorded output) | Stays inactive |
| P3 Scale Tickets | 5 | UNKNOWN | Stays inactive |
| P4 Loading Pictures | 5 | UNKNOWN | Stays inactive |
| P5 Orders and Shipping | 12 | UNKNOWN | Stays inactive |
| P6 Financial | 13 | UNKNOWN | Stays inactive |
| P7 Compliance | 11 | UNKNOWN | Stays inactive |

Activating a specialist is an operator act after GATE-006. The activation wizard requires the GATE-006 reference.

## Invoice learning (native, not AI)

Document AI classifies and routes. It does not digitize bills. Native digitization learns from corrections through two mechanisms. The new runtime tests assert both under the Plasticos bill guard:

1. **Posting a corrected digitized bill queues the corrected values.** `extract_state` becomes `to_validate` and the `account_invoice_extract.ir_cron_ocr_validate` cron is triggered. The cron then sends the corrected reference, total, vendor and line prices, not the first OCR read, and sets `done`. Enterprise source: `account_invoice_extract/models/account_invoice.py:232-237` (`_post` → `_validate_ocr`); the mixin `_validate_ocr` / `_cron_validate` in `iap_extract`.
2. **The next bill of the same detected layout is predicted.** Its vendor comes from the earlier bill with that layout (`_find_partner_from_previous_extracts`, `account_invoice.py:276-298`). Its line account comes from that vendor's posted bills for the same label (`account_accountant/models/account_move.py:834-1030`). It stays in draft: the Plasticos guard never auto-posts a digitized bill.

The IAP service is replaced in the tests; nothing is sent. Whether the live OCR service improves on a vendor's third bill is a Staging question. The protocol below answers it.

### Staging repeat-upload protocol (after GATE-005)

1. Pick 3 vendors and 3 bills each.
2. Upload bill 1 of a vendor.
3. Correct what the OCR misread, then post.
4. Let the validate cron run.
5. Upload bill 2, then bill 3, recording for each:
   - vendor found (yes or no);
   - lines found (count right or wrong);
   - each line's account right or wrong;
   - fields the person had to correct.

Report the 9 bills as a table. Claim no improvement from fewer than 3 bills per vendor.

## Operator observation (unverified)

The operator reported that DeepSeek Flash classified better than GPT-4o. This report records that as an **unverified operator observation**. No comparative run exists in this campaign and none is claimed. Thinking mode is not enabled anywhere: the adapter always sends `reasoning: {effort: none}`, and nothing switches it automatically.

## Next prompt version

A new prompt version (P1 > 1.0.0, or a specialist > 1.0.0) must:

- cite the real misclassified cases it corrects;
- show the expected correction;
- pass the regression replay against the previous version on previously correct documents (`harness.py --baseline`).

Version 1.0.0 cites none because no real document has reached the model.

## To finish UNK-005 and UNK-007

1. **UNK-006:** run the synthetic live probe on Staging with the operator's key.
2. **Synthetic recordings:** record P1, and P2–P7 in their folders, on `synthetic_v1` with the same key. Score them with `harness.py --recorded … --specialists …`, then fill the synthetic columns above.
3. **After GATE-005:** run the operator's labeled Staging set. Record its size and fill the Staging column. Run the 3 × 3 invoice protocol.
4. **Specialists:** activate a specialist only when its measured verdict is `benefit` and its GATE-006 approval exists.
