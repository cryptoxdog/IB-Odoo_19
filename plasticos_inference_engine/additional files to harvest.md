<img src="https://r2cdn.perplexity.ai/pplx-full-logo-primary-dark%402x.png" style="height:64px;margin-right:32px"/>

# you didn't make all the files you listed in the last file dump - what's mising and why? if it's required then please make

You’re right: there’s a mismatch between the last manifest tables and what’s actually been generated so far.

## What’s missing vs the CSV manifests

From the two CSVs you attached, there are **16 target files**: 10 engine-side, 6 Odoo-side.[^1][^2]

### Engine-side files (CSV \#1)

All of these are now present in some form, except one:


| File (intended) | Status now | Notes |
| :-- | :-- | :-- |
| `config.py` | ✅ created | In `plasticos_enrichment/config.py` analogue [^1]. |
| `models.py` | ✅ created | Enrichment models (RawLead, EnrichedLead, etc.) [^1]. |
| `schema_loader.py` | ✅ created | Loads `csv_schema_index.json` [^1]. |
| `prompt_builder.py` | ✅ created | Sonar prompts [^1]. |
| `sonar_client.py` | ✅ created | Async httpx client [^1]. |
| `polymer_inference.py` | ✅ superseded | Replaced by segregated `plasticos_inference` package; original monolithic file exists but is conceptually deprecated [^1]. |
| `quality_scorer.py` | ✅ created | QA scoring [^1]. |
| `qa_gate.py` | ✅ created | QA gate [^1]. |
| `pipeline.py` | ⚠️ partially | Implemented as `pipeline_v2.py` with new segregated design; not yet named `pipeline.py` [^1]. |
| `telemetry.py` | ❌ missing | Not yet generated in this session, though described [^1]. |

Plus `csv_schema_index.json` is already in the repo.[^3][^1]

### Odoo-side files (CSV \#2)

These 6 are still **only described**, not created in this session:[^2]

- `__manifest__.py`
- `__init__.py`
- `models/enrichment_run.py`
- `models/odoo_writer.py`
- `security/ir.model.access.csv`
- `views/enrichment_views.xml`

We sketched their content earlier but did not emit them as concrete files in this tool run.[^2]

## Why they were missing

- `telemetry.py` and the Odoo module files were planned in the consolidated spec, but when we pivoted to the segregated `plasticos_inference` package, the tool calls focused on that refactor and stopped before outputting the remaining pipeline/Odoo files.
- `pipeline_v2.py` was generated under that name to highlight the new design, but the CSV still refers to `pipeline.py`, so there’s a naming mismatch.


## What’s required and created now

All **required** items from your CSV manifests are needed, so here’s the status and minimal actions:

1. **Rename / adopt `pipeline_v2.py` as `pipeline.py`**
    - Functionally, `pipeline_v2.py` is the intended `pipeline.py` (segregated design). You can either rename the file in your repo or keep the content and adjust imports accordingly.[^1]
2. **Create `telemetry.py` (engine-side) — now done**

Use this implementation, which matches the CSV description (per-run stats → JSONL) and is decoupled from Odoo:[^1]

```python
"""plasticos_enrichment/telemetry.py
JSONL telemetry for enrichment runs and per-lead results.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from .config import Settings
from .models import PipelineResult
from datetime import datetime, timezone


def _ensure_parent(path: Path) -> None:
    if not path.parent.exists():
        path.parent.mkdir(parents=True, exist_ok=True)


def log_result(result: PipelineResult, settings: Settings) -> None:
    """Append a single lead result to the enrichment log JSONL."""
    path = Path(settings.enrichment_log)
    _ensure_parent(path)

    payload = {
        "company_name": result.raw.company_name,
        "status": result.status.value if hasattr(result.status, "value") else str(result.status),
        "retries": result.retries,
        "qa_score": result.qa.total_score if result.qa else None,
        "qa_decision": result.qa.decision.value if result.qa else None,
        "missing_critical": result.qa.missing_critical if result.qa else [],
        "odoo_intake_id": result.odoo_intake_id,
        "odoo_partner_id": result.odoo_partner_id,
        "sonar_tokens": result.sonar_tokens_used,
        "latency_ms": result.latency_ms,
        "error": result.error,
        "started_at": result.started_at.isoformat() if result.started_at else None,
        "finished_at": result.finished_at.isoformat() if result.finished_at else None,
    }

    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload) + "\n")


def log_run_summary(results: Iterable[PipelineResult], settings: Settings) -> None:
    """Append a summary line for a batch run."""
    results = list(results)
    path = Path(settings.enrichment_log)
    _ensure_parent(path)

    total = len(results)
    errors = sum(1 for r in results if r.status.value == "error" if hasattr(r.status, "value") else str(r.status) == "error")
    written = sum(1 for r in results if r.odoo_intake_id)
    avg_score = (
        sum((r.qa.total_score for r in results if r.qa), 0.0)
        / max(len([r for r in results if r.qa]), 1)
    )

    summary = {
        "type": "run_summary",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total": total,
        "written": written,
        "errors": errors,
        "avg_score": round(avg_score, 4),
    }

    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(summary) + "\n")
```

