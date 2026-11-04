# v1.4.0: additive `plasticos_export` Business Requirements Specification

**Decision:** preserve all operator-locked v1.3.0 export vs. Documents/Logistics boundaries, introduce the distinct `BRS-EXP-*` rules with positive/negative acceptance cases. The existing Native-First `BRS-POS-*` rules are referenced, **not copied or modified**.

**Scope:** `34` rules across 6 families; Phase 1 FOB pickup / FAS inland freight-to-port/rail; Phase 2 actual international selling; no new application engine. The BRS is an **unadmitted plan**, not code authorization or proof of current deployment.

**Read:** `EXPORT_BRS/README.md` -> `EXPORT_BRS/OWNERSHIP_MATRIX.md` -> `EXPORT_BRS/RULES/` -> `EXPORT_BRS/REGISTRY/rules.json` -> `EXPORT_BRS/ACCEPTANCE/cases.json` -> `EXPORT_BRS/DECISION_FRONTIER.md`.

**Non-regression:** all 20 predecessor non-manifest files preserved byte-for-byte. Prior complete ZIP SHA-256 `8ce7e418f622b5aaf7da146c32747e4cddd10a6b2adf2a7db764369f733f4743`. Attached Native-First BRS ZIP SHA-256 `08e0ac3ecc463f1b701b0e15c505d26fb15526d436fed566b8d48cfbb45089c4`. Semantic adoption not performed. Every generated acceptance case is NOT_RUN.
