"""Point Tiffany's seeded user at sa@scrapmanagement.com.

The owner map's destination login is sa@scrapmanagement.com. Databases that
already loaded the stale tw@scrapmanagement.com login keep that login because
the seed is noupdate. This retargets the seeded user when sa@ is free. If
another user already owns sa@, the seeded login is left alone and the importer
must find that existing account.
"""

import logging

_logger = logging.getLogger(__name__)

_TARGET_LOGIN = "sa@scrapmanagement.com"


def migrate(cr, version):
    if not version:
        return
    cr.execute(
        """
        SELECT u.id, u.login
          FROM res_users u
          JOIN ir_model_data d
            ON d.model = 'res.users'
           AND d.res_id = u.id
         WHERE d.module = 'plasticos_base'
           AND d.name = 'user_sales_rep_tw'
        """
    )
    row = cr.fetchone()
    if not row:
        _logger.info("plasticos_base 19.0.1.1.9: Tiffany seed user is absent")
        return
    user_id, login = row
    if (login or "").casefold() != _TARGET_LOGIN:
        cr.execute(
            "SELECT id FROM res_users WHERE lower(login) = lower(%s) AND id != %s",
            (_TARGET_LOGIN, user_id),
        )
        other = cr.fetchone()
        if other:
            _logger.error(
                "plasticos_base 19.0.1.1.9: leaving Tiffany seed user %s on %s because %s belongs to user %s",
                user_id,
                login,
                _TARGET_LOGIN,
                other[0],
            )
            return
        cr.execute("UPDATE res_users SET login = %s WHERE id = %s", (_TARGET_LOGIN, user_id))
        _logger.info("plasticos_base 19.0.1.1.9: Tiffany login %s -> %s", login, _TARGET_LOGIN)
    cr.execute(
        """
        UPDATE res_partner
           SET email = %s
          FROM res_users
         WHERE res_users.partner_id = res_partner.id
           AND res_users.id = %s
        """,
        (_TARGET_LOGIN, user_id),
    )
