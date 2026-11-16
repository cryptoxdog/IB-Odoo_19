"""Material facts a Gate match cannot run without.

One predicate for both matching routes. The intake route asks it about the
intake's own polymer and form; the Opportunity route asks it about the frozen
approved-lot snapshot. Keys are the Gate query vocabulary both routes already
speak (``build_match_request``). A record may be saved without these facts (a
triaged web lead is a lead to complete); matching and offers are refused until
they are filled.
"""

from __future__ import annotations

from collections.abc import Mapping

# (Gate query key, operator-facing label)
REQUIRED_MATCH_MATERIAL = (
    ("polymer_type", "Polymer"),
    ("form", "Form"),
)


def missing_match_material(values: Mapping) -> list[str]:
    """Labels of the required material facts ``values`` does not carry; empty when complete."""
    return [label for key, label in REQUIRED_MATCH_MATERIAL if not values.get(key)]
