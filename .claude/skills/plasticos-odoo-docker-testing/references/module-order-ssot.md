# Module Order SSOT (Gate Architecture)

## Sources of truth

| File | Role |
|------|------|
| `config/odoo_module_order.yaml` | Human + script install order, enterprise list, `excluded_modules` |
| `scripts/get_odoo_module_order.py` | Prints CSV; `CUSTOM_DEFAULT` must stay in sync with yaml |
| `plasticos_*/__manifest__.py` | `installable`, `auto_install`, `depends`, `version` |

```bash
python3 scripts/get_odoo_module_order.py                 # default_install_order
python3 scripts/get_odoo_module_order.py --all-installable
python3 ci/check_xml_module_ref_deps.py                  # xml ref → depends
```

## Gate shells — MUST install

These are **not** local matchers. They store Gate writebacks / orchestration
state for Odoo → Gate → EIE/CEG → Gate → Odoo
([Cognitive.Engine.Graphs](https://github.com/Quantum-L9/Cognitive.Engine.Graphs)).

| Module | Notes |
|--------|-------|
| `plasticos_gate` | Transport client |
| `plasticos_matching` | Gate shell; `auto_install=True`; needs `plasticos_base` (cron xmlid) |
| `plasticos_enrichment` | Gate shell; `auto_install=True`; no `plasticos_inference_engine` |

Place matching/enrichment **after** `plasticos_gate` + intake/facility deps and
**before** `plasticos_security_base` only when deps allow; security_base does
**not** depend on matching (matching stays commented out there).

## Never install (excluded / deleted)

| Module | Why |
|--------|-----|
| `plasticos_buyer_match_engine` | DELETED — local matching mothballed |
| `plasticos_inference_engine` | DELETED — local IE mothballed |
| `plasticos_enrichment_bridge` | Retired |
| `plasticos_dev_tools` | `installable: False` |
| `plasticos_website` | `installable: False` |
| `plasticos_documents_native` | Enterprise `documents` only |
| `plasticos_odoo_standard_apps` | Skip explicit `-i` (auto bundle) |
| `plasticos_semantic_kernel` | Optional; not Staging critical path |

**Drift bug (caught 2026-08):** yaml listed matching/enrichment as
`installable: False` while manifests had `installable=True` + `auto_install=True`.
Staging auto-installed them; Docker smoke skipped them → false local green.

## Dependency-safe order (critical path)

```
accounting → base → gate → material_profile → logistics → facility → intake
→ product → order_lines → transaction → documents → offer → claims → automation
→ intake_normalizer → matching → enrichment → geolocalize → web_leads
→ security_base → commission → crm_bridge → partner_import → crm_sync
→ admin_dashboard
```

Hard rules:

- `plasticos_security_base` **after** `plasticos_web_leads` and `plasticos_logistics`
  (manifest depends).
- `plasticos_crm_bridge` **after** `plasticos_security_base`.
- `plasticos_partner_import` **after** `plasticos_crm_bridge`.
- `plasticos_crm_sync` **after** `plasticos_crm_bridge` + `plasticos_security_base`.
- Load-dashboard `ir.rule` group bindings live in **security_base**, not logistics
  (circular dep otherwise). Re-home xmlids via security_base migrations.

## Version bumps

When XML/Python/data/migrations change, bump `19.0.X.Y.Z` in the **same module's**
`__manifest__.py`. Migrations only run when the version folder ≤ new version.

Examples from Staging recovery:

- logistics data ownership move → bump logistics even if rules moved out
- security_base new rules + pre-migrate → bump security_base
- matching new depends → bump matching
