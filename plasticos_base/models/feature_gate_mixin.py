import functools
import logging

from odoo import _, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

TRUTHY_PARAM_VALUES = {"true", "1", "yes", "on"}


def feature_gated(param_key):
    """Decorator to guard an interactive model method behind an ir.config_parameter flag.

    Usage:
        @feature_gated('plasticos.matching_engine.enabled')
        def action_match_to_buyers(self):
            ...

    When the flag is False/missing, raises UserError with configurable message.
    When True, executes the decorated method normally.
    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            self._check_feature_gate(param_key)
            return func(self, *args, **kwargs)

        return wrapper

    return decorator


class FeatureGateMixin(models.AbstractModel):
    _name = "plasticos.feature.gate.mixin"
    _description = "PlasticOS Feature Gate Mixin"

    def _get_feature_gate_message(self):
        """Get the user-facing message for disabled features."""
        icp = self.env["ir.config_parameter"].sudo()
        return icp.get_param(
            "plasticos.feature_gate.user_message",
            _("This isn't ready - come back in 5 minutes!"),
        )

    def _is_feature_enabled(self, param_key):
        """Check if a feature flag is enabled."""
        icp = self.env["ir.config_parameter"].sudo()
        enabled = (icp.get_param(param_key, "False") or "False").strip().lower()
        return enabled in TRUTHY_PARAM_VALUES

    def _check_feature_gate(self, param_key):
        """Raise UserError if the feature flag is not enabled.

        For use in interactive (button) methods.
        """
        if self._is_feature_enabled(param_key):
            return True

        message = self._get_feature_gate_message()
        _logger.info(
            "Feature gate blocked: model=%s gate=%s user=%s ids=%s",
            self._name,
            param_key,
            self.env.uid,
            list(self.ids),
        )
        raise UserError(message)

    def _skip_feature_gate_for_cron(self, param_key, cron_name):
        """Check feature gate for cron jobs - returns True if should skip (no exception).

        For use in cron methods where we want to silently skip, not crash.
        Returns True if the feature is disabled (caller should return early).
        Returns False if the feature is enabled (caller should proceed).
        """
        if self._is_feature_enabled(param_key):
            return False

        _logger.warning(
            "Feature gate skip: cron=%s model=%s gate=%s",
            cron_name,
            self._name,
            param_key,
        )
        return True
