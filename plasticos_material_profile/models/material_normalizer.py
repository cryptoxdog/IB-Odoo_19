"""Shared material interpretation for the ERP and CRM importers.

The function resolves canonical masters. It does not create partners, products,
profiles, or transactions, and it does not commit.
"""

from __future__ import annotations

from typing import NamedTuple


class _Spec(NamedTuple):
    """One phrase. An empty slot means that component was not named."""

    polymer: str | None
    material_grade: str | None = None
    grade: str | None = None
    form: str | None = None
    source: str | None = None
    attributes: tuple[str, ...] = ()
    packaging_type: str | None = None
    color: tuple[str, ...] = ()
    filler_type: str | None = None
    process_type: str | None = None


def _color_codes(color) -> tuple[str, ...]:
    """One code, a space-separated cell, or a tuple. Empty stays empty."""
    if not color:
        return ()
    if isinstance(color, str):
        return tuple(part for part in color.split() if part)
    return tuple(color)


def _spec(
    *,
    polymer,
    material_grade=None,
    grade=None,
    form=None,
    source=None,
    attributes=(),
    packaging_type=None,
    color=None,
    filler_type=None,
    process_type=None,
):
    return _Spec(
        polymer=polymer,
        material_grade=material_grade,
        grade=grade,
        form=form,
        source=source,
        attributes=attributes,
        packaging_type=packaging_type,
        color=_color_codes(color),
        filler_type=filler_type,
        process_type=process_type,
    )


def _identity(spec):
    """Slots that must agree. Attributes, packaging, color, filler, and process come from the description."""
    return (spec.polymer, spec.material_grade, spec.grade, spec.form, spec.source)


