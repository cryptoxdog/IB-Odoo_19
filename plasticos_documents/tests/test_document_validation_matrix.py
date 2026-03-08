"""Tests for plasticos.document.validation.matrix — compliance requirements.

Target module: plasticos_documents
Target model:  plasticos.document.validation.matrix

Validates: CRUD, unique constraint, default values, boolean flags,
sequence ordering, and deactivation.
"""

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.exceptions import ValidationError
from odoo.tests import tagged


@tagged("post_install", "-at_install", "plasticos", "documents")
class TestDocumentValidationMatrix(PlasticosTestCase):
    """Test document validation matrix model."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Matrix = cls.env["plasticos.document.validation.matrix"]
        cls.Tag = cls.env["plasticos.document.tag"]

        cls.tag_bol = cls.Tag.create({"name": "Bill of Lading", "code": "DOC_BOL"})
        cls.tag_coa = cls.Tag.create({"name": "Certificate of Analysis", "code": "DOC_COA"})
        cls.tag_pod = cls.Tag.create({"name": "Proof of Delivery", "code": "DOC_POD"})

    def _create_entry(self, **kwargs):
        """Helper: create a matrix entry with defaults."""
        vals = {
            "name": "Test Entry",
            "doc_category": "supplier",
            "tag_id": self.tag_bol.id,
        }
        vals.update(kwargs)
        return self.Matrix.create(vals)

    # ── CRUD ───────────────────────────────────────────────────

    def test_create_basic(self):
        """Matrix entry can be created with required fields."""
        entry = self._create_entry(tag_id=self.tag_pod.id)
        self.assertTrue(entry.id)
        self.assertEqual(entry.doc_category, "supplier")

    def test_default_values(self):
        """Defaults: required_for_close=True, invoice=False, dispatch=False."""
        entry = self._create_entry(
            name="Defaults Check",
            tag_id=self.tag_coa.id,
        )
        self.assertTrue(entry.required_for_close)
        self.assertFalse(entry.required_for_invoice)
        self.assertFalse(entry.required_for_dispatch)
        self.assertTrue(entry.active)
        self.assertEqual(entry.sequence, 10)

    # ── Unique Constraint ──────────────────────────────────────

    def test_duplicate_category_tag_rejected(self):
        """Same (doc_category, tag_id) combo raises ValidationError."""
        self._create_entry(
            name="First",
            doc_category="carrier",
            tag_id=self.tag_bol.id,
        )
        with self.assertRaises(ValidationError):
            self._create_entry(
                name="Duplicate",
                doc_category="carrier",
                tag_id=self.tag_bol.id,
            )

    def test_inactive_entry_allows_same_combo(self):
        """Deactivated entry does not block new active entry."""
        entry = self._create_entry(
            name="Deactivated",
            doc_category="buyer",
            tag_id=self.tag_coa.id,
        )
        entry.write({"active": False})

        new_entry = self._create_entry(
            name="Replacement",
            doc_category="buyer",
            tag_id=self.tag_coa.id,
        )
        self.assertTrue(new_entry.id)

    def test_different_category_same_tag_accepted(self):
        """Different category with same tag is valid."""
        self._create_entry(
            name="Supplier BOL",
            doc_category="supplier",
            tag_id=self.tag_pod.id,
        )
        entry2 = self._create_entry(
            name="Carrier BOL",
            doc_category="carrier",
            tag_id=self.tag_pod.id,
        )
        self.assertTrue(entry2.id)

    # ── Boolean Flags ──────────────────────────────────────────

    def test_all_flags_can_be_set(self):
        """All three requirement flags can be True simultaneously."""
        tag = self.Tag.create({"name": "Multi-Flag Tag", "code": "DOC_MULTI"})
        entry = self._create_entry(
            name="Full Requirement",
            tag_id=tag.id,
            doc_category="internal",
            required_for_close=True,
            required_for_invoice=True,
            required_for_dispatch=True,
        )
        self.assertTrue(entry.required_for_close)
        self.assertTrue(entry.required_for_invoice)
        self.assertTrue(entry.required_for_dispatch)

    # ── Selection Values ───────────────────────────────────────

    def test_all_doc_categories_valid(self):
        """All 4 doc_category values can be used."""
        for i, cat in enumerate(("supplier", "carrier", "buyer", "internal")):
            tag = self.Tag.create(
                {
                    "name": f"Cat Test {cat}",
                    "code": f"CAT_TEST_{i}",
                }
            )
            entry = self._create_entry(
                name=f"Category {cat}",
                doc_category=cat,
                tag_id=tag.id,
            )
            self.assertEqual(entry.doc_category, cat)
