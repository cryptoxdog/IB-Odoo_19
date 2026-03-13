from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestInferenceStub(PlasticosTestCase):
    """Ensure inference boundaries are safe when stubbed/unavailable."""

    def test_run_inference_returns_input_when_stubbed(self):
        ICP = self.env["ir.config_parameter"].sudo()
        ICP.set_param("plasticos.inference_engine.enabled", "False")
        ICP.set_param("plasticos.inference_engine.stubbed", "True")

        svc = self.env["plasticos.enrichment.service"]
        payload = {
            "polymer": "PP",
            "form": "PELLETS",
            "source_type": "POST_INDUSTRIAL",
        }
        result = svc.run_inference(payload, entity_type="supplier")
        self.assertEqual(result, payload)