# Exact phrases only. Unknown stays unspecified: no inferred source, cleanliness,
# dryness, or other attribute, and no mapping onto the OTHER polymer.
# A form is set only when the phrase names that form. An unknown form stays empty;
# identity does not require inventing one. The material grade is what the items were
# (drums, totes, pallets), set only when the phrase names it.
_SPECS = {
    "99 clear ldpe film": _spec(
        polymer="LDPE", grade="A", form="FILM", attributes=("clean", "dry"), packaging_type="bales"
    ),
    "ldpe grade a film": _spec(
        polymer="LDPE", grade="A", form="FILM", attributes=("clean", "dry"), packaging_type="bales"
    ),
    "95 clear ldpe film": _spec(polymer="LDPE", grade="B", form="FILM", attributes=("clean",)),
    "ldpe grade b film": _spec(polymer="LDPE", grade="B", form="FILM", attributes=("clean",)),
    "90 clear ldpe film": _spec(polymer="LDPE", grade="C", form="FILM"),
    "ldpe grade c film": _spec(polymer="LDPE", grade="C", form="FILM"),
    "pp film (bopp)": _spec(polymer="BOPP", form="FILM"),
    "pc/abs": _spec(polymer="PC_ABS", source="POST_INDUSTRIAL"),
    "pc-abs": _spec(polymer="PC_ABS", source="POST_INDUSTRIAL"),
    "3-7": _spec(polymer="3_7_COMMINGLED_BOTTLES", material_grade="BOTTLES", source="POST_CONSUMER"),
    "3-7 commingled bottles": _spec(polymer="3_7_COMMINGLED_BOTTLES", material_grade="BOTTLES", source="POST_CONSUMER"),
    "1-7": _spec(polymer="1_7_COMMINGLED_BOTTLES", material_grade="BOTTLES", source="POST_CONSUMER"),
    "1-7 commingled bottles": _spec(polymer="1_7_COMMINGLED_BOTTLES", material_grade="BOTTLES", source="POST_CONSUMER"),
    "pe": _spec(polymer="HDPE"),
    "pallets": _spec(polymer="PLASTIC_PALLETS"),
    "hdpe drums": _spec(polymer="HDPE", material_grade="DRUMS", packaging_type="loose"),
    "explicit hmw-hdpe drums": _spec(polymer="HDPE_HMW", material_grade="DRUMS"),
    "hdpe drums (hmw-hdpe)": _spec(polymer="HDPE_HMW", material_grade="DRUMS"),
    "ldpe film": _spec(polymer="LDPE", form="FILM", packaging_type="bales"),
    "ldpe film a": _spec(polymer="LDPE", grade="A", form="FILM", attributes=("clean", "dry"), packaging_type="bales"),
    "3-7 commingled": _spec(polymer="3_7_COMMINGLED_BOTTLES", material_grade="BOTTLES"),
    "1-7 commingled": _spec(polymer="1_7_COMMINGLED_BOTTLES", material_grade="BOTTLES"),
    "pp supersacs": _spec(polymer="PP", material_grade="SUPERACS"),
    # Operator ledger 2026-11-04. Both importers resolve these phrases.
    "pp supersacs (un-lined)": _spec(
        polymer="PP", material_grade="SUPERACS", attributes=("unlined",), packaging_type="bales"
    ),
    "pp supersacs - no liners": _spec(
        polymer="PP", material_grade="SUPERACS", attributes=("unlined",), packaging_type="bales"
    ),
    "super sacks": _spec(polymer="PP", material_grade="SUPERACS", attributes=("lined",), packaging_type="bales"),
    "pp supersacs (lined)": _spec(polymer="PP", material_grade="SUPERACS", packaging_type="bales"),
    "tubs": _spec(polymer="PP", material_grade="TUBS_LIDS", source="POST_CONSUMER", packaging_type="bales"),
    "occ bales": _spec(polymer="FIBER", material_grade="OCC", source="POST_CONSUMER", packaging_type="bales"),
    "old corrugated cardboard": _spec(
        polymer="FIBER", material_grade="OCC", source="POST_CONSUMER", packaging_type="bales"
    ),
    "hd/pp cornerboards": _spec(polymer="PP_PE", source="POST_CONSUMER", packaging_type="bales"),
    "pet bottles - post industrial": _spec(
        polymer="PET", material_grade="BOTTLES", source="POST_INDUSTRIAL", packaging_type="bales"
    ),
    "clear film": _spec(polymer="LLDPE", material_grade="STRETCH_FILM", form="FILM", packaging_type="bales"),
    "mixed pails": _spec(polymer="HDPE", material_grade="BUCKETS", form="LOOSE"),
    "hdpe/pp transitional purge regrind (frac melt)": _spec(
        polymer="PP_PE", form="PURGE", source="POST_INDUSTRIAL", attributes=("frac_melt",), packaging_type="gaylords"
    ),
    "pp/hd regrind": _spec(polymer="PP_PE", form="REGRIND", packaging_type="gaylords"),
    "strapping": _spec(polymer="PET", material_grade="STRAPPING"),
    "rigids": _spec(polymer="MRP"),
    # Masters seeded 2026-11-11. Exact ERP phrases only; a blend stays out of this table.
    "epe - pink": _spec(polymer="EPE"),
    "epe - white": _spec(polymer="EPE", color="WHITE"),
    "epp - black": _spec(polymer="EPP", color="BLACK"),
    "mdpe clips": _spec(polymer="MDPE"),
    "mdpe film on rolls - clear with print": _spec(polymer="MDPE", attributes=("printed",), color="CLEAR"),
    "mdpe post industrial printed rolls": _spec(
        polymer="MDPE", form="ROLLSTOCK", source="POST_INDUSTRIAL", attributes=("printed",)
    ),
    "petg bad pellets - bad melt": _spec(polymer="PETG", form="PELLETS"),
    "petg clear rolls": _spec(polymer="PETG", form="ROLLSTOCK", color="CLEAR"),
    "petg clear/cloudy repro pellet": _spec(polymer="PETG", form="PELLETS"),
    "petg resin": _spec(polymer="PETG"),
    "petg rolls - clear": _spec(polymer="PETG", form="ROLLSTOCK", color="CLEAR"),
    "petg rolls - tinted": _spec(polymer="PETG", form="ROLLSTOCK"),
    "petg trays": _spec(polymer="PETG", material_grade="TRAYS"),
    "san regrind": _spec(polymer="SAN", form="REGRIND"),
    # LD/LLD and two named grades. A second master is set only when the phrase names one seeded value.
    "ldpe/lldpe clear repro": _spec(polymer="LDPE_LLDPE", form="REPRO", color="CLEAR"),
    "lldpe/ldpe mixed color purge": _spec(polymer="LDPE_LLDPE", form="PURGE", color="MIXED"),
    "contaminated ldpe/lldpe": _spec(polymer="LDPE_LLDPE"),
    "ld/lldpe repro": _spec(polymer="LDPE_LLDPE", form="REPRO"),
    "ldpe/lldpe blue repro": _spec(polymer="LDPE_LLDPE", form="REPRO", color="BLUE"),
    "ldpe/lldpe blue/white purge": _spec(polymer="LDPE_LLDPE", form="PURGE", color=("BLUE", "WHITE")),
    "ldpe/lldpe repro": _spec(polymer="LDPE_LLDPE", form="REPRO"),
    "spc-a": _spec(polymer="PP", material_grade="TUBS_LIDS", source="POST_CONSUMER", packaging_type="bales"),
    "new opti bins": _spec(polymer="HDPE", material_grade="CRATES"),
    # HDPE crates are injection-molded. The process cell is the profile's origin process.
    "hdpe crates": _spec(polymer="HDPE", material_grade="CRATES", packaging_type="loose", process_type="injection"),
    # Slot fill 2026-11-12. Named rows, the approved 19, and every other corrected phrase.
    "hdpe bottles - mixed color": _spec(polymer="HDPE", material_grade="BOTTLES", color=("MIXED",)),
    "hdpe bottles - natural": _spec(polymer="HDPE", material_grade="BOTTLES", color=("NATURAL",)),
    "pp tubs & lids": _spec(polymer="PP", material_grade="TUBS_LIDS", source="POST_CONSUMER", packaging_type="bales"),
    "lldpe repro": _spec(polymer="LLDPE", form="REPRO"),
    "pet bottles - post consumer bales": _spec(
        polymer="PET", material_grade="BOTTLES", source="POST_CONSUMER", packaging_type="bales"
    ),
    "super sacks a - reusable from peanuts": _spec(polymer="PP", material_grade="SUPERACS", attributes=("reusable",)),
    "plastic pallets": _spec(polymer="PLASTIC_PALLETS", material_grade="PALLETS"),
    "hmw dunnage": _spec(polymer="HDPE_HMW", material_grade="DUNNAGE"),
    "pet trays -clear": _spec(polymer="PET", material_grade="TRAYS", color=("CLEAR",)),
    "lldpe black repro": _spec(polymer="LLDPE", form="REPRO", color=("BLACK",)),
    "pet trays": _spec(polymer="PET", material_grade="TRAYS", form="PARTS", packaging_type="bales"),
    "ibc tote bales": _spec(polymer="HDPE_HMW", material_grade="IBC_TOTES", packaging_type="bales"),
    "hmw drum regrind": _spec(polymer="HDPE_HMW", material_grade="DRUMS", form="REGRIND"),
    "ibc tote regrind": _spec(polymer="HDPE_HMW", material_grade="IBC_TOTES", form="REGRIND"),
    "mixed hd/pp pallets and knockdowns": _spec(polymer="PP_PE", material_grade="PALLETS"),
    "pet trays (clear)": _spec(polymer="PET", material_grade="TRAYS", color=("CLEAR",)),
    "ldpe mixed color repro": _spec(polymer="LDPE", form="REPRO", color=("MIXED",)),
    "1 & 2 bottles": _spec(
        polymer="1_2_COMMINGLED_BOTTLES", material_grade="BOTTLES", source="POST_CONSUMER", packaging_type="bales"
    ),
    "pp corrugated white stacked on pallets": _spec(
        polymer="PP", material_grade="PALLETS", form="CORRUGATED", packaging_type="palletized", color=("WHITE",)
    ),
    "pp trays": _spec(polymer="PP", material_grade="TRAYS"),
    "hdpe bottles - z bales": _spec(polymer="HDPE", material_grade="BOTTLES", packaging_type="bales"),
    "hdpe toters - roll out bins (wheels/axles removed)": _spec(polymer="HDPE", material_grade="TOTERS"),
    "pe feedstock clean & dry mostly clear film baled": _spec(
        polymer="HDPE", form="FILM", packaging_type="bales", attributes=("clean", "dry"), color=("CLEAR",)
    ),
    "ldpe film mixed color": _spec(polymer="LDPE", form="FILM", color=("MIXED",)),
    "hdpe drum regrind - washed": _spec(polymer="HDPE", material_grade="DRUMS", form="REGRIND"),
    "pet clear bottle in original boxes": _spec(polymer="PET", material_grade="BOTTLES", color=("CLEAR",)),
    "pp bales": _spec(polymer="PP", packaging_type="bales"),
    "pp tubs/lids": _spec(polymer="PP", material_grade="TUBS_LIDS"),
    "hdpe pipe": _spec(polymer="HDPE", material_grade="PIPE"),
    "pet trays -black": _spec(polymer="PET", material_grade="TRAYS", color=("BLACK",)),
    "hdpe crate grade regrind": _spec(polymer="HDPE", material_grade="CRATES", form="REGRIND"),
    "pet pellet": _spec(polymer="PET", form="PELLETS"),
    "hdpe jerry cans": _spec(polymer="HDPE", material_grade="JERRY_CANS"),
    "hmw dunnage trays": _spec(polymer="HDPE_HMW"),
    "ldpe printed rolls": _spec(polymer="LDPE", form="ROLLSTOCK", attributes=("printed",)),
    "pp pallet": _spec(polymer="PP", material_grade="PALLETS"),
    "pp repro": _spec(polymer="PP", form="REPRO"),
    "pp supersacs - grade a": _spec(polymer="PP", material_grade="SUPERACS"),
    "hdpe colored bottles in bales": _spec(polymer="HDPE", material_grade="BOTTLES", packaging_type="bales"),
    "hdpe toters": _spec(polymer="HDPE", material_grade="TOTERS"),
    "ldpe repro": _spec(polymer="LDPE", form="REPRO"),
    "pet clear trays": _spec(polymer="PET", material_grade="TRAYS", color=("CLEAR",)),
    "acrylic sheets": _spec(polymer="PMMA", form="SHEET"),
    "bottles (hd/pet)": _spec(
        polymer="1_2_COMMINGLED_BOTTLES", material_grade="BOTTLES", source="POST_CONSUMER", packaging_type="bales"
    ),
    "hdpe hmw drum regrind": _spec(polymer="HDPE_HMW", material_grade="DRUMS", form="REGRIND"),
    "hdpe toters - no metal": _spec(polymer="HDPE", material_grade="TOTERS", attributes=("no_metal",)),
    "post consumer pet bottles in bales": _spec(
        polymer="PET", material_grade="BOTTLES", source="POST_CONSUMER", packaging_type="bales"
    ),
    "hdpe drum regrind - blue/white/black": _spec(
        polymer="HDPE", material_grade="DRUMS", form="REGRIND", color=("BLUE", "WHITE", "BLACK")
    ),
    "hdpe injection - crate grade": _spec(polymer="HDPE", material_grade="CRATES", process_type="injection"),
    "ldpe - white bags in bales": _spec(polymer="LDPE", packaging_type="bales", color=("WHITE",)),
    "pet bottles - clear/green": _spec(polymer="PET", material_grade="BOTTLES", color=("CLEAR", "GREEN")),
    "pet mixed color bottle regrind": _spec(polymer="PET", material_grade="BOTTLES", form="REGRIND", color=("MIXED",)),
    "pp trays - grey & red": _spec(polymer="PP", material_grade="TRAYS", color=("RED", "GRAY")),
    "ps trays": _spec(polymer="PS", material_grade="TRAYS"),
    "abs orange (or black) trays": _spec(polymer="ABS", material_grade="TRAYS", color=("BLACK", "ORANGE")),
    "commingled bottles 1&2": _spec(
        polymer="1_2_COMMINGLED_BOTTLES", material_grade="BOTTLES", source="POST_CONSUMER", packaging_type="bales"
    ),
    "gaylord boxes (full bottom)": _spec(
        polymer="GAYLORD_BOXES", packaging_type="palletized", attributes=("reusable", "full_bottom")
    ),
    "hdpe pill bottle regrind": _spec(polymer="HDPE", material_grade="BOTTLES", form="REGRIND"),
    "hdpe pipe regrind": _spec(polymer="HDPE", material_grade="PIPE", form="REGRIND"),
    "hdpe sheets (black)": _spec(polymer="HDPE", form="SHEET", color=("BLACK",)),
    "hdpe toters - baled": _spec(polymer="HDPE", material_grade="TOTERS", packaging_type="bales"),
    "ldpe clear rolls - no print": _spec(polymer="LDPE", form="ROLLSTOCK", attributes=("no_print",), color=("CLEAR",)),
    "pe / pp regrind mixed": _spec(polymer="PP_PE", form="REGRIND", attributes=("mixed",)),
    "pet clear trim bales": _spec(polymer="PET", packaging_type="bales", color=("CLEAR",)),
    "plastic totes / trash cans (empty and clean)": _spec(
        polymer="HDPE", material_grade="TOTES", attributes=("clean",)
    ),
    "pp sanko pallet r/w w/rubber": _spec(polymer="PP", material_grade="PALLETS"),
    "compression molded regrind": _spec(polymer="PLASTIC_PALLETS", form="REGRIND", process_type="compression_mold"),
    "gaylords of amazon returns": _spec(polymer="MIXED", material_grade="RETURNS", packaging_type="gaylords"),
    "hdpe / ldpe regrind": _spec(polymer="MIXED", form="REGRIND"),
    "hdpe bottle regrind": _spec(polymer="HDPE", material_grade="BOTTLES", form="REGRIND"),
    "hdpe-hmw drum regrind clean - min melt 0.04": _spec(
        polymer="HDPE_HMW", material_grade="DRUMS", form="REGRIND", attributes=("clean",)
    ),
    "ldpe/hdpe grocery film": _spec(polymer="MIXED", form="FILM"),
    "pp corrugated (sheet/rolls/bales)": _spec(polymer="PP", packaging_type="bales"),
    "pp flower pots": _spec(polymer="PP", material_grade="FLOWER_POTS"),
    "baled hdpe shred": _spec(polymer="HDPE", form="SHRED", packaging_type="bales"),
    "hdpe bread trays (stacked on pallets)": _spec(
        polymer="HDPE", material_grade="PALLETS", packaging_type="palletized"
    ),
    "hdpe corrugated pipe": _spec(polymer="HDPE", material_grade="PIPE"),
    "hdpe hmw drum bales": _spec(polymer="HDPE_HMW", material_grade="DRUMS", packaging_type="bales"),
    "hips regrind (dart solo cups)": _spec(polymer="HIPS", material_grade="CUPS", form="REGRIND"),
    "hmw-hdpe drums - baled": _spec(polymer="HDPE_HMW", material_grade="DRUMS", packaging_type="bales"),
    "ldpe white rolls with print": _spec(polymer="LDPE", form="ROLLSTOCK", attributes=("printed",), color=("WHITE",)),
    "pc - clear / in gaylords": _spec(polymer="PC", packaging_type="gaylords", color=("CLEAR",)),
    "pet tray regrind - clear": _spec(polymer="PET", material_grade="TRAYS", form="REGRIND", color=("CLEAR",)),
    "pp regrind (5-10 melt) mixed color to go black": _spec(polymer="PP", form="REGRIND", color=("BLACK", "MIXED")),
    "pp regrind - white with print": _spec(polymer="PP", form="REGRIND", attributes=("printed",), color=("WHITE",)),
    "pp supersacs - reuseable": _spec(polymer="PP", material_grade="SUPERACS", attributes=("reusable",)),
    "pvc regrind white/gray": _spec(polymer="PVC", form="REGRIND", color=("WHITE", "GRAY")),
    "hd and pp purge/regrind/fluff": _spec(polymer="PP_PE", attributes=("mixed",)),
    "hd hmw drum bales": _spec(polymer="HDPE_HMW", material_grade="DRUMS", packaging_type="bales"),
    "hd hmw repro - approx - black and gray": _spec(polymer="HDPE_HMW", form="REPRO", color=("BLACK", "GRAY")),
    "hd tote inserts": _spec(polymer="HDPE", material_grade="TOTES"),
    "hdpe flower pots": _spec(polymer="HDPE", material_grade="FLOWER_POTS"),
    "hdpe frac melt repro - mixed color": _spec(
        polymer="HDPE", form="REPRO", attributes=("frac_melt",), color=("MIXED",)
    ),
    "hdpe pails": _spec(polymer="HDPE", material_grade="BUCKETS"),
    "hdpe pallet bales": _spec(polymer="HDPE", material_grade="PALLETS", packaging_type="bales"),
    "hdpe trays": _spec(polymer="HDPE", material_grade="TRAYS"),
    "hips trays": _spec(polymer="HIPS", material_grade="TRAYS"),
    "hmw black pipe regrind": _spec(polymer="HDPE_HMW", material_grade="PIPE", form="REGRIND", color=("BLACK",)),
    "lldpe m/c repro": _spec(polymer="LLDPE", form="REPRO"),
    "mixed dunnage trays": _spec(polymer="PLASTIC_PALLETS", material_grade="DUNNAGE"),
    "pc sheets": _spec(polymer="PC", form="SHEET"),
    "pet bottle regrind": _spec(polymer="PET", material_grade="BOTTLES", form="REGRIND"),
    "pet clear trays with metal and glass": _spec(
        polymer="PET", material_grade="TRAYS", attributes=("with_metal",), color=("CLEAR",)
    ),
    "pet strapping - opaque": _spec(polymer="PET", material_grade="STRAPPING"),
    "pet trays - clear": _spec(polymer="PET", material_grade="TRAYS", color=("CLEAR",)),
    "pp repro - mixed color": _spec(polymer="PP", form="REPRO", color=("MIXED",)),
    "pp strapping": _spec(polymer="PP", material_grade="STRAPPING"),
    "ps baled trays": _spec(polymer="PS", material_grade="TRAYS", packaging_type="bales"),
    "red totes on casters": _spec(polymer="HDPE", material_grade="TOTERS", color=("RED",)),
    "supersacs - grade a": _spec(polymer="PP", material_grade="SUPERACS"),
    "1-7 co-mingled bales": _spec(
        polymer="1_7_COMMINGLED_BOTTLES", material_grade="BOTTLES", source="POST_CONSUMER", packaging_type="bales"
    ),
    "battery cell trays (abs_hf380g)": _spec(polymer="ABS", material_grade="TRAYS"),
    "black pallets stacked": _spec(
        polymer="PLASTIC_PALLETS", material_grade="PALLETS", packaging_type="palletized", color=("BLACK",)
    ),
    "chopped pet strapping": _spec(polymer="PET", material_grade="STRAPPING", form="CHOPPED"),
    "delivered - baled pp fibc bags": _spec(polymer="PP", packaging_type="bales"),
    "hd repro - grey": _spec(polymer="HDPE", form="REPRO", color=("GRAY",)),
    "hdpe color bales": _spec(polymer="HDPE", packaging_type="bales"),
    "hdpe crate regrind – 5 – 10 melt": _spec(polymer="HDPE", material_grade="CRATES", form="REGRIND"),
    "hdpe drum regrind": _spec(polymer="HDPE", material_grade="DRUMS", form="REGRIND"),
    "hdpe drums in bales": _spec(polymer="HDPE", material_grade="DRUMS", packaging_type="bales"),
    "hdpe hmw drum shred": _spec(polymer="HDPE_HMW", material_grade="DRUMS", form="SHRED"),
    "hdpe low melt drum regrind": _spec(polymer="HDPE", material_grade="DRUMS", form="REGRIND"),
    "hdpe pallet": _spec(polymer="HDPE", material_grade="PALLETS"),
    "hdpe pallet regrind": _spec(polymer="HDPE", material_grade="PALLETS", form="REGRIND"),
    "hmw black and yellow pipe regrind": _spec(
        polymer="HDPE_HMW", material_grade="PIPE", form="REGRIND", color=("BLACK", "YELLOW")
    ),
    "hmw drum and jug bales": _spec(polymer="HDPE_HMW", material_grade="DRUMS", packaging_type="bales"),
    "hmw drum bales": _spec(polymer="HDPE_HMW", material_grade="DRUMS", packaging_type="bales"),
    "hmw drum regrind (need wash)": _spec(polymer="HDPE_HMW", material_grade="DRUMS", form="REGRIND"),
    "ldpe densified foam - natural/mixed color": _spec(polymer="LDPE", form="DENSIFIED", color=("NATURAL", "MIXED")),
    "ldpe printed rolls and loose film in gaylords": _spec(
        polymer="LDPE", packaging_type="gaylords", attributes=("printed",)
    ),
    "ldpe printed/color rolls": _spec(polymer="LDPE", form="ROLLSTOCK", attributes=("printed",)),
    "pc clear trays": _spec(polymer="PC", material_grade="TRAYS", color=("CLEAR",)),
    "pc water bottles baled": _spec(polymer="PC", material_grade="BOTTLES", packaging_type="bales"),
    "pe printed rolls": _spec(polymer="HDPE", form="ROLLSTOCK", attributes=("printed",)),
    "pet bottles baled": _spec(polymer="PET", material_grade="BOTTLES", packaging_type="bales"),
    "pet chopped strapping": _spec(polymer="PET", material_grade="STRAPPING", form="CHOPPED"),
    "pet clear tray / trim": _spec(polymer="PET", material_grade="TRAYS", color=("CLEAR",)),
    "pet pellet - clear, blue, & mixed color": _spec(polymer="PET", form="PELLETS", color=("BLUE", "CLEAR", "MIXED")),
    "pet strapping - chopped": _spec(polymer="PET", material_grade="STRAPPING", form="CHOPPED"),
    "pet thermoform trays - post industrial": _spec(
        polymer="PET", material_grade="TRAYS", source="POST_INDUSTRIAL", process_type="thermoform"
    ),
    "pet tray shred (clear)": _spec(polymer="PET", material_grade="TRAYS", form="SHRED", color=("CLEAR",)),
    "pp corrugated sheet": _spec(polymer="PP", form="SHEET"),
    "pp natural trays (as per sample)": _spec(polymer="PP", material_grade="TRAYS", color=("NATURAL",)),
    "pp nonwoven rolls (on pallets)": _spec(
        polymer="PP", form="ROLLSTOCK", packaging_type="palletized", attributes=("non_woven",)
    ),
    "pp supersacks - peanut bags": _spec(polymer="PP", material_grade="SUPERACS"),
    "pp trays and other items": _spec(polymer="PP", material_grade="TRAYS"),
    "pp yogurt cup regrind - no paper": _spec(polymer="PP", material_grade="CUPS", form="REGRIND"),
    "pvc pipe": _spec(polymer="PVC", material_grade="PIPE"),
    "1 & 2 bottles (pet/hdpe)": _spec(
        polymer="1_2_COMMINGLED_BOTTLES", material_grade="BOTTLES", source="POST_CONSUMER", packaging_type="bales"
    ),
    "1 & 2 pet & hdpe co-mingled bottles (post consumer)": _spec(
        polymer="1_2_COMMINGLED_BOTTLES", material_grade="BOTTLES", source="POST_CONSUMER", packaging_type="bales"
    ),
    "3-7 bales": _spec(
        polymer="3_7_COMMINGLED_BOTTLES", material_grade="BOTTLES", source="POST_CONSUMER", packaging_type="bales"
    ),
    "bopp film bales": _spec(polymer="BOPP", form="FILM", packaging_type="bales"),
    "bopp metalized rolls (unprinted)": _spec(polymer="BOPP", form="ROLLSTOCK", attributes=("metalized", "no_print")),
    "bopp rolls": _spec(polymer="BOPP", form="ROLLSTOCK"),
    "compression molded": _spec(polymer="PLASTIC_PALLETS", material_grade="PALLETS", process_type="compression_mold"),
    "hd hmw repro - grey": _spec(polymer="HDPE_HMW", form="REPRO", color=("GRAY",)),
    "hd/hmw pipe shred": _spec(polymer="HDPE_HMW", material_grade="PIPE", form="SHRED"),
    "hd/hmw repro": _spec(polymer="HDPE_HMW", form="REPRO"),
    "hdpe bales": _spec(polymer="HDPE", packaging_type="bales"),
    "hdpe bucket regrind": _spec(polymer="HDPE", material_grade="BUCKETS", form="REGRIND"),
    "hdpe drum shred": _spec(polymer="HDPE", material_grade="DRUMS", form="SHRED"),
    "hdpe drums/jerry can bales": _spec(polymer="HDPE", material_grade="DRUMS", packaging_type="bales"),
    "hdpe dunnage - orange": _spec(polymer="HDPE", material_grade="DUNNAGE", color=("ORANGE",)),
    "hdpe hmw drum regrind - with soapy residue": _spec(polymer="HDPE_HMW", material_grade="DRUMS", form="REGRIND"),
    "hdpe hmw gas tank regrind black/red": _spec(polymer="HDPE_HMW", form="REGRIND", color=("BLACK", "RED")),
    "hdpe hmw jerry can shred": _spec(polymer="HDPE_HMW", material_grade="JERRY_CANS", form="SHRED"),
    "hdpe knockdown and totes": _spec(polymer="HDPE", material_grade="TOTES"),
    "hdpe knockdowns & totes": _spec(polymer="HDPE", material_grade="TOTES"),
    "hdpe natural - bales with purge": _spec(polymer="HDPE", form="PURGE", packaging_type="bales", color=("NATURAL",)),
    "hdpe pond liner - black regrind": _spec(polymer="HDPE", material_grade="LINERS", form="REGRIND", color=("BLACK",)),
    "hdpe toters - all metal & wheels removed": _spec(
        polymer="HDPE", material_grade="TOTERS", attributes=("no_metal",)
    ),
    "hdpe toters - wheels removed except bottom one": _spec(polymer="HDPE", material_grade="TOTERS"),
    "hdpe toters w/ metal": _spec(polymer="HDPE", material_grade="TOTERS", attributes=("with_metal",)),
    "hdpe z-bales": _spec(polymer="HDPE", packaging_type="bales"),
    "hmw drum regrind (soapy residue)": _spec(polymer="HDPE_HMW", material_grade="DRUMS", form="REGRIND"),
    "hmw ibc bales": _spec(polymer="HDPE_HMW", packaging_type="bales"),
    "ibc tote regrind clean, washed, no paper": _spec(
        polymer="HDPE_HMW", material_grade="IBC_TOTES", form="REGRIND", attributes=("clean",)
    ),
    "ldpe b grade bales": _spec(polymer="LDPE", packaging_type="bales"),
    "ldpe bags with print": _spec(polymer="LDPE", attributes=("printed",)),
    "ldpe black repro": _spec(polymer="LDPE", form="REPRO", color=("BLACK",)),
    "ldpe clear - baled only": _spec(polymer="LDPE", packaging_type="bales", color=("CLEAR",)),
    "ldpe clear printed rolls on pallets": _spec(
        polymer="LDPE",
        material_grade="PALLETS",
        form="ROLLSTOCK",
        packaging_type="palletized",
        attributes=("printed",),
        color=("CLEAR",),
    ),
    "ldpe clear rolls": _spec(polymer="LDPE", form="ROLLSTOCK", color=("CLEAR",)),
    "ldpe color repro": _spec(polymer="LDPE", form="REPRO"),
    "ldpe post industrial rolls - clear": _spec(
        polymer="LDPE", form="ROLLSTOCK", source="POST_INDUSTRIAL", color=("CLEAR",)
    ),
    "ldpe rolls - post industrial": _spec(polymer="LDPE", form="ROLLSTOCK", source="POST_INDUSTRIAL"),
    "lldpe rolls": _spec(polymer="LLDPE", form="ROLLSTOCK"),
    "mrp in bales": _spec(polymer="MRP", packaging_type="bales"),
    "pc regrind - grey & white": _spec(polymer="PC", form="REGRIND", color=("WHITE", "GRAY")),
    "pet bottle clear no cap, no label, no rings": _spec(polymer="PET", material_grade="BOTTLES", color=("CLEAR",)),
    "pet chopped strapping - translucent only": _spec(polymer="PET", material_grade="STRAPPING", form="CHOPPED"),
    "pet clear bales": _spec(polymer="PET", packaging_type="bales", color=("CLEAR",)),
    "pet clear preform & bottle regrind": _spec(
        polymer="PET", material_grade="BOTTLES", form="REGRIND", color=("CLEAR",)
    ),
    "pet monofilament (strands in gaylords)": _spec(polymer="PET", packaging_type="gaylords"),
    "pet pellet - clear - clean - bottle grade": _spec(
        polymer="PET", form="PELLETS", attributes=("clean",), color=("CLEAR",)
    ),
    "pet pellet w/ streamers": _spec(polymer="PET", form="PELLETS"),
    "pet post industrial trays - clear": _spec(
        polymer="PET", material_grade="TRAYS", source="POST_INDUSTRIAL", color=("CLEAR",)
    ),
    "pet strapping (translucent)": _spec(polymer="PET", material_grade="STRAPPING"),
    "pet strapping - baled": _spec(polymer="PET", material_grade="STRAPPING", packaging_type="bales"),
    "pet strapping - chopped green": _spec(polymer="PET", material_grade="STRAPPING", form="CHOPPED", color=("GREEN",)),
    "pet strapping - green": _spec(polymer="PET", material_grade="STRAPPING", color=("GREEN",)),
    "pet trays (black)": _spec(polymer="PET", material_grade="TRAYS", color=("BLACK",)),
    "pet trays (green)": _spec(polymer="PET", material_grade="TRAYS", color=("GREEN",)),
    "pet trays - c;ear (in boxes on pallets)": _spec(
        polymer="PET", material_grade="PALLETS", packaging_type="palletized"
    ),
    "post industrial bopp film rolls & bales": _spec(polymer="BOPP", source="POST_INDUSTRIAL", packaging_type="bales"),
    "pp corrugated bales with paper inserts and labels": _spec(polymer="PP", packaging_type="bales"),
    "pp cups (post industrial)": _spec(polymer="PP", material_grade="CUPS", source="POST_INDUSTRIAL"),
    "pp cups with paper label": _spec(polymer="PP", material_grade="CUPS"),
    "pp supersacks - white - 99% reuseable": _spec(
        polymer="PP", material_grade="SUPERACS", attributes=("reusable",), color=("WHITE",)
    ),
    "pp supersacs - grade a (bright/white)": _spec(polymer="PP", material_grade="SUPERACS", color=("WHITE",)),
    "pp trays - natural": _spec(polymer="PP", material_grade="TRAYS", color=("NATURAL",)),
    "pp woven rolls - white (on pallets)": _spec(
        polymer="PP",
        material_grade="PALLETS",
        form="ROLLSTOCK",
        packaging_type="palletized",
        attributes=("woven",),
        color=("WHITE",),
    ),
    "pvc trays": _spec(polymer="PVC", material_grade="TRAYS"),
    "thermoform pallets in bales": _spec(
        polymer="PLASTIC_PALLETS", material_grade="PALLETS", packaging_type="bales", process_type="thermoform"
    ),
    "toyota totes - stacked on pallets": _spec(
        polymer="PLASTIC_PALLETS", material_grade="PALLETS", packaging_type="palletized"
    ),
    "tubs and lids": _spec(polymer="PP", material_grade="TUBS_LIDS", form="PARTS"),
    "3-7 plastic in bales": _spec(
        polymer="3_7_COMMINGLED_BOTTLES", material_grade="BOTTLES", source="POST_CONSUMER", packaging_type="bales"
    ),
    "black pet thermoform trays": _spec(
        polymer="PET", material_grade="TRAYS", process_type="thermoform", color=("BLACK",)
    ),
    "black pet trays": _spec(polymer="PET", material_grade="TRAYS", color=("BLACK",)),
    "bom - (bopp film bales w/<1% fiber/chip-board)": _spec(polymer="BOPP", form="FILM", packaging_type="bales"),
    "bopp printed": _spec(polymer="BOPP", attributes=("printed",)),
    "bopp printed mixed color - baled": _spec(
        polymer="BOPP", packaging_type="bales", attributes=("printed",), color=("MIXED",)
    ),
    "bopp rolls - printed": _spec(polymer="BOPP", form="ROLLSTOCK", attributes=("printed",)),
    "bopp rolls on pallets": _spec(
        polymer="BOPP", material_grade="PALLETS", form="ROLLSTOCK", packaging_type="palletized"
    ),
    "bopp strips - bales": _spec(polymer="BOPP", packaging_type="bales"),
    "bopp strips in bales": _spec(polymer="BOPP", packaging_type="bales"),
    "bopp white baled": _spec(polymer="BOPP", packaging_type="bales", color=("WHITE",)),
    "chopped green pet strapping": _spec(polymer="PET", material_grade="STRAPPING", form="CHOPPED", color=("GREEN",)),
    "clear pet thermoform trays": _spec(
        polymer="PET", material_grade="TRAYS", process_type="thermoform", color=("CLEAR",)
    ),
    "clear pet tray regrind in gaylords": _spec(
        polymer="PET", material_grade="TRAYS", form="REGRIND", packaging_type="gaylords", color=("CLEAR",)
    ),
    "clear pet trays boxed - on pallets": _spec(
        polymer="PET", material_grade="PALLETS", packaging_type="palletized", color=("CLEAR",)
    ),
    "clear pet trays in bales": _spec(polymer="PET", material_grade="TRAYS", packaging_type="bales", color=("CLEAR",)),
    "eps on pallets": _spec(polymer="EPS", material_grade="PALLETS", packaging_type="palletized"),
    "gaylords / pallets rebate": _spec(polymer="PLASTIC_PALLETS", material_grade="PALLETS", packaging_type="gaylords"),
    "green pet strapping - baled": _spec(
        polymer="PET", material_grade="STRAPPING", packaging_type="bales", color=("GREEN",)
    ),
    "green pet strapping - chopped": _spec(polymer="PET", material_grade="STRAPPING", form="CHOPPED", color=("GREEN",)),
    "hd bottle purge": _spec(polymer="HDPE", material_grade="BOTTLES", form="PURGE"),
    "hd bottle/purge bales": _spec(polymer="HDPE", material_grade="BOTTLES", form="PURGE", packaging_type="bales"),
    "hd hmw repro - gray": _spec(polymer="HDPE_HMW", form="REPRO", color=("GRAY",)),
    "hd hmw sheets / dividers": _spec(polymer="HDPE_HMW", form="SHEET"),
    "hd inj pallet": _spec(polymer="HDPE", material_grade="PALLETS"),
    "hd natural purge/baled bottles": _spec(
        polymer="HDPE", material_grade="BOTTLES", form="PURGE", packaging_type="bales", color=("NATURAL",)
    ),
    "hd tote r/w w/handles": _spec(polymer="HDPE", material_grade="TOTES"),
    "hdpe (#2), pigmented, bales": _spec(polymer="HDPE", packaging_type="bales"),
    "hdpe baled buckets": _spec(polymer="HDPE", material_grade="BUCKETS", packaging_type="bales"),
    "hdpe baled pallets": _spec(polymer="HDPE", material_grade="PALLETS", packaging_type="bales"),
    "hdpe bins, pallets, knockdowns & lids": _spec(polymer="HDPE", material_grade="PALLETS"),
    "hdpe black pails (no metal)": _spec(
        polymer="HDPE", material_grade="BUCKETS", attributes=("no_metal",), color=("BLACK",)
    ),
    "hdpe blue/white drum regrind": _spec(
        polymer="HDPE", material_grade="DRUMS", form="REGRIND", color=("BLUE", "WHITE")
    ),
    "hdpe bottle & white purge": _spec(polymer="HDPE", material_grade="BOTTLES", form="PURGE", color=("WHITE",)),
    "hdpe bottle purge": _spec(polymer="HDPE", material_grade="BOTTLES", form="PURGE"),
    "hdpe bread trays": _spec(polymer="HDPE", material_grade="TRAYS"),
    "hdpe bucket lids": _spec(polymer="HDPE", material_grade="BUCKETS"),
    "hdpe bucket regrind - inj": _spec(polymer="HDPE", material_grade="BUCKETS", form="REGRIND"),
    "hdpe corner boards": _spec(polymer="HDPE", material_grade="CORNERBOARDS"),
    "hdpe crate grade": _spec(polymer="HDPE", material_grade="CRATES"),
    "hdpe crate grade regrind (blue)": _spec(polymer="HDPE", material_grade="CRATES", form="REGRIND", color=("BLUE",)),
    "hdpe crate grade regrind - mixed color": _spec(
        polymer="HDPE", material_grade="CRATES", form="REGRIND", color=("MIXED",)
    ),
    "hdpe drum - loose": _spec(polymer="HDPE", material_grade="DRUMS", form="LOOSE"),
    "hdpe drum regrind - clean": _spec(polymer="HDPE", material_grade="DRUMS", form="REGRIND", attributes=("clean",)),
    "hdpe drum regrind - dirty": _spec(polymer="HDPE", material_grade="DRUMS", form="REGRIND"),
    "hdpe drum regrind w/paper labels": _spec(polymer="HDPE", material_grade="DRUMS", form="REGRIND"),
    "hdpe dunnage": _spec(polymer="HDPE", material_grade="DUNNAGE"),
    "hdpe feed bucket regrind": _spec(polymer="HDPE", material_grade="BUCKETS", form="REGRIND"),
    "hdpe frac melt - milk jugs - natural and white color mixed": _spec(
        polymer="HDPE", attributes=("frac_melt",), color=("WHITE", "NATURAL")
    ),
    "hdpe frac melt bottle purge": _spec(
        polymer="HDPE", material_grade="BOTTLES", form="PURGE", attributes=("frac_melt",)
    ),
    "hdpe frac melt bottle regrind w/ paper label": _spec(
        polymer="HDPE", material_grade="BOTTLES", form="REGRIND", attributes=("frac_melt",)
    ),
    "hdpe frac melt corrugated bales": _spec(polymer="HDPE", packaging_type="bales", attributes=("frac_melt",)),
    "hdpe hmw black/yellow pipe regrind": _spec(
        polymer="HDPE_HMW", material_grade="PIPE", form="REGRIND", color=("BLACK", "YELLOW")
    ),
    "hdpe hmw drum regrind (washed)": _spec(polymer="HDPE_HMW", material_grade="DRUMS", form="REGRIND"),
    "hdpe hmw drum regrind - clean": _spec(
        polymer="HDPE_HMW", material_grade="DRUMS", form="REGRIND", attributes=("clean",)
    ),
    "hdpe hmw drum regrind - w/ cork - no value": _spec(
        polymer="HDPE_HMW", material_grade="DRUMS", form="REGRIND", attributes=("no_value",)
    ),
    "hdpe hmw dunnage": _spec(polymer="HDPE_HMW", material_grade="DUNNAGE"),
    "hdpe hmw ibc tote regrind": _spec(polymer="HDPE_HMW", material_grade="IBC_TOTES", form="REGRIND"),
    "hdpe hmw pipe regrind": _spec(polymer="HDPE_HMW", material_grade="PIPE", form="REGRIND"),
    "hdpe inj m/c bucket": _spec(polymer="HDPE", material_grade="BUCKETS"),
    "hdpe knockdown totes": _spec(polymer="HDPE", material_grade="TOTES"),
    "hdpe mixed color bottle purge": _spec(polymer="HDPE", material_grade="BOTTLES", form="PURGE", color=("MIXED",)),
    "hdpe mixed color bottle regrind": _spec(
        polymer="HDPE", material_grade="BOTTLES", form="REGRIND", color=("MIXED",)
    ),
    "hdpe natural bales": _spec(polymer="HDPE", packaging_type="bales", color=("NATURAL",)),
    "hdpe pallet regrind w/ pp contamination": _spec(
        polymer="HDPE", material_grade="PALLETS", form="REGRIND", attributes=("pp_contaminated",)
    ),
    "hdpe pallets & knockdowns": _spec(polymer="HDPE", material_grade="PALLETS"),
    "hdpe repro": _spec(polymer="HDPE", form="REPRO"),
    "hdpe repro from buckets and pales": _spec(polymer="HDPE", material_grade="BUCKETS", form="REPRO"),
    "hdpe rolls": _spec(polymer="HDPE", form="ROLLSTOCK"),
    "hdpe shredded totes": _spec(polymer="HDPE", material_grade="TOTES", form="SHRED"),
    "hdpe slip sheets in bales": _spec(polymer="HDPE", packaging_type="bales"),
    "hdpe stacked pallets": _spec(polymer="HDPE", material_grade="PALLETS", packaging_type="palletized"),
    "hdpe stadium seats in bales": _spec(polymer="HDPE", packaging_type="bales"),
    "hdpe tote shred": _spec(polymer="HDPE", material_grade="TOTES", form="SHRED"),
    "hdpe toters (metal removed)": _spec(polymer="HDPE", material_grade="TOTERS", attributes=("no_metal",)),
    "hdpe totes (nested on pallets)": _spec(polymer="HDPE", material_grade="TOTES", packaging_type="palletized"),
    "hdpe totes (nested on pallets) - hard plastic scrap": _spec(
        polymer="HDPE", material_grade="TOTES", packaging_type="palletized"
    ),
    "hdpe trays (on pallets - secured to pallet)": _spec(
        polymer="HDPE", material_grade="PALLETS", packaging_type="palletized"
    ),
    "hdpe white bales": _spec(polymer="HDPE", packaging_type="bales", color=("WHITE",)),
    "hdpe-hmw drum regrind (dirty)": _spec(polymer="HDPE_HMW", material_grade="DRUMS", form="REGRIND"),
    "hdpe-hmw dunnage": _spec(polymer="HDPE_HMW", material_grade="DUNNAGE"),
    "hips baled": _spec(polymer="HIPS", packaging_type="bales"),
    "hips bales with slight metal contamination": _spec(
        polymer="HIPS", packaging_type="bales", attributes=("with_metal",)
    ),
    "hips black & white regrind - extrusion grade - 1-3 melt": _spec(
        polymer="HIPS", form="REGRIND", process_type="extrusion", color=("WHITE", "BLACK")
    ),
    "hips black trays": _spec(polymer="HIPS", material_grade="TRAYS", color=("BLACK",)),
    "hips purges": _spec(polymer="HIPS", form="PURGE"),
    "hips regrind (solo cups)": _spec(polymer="HIPS", material_grade="CUPS", form="REGRIND"),
    "hips trays with paper": _spec(polymer="HIPS", material_grade="TRAYS"),
    "hmw drum": _spec(polymer="HDPE_HMW", material_grade="DRUMS"),
    "hmw drum dirty": _spec(polymer="HDPE_HMW", material_grade="DRUMS"),
    "hmw drum regrind (post industrial)": _spec(
        polymer="HDPE_HMW", material_grade="DRUMS", form="REGRIND", source="POST_INDUSTRIAL"
    ),
    "hmw drum regrind (soap/detergent residue)": _spec(polymer="HDPE_HMW", material_grade="DRUMS", form="REGRIND"),
    "hmw drums and ibc totes in bales": _spec(polymer="HDPE_HMW", packaging_type="bales"),
    "hmw pallet regrind": _spec(polymer="HDPE_HMW", material_grade="PALLETS", form="REGRIND"),
    "hmw postal pallet for return to usps": _spec(polymer="HDPE_HMW", material_grade="PALLETS"),
    "hmw toters": _spec(polymer="HDPE_HMW", material_grade="TOTERS"),
    "hmw-hdpe regrind - blue/white": _spec(polymer="HDPE_HMW", form="REGRIND", color=("BLUE", "WHITE")),
    "hmw-hdpe/dunnage": _spec(polymer="HDPE_HMW", material_grade="DUNNAGE"),
    "igps/kroger/miller/coors pallet unrunable metal": _spec(polymer="METAL", material_grade="PALLETS"),
    "ldpe a - stretch - no gaylord liners/laundry film": _spec(
        polymer="LDPE", material_grade="LINERS", grade="A", form="FILM", packaging_type="bales", attributes=("clean",)
    ),
    "ldpe blue bales": _spec(polymer="LDPE", packaging_type="bales", color=("BLUE",)),
    "ldpe clear bales": _spec(polymer="LDPE", packaging_type="bales", color=("CLEAR",)),
    "ldpe clear film in bales": _spec(polymer="LDPE", form="FILM", packaging_type="bales", color=("CLEAR",)),
    "ldpe clear in bales": _spec(polymer="LDPE", packaging_type="bales", color=("CLEAR",)),
    "ldpe clear with print in boxes": _spec(polymer="LDPE", attributes=("printed",), color=("CLEAR",)),
    "ldpe film in bales": _spec(polymer="LDPE", form="FILM", packaging_type="bales"),
    "ldpe foam repro": _spec(polymer="LDPE", form="REPRO"),
    "ldpe foam repro (blue)": _spec(polymer="LDPE", form="REPRO", color=("BLUE",)),
    "ldpe mixed color in gaylords": _spec(polymer="LDPE", packaging_type="gaylords", color=("MIXED",)),
    "ldpe money bags and shrink wrap.": _spec(polymer="LDPE", material_grade="SHRINK_WRAP"),
    "ldpe pellet": _spec(polymer="LDPE", form="PELLETS"),
    "ldpe pellet - post industrial": _spec(polymer="LDPE", form="PELLETS", source="POST_INDUSTRIAL"),
    "ldpe pond liner all black": _spec(polymer="LDPE", material_grade="LINERS", color=("BLACK",)),
    "ldpe post industrial bales- clear": _spec(
        polymer="LDPE", source="POST_INDUSTRIAL", packaging_type="bales", color=("CLEAR",)
    ),
    "ldpe printed rolls - clear": _spec(polymer="LDPE", form="ROLLSTOCK", attributes=("printed",), color=("CLEAR",)),
    "ldpe printed rolls - post industrial": _spec(
        polymer="LDPE", form="ROLLSTOCK", source="POST_INDUSTRIAL", attributes=("printed",)
    ),
    "ldpe printed white rolls": _spec(polymer="LDPE", form="ROLLSTOCK", attributes=("printed",), color=("WHITE",)),
    "ldpe repro - green": _spec(polymer="LDPE", form="REPRO", color=("GREEN",)),
    "ldpe shrink pallet wrap rolls": _spec(polymer="LLDPE", material_grade="SHRINK_WRAP", form="ROLLSTOCK"),
    "lldpe blue/clear repro": _spec(polymer="LLDPE", form="REPRO", color=("BLUE", "CLEAR")),
    "lldpe clear rolls on pallets": _spec(
        polymer="LLDPE", form="ROLLSTOCK", packaging_type="palletized", color=("CLEAR",)
    ),
    "lldpe rolls - unscheduled material": _spec(polymer="LLDPE", form="ROLLSTOCK"),
    "lldpe stretch film in bales": _spec(polymer="LLDPE", form="FILM", packaging_type="bales"),
    "loode occ/baled": _spec(polymer="OCC", packaging_type="bales"),
    "mix hd bales - downgraded": _spec(polymer="HDPE", packaging_type="bales"),
    "mixed ldpe rolls stock": _spec(polymer="LDPE", form="ROLLSTOCK"),
    "mixed plastic pallets - pp skids": _spec(polymer="PP", material_grade="PALLETS"),
    "nylon pellet": _spec(polymer="NYLON", form="PELLETS"),
    "nylon tubing w/barium liner": _spec(polymer="NYLON", material_grade="LINERS"),
    "nylon zip ties - black/gray": _spec(polymer="NYLON", color=("BLACK", "GRAY")),
    "occ baled": _spec(polymer="OCC", packaging_type="bales"),
    "pc ht clear pellet": _spec(polymer="PC", form="PELLETS", color=("CLEAR",)),
    "pe ag trays": _spec(polymer="HDPE", material_grade="TRAYS"),
    "pe corner boards": _spec(polymer="HDPE", material_grade="CORNERBOARDS"),
    "peanut super sacks grade a - cut": _spec(polymer="PP", material_grade="SUPERACS"),
    "pet baled": _spec(polymer="PET", packaging_type="bales"),
    "pet bottle flake mixed color": _spec(polymer="PET", material_grade="BOTTLES", form="FLAKE", color=("MIXED",)),
    "pet bottles - baled": _spec(polymer="PET", material_grade="BOTTLES", packaging_type="bales"),
    "pet bottles - bales": _spec(polymer="PET", material_grade="BOTTLES", packaging_type="bales"),
    "pet ckear bales with paper/wood/contamination": _spec(polymer="PET", packaging_type="bales"),
    "pet clamshells (baled)": _spec(polymer="PET", packaging_type="bales"),
    "pet clean stacked trays": _spec(
        polymer="PET", material_grade="TRAYS", packaging_type="palletized", attributes=("clean",)
    ),
    "pet clear bales heavy paper contamination disposed": _spec(
        polymer="PET", packaging_type="bales", color=("CLEAR",)
    ),
    "pet clear rolls / trim": _spec(polymer="PET", form="ROLLSTOCK", color=("CLEAR",)),
    "pet clear tray regrind": _spec(polymer="PET", material_grade="TRAYS", form="REGRIND", color=("CLEAR",)),
    "pet clear tray/trim": _spec(polymer="PET", material_grade="TRAYS", color=("CLEAR",)),
    "pet clear trays w/ silica packets": _spec(polymer="PET", material_grade="TRAYS", color=("CLEAR",)),
    "pet clear trim (from sheet/tray)": _spec(polymer="PET", material_grade="TRAYS", form="SHEET", color=("CLEAR",)),
    "pet clear w/contamination from bales": _spec(polymer="PET", packaging_type="bales", color=("CLEAR",)),
    "pet clear w/heavy contamination from bales": _spec(polymer="PET", packaging_type="bales", color=("CLEAR",)),
    "pet clear w/light contamination from bales": _spec(polymer="PET", packaging_type="bales", color=("CLEAR",)),
    "pet green & clear preforms w/dust": _spec(polymer="PET", color=("CLEAR", "GREEN")),
    "pet green strapping - chopped": _spec(polymer="PET", material_grade="STRAPPING", form="CHOPPED", color=("GREEN",)),
    "pet mixed color - white - regrind": _spec(polymer="PET", form="REGRIND", color=("WHITE", "MIXED")),
    "pet pellet - iv test": _spec(polymer="PET", form="PELLETS"),
    "pet post consumer bottles in bales": _spec(
        polymer="PET", material_grade="BOTTLES", source="POST_CONSUMER", packaging_type="bales"
    ),
    "pet post industrial bales": _spec(polymer="PET", source="POST_INDUSTRIAL", packaging_type="bales"),
    "pet preform and bottle regrind - all clear": _spec(
        polymer="PET", material_grade="BOTTLES", form="REGRIND", color=("CLEAR",)
    ),
    "pet preforms - clear/green": _spec(polymer="PET", color=("CLEAR", "GREEN")),
    "pet preforms clear/green in gaylords": _spec(polymer="PET", packaging_type="gaylords", color=("CLEAR", "GREEN")),
    "pet preforms in gaylords": _spec(polymer="PET", packaging_type="gaylords"),
    "pet preforms in gaylords - some dirt/residue": _spec(polymer="PET", packaging_type="gaylords"),
    "pet regrind - clear cups w/ mixed color print": _spec(
        polymer="PET", material_grade="CUPS", form="REGRIND", color=("CLEAR", "MIXED")
    ),
    "pet strapping (baled)": _spec(polymer="PET", material_grade="STRAPPING", packaging_type="bales"),
    "pet strapping (chopped)": _spec(polymer="PET", material_grade="STRAPPING", form="CHOPPED"),
    "pet strapping - green only": _spec(polymer="PET", material_grade="STRAPPING", color=("GREEN",)),
    "pet strapping - translucent green chopped": _spec(
        polymer="PET", material_grade="STRAPPING", form="CHOPPED", color=("GREEN",)
    ),
    "pet strapping baled": _spec(polymer="PET", material_grade="STRAPPING", packaging_type="bales"),
    "pet strapping chopped": _spec(polymer="PET", material_grade="STRAPPING", form="CHOPPED"),
    "pet strapping opaque and translucent - baled": _spec(
        polymer="PET", material_grade="STRAPPING", packaging_type="bales"
    ),
    "pet trays - black": _spec(polymer="PET", material_grade="TRAYS", color=("BLACK",)),
    "pet trays - clean": _spec(polymer="PET", material_grade="TRAYS", attributes=("clean",)),
    "pet trays - dirty": _spec(polymer="PET", material_grade="TRAYS"),
    "pet trays - mixed color": _spec(polymer="PET", material_grade="TRAYS", color=("MIXED",)),
    "pet trays - oily residue": _spec(polymer="PET", material_grade="TRAYS", attributes=("oily",)),
    "pet trays - white": _spec(polymer="PET", material_grade="TRAYS", color=("WHITE",)),
    "pet trays with stickers": _spec(polymer="PET", material_grade="TRAYS"),
    "pet trays/trim bales": _spec(polymer="PET", material_grade="TRAYS", packaging_type="bales"),
    "post industrial pp cups & lids": _spec(polymer="PP", material_grade="CUPS", source="POST_INDUSTRIAL"),
    "post industrial ps trays": _spec(polymer="PS", material_grade="TRAYS", source="POST_INDUSTRIAL"),
    "pp black and blue pallets": _spec(polymer="PP", material_grade="PALLETS", color=("BLUE", "BLACK")),
    "pp bottle caps (post industrial)": _spec(polymer="PP", form="PARTS", source="POST_INDUSTRIAL"),
    "pp clear rolls": _spec(polymer="PP", form="ROLLSTOCK", color=("CLEAR",)),
    "pp corner boards": _spec(polymer="PP", material_grade="CORNERBOARDS"),
    "pp corrugated - white sheet": _spec(polymer="PP", form="SHEET", color=("WHITE",)),
    "pp corrugated bales": _spec(polymer="PP", packaging_type="bales"),
    "pp corrugated in bales - no metal no velcro dry": _spec(
        polymer="PP", packaging_type="bales", attributes=("dry", "no_metal")
    ),
    "pp corrugated sheet on pallets": _spec(polymer="PP", form="CORRUGATED", packaging_type="palletized"),
    "pp cup regrind": _spec(polymer="PP", material_grade="CUPS", form="REGRIND"),
    "pp cup regrind with print": _spec(polymer="PP", material_grade="CUPS", form="REGRIND", attributes=("printed",)),
    "pp dunnage": _spec(polymer="PP", material_grade="DUNNAGE"),
    "pp pallet r/w w/rubber": _spec(polymer="PP", material_grade="PALLETS"),
    "pp pallet shred": _spec(polymer="PP", material_grade="PALLETS", form="SHRED"),
    "pp parts (new on pallets)": _spec(
        polymer="PP", material_grade="PALLETS", form="PARTS", packaging_type="palletized"
    ),
    "pp post industrial bales": _spec(polymer="PP", source="POST_INDUSTRIAL", packaging_type="bales"),
    "pp purge and bales": _spec(polymer="PP", form="PURGE", packaging_type="bales"),
    "pp regrind - white and grey": _spec(polymer="PP", form="REGRIND", color=("WHITE", "GRAY")),
    "pp sacks with liners": _spec(polymer="PP", material_grade="LINERS"),
    "pp sanko pallet r/w rubber": _spec(polymer="PP", material_grade="PALLETS"),
    "pp sanko pallet w/rubber": _spec(polymer="PP", material_grade="PALLETS"),
    "pp supersacs (white)": _spec(polymer="PP", material_grade="SUPERACS", color=("WHITE",)),
    "pp supersacs - a": _spec(polymer="PP", material_grade="SUPERACS"),
    "pp supersacs - clean/dry (unlined)": _spec(polymer="PP", material_grade="SUPERACS", attributes=("clean", "dry")),
    "pp supersacs - grade a (white)": _spec(polymer="PP", material_grade="SUPERACS", color=("WHITE",)),
    "pp supersacs - peanut bags": _spec(polymer="PP", material_grade="SUPERACS"),
    "pp supersacs - reuseable - clean/dry": _spec(
        polymer="PP", material_grade="SUPERACS", attributes=("clean", "dry", "reusable")
    ),
    "pp supersacs - reuseable @ $1/bag": _spec(polymer="PP", material_grade="SUPERACS", attributes=("reusable",)),
    "pp supersacs - unused": _spec(polymer="PP", material_grade="SUPERACS"),
    "pp supersacs - white/tan/blue": _spec(polymer="PP", material_grade="SUPERACS", color=("BLUE", "WHITE")),
    "pp supersacs in bales": _spec(polymer="PP", material_grade="SUPERACS", packaging_type="bales"),
    "pp supersacs white": _spec(polymer="PP", material_grade="SUPERACS", color=("WHITE",)),
    "pp trays (black & white)": _spec(polymer="PP", material_grade="TRAYS", color=("WHITE", "BLACK")),
    "pp trays - black": _spec(polymer="PP", material_grade="TRAYS", color=("BLACK",)),
    "pp trays - pink": _spec(polymer="PP", material_grade="TRAYS"),
    "pp trays with contamination": _spec(polymer="PP", material_grade="TRAYS"),
    "pp tubs and lids": _spec(polymer="PP", material_grade="TUBS_LIDS", source="POST_CONSUMER", packaging_type="bales"),
    "pp white bales (trays, sheet, and purge)": _spec(
        polymer="PP", material_grade="TRAYS", packaging_type="bales", color=("WHITE",)
    ),
    "pp yogurt cup regrind - no paper, mfi 8+": _spec(polymer="PP", material_grade="CUPS", form="REGRIND"),
    "ps ag trays": _spec(polymer="PS", material_grade="TRAYS"),
    "ps cups (post industrial)": _spec(polymer="PS", material_grade="CUPS", source="POST_INDUSTRIAL"),
    "ps post industrial trays": _spec(polymer="PS", material_grade="TRAYS", source="POST_INDUSTRIAL"),
    "ps stacked green trays": _spec(
        polymer="PS", material_grade="TRAYS", packaging_type="palletized", color=("GREEN",)
    ),
    "pvc clear tray regrind": _spec(polymer="PVC", material_grade="TRAYS", form="REGRIND", color=("CLEAR",)),
    "pvc fencing - 2 bales rejected": _spec(polymer="PVC", packaging_type="bales"),
    "pvc fencing baled": _spec(polymer="PVC", packaging_type="bales"),
    "pvc fencing parts in gaylords (clean)": _spec(
        polymer="PVC", form="PARTS", packaging_type="gaylords", attributes=("clean",)
    ),
    "pvc flex parts (black) - post industrial in gaylords": _spec(
        polymer="PVC", form="PARTS", source="POST_INDUSTRIAL", packaging_type="gaylords", color=("BLACK",)
    ),
    "pvc siding bales": _spec(polymer="PVC", packaging_type="bales"),
    "pvc trays-rejected": _spec(polymer="PVC", material_grade="TRAYS"),
    "reusable super sacks in bales": _spec(
        polymer="PP", material_grade="SUPERACS", packaging_type="bales", attributes=("reusable",)
    ),
    "stacked pet trays": _spec(polymer="PET", material_grade="TRAYS", packaging_type="palletized"),
    "super sacks a - reusable": _spec(polymer="PP", material_grade="SUPERACS", attributes=("reusable",)),
    "tpo natural widespec pellet": _spec(polymer="TPO", form="PELLETS", color=("NATURAL",)),
    "uniform stacked pallets": _spec(polymer="PLASTIC_PALLETS", material_grade="PALLETS", packaging_type="palletized"),
    "z bales": _spec(
        polymer="HDPE", material_grade="BOTTLES", source="POST_CONSUMER", packaging_type="bales", color=("MIXED",)
    ),
    "z-bales": _spec(
        polymer="HDPE", material_grade="BOTTLES", source="POST_CONSUMER", packaging_type="bales", color=("MIXED",)
    ),
    "99% clear ldpe film": _spec(
        polymer="LDPE", grade="A", form="FILM", packaging_type="bales", attributes=("clean", "dry"), color=("CLEAR",)
    ),
    "hdpe toters - roll out bins": _spec(polymer="HDPE", material_grade="TOTERS", form="PARTS", packaging_type="loose"),
}

