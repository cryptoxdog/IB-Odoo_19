"""GATE_URL is the matching-engine enablement switch."""

import os

from odoo.addons.plasticos_base.models.matching_engine_icp import (
    matching_engine_is_enabled,
    matching_engine_require_enabled_for_ui,
    matching_engine_should_skip_cron,
)
from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.exceptions import UserError
from odoo.tests.common import tagged

_GATE_URL = "GATE_URL"
_CRON_NAME = "test_matching_engine_gate_url"


@tagged("post_install", "-at_install")
class TestMatchingEngineGateUrl(PlasticosTestCase):
    def _run(self, value, check):
        saved = os.environ.get(_GATE_URL)
        try:
            if value is None:
                os.environ.pop(_GATE_URL, None)
            else:
                os.environ[_GATE_URL] = value
            check()
        finally:
            if saved is None:
                os.environ.pop(_GATE_URL, None)
            else:
                os.environ[_GATE_URL] = saved

    def _assert_disabled(self):
        self.assertFalse(matching_engine_is_enabled(self.env))
        self.assertTrue(matching_engine_should_skip_cron(self.env, _CRON_NAME))
        with self.assertRaises(UserError):
            matching_engine_require_enabled_for_ui(self.env)

    def test_unset_url_disables_matching(self):
        self._run(None, self._assert_disabled)

    def test_whitespace_url_disables_matching(self):
        self._run(" \t\n", self._assert_disabled)

    def test_set_url_enables_matching(self):
        def check():
            self.assertTrue(matching_engine_is_enabled(self.env))
            self.assertFalse(matching_engine_should_skip_cron(self.env, _CRON_NAME))
            matching_engine_require_enabled_for_ui(self.env)

        self._run("http://127.0.0.1:9", check)
