# `plasticos_documents` | Agent Binding to Native-First BRS

**Read first when editing Documents compliance, documentary weights/verification, SLAs, or document-related accounting eligibility:** `business_rules/README.md`, `REGISTRY.json`, `EFFECTIVE_RULES.md`, the verbatim `BRS-POS-02`, `BRS-POS-03`, `BRS-POS-09` chapters, `OWNERSHIP_AND_INTEROP.md`, and `OPEN_DECISIONS_AND_PROOFS.md`. Read applicable accepted root `docs/adr/`, root `AGENTS.md`, repository invariants and current source before writing code.

External-send ownership of BRS-POS-09-R006 through BRS-POS-09-R012 moved to `plasticos_logistics` by the dated supersession in `business_rules/SUPERSESSION.md`. The count 44 is installed verbatim text, not current ownership; 37 rules remain Documents-owned. BRS-POS-04 through BRS-POS-08, BRS-POS-11 and BRS-POS-12 stay with their owners.

Treat these module-local BRS as change-controlled requirements comparable in care to ADRs once admitted; **never assume their presence outranks an accepted ADR**. Cite exact rule IDs and both positive and falsifying acceptance tests in each changed-code PR. Preserve `LOCKED` vs `DESIGN` vs `CONDITIONAL` and `NOT_RUN` truth. As of 2026-10-27 the branch's non-documentation blobs match #316 `53b18fd90046696e946a0d8e1e60e88595a5e143`; admission stays candidate and Documents runtime stays `NOT_RUN`.

`plasticos_documents` owns business evidence, verification/compliance policy and exact links, not native document originals, Linda external sends, physical inventory, commercial orders, or native Accounting posting. Native Requests/Activities are internal-only. No external Documents access. No invoice auto-post from compliance recompute or document upload. No duplicate originals/verification writers, fuzzy association, fictional load, automatic liability/weight, custom scheduler or silent billing.

**Do not place BRS under `docs/adr/` or duplicate it in `plasticos_documents_native/`.** This module is the canonical local home. Future BRS changes require explicit supersession and owner review; source file history is immutable.