# CRM lead phrases that are not worksheet phrases. The whole collapsed
# description must match. A hit in ``_SPECS`` wins and never reaches this table.
# Bare LDPE is film. A trailing hyphen on HDPE- stays HDPE, distinct from HDPE-HMW.
_CRM_EXACT = {
    key: _spec(polymer=polymer, form=form)
    for key, polymer, form in (
        ("ldpe", "LDPE", "FILM"),
        ("nylon", "NYLON", None),
        ("metal", "METAL", None),
        ("e-waste", "EWASTE", None),
        ("hdpe-", "HDPE", None),
        ("hdpe-hmw", "HDPE_HMW", None),
        ("plastic pallets", "PLASTIC_PALLETS", None),
        ("gaylord boxes", "GAYLORD_BOXES", None),
        ("hdpe", "HDPE", None),
        ("pp", "PP", None),
        ("mrp", "MRP", None),
        ("pet", "PET", None),
        ("abs", "ABS", None),
        ("pc", "PC", None),
        ("ps", "PS", None),
        ("hips", "HIPS", None),
        ("pvc", "PVC", None),
        ("eps", "EPS", None),
        ("bopp", "BOPP", None),
        ("tpo", "TPO", None),
        ("tpe", "TPE", None),
        ("pbt", "PBT", None),
        ("lldpe", "LLDPE", None),
        # Operator-approved 2026-11-05 (mapping matrix sync)
        ("tpu", "TPU", None),
        ("tpv", "TPV", None),
        ("pvb", "PVB", None),
        ("ubc", "UBC", None),
        ("textile", "TEXTILE", None),
    )
}

