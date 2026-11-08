#!/usr/bin/env python3
"""External intelligence readiness validator for PlasticOS Gate consumer (M0 / TASK-046).

Validates that Odoo-side Gate consumer surfaces stay aligned with owner payload
schemas and that Gate availability classification is coherent. Exit 0 on PASS.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OWNER_ROOTS = [
    Path.home() / "l9-constellation-repos" / "Cognitive.Engine.Graphs",
    Path.home() / "l9-constellation-repos" / "Enrichment.Inference.Engine",
]

REQUIRED_ACTIONS = {"match", "converge"}
OWNER_SCHEMA_RELATIVE = [
    ("ceg", "contracts/payloads/match-request.schema.yaml"),
    ("ceg", "contracts/payloads/match-response.schema.yaml"),
    ("eie", "contracts/feature_evidence/feature-evidence.schema.yaml"),
]


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return f"sha256:{digest.hexdigest()}"


def _import_gate_modules() -> dict[str, Any]:
    sys.path.insert(0, str(ROOT))
    from plasticos_gate.services import gate_client, gate_config, gate_contracts

    return {
        "gate_config": gate_config,
        "gate_client": gate_client,
        "gate_contracts": gate_contracts,
    }


def check_actions(mods: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    # Default ICP actions must remain match/converge (Gate routing authority).
    class _ICP:
        def get_param(self, key: str, default=None):
            return default

    class _Env:
        def __getitem__(self, key: str):
            if key == "ir.config_parameter":
                return self
            raise KeyError(key)

        def sudo(self):
            return self

        def get_param(self, key: str, default=None):
            return _ICP().get_param(key, default)

        cr = type("CR", (), {"dbname": "readiness"})()

    env = _Env()
    matching = mods["gate_config"].get_matching_action(env)
    enrichment = mods["gate_config"].get_enrichment_action(env)
    if matching not in REQUIRED_ACTIONS:
        errors.append(f"matching action must be one of {sorted(REQUIRED_ACTIONS)}, got {matching!r}")
    if enrichment not in REQUIRED_ACTIONS:
        errors.append(f"enrichment action must be one of {sorted(REQUIRED_ACTIONS)}, got {enrichment!r}")
    if matching != "match":
        errors.append(f"default matching action expected 'match', got {matching!r}")
    if enrichment != "converge":
        errors.append(f"default enrichment action expected 'converge', got {enrichment!r}")
    return errors


def check_contract_symbols(mods: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required = [
        "MatchRequest",
        "MatchResponse",
        "ConvergeRequest",
        "ConvergeResponse",
        "OdooContext",
    ]
    for name in required:
        if not hasattr(mods["gate_contracts"], name):
            errors.append(f"missing gate_contracts symbol: {name}")
    if not hasattr(mods["gate_client"], "failure_class_for"):
        errors.append("missing gate_client.failure_class_for (projection of the SDK retryability verdict)")
    if not hasattr(mods["gate_client"], "ensure_admitted"):
        errors.append("missing gate_client.ensure_admitted (Gate admission via GateClient.activate)")
    if getattr(mods["gate_client"], "_ODOO_REQUIRED_ACTIONS", None) != ("match", "converge"):
        errors.append("gate_client._ODOO_REQUIRED_ACTIONS must be exactly ('match', 'converge')")
    if not hasattr(mods["gate_config"], "classify_gate_availability"):
        errors.append("missing gate_config.classify_gate_availability")
    return errors


# Ownership boundary (GAR-ODOO-GATE-ALIGNMENT-001): Gate_SDK owns transport
# truth, configuration parsing and admission; Odoo must not carry a shadow of
# any of them. Static source checks only — this script is not a Gate client.
_BOUNDARY_FORBIDDEN = {
    "gate_client.py": (
        "import httpx",
        "classify_transport_failure",
        "_activated_ok",
        "_maybe_activate",
        "status_code",
        "TimeoutException",
    ),
    "gate_config.py": (
        "resolve_gate_signing",
        "_parse_verifying_keys",
        "_copy_supported_overrides",
        "_sdk_config_from_env",
        "GateClientConfig(",
        "model_copy(",
    ),
}
_BOUNDARY_REQUIRED = {
    "gate_client.py": (".retryable", "client.activate(required_actions=_ODOO_REQUIRED_ACTIONS"),
    "gate_config.py": ("get_gate_client_config_from_env(",),
}


def _code_text(path: Path) -> str:
    """Source with comments and docstrings stripped: prose may name a forbidden concept to explain it."""
    lines: list[str] = []
    in_doc = False
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.count('"""') == 1:
            in_doc = not in_doc
            continue
        if in_doc or stripped.startswith("#") or stripped.startswith('"""'):
            continue
        lines.append(line.split("#", 1)[0])
    return "\n".join(lines)


def check_ownership_boundary() -> list[str]:
    errors: list[str] = []
    services = ROOT / "plasticos_gate" / "services"
    for name, forbidden in _BOUNDARY_FORBIDDEN.items():
        code = _code_text(services / name)
        for token in forbidden:
            if token in code:
                errors.append(f"{name} re-implements an SDK-owned concern: {token!r}")
        for token in _BOUNDARY_REQUIRED[name]:
            if token not in code:
                errors.append(f"{name} does not consume the SDK-owned surface: {token!r}")
    for rel in ("plasticos_matching/models/match_orchestrator.py", "plasticos_enrichment/models/enrichment_run.py"):
        if "classify_transport_failure" in _code_text(ROOT / rel):
            errors.append(f"{rel} reclassifies Gate transport instead of consuming the bridge category")
    return errors


def check_owner_schemas(owner_roots: list[Path]) -> tuple[list[str], list[dict[str, Any]]]:
    errors: list[str] = []
    digests: list[dict[str, Any]] = []
    root_by_id = {}
    for root in owner_roots:
        name = root.name.lower()
        if "cognitive" in name or name.endswith("graphs"):
            root_by_id["ceg"] = root
        if "enrichment" in name or "inference" in name:
            root_by_id["eie"] = root
    for owner_id, relative in OWNER_SCHEMA_RELATIVE:
        root = root_by_id.get(owner_id)
        if root is None:
            errors.append(f"owner root for {owner_id} not provided")
            continue
        path = root / relative
        if not path.is_file():
            errors.append(f"missing owner schema: {path}")
            continue
        digests.append(
            {
                "owner": owner_id,
                "path": str(path),
                "digest": _sha256_file(path),
            }
        )
    return errors, digests


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--owner-root",
        action="append",
        type=Path,
        default=[],
        help="Owner repository root (repeatable). Defaults to constellation-repos CEG+EIE.",
    )
    parser.add_argument("--json-out", type=Path, default=None, help="Optional JSON report path")
    args = parser.parse_args(argv)

    owner_roots = list(args.owner_root) or [p for p in DEFAULT_OWNER_ROOTS if p.is_dir()]
    mods = _import_gate_modules()
    errors: list[str] = []
    errors.extend(check_contract_symbols(mods))
    errors.extend(check_ownership_boundary())
    errors.extend(check_actions(mods))
    schema_errors, digests = check_owner_schemas(owner_roots)
    errors.extend(schema_errors)

    report = {
        "schema": "l9.odoo_external_intelligence_readiness.v1",
        "result": "PASS" if not errors else "FAIL",
        "errors": errors,
        "owner_schema_digests": digests,
        "required_actions": sorted(REQUIRED_ACTIONS),
    }
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
