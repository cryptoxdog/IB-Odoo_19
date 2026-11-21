# TASK-001 — Ship an Odoo 19 Dashboard as module data (spike report)

Campaign `ib-odoo-dashboard-command-centers` · Lane C · Decision DEC-001 (OPT-A) · Unknown UNK-001 · Acceptance AC-001.
Report only: no product code is committed by this PR. The throwaway module lived on a local branch and was never pushed.

## Verdict

| Question | Verdict | Basis |
|---|---|---|
| A `spreadsheet.dashboard` record in the official 19.0 shape installs from IB-Odoo_19 module data with role `group_ids` and `company_ids` | **SUPPORTED**, with a dependency caveat | Runtime: install on the admitted Enterprise fixture, rc=0. The spike manifest depended only on `spreadsheet_dashboard` and `plasticos_logistics`, yet its XML references `plasticos_security_base.group_logistics`; `plasticos_logistics` does not depend on `plasticos_security_base`, so the 173-module fixture masked a fresh-install failure. A shipped dashboard module must declare `plasticos_security_base` (and any module whose groups or menus it names) in `depends`. |
| `-u` twice reproduces the shipped JSON exactly | **SUPPORTED** | Runtime: stored JSON == shipped file after `-u` #2 and `-u` #3; sha256 identical. Install and `-u` #1 ran (rc=0) but their stored JSON was not compared. |
| A UI edit of a shipped dashboard is not a source of truth (DEC-001 locked consequence) | **SUPPORTED** | Runtime: an edited JSON and sequence were overwritten by the next `-u` |
| `group_ids` and `company_ids` gate who sees the dashboard | **SUPPORTED**, not the only gate | Runtime: Logistics user sees it; Sales rep does not; a Logistics user of another company does not. Exception, measured: a `spreadsheet_dashboard.group_dashboard_manager` (Dashboard Admin) user outside Logistics also sees it, because its manager rule is `[(1, '=', 1)]` and group rules combine with OR (`security.xml` L31-36). `base.user_root` and `base.user_admin` are in that group by default. |
| `chartOdooMenusReferences` names a module menu by XML id | **SUPPORTED** (server-side) | Runtime: `plasticos_logistics.menu_plasticos_loads` resolves to *Logistics/Loads*, action model `plasticos.load` |
| The JSON was authored in the Enterprise spreadsheet editor and exported | **UNKNOWN — NOT RUN** | The JSON was hand-authored key-for-key from the official `sales_dashboard.json` (shape below). Driving the Enterprise editor UI was not done in this session. |
| Clicking the chart / pivot in the browser opens the expected records | **UNKNOWN — NOT RUN** | No browser click-test was run. Only the server-side resolution above was proven. |