# Operator-approved VanillaSoft aliases (POLYMER MAPPING sheet, ALIAS rows, approved 2026-10-30).
# Polymer is the sheet's code. material_grade is what the items were. grade is the A/B/C letter.
# A form is set only when the phrase names exactly one form master.
# The whole collapsed description must match; ``_SPECS`` and ``_CRM_EXACT`` win over this table.
_CRM_ALIASES = {
    key: _spec(polymer=polymer, material_grade=material_grade, grade=grade, form=form)
    for key, (polymer, form, grade, material_grade) in {
        "pet bottles": ("PET", None, None, "BOTTLES"),
        "pp supersacs": ("PP", None, None, "SUPERACS"),
        "hdpe bottles": ("HDPE", None, None, "BOTTLES"),
        "ldpe stretch film": ("LDPE", "FILM", None, "STRETCH_FILM"),
        "pet industrial": ("PET", None, None, None),
        "hdpe bottles - mixed color": ("HDPE", None, None, "BOTTLES"),
        "hdpe bottles - natural": ("HDPE", None, None, "BOTTLES"),
        "ldpe film b": ("LDPE", "FILM", "B", None),
        "acrylic / pmma": ("PMMA", None, None, None),
        "ldpe film": ("LDPE", "FILM", None, None),
        "nylon 6": ("NYLON", None, None, None),
        "pet strapping": ("PET", None, None, "STRAPPING"),
        "mrp export": ("MRP", None, None, None),
        "pvc flex": ("PVC", None, None, None),
        "hdpe buckets": ("HDPE", None, None, "BUCKETS"),
        "nylon 6.6": ("NYLON", None, None, None),
        "pp regrind": ("PP", "REGRIND", None, None),
        "ldpe post industrial": ("LDPE", None, None, None),
        "ibc totes (hmw-hdpe)": ("HDPE_HMW", None, None, "IBC_TOTES"),
        "hdpe totes": ("HDPE", None, None, "TOTES"),
        "hdpe bottles - z bales": ("HDPE", None, None, None),
        "hdpe crates": ("HDPE", None, None, "CRATES"),
        "mrp domestic": ("MRP", None, None, None),
        "ldpe film mixed color": ("LDPE", "FILM", None, None),
        "pp parts": ("PP", "PARTS", None, None),
        "ldpe film c": ("LDPE", "FILM", "C", None),
        "pet bottles - 70/30 curbside": ("PET", None, None, "BOTTLES"),
        "pp bottles - domestic pack": ("PP", None, None, "BOTTLES"),
        "hdpe toters (roll-out carts)": ("HDPE", None, None, "TOTERS"),
        "mrp-a": ("MRP", None, None, None),
        "tpo bumpers": ("TPO", None, None, "BUMPERS"),
        "acetal": ("POM", None, None, None),
        "pp purge": ("PP", "PURGE", None, None),
        "pp tubs/lids": ("PP", None, None, None),
        "hdpe pipe": ("HDPE", None, None, None),
        "mrp a": ("MRP", None, None, None),
        "ld/lldpe thick/stretch": ("LDPE_LLDPE", None, None, None),
        "pp crates": ("PP", None, None, "CRATES"),
        "pp repro": ("PP", None, None, None),
        "ldpe purge": ("LDPE", "PURGE", None, None),
        "mrp - export": ("MRP", None, None, None),
        "pp bottles": ("PP", None, None, "BOTTLES"),
        "hdpe roto-mold tanks": ("HDPE", None, None, None),
        "hdpe corrugated pipe": ("HDPE", None, None, None),
        "ldpe logs": ("LDPE", "LOGS", None, None),
        "mrp - domestic": ("MRP", None, None, None),
        "pet bottles - deposit bill": ("PET", None, None, "BOTTLES"),
        "hdpe pill bottles": ("HDPE", None, None, "BOTTLES"),
        "mrp c&d": ("MRP", None, None, None),
        "pc - polycarb": ("PC", None, None, None),
        "hdpe drip tube": ("HDPE", None, None, None),
        "ldpe nursery film": ("LDPE", "FILM", None, None),
        "ldpe redemption bags": ("LDPE", None, None, None),
        "mrp-b": ("MRP", None, None, None),
        "e-waste - dark": ("EWASTE", None, None, None),
        "ldpe camelback": ("LDPE", None, None, None),
        "ldpe cotton film": ("LDPE", "FILM", None, None),
        "mrp industrial": ("MRP", None, None, None),
        "pa": ("NYLON", None, None, None),
        "pp bottles domestic": ("PP", None, None, "BOTTLES"),
        "pp hangers": ("PP", None, None, None),
        ".01 fob grade a mrp": ("MRP", None, None, None),
        "acrylic": ("PMMA", None, None, None),
        "also mentioned they buy pp gf 25-50% - black has golf material. mention and request references.": (
            "PP",
            None,
            None,
            None,
        ),
        "and occ -": ("OCC", None, None, None),
        "bopp printed": ("BOPP", None, None, None),
        "crate grade hdpe": ("HDPE", None, None, "CRATES"),
        "curb sorted no mrp - cb and pich for future -": ("MRP", None, None, None),
        "does marketing for 6 separate counties in maryland which generate mrp. got on bid list": (
            "MRP",
            None,
            None,
            None,
        ),
        "e-waste - light": ("EWASTE", None, None, None),
        "ext218 - pp sacks": ("PP", None, None, None),
        "gas tanks and so on. pvc post industrial.": ("PVC", None, None, None),
        "generates eps": ("EPS", None, None, None),
        "generates pet": ("PET", None, None, None),
        "had mrp and sacks. had loads of all.": ("MRP", None, None, None),
        "has 2 loads of ldpe film": ("LDPE", "FILM", None, None),
        "has ftl's of ldpe film from commercial dryer": ("LDPE", "FILM", None, None),
        "has mrp and everything else.": ("MRP", None, None, None),
        "has mrp and has c grade film": ("MRP", None, None, None),
        "has mrp b+": ("MRP", None, None, None),
        "has non-wove pp": ("PP", None, None, None),
        "has pp sacks": ("PP", None, None, None),
        "has pp super sacks with carbon black residue": ("PP", None, None, None),
        "has some colored eps. sometimes has white eps he needs to sell.": ("EPS", None, None, None),
        "hdpe bott": ("HDPE", None, None, None),
        "hdpe bottles.": ("HDPE", None, None, "BOTTLES"),
        "hdpe dumpster lids": ("HDPE", None, None, None),
        "hdpe gas tanks": ("HDPE", None, None, None),
        "hmw-hdpe/dunnage": ("HDPE_HMW", None, None, None),
        "ldpe house wrap": ("LDPE", None, None, None),
        "ldpe money bags and shrink wrap.": ("LDPE", None, None, None),
        "ldpe rolls": ("LDPE", "ROLLSTOCK", None, None),
        "mentioned: pp super sacsk": ("PP", None, None, None),
        "mrp looks like grade b": ("MRP", None, None, None),
        "pc regrind.": ("PC", "REGRIND", None, None),
        "pet baled": ("PET", None, None, None),
        "pet bott": ("PET", None, None, None),
        "pet preforms": ("PET", None, None, None),
        "plastic & textile nylon": ("NYLON", None, None, None),
        "pp battery casing": ("PP", None, None, None),
        "pp bins and other grades. seems to be marketing direct with prices as high as .25 for film.": (
            "PP",
            None,
            None,
            None,
        ),
        "pp rolls": ("PP", "ROLLSTOCK", None, None),
        "pp super sack offered 0.06/lb. has 30k now": ("PP", None, None, None),
        "quote on mrp. 0.05/lb and 0.12/lb": ("MRP", None, None, None),
        "should have other stuff. we sold him pvc": ("PVC", None, None, None),
        "should have tons of mrp": ("MRP", None, None, None),
        "they generate hdpe": ("HDPE", None, None, None),
        "they mostly work with pet bottles.": ("PET", None, None, "BOTTLES"),
    }.items()
}
_CRM_ALIASES["hdpe frac melt"] = _spec(polymer="HDPE", attributes=("frac_melt",))
_CRM_ALIASES["pvc rigid"] = _spec(polymer="PVC", attributes=("rigid",))
_CRM_ALIASES["ldpe thick gauge"] = _spec(polymer="LDPE", attributes=("thick_gauge",))
# Operator-approved 2026-11-05 (mapping matrix sync)
_CRM_ALIASES["foam - pu"] = _spec(polymer="PU_FOAM")
_CRM_ALIASES["ibc totes (hmw)"] = _spec(polymer="HDPE_HMW", material_grade="IBC_TOTES")
_CRM_ALIASES["knock-down crates"] = _spec(polymer="HDPE", material_grade="CRATES")
_CRM_ALIASES["drip tube"] = _spec(polymer="HDPE")
_CRM_ALIASES["1-7 bottles"] = _spec(polymer="1_7_COMMINGLED_BOTTLES", material_grade="BOTTLES", source="POST_CONSUMER")
_CRM_ALIASES["co-mingled 1-7 all plastics"] = _spec(
    polymer="1_7_COMMINGLED_BOTTLES", material_grade="BOTTLES", source="POST_CONSUMER"
)
_CRM_ALIASES["1-7 mrp"] = _spec(polymer="1_7_COMMINGLED_BOTTLES", material_grade="BOTTLES", source="POST_CONSUMER")
_CRM_ALIASES["3-7 mixed plastic"] = _spec(
    polymer="3_7_COMMINGLED_BOTTLES", material_grade="BOTTLES", source="POST_CONSUMER"
)
_CRM_ALIASES["3-7 bottles"] = _spec(polymer="3_7_COMMINGLED_BOTTLES", material_grade="BOTTLES", source="POST_CONSUMER")
_CRM_ALIASES["mrp 3-7"] = _spec(polymer="3_7_COMMINGLED_BOTTLES", material_grade="BOTTLES", source="POST_CONSUMER")
# Operator-approved 2026-11-05 (mapping matrix resolution ledger)
_CRM_ALIASES["1 & 2 bottles"] = _spec(
    polymer="1_2_COMMINGLED_BOTTLES", material_grade="BOTTLES", source="POST_CONSUMER"
)
_CRM_ALIASES["bottles (hd/pet)"] = _spec(
    polymer="1_2_COMMINGLED_BOTTLES", material_grade="BOTTLES", source="POST_CONSUMER"
)
_CRM_ALIASES["1 & 2 bottles (pet/hdpe)"] = _spec(
    polymer="1_2_COMMINGLED_BOTTLES", material_grade="BOTTLES", source="POST_CONSUMER"
)
_CRM_ALIASES["1 & 2 pet & hdpe co-mingled bottles"] = _spec(
    polymer="1_2_COMMINGLED_BOTTLES", material_grade="BOTTLES", source="POST_CONSUMER"
)
_CRM_ALIASES["commingled bottles 1&2"] = _spec(
    polymer="1_2_COMMINGLED_BOTTLES", material_grade="BOTTLES", source="POST_CONSUMER"
)
_CRM_ALIASES["ldpe/hdpe grocery film"] = _spec(polymer="MIXED", form="FILM")


