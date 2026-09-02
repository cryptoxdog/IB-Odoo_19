"""Structural guards for the three pristine-runtime operator seams.

The executable proofs for these seams live in
``tests/runtime_gates/run_s1_s3_pristine_seams.py`` and need a live Odoo 19
registry plus a live PostgreSQL server, which the ``pure-python-tests`` CI tier
does not have. These guards are the CI-side half: they cannot prove the seams
work, but they fail the moment the specific construction that made each seam
break is reintroduced.

That division already exists in this repository for I2/I3 (see
``docs/runbooks/LAUNCH_GATES.md`` and ``tests/test_legacy_erp_import_contract.py``);
this module extends it to S1/S2/S3.
"""

import ast
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
ORCHESTRATOR = ROOT / "plasticos_crm_sync" / "services" / "orchestrator.py"
WEBHOOK = ROOT / "plasticos_crm_sync" / "controllers" / "webhook.py"
IMPORTER = ROOT / "plasticos_transaction" / "models" / "legacy_erp_import_service.py"
GATE_SCRIPT = ROOT / "tests" / "runtime_gates" / "run_s1_s3_pristine_seams.py"


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"))


def _function(tree: ast.Module, name: str) -> ast.FunctionDef:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"{name} is not defined")


# ----------------------------------------------------------------------
# S1 — the connection must be durable before the owned cursor references it
# ----------------------------------------------------------------------
def _call_lines(tree: ast.AST, attr: str) -> list[int]:
    return [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == attr
    ]


# Both public entrypoints open the same owned cursor for the same FK-bearing
# audit row, so both carry the same precondition.
DURABLE_CURSOR_ENTRYPOINTS = ["run_connection", "run_full_import"]


@pytest.mark.parametrize("entrypoint", DURABLE_CURSOR_ENTRYPOINTS)
def test_entrypoint_makes_caller_state_durable_before_its_owned_cursor(entrypoint):
    """`_create_sync_run_durable` INSERTs a row whose FK points at the connection.

    That INSERT happens on a cursor of its own, so a connection the caller has
    not committed is invisible to it and the FK fails — the first-run Settings
    path. The boundary must therefore precede the call, not follow it.
    """
    func = _function(_tree(ORCHESTRATOR), entrypoint)
    boundary_lines = _call_lines(func, "_ensure_caller_state_durable")
    durable_create_lines = _call_lines(func, "_create_sync_run_durable")

    assert durable_create_lines, f"{entrypoint} no longer creates the durable sync run"
    assert boundary_lines, f"{entrypoint} does not establish the durability boundary"
    assert min(boundary_lines) < min(durable_create_lines), (
        f"{entrypoint} must make the caller's state durable BEFORE "
        "_create_sync_run_durable opens its own cursor, or a freshly created "
        "connection is invisible to that cursor and the foreign key fails"
    )


def test_the_durability_boundary_actually_commits():
    """The boundary is only real if it commits; a rename must not hollow it out."""
    boundary = _function(_tree(ORCHESTRATOR), "_ensure_caller_state_durable")
    assert _call_lines(boundary, "commit"), "_ensure_caller_state_durable performs no commit"


@pytest.mark.parametrize("scope", [*DURABLE_CURSOR_ENTRYPOINTS, "_ensure_caller_state_durable"])
def test_flush_is_not_used_as_a_cross_transaction_boundary(scope):
    """A flush writes inside the caller's transaction; it commits nothing.

    Substituting one for the commit reintroduces the defect while looking like
    a fix, so the shape is guarded explicitly.
    """
    func = _function(_tree(ORCHESTRATOR), scope)
    for attr in ("flush", "flush_recordset", "flush_model"):
        assert not _call_lines(func, attr), (
            f"{scope}: flush() does not make a row visible to another transaction; commit does"
        )


# ----------------------------------------------------------------------
# S2 — the webhook must elevate with a real Environment, after authenticating
# ----------------------------------------------------------------------
def test_webhook_never_calls_sudo_on_an_environment():
    """`sudo()` is a recordset method. `Environment` has no such attribute."""
    source = WEBHOOK.read_text(encoding="utf-8")
    assert "request.env.sudo()" not in source, "Environment has no sudo(); use request.env(su=True)"
    # `env.su` is a boolean state flag, not an Environment. The negative
    # lookahead keeps this from re-matching the `sudo()` spelling above, and
    # `env(su=True)` is a call so it never matches this attribute access.
    assert not re.search(r"request\.env\.su(?!do)\b", source), "env.su is a boolean state flag, not an Environment"


def test_webhook_elevates_with_env_su_true():
    tree = _tree(WEBHOOK)
    handler = _function(tree, "vanillasoft_weblead")
    elevated = [
        node for node in ast.walk(handler) if isinstance(node, ast.Call) and any(kw.arg == "su" for kw in node.keywords)
    ]
    assert elevated, "the webhook must build its elevated environment with env(su=True)"


def test_webhook_authenticates_before_it_elevates():
    """The token check must dominate every privileged statement."""
    handler = _function(_tree(WEBHOOK), "vanillasoft_weblead")

    compare_digest_lines = [
        node.lineno
        for node in ast.walk(handler)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "compare_digest"
    ]
    elevation_lines = [
        node.lineno
        for node in ast.walk(handler)
        if isinstance(node, ast.Call) and any(kw.arg == "su" for kw in node.keywords)
    ]
    assert compare_digest_lines, "the webhook no longer compares the token"
    assert elevation_lines, "the webhook no longer elevates"
    assert max(compare_digest_lines) < min(elevation_lines), (
        "authentication must complete before any privileged environment exists"
    )


# ----------------------------------------------------------------------
# S3 — the importer must not assume a res.partner field exists
# ----------------------------------------------------------------------
def test_importer_never_writes_mobile_unconditionally():
    """Odoo 19 base has no `res.partner.mobile`; the field must be resolved."""
    source = IMPORTER.read_text(encoding="utf-8")
    assert '_set_if(values, "mobile"' not in source, (
        "res.partner has no `mobile` field in Odoo 19 — resolve it from "
        "the installed registry via _partner_mobile_field()"
    )


def test_importer_resolves_the_mobile_field_from_the_registry():
    tree = _tree(IMPORTER)
    helper = _function(tree, "_partner_mobile_field")
    body = ast.dump(helper)
    assert "_fields" in body, "the mobile field must be resolved against the live registry"


def test_importer_never_falls_back_to_phone_for_mobile():
    """`phone` carries PhoneBusiness. Writing a mobile over it destroys data."""
    contacts = _function(_tree(IMPORTER), "_import_contacts")
    for node in ast.walk(contacts):
        if not (isinstance(node, ast.Call) and getattr(node.func, "id", "") == "_set_if"):
            continue
        if len(node.args) < 3:
            continue
        key, value = node.args[1], node.args[2]
        if not (isinstance(key, ast.Constant) and key.value == "phone"):
            continue
        assert "PhoneMobile" not in ast.dump(value), "PhoneMobile must never be written into the business phone field"


# ----------------------------------------------------------------------
# The runtime proofs must remain present and uncollected
# ----------------------------------------------------------------------
def test_runtime_gate_script_exists_and_is_not_collected():
    assert GATE_SCRIPT.is_file(), "the S1-S3 runtime gate script is missing"
    assert not GATE_SCRIPT.name.startswith("test_"), (
        "runtime gates need a live registry and must not be collected by pytest"
    )


@pytest.mark.parametrize("gate", ["gate_s1", "gate_s2", "gate_s3"])
def test_runtime_gate_script_defines_each_gate(gate):
    assert _function(_tree(GATE_SCRIPT), gate).name == gate
