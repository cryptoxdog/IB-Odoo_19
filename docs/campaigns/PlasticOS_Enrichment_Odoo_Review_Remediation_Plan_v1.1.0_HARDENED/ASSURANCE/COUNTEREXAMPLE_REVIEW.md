# Adversarial recursive-alignment check (self-audit only)

| Claim attacked | Counterexample | Required disposition |
|---|---|---|
| Editing the review screen makes approval safe | A base.group_user can call action_inject or write(state + gate_proposal) | Guard action methods and state, remove broad CRUD and add company rules before UI |
| Provenance model should double as proposal | Historic written rows would be interpreted as merely pending | New narrow proposal-line model; preserve applied audit |
| EIE returned per-field confidence/source | EIE mapper provides aggregate confidence and KB fragments without field binding | Label scope honestly, add operator-attested source or block field |
| A disabled cron XML means disabled live | XML `noupdate=1`; manually enabled DB cron can remain active | Installed scan + versioned correction; no cron restart |
| Retired cron cannot elevate an actor | post_init_hook grants manager group and existing DB retains it | Enumerate legitimate cron users, revoke precisely with migration |
| `gate_auto_writeback_enabled` config is all that matters | Both config flags ON triggers old immediate branch in run action_execute | Scoped addon forces manual review and preflight OFF, no Gate service edits |
| Empty fields prove EIE/Gate failure | Successfully completed response can have no allowed new fields | Evidence-only/no_action status, keep packet/reason |
| Falsy is equivalent to blank | Valid False or numeric zero may be existing confirmed fact | Field-type-aware missingness and CAS; no blanket truthy check |
| A source-locked plan is a deployed feature | Live Gate packet, installed Odoo Enterprise and dynamic consumers unobserved | U00 blocks precode, tests all NOT_RUN |
| A 33-effect ledger means full blast radius | DB server actions and external clients may still exist | Explicit frontier and invalidation, no claim of completed runtime census |
| No changes to external repositories imply no integration gap | Actual EIE payload may omit field source evidence | Odoo UI reports missing evidence and blocks unsafe approval; don't invent external wire |
| Clean architecture means delete local histories | Existing `engine_used=local` audit/source/extraction links are legally/historically relevant | Tombstone executable paths only, preserve all historical rows/IDs |

This is a model-authored challenge of the proposed plan, **not** an independent architecture break test by another agent or runtime. Independent semantic review is required before implementation admission.