# Phrases that are call-note text, not material descriptions. The CRM importer
# checks this before passing a phrase to normalize_material so that call notes
# in the Materials field produce no error and no profile row.
_CRM_CALL_NOTE_PHRASES: frozenset[str] = frozenset(
    {
        ".22",
        "0.12/lb on gas tanks",
        "1 load of rigids. 1/23/14",
        "3 loads of film",
        "3 weeks!",
        "3/9 has sorted bottles",
        "4/19 has buckets with residue",
        "50/50 loads of camel back/stretch.",
        "600+750/36k=.0375 sell as b .12",
        "98 film",
        "acrylic. interested in buying pvc from us.",
        "ag",
        "ag program",
        "albert circconi",
        "aluminum",
        "and green/black strapping.",
        "and regrind",
        "and so on.",
        "automotive bales",
        "baled on roll ends.",
        "became a disaster.",
        "black film.",
        "black/white silage film",
        "broker",
        "bubble wrap",
        "bumpers -offered 0.06/lb",
        "buying spc",
        "call and ask for nathan",
        "call back.",
        "called",
        "called me back",
        "carl alm",
        "chopped banding - combo loads only",
        "combustible petroleums",
        "complete mix",
        "crates",
        "dave gelharn",
        "did 2 loads with him",
        "diesel",
        "different gauges 10-62",
        "directed to them by cannon and sons",
        "distribution center",
        "do a very small amount",
        "does 2-3 rigid loads a month.",
        "does a load a month.",
        "don't bail.",
        "double for national. not current.",
        "double: not current",
        "faxed over pricing",
        "films",
        "finally spoke to buford",
        "follow up",
        "follow up.",
        "frank is operations manager",
        "gas pipe",
        "gas tanks",
        "generates 1-7 and mixed bags.",
        "generates abs and acrylic sign scrap",
        "gets rigid",
        "getting 0.10/lb",
        "givving it to westrock.",
        "glass",
        "going to be a tough nut to crack",
        "got her on phone",
        "grade b film",
        "grocery",
        "hangers",
        "has 2 harris balers",
        "has 3 facilities",
        "has 3-7",
        "has b super sacks.",
        "has bol.",
        "has c & d buckets",
        "has film",
        "has film indeed.",
        "has grade a & b film",
        "has mats",
        "has mixed roll stock",
        "has rigids and other plastics",
        "has weight issue",
        "he doesn't like that number.",
        "head lights",
        "heavy weights. good guy.",
        "hmw",
        "hmw drums",
        "howard no longer works there.",
        "hydraulic fuel",
        "i need to drive up there",
        "i offered 0.05/lb",
        "import/foreign",
        "iv 72 - clear",
        "ld",
        "left a vm 6/6",
        "left a vm for kurt on contact date.",
        "left a vm on 3rd",
        "left a vm on 7/6/09.",
        "left emmette a vm on the 11th",
        "light load.",
        "local guy.",
        "long island – main office:",
        "low volume at first. 1 -2 bales a week.",
        "matress foam",
        "milk crates baled",
        "mixed buckets",
        "mixed rigid plastics",
        "mixed rigids shit quality",
        "mrp quoted .085sell price of .12 for his pvc p/u",
        "msw",
        "need to further qualify",
        "need to know what they thought.",
        "new york 11590",
        "no more drums",
        "nobody is aware of anybody here…",
        "offerd 0.01/lb -0.02/lb",
        "offered 0.05/lb for his material",
        "offered 0.17/lb on film",
        "offered him 0.02/lb",
        "offered him 0.08/lb",
        "offered lead",
        "on 3-17",
        "penn mar asked me to call john",
        "pet hdpe bottle only combo loads 1 per quarter - just sold.1/12 next in march.",
        "pi plastic",
        "post consume bottles",
        "pp nonwoven. generates clean abs",
        "printed as well - .42 baled",
        "probably won't get it.. but if it will.. we whisper… 6/3",
        "quoted 0.015/lb on his rigids.",
        "quoted him 0.18/lb on film",
        "raff",
        "regrinds.",
        "rich has plastic regrind mostly",
        "right next door to hopewell nursery",
        "rolls",
        "royal oak recycling ohio",
        "runs a huge jersey and brooklyn mrf",
        "sarah denis might be new contact",
        "secretary said they do plastics.",
        "sending me app for downstream",
        "sends his stuff to town of southold",
        "sent e-mail should add me on bid.",
        "sent tammy an e-mail",
        "ships pe",
        "should get me pictures today.",
        "should have plastic scrap",
        "should start bidding soon.",
        "should start doing that too.",
        "should try back shortly.",
        "some on rolls. non laminated",
        "sorted bottles",
        "spoke to a guy named les",
        "spoke to chris",
        "spoke to david",
        "spoke to him finally",
        "steve luteri passed lead",
        "stretch",
        "structural foam",
        "they received",
        "they sell mixed pe film",
        "they ship films",
        "today!",
        "totes",
        "under contract with apc",
        "uses dom as i use liotta",
        "visit",
        "visited facility",
        "waiting till he gets 38k.",
        "walmart 95",
        "wants .04 fob or wont bale it",
        "wants 0.12/lb across",
        "wants to sit on his material.",
        "wants us to bid on everything",
        "westbury",
        "wonderful lady",
        "wv is simple grinder/shredder op.",
    }
)