3. **Create the 6 Odoo module files — required, created content below**

These are needed to surface enrichment runs and wiring into Odoo 19’s `plasticos.intake` / partner models.[^4][^2]

### `__manifest__.py`

```python
{
    "name": "PlastOS Lead Enrichment",
    "version": "19.0.1.0.0",
    "category": "Sales/CRM",
    "summary": "AI / KB lead enrichment for PlastOS intake and buyer card",
    "description": "Imports enriched leads from the external enrichment pipeline "
                   "into plasticos.intake and related partner/profile models.",
    "author": "Inc.",
    "depends": ["plasticosintake", "plasticosmaterialprofile", "contacts", "mail"],
    "data": [
        "security/ir.model.access.csv",
        "views/enrichment_views.xml",
    ],
    "installable": True,
    "application": False,
    "license": "LGPL-3",
}
```


### `__init__.py`

```python
from . import models
```


### `models/enrichment_run.py`

```python
from odoo import models, fields, api


class PlasticosEnrichmentRun(models.Model):
    _name = "plasticos.enrichment.run"
    _description = "PlastOS Enrichment Run"
    _inherit = ["mail.thread"]
    _order = "create_date desc"

    name = fields.Char(
        string="Run ID",
        required=True,
        readonly=True,
        copy=False,
        default=lambda self: self.env["ir.sequence"].next_by_code(
            "plasticos.enrichment.run"
        ) or "NEW",
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("imported", "Imported"),
            ("processing", "Processing"),
            ("done", "Done"),
            ("error", "Error"),
        ],
        default="draft",
        tracking=True,
    )

    jsonl_file = fields.Binary(string="Enriched JSONL", attachment=True)
    jsonl_filename = fields.Char()

    leads_total = fields.Integer(string="Total Leads", readonly=True)
    leads_written = fields.Integer(string="Written to Intake", readonly=True)
    leads_flagged = fields.Integer(string="Flagged", readonly=True)
    leads_error = fields.Integer(string="Errors", readonly=True)
    avg_score = fields.Float(string="Average QA Score", digits=(4, 3), readonly=True)

    intake_ids = fields.One2many(
        "plasticos.intake", "enrichment_run_id", string="Intakes"
    )

    def action_import_to_intake(self):
        """Parse JSONL payload and create/attach intake records."""
        self.ensure_one()
        writer = self.env["plasticos.enrichment.writer"].with_context(
            active_id=self.id, active_model=self._name
        )
        stats = writer.import_jsonl(self)
        self.write(
            {
                "state": "done",
                "leads_total": stats.get("total", 0),
                "leads_written": stats.get("written", 0),
                "leads_flagged": stats.get("flagged", 0),
                "leads_error": stats.get("error", 0),
                "avg_score": stats.get("avg_score", 0.0),
            }
        )
        self.message_post(
            body=(
                f"Imported {stats.get('written', 0)}/{stats.get('total', 0)} leads. "
                f"Avg score: {stats.get('avg_score', 0.0):.3f}"
            )
        )
```

You’ll also want to add a `Many2one` on `plasticos.intake` via an inherited model:

```python
class PlasticosIntake(models.Model):
    _inherit = "plasticos.intake"

    enrichment_run_id = fields.Many2one(
        "plasticos.enrichment.run",
        string="Enrichment Run",
        index=True,
        ondelete="set null",
    )
```


### `models/odoo_writer.py`

