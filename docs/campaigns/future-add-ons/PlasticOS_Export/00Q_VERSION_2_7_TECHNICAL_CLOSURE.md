# v2.7.0 Export | Final bounded technical architecture closure

**New working-pack decision:** The **physical ISO-container journey (J1) and its exact physical source associations (J2)** belong to Logistics, independently of the Export booking slot. An Export capacity slot binds **at most one active J1**, and J1 can have multiple legitimate feeder movements; a real FAS supplier shipment requires no fictitious Odoo load or Stock picking. The original proposed E3 `load_id` is **not** the selected design. Native commercial, fulfillment, evidence, Linda and accounting authorities remain unchanged.

**Read exactly one technical authority for this release:** `EXPORT_BRS/MODULE_DESIGN/TECHNICAL_CLOSURE_v2.7.md`. Its derived machine-readable implementation index is `EXPORT_BRS/MODULE_DESIGN/TECHNICAL_CONTRACT_v2.7.json`. The v2.5 readiness and v2.6 cross-module documents remain as source/evidence and historical candidates, not competing live field shapes. The 120 stable BRS rules and 120 acceptance cases remain byte-identical to the v2.6 source.

**Contained:** Product architecture selected and protected within the working pack; four Export schemas, two nominated Logistics-only physical models and 12 proposed exact owner method signatures; seven-source-owner adoption/dependency matrix; migration M0-M7 and Enterprise checks EE-01..09; five ordered implementation units P0..P4 with stop rules.

**Not claimed:** Adopted source-owner code/schema/methods, tested native Enterprise support, current canonical GAR observer projection/receipt, independent architecture review, runtime PASS, code permission, repository change, PR, live mail, release or deployment. Source-owner adoption and installed Odoo validation must precede affected coding. Repository constitutional `INVARIANTS.md` v2.2.0 remains active; v3.3.0 is still a draft.

**Single next handoff:** exact Logistics/Transaction owner review of J1/J2 and stored buyer-optional company identity, plus the minimal Odoo 19 Enterprise schema proof; stop on a proven alternative owner realization rather than adding duplicate physical truth.
