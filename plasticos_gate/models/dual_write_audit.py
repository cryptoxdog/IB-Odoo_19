"""Documentation-facing dual-write audit constants (no ORM table in this slice).

Projection rows remain optional; service-layer audit entries are the TASK-032
control surface. ORM persistence can land in a later wave without changing the ICP flag.
"""

from __future__ import annotations

DUAL_WRITE_ICP_KEY = "plasticos.gate.dual_write_enabled"
DUAL_WRITE_DEFAULT = "0"
FORBIDDEN_LOCAL_AUTHORITY = (
    "buyer.matcher",
    "local inference",
    "local matching engine",
)
