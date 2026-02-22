"""
plasticos_inference/polymer_aliases.py
Canonical polymer name normalization.
"""

from __future__ import annotations

_ALIASES: dict[str, str] = {
    # HDPE
    "hdpe": "HDPE",
    "pe-hd": "HDPE",
    "high density polyethylene": "HDPE",
    "high-density polyethylene": "HDPE",
    "pehd": "HDPE",
    # LDPE
    "ldpe": "LDPE",
    "pe-ld": "LDPE",
    "low density polyethylene": "LDPE",
    "low-density polyethylene": "LDPE",
    "peld": "LDPE",
    # LLDPE
    "lldpe": "LLDPE",
    "pe-lld": "LLDPE",
    "linear low density polyethylene": "LLDPE",
    "linear low-density polyethylene": "LLDPE",
    # PP
    "pp": "PP",
    "polypropylene": "PP",
    "poly propylene": "PP",
    # PS
    "ps": "PS",
    "polystyrene": "PS",
    # HIPS
    "hips": "HIPS",
    "high impact polystyrene": "HIPS",
    "high-impact polystyrene": "HIPS",
    # PET
    "pet": "PET",
    "polyethylene terephthalate": "PET",
    # ABS
    "abs": "ABS",
    "acrylonitrile butadiene styrene": "ABS",
    # TPO
    "tpo": "TPO",
    "thermoplastic olefin": "TPO",
    # PC
    "pc-pmma": "PC-PMMA",
    # Other
    "bopp": "BOPP",
    "pvc": "PVC",
    "pa": "PA",
    "nylon": "PA",
    "hmw hdpe": "HMW HDPE",
    "hmw-hdpe": "HMW HDPE",
    "mixed": "Mixed",
    "mrp": "MRP",
    "eps": "EPS",
    "pp-pe": "PP-PE",
}


def normalize(raw: str) -> str:
    """
    Normalize a raw polymer string to its canonical PlastOS code.

    Examples
    --------
    >>> normalize("high density polyethylene")
    'HDPE'
    >>> normalize("PP")
    'PP'
    >>> normalize("  ldpe  ")
    'LDPE'
    """
    key = raw.strip().lower()
    if key in _ALIASES:
        return _ALIASES[key]
    # Already canonical?
    upper = raw.strip().upper()
    if upper in {v for v in _ALIASES.values()}:
        return upper
    return raw.strip()