**Overall: SUPPORTED for shipping and reproducing dashboards as module data (UNK-001's core question). Two proofs stay open, both NOT RUN: authoring in the editor, and the browser drill click.** TASK-031 may rely on the record shape and on reproducibility. Before its own dashboard is accepted, someone must still open it once in the editor and click through it in a browser (prerequisite: a browser session on the fixture with the Enterprise `spreadsheet_dashboard_edition` module).

## Environment (what actually ran)

- Target: `cryptoxdog/IB-Odoo_19` `Staging` @ `45e00ee0542e91d0ea751b2126977a3d0026d896`.
- Runtime: `make runtime-bootstrap` admitted the pinned fixture `odoo_test_tpl_ee_c9e8a81f52f23680` (parity ee, 173 modules installed, including `spreadsheet_dashboard`, `spreadsheet_edition`, `documents_spreadsheet`). Odoo `19.0-20261112` (image `odoo:19`). Enterprise source `Quantum-L9/odoo-enterprise` @ `3225e0e80692` (read-only).
- Disposable clone `odoo_test_lanec001` via `scripts/test_env.sh clone`; every run went through `scripts/test_env.sh run` (no extra mounts, no addons-path override).
- Throwaway module `zz_lanec_task001_dashboard_spike` (depends `spreadsheet_dashboard`, `plasticos_logistics`); never committed to a pushed branch.

## Official record shape (EVID-007)

| Source (odoo/odoo 19.0, as installed in `odoo:19`) | Lines | What it fixes |
|---|---|---|
| `addons/spreadsheet_dashboard_account/data/dashboards.xml` | L4-13 | Record shape: `spreadsheet_binary_data` (`type="base64" file=…`), `main_data_model_ids`, `sample_dashboard_file_path`, `dashboard_group_id`, `group_ids`, `sequence`, `is_published` |
| `addons/spreadsheet_dashboard/models/spreadsheet_dashboard.py` | L8-31 | Model `spreadsheet.dashboard` inherits `spreadsheet.mixin`; fields `dashboard_group_id` (required), `sequence`, `sample_dashboard_file_path`, `is_published`, `company_ids`, `group_ids` (default `base.group_user`), `main_data_model_ids` |
| same file | L47-57 | `_get_serialized_readonly_dashboard` serves `spreadsheet_data` as the snapshot (read-only viewer) |
| same file | L66-73 | `_dashboard_is_empty`: an empty main data model switches to the sample file |
| `addons/spreadsheet/models/spreadsheet_mixin.py` | L22-34 | `spreadsheet_binary_data` Binary, `spreadsheet_data` computed/inverse, JSON validated on write |
| `addons/spreadsheet_dashboard/security/security.xml` | L4-9, L11-15, L31-36 | Rules: `group_ids in user.all_group_ids`; `company_ids in company_ids + [False]`; Dashboard Admin manager rule `[(1, "=", 1)]` |
| `addons/spreadsheet_dashboard_sale/data/files/sales_dashboard.json` | top-level keys | `version` `18.5.10`, `sheets`, `pivots`, `globalFilters`, `lists`, `chartOdooMenusReferences`, `pivotNextId`, `listNextId`, `settings`, `revisionId`, `uniqueFigureIds` |

**Native finding (shape):** in 19.0 the global filter carries no `fieldMatching`. It is `{id, type: "date", label, defaultValue}`. Each data source (each pivot, and each Odoo chart's `data`) carries a `fieldMatching` map keyed by the filter id (`{chain, type, offset}`). A "global date filter with fieldMatching" therefore means one filter plus one matching entry per data source it should filter. Data sources without an entry are not filtered.

## Exact XML (as installed)

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <record id="spreadsheet_dashboard_group_logistics_spike" model="spreadsheet.dashboard.group">
        <field name="name">Logistics (spike)</field>
        <field name="sequence">90</field>
    </record>
    <record id="dashboard_logistics_spike" model="spreadsheet.dashboard">
        <field name="name">Logistics Spike</field>
        <field name="spreadsheet_binary_data" type="base64" file="zz_lanec_task001_dashboard_spike/data/files/logistics_spike_dashboard.json"/>
        <field name="main_data_model_ids" eval="[(4, ref('plasticos_logistics.model_plasticos_load'))]"/>
        <field name="dashboard_group_id" ref="spreadsheet_dashboard_group_logistics_spike"/>
        <field name="group_ids" eval="[Command.link(ref('plasticos_security_base.group_logistics'))]"/>
        <field name="company_ids" eval="[Command.link(ref('base.main_company'))]"/>
        <field name="sequence">10</field>
        <field name="is_published">True</field>
    </record>
</odoo>
```

The shipped record adds `company_ids` to the official shape. The official account dashboard omits it, and DEC-001 requires it. It also omits `sample_dashboard_file_path`, so an empty `plasticos.load` shows an empty dashboard rather than a sample.

## Dashboard JSON (data-source excerpt)

```json
{
  "pivots": {
    "1": {
      "columns": [],
      "context": {
        "group_by": []
      },
      "domain": [
        [
          "state",
          "in",
          [
            "scheduled",
            "dispatched",
            "picked_up"
          ]
        ]
      ],
      "fieldMatching": {
        "f0a1b2c3-0001-4000-8000-00000000d001": {
          "chain": "pickup_datetime",
          "offset": 0,
          "type": "datetime"
        }
      },
      "formulaId": "1",
      "id": "1",
      "measures": [
        {
          "fieldName": "__count",
          "id": "__count"
        }
      ],
      "model": "plasticos.load",
      "name": "Loads in motion",
      "rows": [
        {
          "fieldName": "state"
        }
      ],
      "sortedColumn": null,
      "type": "ODOO"
    }
  },
  "globalFilters": [
    {
      "defaultValue": "last_90_days",
      "id": "f0a1b2c3-0001-4000-8000-00000000d001",
      "label": "Pickup",
      "type": "date"
    }
  ],
  "chartOdooMenusReferences": {
    "c0a1b2c3-0001-4000-8000-00000000c001": "plasticos_logistics.menu_plasticos_loads"
  },
  "chart_figure_data": {
    "axesDesign": {},
    "background": "#FFFFFF",
    "chartId": "c0a1b2c3-0001-4000-8000-00000000c001",
    "dataSets": [
      {}
    ],
    "fieldMatching": {
      "f0a1b2c3-0001-4000-8000-00000000d001": {
        "chain": "pickup_datetime",
        "offset": 0,
        "type": "datetime"
      }
    },
    "legendPosition": "none",
    "metaData": {
      "groupBy": [
        "state"
      ],
      "measure": "__count",
      "mode": "bar",
      "order": null,
      "resModel": "plasticos.load"
    },
    "searchParams": {
      "comparison": null,
      "context": {
        "group_by": []
      },
      "domain": [
        [
          "state",
          "in",
          [
            "scheduled",
            "dispatched",
            "picked_up"
          ]
        ]
      ],
      "groupBy": [
        "state"
      ],
      "orderBy": []
    },
    "stacked": false,
    "title": {
      "text": "Loads by status"
    },
    "type": "odoo_bar",
    "verticalAxisPosition": "left"
  }
}
```

The sheet has `A20 = =PIVOT(1)` plus one `odoo_bar` figure. Pivot and chart share one domain and one `fieldMatching` entry for the date filter on `pickup_datetime`.

## Reproducibility evidence

| Step | rc | Stored `spreadsheet_data` == shipped file | sha256 of stored JSON (sorted keys) |
|---|---|---|---|
| `-i` | 0 | not compared | — |
| `-u` #1 | 0 | not compared | — |
| `-u` #2 | 0 | **True** | `168fd753275bc8bdb4f384404e85b29c2823d37774bbf8cb035516adf60d677e` |
| UI-equivalent edit (pivot renamed, sequence 99) | — | False | `1d4b68689a390a2a840de60c57c5afc260b94954a69af1af84b43a1167bcde01` |
| `-u` #3 | 0 | **True** | `168fd753…` (record dump identical to the one after `-u` #2: `diff` empty) |

The record is updatable (not `noupdate`), so every `-u` re-applies the module file. That matches DEC-001's locked consequence. It also means an operator's in-UI change to a shipped dashboard is lost on the next upgrade; changes must come back through the module.

## Access evidence (rolled back)

| Viewer | Sees the dashboard |
|---|---|
| `plasticos_security_base.group_logistics`, main company | yes |
| `plasticos_security_base.group_sales_rep`, main company | no |
| `group_logistics`, another company only | no |
| `spreadsheet_dashboard.group_dashboard_manager` only (no Logistics), main company | **yes** (manager rule) |

The record rules on `plasticos.load` still filter the pivot's data per viewer. The dashboard's own `group_ids`/`company_ids` only gate the dashboard record.

## Drill-down

- Server-side: the chart's `chartOdooMenusReferences` entry resolves to menu *Logistics/Loads*, whose action opens `plasticos.load`. Pivot domain `[["state","in",["scheduled","dispatched","picked_up"]]]` evaluated with `search_count` and `_read_group` on the fixture: 0 records in those states, so value-versus-drill parity is not exercised by fixture data.
- Browser click-test: **NOT RUN**.

## Native gaps that would need the Owl review surface

None for the analytical dashboards. The dashboards are read-only spreadsheets of native pivots, lists and charts, and drills open native window actions. DEC-001's Owl exception concerns the Operations side-by-side review surface (original, candidate facts, current values and discrepancy together). That is outside this spike, so it remains **UNKNOWN**.

## Consequences for dependent tasks

- TASK-031 / TASK-032 may ship dashboards in the record shape above, with `company_ids`, role `group_ids` and one `fieldMatching` entry per data source per filter, with three corrections:
  - declare every module whose XML ids the record names (here `plasticos_security_base`) in `depends`;
  - use replacement semantics (`Command.set([...])`) when the module owns the complete list of `group_ids` and `company_ids`. `Command.link` only adds, so on an updatable record a group or company removed in a later version would stay on the record after `-u` and keep seeing the dashboard (not tested here: this spike changed no membership);
  - do not treat `group_ids` as the only visibility gate: Dashboard Admins see every dashboard in their companies. Record rules on the source models still filter the data itself.
- DEC-007 KPI-drill parity is not provided by the dashboard. A KPI value in a pivot cell and its drill share one domain only if the JSON declares them once. Tests must assert parity on the source model (`search_count(domain)`), as TASK-032 does for its views.
- Keep `sample_dashboard_file_path` unset unless a sample file is shipped. `_dashboard_is_empty` switches to the sample whenever the main data model has no records.

## Not done / truth contract

- Editor authoring: NOT RUN (hand-authored in the official shape).
- Browser drill click-test: NOT RUN.
- No claim about the live Staging UI.
