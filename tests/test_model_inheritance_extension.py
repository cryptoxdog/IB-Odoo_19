"""A renamed ``_inherit`` defines a new model. An equal name extends the old one."""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _checker():
    path = ROOT / "ci" / "check_model_inheritance.py"
    spec = importlib.util.spec_from_file_location("check_model_inheritance", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_renamed_inherit_stays_a_definition():
    extends = _checker()._extends_named_model
    assert extends({"_name": "plasticos.new", "_inherit": "plasticos.old", "_inherit_list": None}) is False
    assert extends({"_name": "plasticos.old", "_inherit": "plasticos.old", "_inherit_list": None}) is True
    assert extends({"_name": None, "_inherit": "plasticos.old", "_inherit_list": None}) is True
    assert (
        extends(
            {
                "_name": "plasticos.transaction",
                "_inherit": None,
                "_inherit_list": ["plasticos.transaction", "mail.activity.mixin"],
            }
        )
        is True
    )
