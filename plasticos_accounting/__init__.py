import logging

_logger = logging.getLogger(__name__)


def pre_init_hook(env):
    """Ensure account_account.create_asset has a DB default before XML loads.

    The account_asset Enterprise module adds a NOT NULL create_asset column
    but may not set a DB-level DEFAULT. Our accounts.xml INSERT triggers a
    constraint violation without it.
    """
    cr = env.cr
    cr.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'account_account' AND column_name = 'create_asset'
    """)
    if cr.fetchone():
        cr.execute("""
            ALTER TABLE account_account
            ALTER COLUMN create_asset SET DEFAULT 'no'
        """)
        _logger.info("Set DEFAULT 'no' on account_account.create_asset")
