from . import models


def uninstall_hook(env):
    """Delete open intakes on module uninstall/rebuild."""
    env.cr.execute("""
        DELETE FROM plasticos_intake
        WHERE state IN ('draft', 'pending', 'open')
    """)
    env.cr.commit()
