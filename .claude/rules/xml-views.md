---
paths:
  - "plasticos_*/views/**/*.xml"
  - "plasticos_*/data/**/*.xml"
---
# XML Views & Data — Path-Scoped Pointer

**Authority:** `75-plasticos-xml-data-rules.mdc` · `84-ci-odoo19-patterns.mdc` · `plasticos-xml-view` skill

**Odoo 19:** `<list>` not `<tree>` · `invisible=` not `attrs=` · no `<group>` in `<search>` · no `numbercall` on crons.

**Seed data:** `<odoo noupdate="1">` · external IDs `plasticos_module.record_name` · no CSV runtime bootstrap.

**Validate:** `python3 ci/check_odoo19_xml.py` · `pre-commit run odoo19-xml --all-files`
