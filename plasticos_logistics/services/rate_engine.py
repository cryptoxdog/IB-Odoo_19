import logging

_logger = logging.getLogger(__name__)


def get_recent_lane_rate(env, carrier_id, lane_key):
    """Compatibility shim after cache retirement; never read legacy cache evidence."""
    _logger.warning(
        "Legacy rate-memory lookup requested for carrier %s and lane %s; canonical freight history is required.",
        carrier_id,
        lane_key,
    )
    return None
