# `plasticos_documents` | Agent Binding to Native-First BRS

**Read first when editing Documents compliance, documentary weights/verification, SLAs, or document-related accounting eligibility:** `business_rules/README.md`, `REGISTRY.json`, `EFFECTIVE_RULES.md`, the verbatim `BRS-POS-02`, `BRS-POS-03`, `BRS-POS-09` chapters, `OWNERSHIP_AND_INTEROP.md`, and `OPEN_DECISIONS_AND_PROOFS.md`. Read applicable accepted root `docs/adr/`, root `AGENTS.md`, repository invariants and current source before writing code.

Treat these module-local BRS as change-controlled requirements comparable in care to ADRs once admitted; **never assume their presence outranks an accepted ADR**. Cite exact rule IDs and both positive and falsifying acceptance tests in each changed-code PR. Preserve `LOCKED` vs `DESIGN` vs `CONDITIONAL` and `NOT_RUN` truth.

`plasticos_documents` owns business evidence, verification/compliance policy and exact links, not native document originals, Linda external sends, physical inventory, commercial orders, or native Accounting posting. Native Requests/Activities are internal-only. No external Documents access. No invoice auto-post from compliance recompute or document upload. No duplicate originals/verification writers, fuzzy association, fictional load, automatic liability/weight, custom scheduler or silent billing.

**Do not place BRS under `docs/adr/` or duplicate it in `plasticos_documents_native/`.** This module is the canonical local home. Future BRS changes require explicit supersession and owner review; source file history is immutable.
