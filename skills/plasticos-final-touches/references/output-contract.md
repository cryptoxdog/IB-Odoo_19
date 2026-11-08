<!-- L9_META
skill_schema: 1
parent: plasticos-final-touches
layer: reference
role: output_contract
tags: [plasticos, go-live, report, yaml]
owner: igor_beylin
status: active
version: 1.1.0
updated: 2026-06-06
/L9_META -->

# Final Touches Output Contract

## Report Shape

```yaml
final_touches_report:
  date: ""
  branch: ""
  gate_results:
    dev_tools_fence: pass | fail
    audit_quick: pass | fail
    odoo19_xml: pass | fail
    acl: pass | fail
    cron_safety: pass | fail
    pipeline_v2_guard: pass | fail
    orphan_refs: pass | fail
    orm_safety: pass | fail
    xpath_stability: pass | fail
    module_wiring: pass | fail
    pr_check: pass | fail
  changes_made: []
  open_issues: []
  verdict: ready_for_production | needs_remediation
```

## Definition of Done

```yaml
definition_of_done:
  objective: "prepare IB-Odoo_19 Production branch for go-live"
  gate_1_dev_tools: pass
  gate_2_audit_quick: pass
  gate_3_odoo19_xml: pass
  gate_4_acl: pass
  gate_5_cron: pass
  gate_6_pipeline_v2_guard: pass
  gate_7_orphan_refs: pass
  gate_8_orm_safety: pass
  gate_9_xpath: pass
  gate_10_wiring: pass
  final_pr_check: pass
  no_new_features_introduced: true
  web_lead_classification_untouched: true
  todo_1_4_not_duplicated: true
  verdict: ready_for_production
```
