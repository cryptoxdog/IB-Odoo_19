# Unverified Boundaries and Required Runtime Proof

These items are **Unknown**, not green. A correctly assembled archive does not prove Odoo installation.

| Gate | Needed evidence | Current disposition |
|---|---|---|
| Enterprise registry | Install four addon roots on an isolated Odoo 19 Enterprise database using the pinned Staging owner code; resolve all XML/model/ACL references. | NOT RUN |
| Native reviewer authorization | Demonstrate that internal users without the reviewer group cannot admit, version or retire knowledge. | NOT RUN |
| Company/party isolation | Two users, distinct companies; source read, advice, feedback and consultation receipts must not disclose unauthorized records. | NOT RUN |
| Lifecycle and replay | Concurrent approvals and retirements, request-key/message replay, duplicate feedback and module upgrade should preserve one history. | NOT RUN |
| Odoo attachments | Validate original supporting attachment accessibility, scope, revision and empty-file rejection through native `ir.attachment`. | NOT RUN |
| Shadow qualification | Off must be behaviorally identical; shadow adds no model call or final routing change; live never injects knowledge. | NOT RUN |
| Rejection owner | Native Offer/Match source access and approved-reference ambiguity must not change any lifecycle or exclusion. | NOT RUN |
| Full compatibility | Original standalone three-addon ZIP and its exact 38 drafts were not among authorized inputs. | SOURCE UNAVAILABLE |
| Long-lived receipt visibility | Recheck historical receipt/feedback reads after a user loses source-record read rights. Policy requirements remain unresolved. | UNKNOWN |

Source-aligned improvements are suitable for **isolated runtime validation**, not Production deployment.

## Alignment-specific runtime gates

- **Company isolation / ALN-01:** Execute advice and rejection queries with a user allowed companies A+B while inspecting a source belonging exclusively to A; B's approved knowledge must be absent. Check a source with no company uses the active operator company. **NOT RUN**.
- **Reviewer attestation / ALN-02:** Reproduce edited draft scope/evidence after a prior attestation, confirm reset, and test save-and-attest rejection through actual Odoo ORM. **NOT RUN**.
- **Feedback replay / ALN-03:** Verify a pre-alignment receipt can be replayed idempotently and company-distinct observations cannot collide under Odoo record rules and PostgreSQL indexes. **NOT RUN**.
- **Web-lead shadow / ALN-04:** Inject a failed query inside the savepoint; verify the native qualification transaction remains usable and routing stays on its canonical owner. **NOT RUN**.
- **Original attachment integrity:** Read Odoo `ir.attachment` permissions after admission to determine whether source evidence can be replaced or deleted without supersession; if so, correction belongs at the native attachment authority boundary, not a silent local copy. **UNKNOWN**.
- **Overlapping global/company knowledge identities:** No approved precedence policy exists for the same stable key in both scopes. Conservative review and live Odoo test are required before assuming one overrides another. **UNKNOWN**.
- **Fresh Staging:** Only two documentation-only commits separate the previous source pin from `d25da3236887c924c8a0164b00c1198f1804a2ea`; source interfaces used here were not modified. PR #471 is Export documentation, not a runtime override.
