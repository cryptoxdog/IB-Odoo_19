"""Image count is one attachment query and keeps the image-mimetype domain."""

import base64

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.tests.common import tagged

_PNG_DATAS = base64.b64encode(b"png")
_PDF_DATAS = base64.b64encode(b"pdf")


@tagged("post_install", "-at_install", "intake")
class TestIntakeImageCount(PlasticosTestCase):
    def test_image_count_filters_mimetype_and_model(self):
        first = self._create_intake()
        second = self._create_intake(partner=self._create_partner("Second Intake Partner"))
        attachment = self.env["ir.attachment"]
        attachment.create(
            [
                {
                    "name": "intake-a.png",
                    "res_model": "plasticos.intake",
                    "res_id": first.id,
                    "mimetype": "image/png",
                    "datas": _PNG_DATAS,
                },
                {
                    "name": "intake-b.png",
                    "res_model": "plasticos.intake",
                    "res_id": first.id,
                    "mimetype": "image/png",
                    "datas": _PNG_DATAS,
                },
                {
                    "name": "intake-a.pdf",
                    "res_model": "plasticos.intake",
                    "res_id": first.id,
                    "mimetype": "application/pdf",
                    "datas": _PDF_DATAS,
                },
                {
                    "name": "other-model.png",
                    "res_model": "res.partner",
                    "res_id": first.id,
                    "mimetype": "image/png",
                    "datas": _PNG_DATAS,
                },
            ]
        )
        pair = first | second
        pair.invalidate_recordset(["image_count"])
        self.assertEqual(pair.mapped("image_count"), [2, 0])

    def test_unsaved_intake_image_count_is_zero(self):
        self.assertEqual(self.env["plasticos.intake"].new({}).image_count, 0)
