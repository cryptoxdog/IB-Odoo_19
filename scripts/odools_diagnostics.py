#!/usr/bin/env python3
"""Dump OdooLS diagnostics so an agent can remediate from file, span, and OLS code.

One run writes the current set. Read stdout or .l9/odools/diagnostics.jsonl.
Run again only after an edit, to see whether those diagnostics are gone.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.parse
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT_DIR = REPO / ".l9" / "odools"
RAW_PATH = OUT_DIR / "raw.json"
JSONL_PATH = OUT_DIR / "diagnostics.jsonl"
LOG_DIR = OUT_DIR / "logs"
COMMUNITY = Path.home() / "dev" / "odoo-19"
ENTERPRISE = Path.home() / "Dropbox" / "Repo_Dropbox_IB" / "IB-Odoo_19" / "odoo-enterprise"
EXTENSIONS = Path.home() / ".cursor" / "extensions"

SEVERITY_NAMES = {1: "error", 2: "warning", 3: "information", 4: "hint"}


def find_server() -> Path:
    """Highest installed odoo_ls_server, or $ODOO_LS_SERVER when that file exists."""
    override = os.environ.get("ODOO_LS_SERVER")
    if override:
        path = Path(override)
        if not path.is_file():
            raise SystemExit(f"ODOO_LS_SERVER is not a file: {path}")
        return path
    matches = [path for path in EXTENSIONS.glob("odoo.odoo-*/odoo_ls_server") if path.is_file()]
    if not matches:
        raise SystemExit(f"odoo_ls_server not found under {EXTENSIONS}/odoo.odoo-*/odoo_ls_server")
    return max(matches, key=_server_version)


def _server_version(path: Path) -> tuple[int, ...]:
    name = path.parent.name.removeprefix("odoo.odoo-")
    version = name.split("-", 1)[0]
    parts: list[int] = []
    for piece in version.split("."):
        parts.append(int(piece) if piece.isdigit() else 0)
    return tuple(parts)


def run_parse(server: Path) -> None:
    """Write raw server JSON. On failure leave raw.json untouched and name the log directory."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    python = REPO / ".venv" / "bin" / "python"
    if not python.is_file():
        raise SystemExit(f"Python not found: {python}")
    partial = RAW_PATH.with_suffix(".json.partial")
    partial.unlink(missing_ok=True)
    command = [
        str(server),
        "--parse",
        "--config-path",
        str(REPO / "odools.toml"),
        "--selected-config",
        "default",
        "--community-path",
        str(COMMUNITY),
        "--python",
        str(python),
        "--tracked-folders",
        str(REPO),
        "--log-level",
        "error",
        "--logs-directory",
        str(LOG_DIR),
        "-o",
        str(partial),
    ]
    # The server writes progress with carriage returns. Keep that off the diagnostic stdout.
    with (LOG_DIR / "parse.stdout").open("wb") as server_stdout, (LOG_DIR / "parse.stderr").open("wb") as server_stderr:
        completed = subprocess.run(command, cwd=REPO, check=False, stdout=server_stdout, stderr=server_stderr)
    if completed.returncode != 0 or not partial.is_file():
        partial.unlink(missing_ok=True)
        raise SystemExit(f"odoo_ls_server failed (exit {completed.returncode}). Logs: {LOG_DIR}")
    try:
        json.loads(partial.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        partial.unlink(missing_ok=True)
        raise SystemExit(f"odoo_ls_server wrote invalid JSON ({exc}). Logs: {LOG_DIR}") from exc
    partial.replace(RAW_PATH)


def rows_from_payload(payload: dict, repo: Path, *, include_all: bool) -> list[dict]:
    """Map a --parse document to 1-based remediation rows."""
    rows: list[dict] = []
    for event in payload.get("events", []):
        if event.get("type") != "diagnostic":
            continue
        path = _uri_to_path(event.get("uri", ""))
        if path is None or _is_upstream(path):
            continue
        display = _display_path(path, repo)
        for diagnostic in event.get("diagnostics") or []:
            row = _row(display, diagnostic)
            if include_all or _matches_plasticos(row):
                rows.append(row)
    return rows


def format_row(row: dict) -> str:
    """One remediation line: path, span, severity, OLS code, message, source."""
    code = row["code"] if row["code"] else "-"
    start = row["start"]
    end = row["end"]
    return (
        f"{row['path']}:{start['line']}:{start['character']}-{end['line']}:{end['character']} "
        f"[{row['severity']}] [{code}] {row['message']} ({row['source']})"
    )


def _row(display: str, diagnostic: dict) -> dict:
    return {
        "path": display,
        "severity": SEVERITY_NAMES.get(diagnostic.get("severity"), str(diagnostic.get("severity"))),
        "code": _code(diagnostic.get("code")),
        "source": diagnostic.get("source") or "",
        "message": diagnostic.get("message") or "",
        "start": _one_based(diagnostic.get("range", {}).get("start", {})),
        "end": _one_based(diagnostic.get("range", {}).get("end", {})),
    }


def _code(code: object) -> str | None:
    if code is None or code == "":
        return None
    if isinstance(code, dict):
        value = code.get("value")
        if value in (None, ""):
            return None
        return str(value)
    return str(code)


def _one_based(position: dict) -> dict:
    return {
        "line": int(position.get("line", 0)) + 1,
        "character": int(position.get("character", 0)) + 1,
    }


def _matches_plasticos(row: dict) -> bool:
    # A leading slash makes a repo-relative plasticos_* path match the same way an absolute path does.
    if "/plasticos_" in f"/{row['path']}":
        return True
    return "plasticos" in row["message"]


def _uri_to_path(uri: str) -> Path | None:
    if not uri:
        return None
    parsed = urllib.parse.urlparse(uri)
    if parsed.scheme == "file":
        return Path(urllib.parse.unquote(parsed.path))
    return Path(urllib.parse.unquote(uri))


def _is_upstream(path: Path) -> bool:
    resolved = path.resolve()
    for root in (COMMUNITY, ENTERPRISE):
        try:
            resolved.relative_to(root.resolve())
        except ValueError:
            continue
        return True
    return False


def _display_path(path: Path, repo: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(repo.resolve()).as_posix()
    except ValueError:
        return resolved.as_posix()


def write_reports(rows: list[dict]) -> None:
    JSONL_PATH.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    for row in rows:
        print(format_row(row))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Dump OdooLS diagnostics for remediation.")
    parser.add_argument(
        "--all",
        action="store_true",
        help="Print every workspace diagnostic. The default keeps plasticos paths and messages.",
    )
    args = parser.parse_args(argv)
    run_parse(find_server())
    payload = json.loads(RAW_PATH.read_text(encoding="utf-8"))
    write_reports(rows_from_payload(payload, REPO, include_all=args.all))
    return 0


if __name__ == "__main__":
    sys.exit(main())
