"""Projected material description joins every color on the line."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace

_LABEL = Path(__file__).resolve().parents[1] / "plasticos_order_lines" / "models" / "material_label.py"
_spec = importlib.util.spec_from_file_location("material_label", _LABEL)
_module = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_module)
projected_material = _module.projected_material


class _Names:
    def __init__(self, names):
        self._names = names

    def mapped(self, _field):
        return list(self._names)

    def __bool__(self):
        return bool(self._names)


def test_projected_material_joins_every_color():
    line = SimpleNamespace(
        material_grade_id=SimpleNamespace(name="Drums"),
        color_ids=_Names(["Blue", "Green"]),
        filler_type_id=False,
        form_id=SimpleNamespace(name="Regrind"),
        packaging_type_id=False,
        source_type_id=False,
        material_attribute_ids=_Names([]),
        product_id=SimpleNamespace(name="HDPE", polymer_id=False),
    )
    assert projected_material(line) == "HDPE - Drums - Blue, Green - Regrind"
