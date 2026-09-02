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
# The single SDK invocation surface (ADR-007). Anchored to the Gate client
# handle so it cannot collide with `cr.execute(` SQL calls.
_SDK_INVOKE_RE = re.compile(r"\bclient\.execute\(")


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


# ── ADR-014 — architecture boundary guards are release gates ──────────────
#
# The tests above prove Gate traffic has ONE egress module. These prove that
# module is an SDK *consumer* rather than a second Gate SDK: no Odoo-owned
# HTTP, hashing, signing, transport validation, retry, or peer routing anywhere
# in production code (pack ADR-001/ADR-013/ADR-016).

# Transport primitives Gate_SDK owns. Odoo must not implement or call these:
# hashing, signing, packet validation, hop/lineage construction.
_SDK_OWNED_TRANSPORT_RE = re.compile(
    r"\b("
    r"compute_transport_hash|compute_payload_hash|recompute_transport_core|"
    r"sign_transport_packet|verify_transport_packet_signature|"
    r"validate_transport_packet|validate_derived_transport_packet|"
    r"validate_outbound_gate_packet|canonical_json|"
    r"TransportHop\(|TransportLineage\(|TransportSecurity\(|TransportHeader\("
    r")"
)

# Direct HTTP *to Gate*. `/v1/execute` is Gate's own ingress path; an Odoo
# module naming it is by construction a second transport.
#
# Scope note: this deliberately does NOT forbid outbound HTTP generally. Odoo
# legitimately calls third parties that are not constellation nodes (the
# VanillaSoft CRM adapter, an LLM endpoint, lead image fetches). The contract
# prohibits a second *Gate* transport and any peer-worker address — not every
# socket Odoo opens. Widening this guard to all HTTP would fail on unrelated
# CRM modules and push the scope of a shadow-SDK removal into places it does
# not belong.
_GATE_INGRESS_RE = re.compile(r"/v1/(?:execute|health)\b")
_ANY_HTTP_RE = re.compile(
    r"(httpx\.(?:post|get|request|stream|AsyncClient|Client)|"
    r"requests\.(?:post|get|request|Session)|urllib\.request|http\.client)"
)

# Peer worker addresses. Odoo may know Gate; it must never know EIE (ADR-002).
_PEER_ADDRESS_RE = re.compile(
    r"(enrichment\.inference|eie_url|eie_endpoint|eie_host|worker_url|EIE_URL|EIE_HOST)",
    re.IGNORECASE,
)

# Retry/backoff machinery wrapped around a Gate call (ADR-008).
_RETRY_RE = re.compile(
    r"\b(tenacity|backoff\.on_exception|@retry\b|max_retries|retry_count|for _ in range\(\s*\d+\s*\):\s*#\s*retry)"
)


def _scan(pattern: re.Pattern[str], *, allow: tuple[Path, ...] = ()) -> list[str]:
    """Return `path:line` hits for a pattern across production addon code."""
    offenders: list[str] = []
    for module_dir in _SCAN_DIRS:
        for path in _py_files(module_dir):
            if path in allow or "/tests/" in path.as_posix():
                continue
            for lineno, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
                stripped = line.strip()
                # Comments and docstring prose may name a prohibited concept in
                # order to explain why it is prohibited; code may not.
                if stripped.startswith("#"):
                    continue
                if pattern.search(line):
                    offenders.append(f"{_rel(path)}:{lineno}")
    return offenders


def test_odoo_implements_no_sdk_owned_transport_primitive():
    """ADR-001 — hashing, signing, and packet validation belong to Gate_SDK."""
    offenders = _scan(_SDK_OWNED_TRANSPORT_RE)
    assert not offenders, (
        "Odoo production code touches an SDK-owned transport primitive "
        f"(hashing/signing/validation/hop/lineage) at: {offenders}. "
        "Gate_SDK is the sole transport authority (pack ADR-001)."
    )


