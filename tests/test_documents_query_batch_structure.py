"""The documents batch is structural. The performance scanner cannot see a helper."""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCUMENTS = ROOT / "plasticos_documents" / "models"
_QUERY_ATTRS = frozenset({"search", "search_count", "search_read", "read", "read_group"})


def _function(path: Path, name: str) -> ast.FunctionDef:
    tree = ast.parse(path.read_text())
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        for item in node.body:
            if isinstance(item, ast.FunctionDef) and item.name == name:
                return item
    raise AssertionError(f"{path.name} has no {name}")


def _query_calls(node: ast.AST) -> list[tuple[int, str]]:
    calls = []
    for child in ast.walk(node):
        if isinstance(child, ast.Call) and isinstance(child.func, ast.Attribute) and child.func.attr in _QUERY_ATTRS:
            calls.append((child.lineno, child.func.attr))
    return calls


def _query_calls_in_loops(func: ast.FunctionDef) -> list[tuple[int, str]]:
    calls = []
    for node in ast.walk(func):
        if isinstance(node, (ast.For, ast.While)):
            calls.extend(_query_calls(node))
    return calls


def test_scale_ticket_helper_does_not_search():
    helper = _function(DOCUMENTS / "transaction_docs.py", "_record_scale_ticket_escalation")
    assert _query_calls(helper) == []


def test_batched_queries_are_outside_the_record_loops():
    related = _function(DOCUMENTS / "document.py", "_get_related_transactions")
    missing = _function(DOCUMENTS / "transaction_docs.py", "cron_check_missing_docs")
    page = _function(DOCUMENTS / "transaction_docs.py", "_apply_missing_doc_page")
    scale = _function(DOCUMENTS / "transaction_docs.py", "cron_check_scale_tickets")
    assert _query_calls_in_loops(related) == []
    assert _query_calls_in_loops(missing) == []
    assert _query_calls_in_loops(page) == []
    assert _query_calls_in_loops(scale) == []
    cron_queries = [
        call
        for call in ast.walk(missing)
        if isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute) and call.func.attr in _QUERY_ATTRS
    ]
    assert len(cron_queries) == 1
    assert cron_queries[0].func.attr == "search"
    assert isinstance(cron_queries[0].func.value, ast.Name)
    assert cron_queries[0].func.value.id == "self"
