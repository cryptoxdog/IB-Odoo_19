# Private operator data

This directory holds a historical CRM source snapshot and operator-approved mapping evidence, including personal and contact information. Those files stay on the operator's machine. They are gitignored and are not in this repository; only this note and the `.gitignore` are tracked.

`INPUT_MANIFEST.json` names each file with its size and SHA256 so a local copy can be verified before a run.

Do not paste raw rows, names, customer emails, phone numbers, notes, or credential values into chat, logs, or pull-request text. The frozen source CSV is an ID census, not an Odoo importer. The identity crosswalk CSV is a pinned allowlist, not a contact payload.
