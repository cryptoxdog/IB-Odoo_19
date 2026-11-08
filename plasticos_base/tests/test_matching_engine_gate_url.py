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


def _restore_gate_url(saved):
    if saved is None:
        os.environ.pop(_GATE_URL, None)
    else:
        os.environ[_GATE_URL] = saved


def _set_gate_url(value):
    saved = os.environ.get(_GATE_URL)
    if value is None:
        os.environ.pop(_GATE_URL, None)
    else:
        os.environ[_GATE_URL] = value
    return saved


@tagged("post_install", "-at_install")
class TestMatchingEngineGateUrl(PlasticosTestCase):
    def test_unset_url_disables_matching(self):
        saved = _set_gate_url(None)
        try:
            self.assertFalse(matching_engine_is_enabled(self.env))
            self.assertTrue(matching_engine_should_skip_cron(self.env, _CRON_NAME))
            with self.assertRaises(UserError):
                matching_engine_require_enabled_for_ui(self.env)
        finally:
            _restore_gate_url(saved)

    def test_whitespace_url_disables_matching(self):
        saved = _set_gate_url(" \t\n")
        try:
            self.assertFalse(matching_engine_is_enabled(self.env))
            self.assertTrue(matching_engine_should_skip_cron(self.env, _CRON_NAME))
            with self.assertRaises(UserError):
                matching_engine_require_enabled_for_ui(self.env)
        finally:
            _restore_gate_url(saved)

    def test_set_url_enables_matching(self):
        saved = _set_gate_url("http://127.0.0.1:9")
        try:
            self.assertTrue(matching_engine_is_enabled(self.env))
            self.assertFalse(matching_engine_should_skip_cron(self.env, _CRON_NAME))
            matching_engine_require_enabled_for_ui(self.env)
        finally:
            _restore_gate_url(saved)
