"""Adopt one existing Buyer or Supplier crm.tag before XML seed records.

A second row is not created when the XML id already names a live tag, and a
stale or wrong-model XML id is left untouched. Native ``crm.tag`` name
uniqueness is the database rule; this helper does not merge ambiguous rows.
"""


def adopt_role_tag(env, name, xmlid) -> bool:
    """Bind ``xmlid`` to the one ``crm.tag`` named ``name``, or create that tag."""
    module, xml_name = xmlid.split(".", 1)
    data = (
        env["ir.model.data"]
        .sudo()
        .search(  # installer owns ir.model.data, not a CRM user
            [("module", "=", module), ("name", "=", xml_name)]
        )
    )
    if len(data) > 1:
        return False
    if data:
        if data.model != "crm.tag":
            return False
        tag = env["crm.tag"].sudo().browse(data.res_id).exists()  # installer reads the seeded tag
        if not tag or tag.name != name:
            return False
        return True
    tags = env["crm.tag"].sudo().search([("name", "=", name)])  # installer reads role tags
    if len(tags) != 1:
        if tags:
            return False
        tags = env["crm.tag"].sudo().create({"name": name})  # installer creates the only role tag
    env["ir.model.data"].sudo().create(  # installer binds the XML id to that tag
        {
            "module": module,
            "name": xml_name,
            "model": "crm.tag",
            "res_id": tags.id,
            "noupdate": True,
        }
    )
    return True