def is_crm_call_note(phrase: str) -> bool:
    """Return True when *phrase* is a call-note string, not a material name.

    The CRM importer calls this before ``normalize_material`` so that call-note
    text in the ``Materials`` field is silently skipped rather than logged as an
    unresolved material error.
    """
    return _phrase(phrase) in _CRM_CALL_NOTE_PHRASES


class MaterialNormalization:
    """One material phrase resolved to existing masters, or left unresolved."""

    def __init__(
        self,
        source_description,
        polymer,
        form,
        source_type,
        attributes,
        grade,
        unresolved,
        material_grade,
        *,
        color,
        packaging_type,
        filler_type=None,
        process_type=None,
    ):
        self.source_description = source_description
        self.polymer = polymer
        self.material_grade = material_grade
        self.form = form
        self.source_type = source_type
        self.attributes = attributes
        self.grade = grade
        self.unresolved = tuple(unresolved)
        self.color = color
        self.packaging_type = packaging_type
        self.filler_type = filler_type
        self.process_type = process_type


# One collapsed word, used only when the whole phrase misses ``_SPECS`` and the
# caller is not resolving a CRM alias. An unmapped VanillaSoft token stays
# unresolved. A grade word is what the items were. It is never a form. The
# worksheet phrase ``pallets`` stays the polymer spec.
_FORM_WORDS = {
    "bale": "BALES",
    "baled": "BALES",
    "bales": "BALES",
    "regrind": "REGRIND",
    "flake": "FLAKE",
    "flakes": "FLAKE",
    "pellet": "PELLETS",
    "pellets": "PELLETS",
    "rollstock": "ROLLSTOCK",
    "purge": "PURGE",
    "lump": "OTHER",
    "lumps": "OTHER",
    "film": "FILM",
    "fluff": "FLUFF",
    "sheet": "SHEET",
    "powder": "POWDER",
    "parts": "PARTS",
    "part": "PARTS",
    "re-useable": "OTHER",
    "reuseable": "OTHER",
    "reusable": "OTHER",
    "roll": "ROLLSTOCK",
    "rolls": "ROLLSTOCK",
}
_GRADE_WORDS = {
    "pallet": "PALLETS",
    "pallets": "PALLETS",
    "tote": "TOTES",
    "totes": "TOTES",
    "crate": "CRATES",
    "crates": "CRATES",
    "bottle": "BOTTLES",
    "bottles": "BOTTLES",
    "drum": "DRUMS",
    "drums": "DRUMS",
    "bucket": "BUCKETS",
    "buckets": "BUCKETS",
    "pail": "BUCKETS",
    "pails": "BUCKETS",
}
GRADE_WORD_PRIORITY = ("PALLETS", "TOTES", "CRATES")
# Commas and periods ride on the word in seller text (``pallets,``, ``crates.``).
# They are not part of the lookup key. A hyphen inside ``re-useable`` stays.
_EDGE_PUNCTUATION = ".,;:!?\"'`()[]{}"