def test_no_odoo_module_names_the_gate_ingress_path():
    """ADR-001/ADR-016 — `/v1/execute` is Gate_SDK's to call, never Odoo's."""
    offenders = _scan(_GATE_INGRESS_RE)
    assert not offenders, (
        f"Odoo production code names a Gate ingress path at: {offenders}. "
        "All Gate traffic goes through GateClient.send_to_gate (pack ADR-001)."
    )


def test_the_gate_boundary_module_opens_no_socket_of_its_own():
    """ADR-001 — the bridge invokes the SDK; it never performs HTTP itself.

    Scoped to `plasticos_gate/` because that is the module whose job is Gate
    transport, and therefore the only place a hand-rolled Gate HTTP client
    could plausibly be mistaken for correct.
    """
    offenders = []
    for path in _py_files(_BRIDGE_DIR):
        if "/tests/" in path.as_posix():
            continue
        for lineno, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if line.strip().startswith("#"):
                continue
            if _ANY_HTTP_RE.search(line):
                offenders.append(f"{_rel(path)}:{lineno}")
    assert not offenders, (
        f"plasticos_gate performs its own HTTP at: {offenders}. The bridge is "
        "an SDK consumer, not a Gate client (pack ADR-001/ADR-016)."
    )


def test_odoo_knows_no_peer_worker_address():
    """ADR-002 — Odoo addresses Gate; Gate resolves the worker."""
    offenders = _scan(_PEER_ADDRESS_RE)
    assert not offenders, (
        f"Odoo production code references a peer worker address at: {offenders}. "
        "Gate-only egress is release-blocking (INV-ODOO-GATE-ONLY-EGRESS)."
    )


def test_odoo_wraps_gate_in_no_retry_layer():
    """ADR-008 — retry belongs to EIE, Gate, and Gate_SDK; never to Odoo."""
    offenders = _scan(_RETRY_RE, allow=(ROOT / "plasticos_gate" / "services" / "gate_config.py",))
    assert not offenders, (
        f"Odoo production code adds a transport retry layer at: {offenders}. "
        "Odoo must not automatically replay a Gate operation "
        "(INV-ODOO-NO-TRANSPORT-RETRY)."
    )


def test_only_one_module_invokes_the_gate_sdk():
    """ADR-007 — one SDK invocation surface, not a caller per consumer.

    This previously asserted exactly one module *builds a packet*
    (``create_transport_packet(``), because SDK-GAP-1 forced Odoo to construct
    one. That gap is closed: ``GateClient.execute()`` takes business inputs and
    builds the packet itself, so the count of packet builders is now zero and
    an equality assertion against the bridge would fossilize the leak ADR-016
    exists to remove. The invariant ADR-007 actually states — one invocation
    surface — is asserted directly instead, and ``test_odoo_never_builds_a_
    transport_packet`` holds the zero-builders half.
    """
    callers = []
    for module_dir in _SCAN_DIRS:
        for path in _py_files(module_dir):
            if "/tests/" in path.as_posix():
                continue
            # Anchored to the Gate client handle on purpose: a bare `.execute(`
            # matches every `cr.execute(` SQL call in the addon tree.
            if _SDK_INVOKE_RE.search(path.read_text(encoding="utf-8", errors="replace")):
                callers.append(_rel(path))
    assert callers == [_rel(_BRIDGE_CLIENT)], (
        f"The Gate SDK is invoked from {callers}; exactly one invocation surface is permitted (pack ADR-007)."
    )


def test_gate_consumers_share_one_invocation_surface():
    """Matching and enrichment must not grow separate transport implementations.

    Contract §15: different domain payloads and actions are expected; different
    transport implementations are not.
    """
    client_src = _BRIDGE_CLIENT.read_text(encoding="utf-8")
    # Every public send_* helper must delegate to the single send_action core.
    helpers = re.findall(r"^def (send_\w+_action)\(", client_src, re.MULTILINE)
    assert set(helpers) >= {"send_match_action", "send_converge_action"}, helpers
    for helper in helpers:
        body = client_src.split(f"def {helper}(", 1)[1]
        assert "return send_action(" in body.split("\ndef ", 1)[0], (
            f"{helper} does not delegate to send_action — a second transport path is forming (pack ADR-007)."
        )
