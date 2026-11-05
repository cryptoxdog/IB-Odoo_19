# Documents BRS | Supersession and Authority

**2026-10-26 initial repository installation candidate.** Source is frozen BRS-POS v1.0.0, not the superseded October 23 Documents development-pack BRS. The original three BRS-POS chapter files are copied byte-for-byte. No rule's `normative_text`, status, identifier or original source acceptance has been rewritten. The installation adds indexing, exact cross-module owner boundaries and optional cross-domain counterexamples only.

## Source and interpretation

- These local BRS are proposed repo-level documentation until the dedicated child PR is reviewed/merged according to the repository's owning authority; they do not outrank already accepted ADRs or current canonical invariants merely by being committed.
- `BRS-POS-02` belongs to native document-original custody in `plasticos_documents_native`; `BRS-POS-03` belongs to business evidence/verification in `plasticos_documents`; `BRS-POS-09` governs their native Request, Activity and scheduler interoperability, while Linda retains external mail.
- The 126 other BRS-POS rules remain in their semantic domains. `ALL_170_RULES_SCOPE.csv` is cross-reference only and cannot claim Documents ownership.
- Source states `LOCKED`, `DESIGN`, `CONDITIONAL` retain their precise meanings. No runtime implementation, cost approval, financial authority, Enterprise proof or external messaging authorization is conferred.
- Historical `Documents_Build_Pack_v1.0.0_2026-10-23.zip` is nonoperative historical context, not a parallel BRS authority.

## Change control

A new or changed business rule requires a dated operator-approved supersession recording source revision/bytes, prior and successor ID, reason, exact affected owners, positive+negative acceptance implications and effective admission. Keep original frozen source chapter bytes and prior versions. Design questions needing new module fields or ownership go to their rightful ADR/architecture owner. A PR description, README, AI-generated plan or green test cannot independently rewrite business intent.

No automatic activation, no code changes and no Odoo runtime tests occurred during installation. Future code PRs must be stacked on the accepted/current BRS installation head and cite exact BRS IDs.

## 2026-11-05 external send {#2026-11-05-external-send}

External-send ownership of these seven clauses moves to `plasticos_logistics`. The chapter file `BRS-POS-09-native-documents-requests-activities-automation-and-scheduler.md` stays byte-for-byte in this module. Documents and Activities keep status and activity supply. They do not send the external chase.

| Rule ID | Title | External-send owner |
| --- | --- | --- |
| `BRS-POS-09-R006` | Only one external reminder writer | `plasticos_logistics` |
| `BRS-POS-09-R007` | Supplier document business clock | `plasticos_logistics` |
| `BRS-POS-09-R008` | Carrier document business clock | `plasticos_logistics` |
| `BRS-POS-09-R009` | Buyer document business clock | `plasticos_logistics` |
| `BRS-POS-09-R010` | No duplicate daily touch | `plasticos_logistics` |
| `BRS-POS-09-R011` | Quiet hours and locale aware deadlines | `plasticos_logistics` |
| `BRS-POS-09-R012` | Stop on verified or inapplicable | `plasticos_logistics` |

`REGISTRY.json` `source_rule_ids`, `local_rule_count` (44) and `external_rule_count` (126) stay the installed-text inventory. `ownership_transferred` records the seven IDs. `ALL_170_RULES_SCOPE.csv` classifies them `CROSS_DOMAIN_CONSUMER_REFERENCE`. The logistics admission is the same date in `plasticos_logistics/business_rules/SUPERSESSION.md`, cross-referenced to the existing clocks `BRS-02-R007`, `BRS-06-R039` and `BRS-07-R051`. This entry does not install `BRS-POS-04` through `BRS-POS-08`, `BRS-POS-11` or `BRS-POS-12`.
