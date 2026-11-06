"""Code uniqueness preflight is one query per create or write batch and keeps its messages."""

import uuid
from unittest.mock import patch

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged

# model -> message label used by its create()/write() guards
_CODE_MODELS = {
    "plasticos.filler.type": "Filler type",
    "plasticos.process.type": "Process type",
    "plasticos.source.type": "Source type",
    "plasticos.material.attribute": "Attribute",
    "plasticos.packaging.type": "Packaging type",
    "plasticos.material.form": "Material form",
    "plasticos.polymer": "Polymer",
    "plasticos.material.color": "Material color",
}


def _counting_search(model_cls, calls):
    real = model_cls.search

    def search(self, *args, **kwargs):
        calls.append(args[0] if args else kwargs.get("domain"))
        return real(self, *args, **kwargs)

    return patch.object(model_cls, "search", search)


@tagged("post_install", "-at_install")
class TestCodeUniquenessBatch(TransactionCase):
    def _code(self, label):
        return f"uniq-{label}-{uuid.uuid4().hex[:8]}"

    def test_batch_create_rejects_an_existing_code_before_insert(self):
        for model_name, label in _CODE_MODELS.items():
            with self.subTest(model=model_name):
                model = self.env[model_name]
                held = self._code("held")
                fresh = self._code("fresh")
                model.create({"name": "Held", "code": held})
                with self.assertRaises(ValidationError) as caught:
                    model.create([{"name": "Fresh", "code": fresh}, {"name": "Duplicate", "code": held}])
                self.assertIn(f"{label} code '{held}' already exists.", str(caught.exception))
                self.assertEqual(model.search_count([("code", "=", fresh)]), 0)

    def test_batch_create_runs_one_uniqueness_search(self):
        for model_name in _CODE_MODELS:
            with self.subTest(model=model_name):
                model = self.env[model_name]
                vals_list = [{"name": f"Fresh {index}", "code": self._code(str(index))} for index in range(3)]
                calls = []
                with _counting_search(type(model), calls):
                    records = model.create(vals_list)
                self.assertEqual(len(records), 3)
                self.assertEqual(len(calls), 1, calls)

    def test_single_write_of_a_held_code_raises_and_a_free_code_is_one_search(self):
        for model_name, label in _CODE_MODELS.items():
            with self.subTest(model=model_name):
                model = self.env[model_name]
                held = self._code("held")
                model.create({"name": "Held", "code": held})
                record = model.create({"name": "Other", "code": self._code("other")})
                with self.assertRaises(ValidationError) as caught:
                    record.write({"code": held})
                self.assertIn(f"{label} code '{held}' already exists.", str(caught.exception))
                calls = []
                free = self._code("free")
                with _counting_search(type(model), calls):
                    record.write({"code": free})
                self.assertEqual(record.code, free)
                self.assertEqual(len(calls), 1, calls)

    def test_multi_record_write_of_one_code_raises_without_a_per_record_search(self):
        for model_name, label in _CODE_MODELS.items():
            with self.subTest(model=model_name):
                model = self.env[model_name]
                first = model.create({"name": "First", "code": self._code("first")})
                second = model.create({"name": "Second", "code": self._code("second")})
                shared = self._code("shared")
                calls = []
                with _counting_search(type(model), calls), self.assertRaises(ValidationError) as caught:
                    (first | second).write({"code": shared})
                self.assertIn(f"{label} code '{shared}' already exists.", str(caught.exception))
                self.assertLessEqual(len(calls), 1, calls)
