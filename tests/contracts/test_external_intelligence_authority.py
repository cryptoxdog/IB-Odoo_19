"""Authority contract tests for single external intelligence (M1 / TASK-045).

Docs-only constitutional lock: local algorithmic engines are not architectural authority.
Distinct from ``test_external_intelligence_contract_parity.py`` (M0 readiness/parity).
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

ADR_SINGLE = ROOT / "docs/adr/ADR-003-single-external-intelligence-authority.md"
ADR_CONTACT = ROOT / "docs/adr/ADR-003-contact-import-configuration.md"
ADR_002 = ROOT / "docs/adr/ADR-002-gate-hub-phased-autonomy.md"
INVARIANTS = ROOT / "INVARIANTS.md"
ARCHITECTURE = ROOT / "ARCHITECTURE.md"
AGENTS = ROOT / "AGENTS.md"
ROADMAP = ROOT / "docs/GATE_AUTONOMY_ROADMAP.md"
TRACK_B_04 = ROOT / "docs/track_b/04_odoo_gate_consumer_wiring.md"


def test_mothball_adr_exists_and_declares_single_authority():
    text = ADR_SINGLE.read_text(encoding="utf-8")
    assert "Single External Intelligence Authority" in text
    assert "Accepted" in text
    assert "supersedes" in text.lower()
    assert "ADR-002" in text
    assert "architectural authority" in text.lower() or "not architectural" in text.lower()
    assert "Gate" in text
    assert "CEG" in text and "EIE" in text


def test_contact_import_adr_preserved_under_filename_collision():
    assert ADR_CONTACT.is_file(), "must not overwrite contact-import ADR-003"
    contact = ADR_CONTACT.read_text(encoding="utf-8")
    assert "Contact Import Configuration" in contact
    mothball = ADR_SINGLE.read_text(encoding="utf-8")
    assert "contact-import" in mothball.lower() or "ADR-003-contact-import" in mothball


def test_adr_002_topology_still_present():
    assert ADR_002.is_file()
    text = ADR_002.read_text(encoding="utf-8")
    assert "Gate is the mandatory hub" in text or "Gate is the mandatory hub" in text.replace("—", "-")
    assert "never Odoo" in text or "must not call CEG" in text


def test_invariants_declare_external_intelligence_authority():
    text = INVARIANTS.read_text(encoding="utf-8")
    assert "Single External Intelligence Authority" in text
    assert "ADR-003-single-external-intelligence-authority" in text
    assert "not architectural authority" in text.lower() or "Non-authority" in text


def test_architecture_points_at_successor_adr_not_fallback_authority():
    text = ARCHITECTURE.read_text(encoding="utf-8")
    assert "ADR-003-single-external-intelligence-authority" in text
    assert "Non-authority transitional residue" in text or "non-authority" in text.lower()
    # Architectural fallback row must not remain as product design.
    assert "| Fallback path | In-Odoo matcher" not in text


def test_agents_forbid_local_engines_as_authority():
    text = AGENTS.read_text(encoding="utf-8")
    assert "ADR-003-single" in text or "ADR-003-single-external-intelligence-authority" in text
    assert "architectural intelligence authority" in text.lower()
    assert "remove local matcher fallback in Phase 1" not in text


def test_roadmap_and_track_b_cite_successor_authority():
    roadmap = ROADMAP.read_text(encoding="utf-8")
    assert "ADR-003-single-external-intelligence-authority" in roadmap
    assert "Mothball authority" in roadmap or "non-authority" in roadmap.lower()

    track = TRACK_B_04.read_text(encoding="utf-8")
    assert "ADR-003-single" in track or "ADR-003-single-external-intelligence-authority" in track
    assert "NON-AUTHORITY" in track or "non-authority" in track.lower()
    assert "Preserve **try-Gate → local-fallback**" not in track


def test_acceptance_local_engines_no_longer_architectural_authority():
    """Registry acceptance: local algorithmic fallback is no longer architectural authority."""
    corpus = "\n".join(
        p.read_text(encoding="utf-8") for p in (ADR_SINGLE, INVARIANTS, ARCHITECTURE, AGENTS, ROADMAP, TRACK_B_04)
    )
    assert "architectural authority" in corpus.lower()
    assert "ADR-003-single-external-intelligence-authority" in corpus