def classify_material_word(token) -> tuple[str | None, str | None]:
    """Return ``(form_code, grade_code)`` for one word. One of them is empty.

    Edge punctuation is removed before the exact form and grade tables are read.
    """
    word = _phrase(token).strip(_EDGE_PUNCTUATION)
    if not word or " " in word:
        return None, None
    form_code = _FORM_WORDS.get(word)
    if form_code:
        return form_code, None
    return None, _GRADE_WORDS.get(word)


def normalize_material(env, description, grade_evidence=None, structured=None, *, crm_aliases=False):
    """Resolve one material phrase.

    ``description`` is preserved. ``grade_evidence`` and ``structured`` count
    only when they are themselves a worksheet phrase. A disagreement on polymer,
    form, source, grade letter, or material grade is unresolved and does not
    pick a side. Attributes, color, packaging, filler, and process come from the
    description when it matches. With ``crm_aliases``, a description that misses ``_SPECS``
    may match ``_CRM_EXACT``, then ``_CRM_ALIASES``. A miss stays unresolved:
    a single form or grade word is not applied on that path. Hints stay on
    ``_SPECS``.
    """
    source = _collapse(description)
    text = _phrase(description)
    specs = []
    description_spec = _SPECS.get(text)
    if description_spec is None and crm_aliases:
        description_spec = _CRM_EXACT.get(text) or _CRM_ALIASES.get(text)
    if description_spec is None and not crm_aliases and text and " " not in text:
        form_code, grade_code = classify_material_word(text)
        if form_code or grade_code:
            description_spec = _spec(polymer=None, form=form_code, material_grade=grade_code)
    if description_spec is not None:
        specs.append(description_spec)
    for hint in (_phrase(grade_evidence), *_structured_phrases(structured)):
        spec = _SPECS.get(hint)
        if spec is not None:
            specs.append(spec)
    if not source:
        source = _collapse(grade_evidence)
    if len({_identity(spec) for spec in specs}) > 1:
        return _empty(env, source, ("conflicting material evidence",))
    if not specs:
        reason = (
            ("unresolved material",) if source or _phrase(grade_evidence) or _structured_phrases(structured) else ()
        )
        return _empty(env, source, reason)
    return _realize(env, source, specs[0])


