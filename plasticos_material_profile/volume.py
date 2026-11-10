"""Monthly volume for a material profile.

The stored field multiplies the two supply inputs. Avg Weight Lbs is not an input.
"""


def monthly_volume_lbs(quantity_per_load_lbs, loads_per_month):
    """Return Quantity per Load times Loads per Month. Missing inputs count as zero."""
    quantity = float(quantity_per_load_lbs or 0.0)
    loads = float(loads_per_month or 0)
    return quantity * loads