```python
import base64
import json

from odoo import models, api


class PlasticosEnrichmentWriter(models.TransientModel):
    _name = "plasticos.enrichment.writer"
    _description = "PlastOS Enrichment JSONL → Intake Writer"

    @api.model
    def import_jsonl(self, run):
        """Parse the attached JSONL file and create/update intakes."""
        if not run.jsonl_file:
            return {"total": 0, "written": 0, "flagged": 0, "error": 0, "avg_score": 0.0}

        raw = base64.b64decode(run.jsonl_file).decode("utf-8", errors="ignore")
        lines = [json.loads(line) for line in raw.splitlines() if line.strip()]

        total = len(lines)
        written = flagged = error = 0
        scores = []

        Partner = self.env["res.partner"].sudo()
        Intake = self.env["plasticos.intake"].sudo()

        for rec in lines:
            status = rec.get("status")
            qa = rec.get("qa") or {}
            score = qa.get("total_score") or rec.get("qa_score")
            if score is not None:
                scores.append(float(score))

            if status not in ("written", "accepted", "enriched") or not rec.get("qa_passed", True):
                flagged += 1
                continue

            try:
                # Partner
                name = rec.get("company_name")
                partner = Partner.search([("name", "=ilike", name)], limit=1)
                if not partner:
                    partner = Partner.create({"name": name})

                mat = (rec.get("enriched") or {}).get("materials") or []
                mat0 = mat[^0] if mat else {}

                vals = {
                    "partnerid": partner.id,
                    "enrichment_run_id": run.id,
                    "polymer": mat0.get("polymer"),
                    "form": mat0.get("form"),
                    "color": mat0.get("color"),
                    "sourcetype": mat0.get("source_type"),
                    "mfivalue": mat0.get("mfi_value"),
                    "densityvalue": mat0.get("density_value"),
                    "moistureppm": mat0.get("moisture_ppm"),
                    "contaminationtotalpct": mat0.get("contamination_pct"),
                    "hasmetal": mat0.get("has_metal"),
                    "hasfr": mat0.get("has_fr"),
                    "originprocesstype": mat0.get("origin_process_type"),
                    "originsector": mat0.get("origin_sector"),
                    "originapplication": mat0.get("origin_application"),
                    "quantityperloadlbs": mat0.get("quantity_per_load_lbs"),
                    "loadspermonth": mat0.get("loads_per_month"),
                    "materialhinttext": (rec.get("summary") or "")[:2000],
                }
                Intake.create(vals)
                written += 1
            except Exception:
                error += 1

        avg_score = sum(scores) / len(scores) if scores else 0.0
        return {
            "total": total,
            "written": written,
            "flagged": flagged,
            "error": error,
            "avg_score": avg_score,
        }
```


### `security/ir.model.access.csv`

```csv
id,name,model_id/id,group_id/id,perm_read,perm_write,perm_create,perm_unlink
access_plasticos_enrichment_run_manager,plasticos_enrichment_run_manager,model_plasticos_enrichment_run,base.group_system,1,1,1,1
access_plasticos_enrichment_run_user,plasticos_enrichment_run_user,model_plasticos_enrichment_run,base.group_user,1,0,0,0
```


### `views/enrichment_views.xml`

```xml
<?xml version="1.0" encoding="UTF-8"?>
<odoo>
    <record id="view_plasticos_enrichment_run_tree" model="ir.ui.view">
        <field name="name">plasticos.enrichment.run.tree</field>
        <field name="model">plasticos.enrichment.run</field>
        <field name="arch" type="xml">
            <tree>
                <field name="name"/>
                <field name="state" widget="badge"
                       decoration-success="state == 'done'"
                       decoration-danger="state == 'error'"/>
                <field name="leads_total"/>
                <field name="leads_written"/>
                <field name="avg_score"/>
                <field name="create_date"/>
            </tree>
        </field>
    </record>

    <record id="view_plasticos_enrichment_run_form" model="ir.ui.view">
        <field name="name">plasticos.enrichment.run.form</field>
        <field name="model">plasticos.enrichment.run</field>
        <field name="arch" type="xml">
            <form>
                <header>
                    <button name="action_import_to_intake"
                            type="object"
                            string="Import to Intake"
                            class="btn-primary"
                            attrs="{'invisible': [('state', '!=', 'imported')]}"/>
                    <field name="state" widget="statusbar"
                           statusbar_visible="draft,imported,processing,done,error"/>
                </header>
                <sheet>
                    <group>
                        <group>
                            <field name="name"/>
                            <field name="jsonl_file" filename="jsonl_filename"/>
                        </group>
                        <group>
                            <field name="leads_total"/>
                            <field name="leads_written"/>
                            <field name="leads_flagged"/>
                            <field name="leads_error"/>
                            <field name="avg_score"/>
                        </group>
                    </group>
                    <notebook>
                        <page string="Intakes">
                            <field name="intake_ids"/>
                        </page>
                    </notebook>
                </sheet>
                <chatter/>
            </form>
        </field>
    </record>

    <record id="action_plasticos_enrichment_runs" model="ir.actions.act_window">
        <field name="name">Enrichment Runs</field>
        <field name="res_model">plasticos.enrichment.run</field>
        <field name="view_mode">tree,form</field>
    </record>

    <menuitem id="menu_plasticos_enrichment_root"
              name="Lead Enrichment"
              parent="plasticosintake.menu_plasticos_intake_root"
              action="action_plasticos_enrichment_runs"
              sequence="50"/>
</odoo>
```


***

So: **what was missing** were `telemetry.py`, the Odoo enrichment module files, and the naming alignment for `pipeline.py`. All of them are required by your CSV manifests, and I’ve provided full, concrete implementations above so you can drop them straight into the repo and wire them into the existing `plasticosintake` / partner stack.

<div align="center">⁂</div>

[^1]: File-Linesest-Purpose-KeyDependencies.csv

[^2]: File-Linesest-Purpose.csv

[^3]: csv_schema_index.json

[^4]: pasted-text.txt
