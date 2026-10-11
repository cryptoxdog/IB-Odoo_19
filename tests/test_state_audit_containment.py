"""GMP-NC-C: the CI state guard and STATE_BYPASS do not contain each other."""

from __future__ import annotations

import importlib.util
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, path: Path, extra: Path):
    sys.path.insert(0, str(extra))
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


GUARD = _load("state_guard_under_test", ROOT / "ci" / "check_state_guard_bypass.py", ROOT / "ci")
AUDIT = _load(
    "business_logic_under_test",
    ROOT / "scripts" / "audit" / "business_logic_audit.py",
    ROOT / "scripts" / "audit",
)


def _module(root: Path, source: str) -> None:
    path = root / "plasticos_sample" / "models" / "load.py"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(source), encoding="utf-8")


def _server_action(root: Path) -> None:
    path = root / "plasticos_sample" / "data" / "action.xml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        textwrap.dedent(
            """
            <odoo>
              <record id="act_force" model="ir.actions.server">
                <field name="model_id" ref="plasticos_sample.model_plasticos_sample_load"/>
                <field name="code">env['plasticos.sample.load'].write({'state': 'done'})</field>
              </record>
            </odoo>
            """
        ),
        encoding="utf-8",
    )


def _ci(root: Path, monkeypatch) -> list[dict]:
    monkeypatch.setattr(GUARD, "get_git_tracked_files", lambda *_args, **_kwargs: [])
    guarded = GUARD._detect_guarded_models(root)
    return GUARD.check_state_guard_bypass(root, guarded) + GUARD.check_python_state_writes(root, guarded)


def _moderate(root: Path) -> list[dict]:
    return AUDIT.BusinessLogicAudit(root).check_state_machine_bypasses()


def test_selection_write_without_the_guard_is_only_a_moderate(tmp_path: Path, monkeypatch):
    _module(
        tmp_path,
        """
        class SampleLoad:
            _name = "plasticos.sample.load"
            state = fields.Selection([("draft", "Draft"), ("done", "Done")])

            def cron_touch(self):
                self.write({"state": "done"})
        """,
    )
    moderate = _moderate(tmp_path)
    assert len(moderate) == 1
    assert moderate[0]["type"] == "STATE_BYPASS"
    assert _ci(tmp_path, monkeypatch) == []


def test_xml_server_action_is_only_a_guard_finding(tmp_path: Path, monkeypatch):
    _module(
        tmp_path,
        """
        class SampleLoad:
            _name = "plasticos.sample.load"
            state = fields.Selection([("draft", "Draft"), ("done", "Done")])

            def _validate_state_transition(self):
                return None
        """,
    )
    _server_action(tmp_path)
    assert _moderate(tmp_path) == []
    issues = _ci(tmp_path, monkeypatch)
    assert len(issues) == 1
    assert issues[0]["severity"] == "BLOCKER"
    assert issues[0]["record_id"] == "act_force"


def test_documented_transition_is_only_a_guard_finding(tmp_path: Path, monkeypatch):
    _module(
        tmp_path,
        """
        class SampleLoad:
            _name = "plasticos.sample.load"
            state = fields.Selection([("draft", "Draft"), ("done", "Done")])

            def _validate_state_transition(self):
                return None

            def cron_touch(self):
                \"\"\"State transitions for the nightly close.\"\"\"
                self.write({"state": "done"})
        """,
    )
    assert _moderate(tmp_path) == []
    issues = _ci(tmp_path, monkeypatch)
    assert len(issues) == 1
    assert issues[0]["severity"] == "HIGH"
    assert "cron_touch" in issues[0]["record_id"]


def test_both_owners_stay_wired():
    runner = (ROOT / "scripts" / "audit" / "run_all_audits.py").read_text(encoding="utf-8")
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "check_state_machine_bypasses()" in runner
    assert "ci/check_state_guard_bypass.py" in workflow
