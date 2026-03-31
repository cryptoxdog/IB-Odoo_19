import logging

_logger = logging.getLogger(__name__)

ICP_DEFAULTS = {
    "plasticos.matching_engine.enabled": "False",
    "plasticos.matching_engine.stub": "True",
    "plasticos_graph.match_geo_radius_miles": "500",
}


def migrate(cr, version):
    """Seed ICP defaults for matching engine if not already set.

    Idempotent: only writes keys that are completely absent.
    Never overwrites existing operator configuration.
    """
    if not version:
        _logger.info("post-migrate: fresh install, seeding ICP defaults")
    for key, default_val in ICP_DEFAULTS.items():
        cr.execute(
            "SELECT value FROM ir_config_parameter WHERE key = %s",
            (key,),
        )
        row = cr.fetchone()
        if row is None:
            cr.execute(
                "INSERT INTO ir_config_parameter (key, value) VALUES (%s, %s)",
                (key, default_val),
            )
            _logger.info("post-migrate: seeded ICP key=%s value=%s", key, default_val)
        else:
            _logger.debug("post-migrate: ICP key=%s already set, skipping", key)
