"""Architecture guard: plasticos_gate is the single Gate egress point.

All Gate traffic must flow through ``plasticos_gate/services/gate_client.py``
(the sole ``constellation_node_sdk`` import site). This test fails CI if a
second egress path is introduced anywhere in the addon tree:

1. ``constellation_node_sdk`` imported outside ``plasticos_gate``.
2. ``plasticos.gate.url`` read outside ``plasticos_gate`` (a direct HTTP
   client pointed at the Gate would need the URL).
3. SDK transport primitives (``GateClient(``, ``send_to_gate``) referenced
   outside the canonical bridge module.
4. ``create_transport_packet(`` referenced ANYWHERE in the addon tree,
   including the bridge. Since the SDK grew ``GateClient.execute()``, packet
   construction belongs to the SDK; Odoo supplies an action and a payload and
   never builds a TransportPacket itself.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Addon/module code that must obey the single-egress rule. Tests are exempt
# (they import the bridge to exercise it); docs and CI tooling are not code.
_SCAN_DIRS = sorted(p for p in ROOT.iterdir() if p.is_dir() and p.name.startswith("plasticos_"))

_BRIDGE_DIR = ROOT / "plasticos_gate"
_BRIDGE_CLIENT = _BRIDGE_DIR / "services" / "gate_client.py"
_BRIDGE_CONFIG = _BRIDGE_DIR / "services" / "gate_config.py"

_SDK_IMPORT_RE = re.compile(r"^\s*(?:from|import)\s+constellation_node_sdk\b", re.MULTILINE)
_GATE_URL_RE = re.compile(r"plasticos\.gate\.url")
_TRANSPORT_RE = re.compile(r"GateClient\(|send_to_gate")
# Packet construction is the SDK's, everywhere — the bridge included.
_PACKET_BUILD_RE = re.compile(r"create_transport_packet\(")


def _py_files(base: Path):
    yield from base.rglob("*.py")


def _rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def test_sdk_imported_only_inside_plasticos_gate():
    offenders = []
    for module_dir in _SCAN_DIRS:
        for path in _py_files(module_dir):
            if path.is_relative_to(_BRIDGE_DIR):
                continue
            if _SDK_IMPORT_RE.search(path.read_text(encoding="utf-8", errors="replace")):
                offenders.append(_rel(path))
    assert not offenders, (
        "constellation_node_sdk imported outside plasticos_gate — single-egress "
        f"violation in: {offenders}. Route Gate traffic through "
        "plasticos_gate.services.gate_client instead."
    )


def test_gate_url_param_read_only_inside_plasticos_gate():
    offenders = []
    for module_dir in _SCAN_DIRS:
        for path in _py_files(module_dir):
            if path.is_relative_to(_BRIDGE_DIR):
                continue
            if _GATE_URL_RE.search(path.read_text(encoding="utf-8", errors="replace")):
                offenders.append(_rel(path))
    assert not offenders, (
        "plasticos.gate.url read outside plasticos_gate — single-egress "
        f"violation in: {offenders}. Only the canonical bridge may resolve the Gate URL."
    )


def test_transport_primitives_only_in_gate_client():
    offenders = []
    for module_dir in _SCAN_DIRS:
        for path in _py_files(module_dir):
            if path in (_BRIDGE_CLIENT, _BRIDGE_CONFIG):
                continue
            if _TRANSPORT_RE.search(path.read_text(encoding="utf-8", errors="replace")):
                offenders.append(_rel(path))
    assert not offenders, (
        "Gate transport primitives (GateClient/send_to_gate) "
        f"used outside the canonical bridge — single-egress violation in: {offenders}."
    )


def test_odoo_never_builds_a_transport_packet():
    """TransportPacket construction is the SDK's, including inside the bridge.

    The bridge calls ``GateClient.execute(action=..., payload=...)``; the SDK
    builds the root packet, forces the Gate destination, and owns the deadline.
    A reappearance of ``create_transport_packet(`` anywhere in the addon tree
    means Odoo has taken transport ownership back.
    """
    offenders = []
    for module_dir in _SCAN_DIRS:
        for path in _py_files(module_dir):
            if _PACKET_BUILD_RE.search(path.read_text(encoding="utf-8", errors="replace")):
                offenders.append(_rel(path))
    assert not offenders, (
        "create_transport_packet( found in the addon tree — Odoo must not build "
        f"TransportPackets; call GateClient.execute() instead. Offenders: {offenders}."
    )


def test_bridge_module_exists():
    """Guard the guard: the canonical bridge file must exist where documented."""
    assert _BRIDGE_CLIENT.is_file(), "plasticos_gate/services/gate_client.py missing"
    assert _BRIDGE_CONFIG.is_file(), "plasticos_gate/services/gate_config.py missing"
