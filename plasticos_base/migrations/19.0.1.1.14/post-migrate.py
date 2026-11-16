"""Archive the BALE form tag: Bales are packaging, not a form.

``material_taxonomy.xml`` now loads ``form_bale`` inactive. The record is archived
here as well, in case its external id is marked noupdate on this database.
Partners keep the tag; it is not deleted.
"""

from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    tag = env.ref("plasticos_base.form_bale", raise_if_not_found=False)
    if tag and tag.active:
        tag.write({"active": False})