def _realize(env, source, spec):
    polymer, polymer_missing = _master(env, "plasticos.polymer", spec.polymer)
    material_grade, material_grade_missing = _master(env, "plasticos.material.grade", spec.material_grade)
    form, form_missing = _master(env, "plasticos.material.form", spec.form)
    source_type, source_missing = _master(env, "plasticos.source.type", spec.source)
    attributes, attribute_missing = _attributes(env, spec.attributes)
    color, color_missing = _colors(env, spec.color)
    packaging_type, packaging_missing = _master(env, "plasticos.packaging.type", spec.packaging_type)
    filler_type, filler_missing = _master(env, "plasticos.filler.type", spec.filler_type)
    process_type, process_missing = _process_code(spec.process_type)
    unresolved = tuple(
        item
        for item in (
            polymer_missing,
            material_grade_missing,
            form_missing,
            source_missing,
            *color_missing,
            packaging_missing,
            filler_missing,
            process_missing,
            *attribute_missing,
        )
        if item
    )
    if unresolved:
        return _empty(env, source, unresolved)
    return MaterialNormalization(
        source,
        polymer,
        form,
        source_type,
        attributes,
        spec.grade,
        (),
        material_grade,
        color=color,
        packaging_type=packaging_type,
        filler_type=filler_type,
        process_type=process_type,
    )


def _empty(env, source, unresolved):
    return MaterialNormalization(
        source,
        env["plasticos.polymer"].browse(),
        env["plasticos.material.form"].browse(),
        env["plasticos.source.type"].browse(),
        env["plasticos.material.attribute"].browse(),
        None,
        unresolved,
        env["plasticos.material.grade"].browse(),
        color=env["plasticos.material.color"].browse(),
        packaging_type=env["plasticos.packaging.type"].browse(),
        filler_type=env["plasticos.filler.type"].browse(),
        process_type=None,
    )


def _process_code(code):
    """Return the profile selection code, or a missing-master reason."""
    if not code:
        return None, None
    from ..process_codes import PROCESS_CODES  # noqa: PLC0415 - ledger loader imports this file by path

    if code not in PROCESS_CODES:
        return None, f"missing process type {code}"
    return code, None


def _master(env, model, code):
    if not code:
        return env[model].browse(), None
    found = env[model].search([("code", "=", code)], limit=1)
    if not found:
        return env[model].browse(), f"missing {model} {code}"
    return found, None


def _colors(env, codes):
    found = env["plasticos.material.color"].browse()
    missing = []
    for code in codes:
        color, reason = _master(env, "plasticos.material.color", code)
        if reason:
            missing.append(reason)
        else:
            found |= color
    return found, missing


def _attributes(env, codes):
    found = env["plasticos.material.attribute"].browse()
    missing = []
    for code in codes:
        attribute, reason = _master(env, "plasticos.material.attribute", code)
        if reason:
            missing.append(reason)
        else:
            found |= attribute
    return found, missing


def _structured_phrases(structured):
    if not structured:
        return []
    if isinstance(structured, str):
        values = [structured]
    elif isinstance(structured, dict):
        values = list(structured.values())
    elif isinstance(structured, (list, tuple)):
        values = list(structured)
    else:
        return []
    return [phrase for phrase in (_phrase(value) for value in values) if phrase]


def _phrase(value) -> str:
    return _collapse(value).casefold()


def _collapse(value) -> str:
    return " ".join(str(value or "").split())
