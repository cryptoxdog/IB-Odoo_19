# 2026-11-09 working release checkpoint | supersedes live claims in October 30 checkpoint

GitHub `Production@729d3ab0b7cd7a0cb1058528e7c0e28cdcc08b56` contains PR #408 (merged 2026-11-08; promoted `Staging@b5b6056f01639212e722ccdec5b964b36deee9f5`). `Staging@bdc222246fbfb647e8e008046b759eecd60a2028` has newer changes; #418 was open. A GitHub branch SHA is **not** an observed Odoo.sh build or populated database.

**New near-term target:** today Production should be test-ready with all *eligible* transactions, ERP and approved CRM contacts imported and reconciled, basic code quality, usable Admin dashboard, and no blocker errors. Expect no new live commercial events initially, so zero live KPIs may be normal; imported history still must be present in its own views/census.

**Progression:** verify import / hosted Admin -> native web lead, logistics/Linda and Documents automations -> user-driven full UI/button sweep -> operator-reviewed Export integration milestone. Not current scope: matching, enrichment, AI extraction, Export implementation, warehouse hardware, autonomous financial cutover.

**Known source discrepancy:** existing Logistics Dashboard projection filters closed loads older than current month. Admin root menu and Action exist but module requires explicit installation and system admin group. Check, do not assume.

**Historical:** The October 30 v4 graph tied to `Staging@fba54b2` was prior working state. Its reports remain in the package for traceability and are revised only where affected; any source-bound old PR receipt remains historical evidence, not current Production proof.
