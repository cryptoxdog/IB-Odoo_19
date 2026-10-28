"""Adopt one existing Buyer or Supplier crm.tag before XML seed records.

A second row is not created when the XML id already names a live tag, and a
stale or wrong-model XML id is left untouched. Native ``crm.tag`` name
uniqueness is the database rule; this helper does not merge ambiguous rows.
"""


def role_tag_binding(env, name, xmlid):
    """Classify the XML id that should name one live ``crm.tag``.

    Returns ``("bound", tag)`` when that row points at the tag named ``name``.
    Returns ``("absent", None)`` when no ``ir.model.data`` row exists.
    Returns ``("invalid", None)`` when a row exists but does not name that tag.
    Does not create, rebind, or search by name. A foreign model that happens
    to use the same numeric id is invalid, not a tag.
    """
    module, xml_name = xmlid.split(".", 1)
    data = (
        env["ir.model.data"]
        .sudo()
        .search(  # XML-id metadata, not a CRM customer record
            [("module", "=", module), ("name", "=", xml_name)]
        )
    )
    if not data:
        return "absent", None
    if len(data) != 1 or data.model != "crm.tag":
        return "invalid", None
    tag = env["crm.tag"].browse(data.res_id).exists()
    if len(tag) != 1 or tag._name != "crm.tag" or tag.name != name:
        return "invalid", None
    return "bound", tag


def adopt_role_tag(env, name, xmlid) -> bool:
    """Bind ``xmlid`` to the one ``crm.tag`` named ``name``, or create that tag."""
    module, xml_name = xmlid.split(".", 1)
    state, _tag = role_tag_binding(env.sudo(), name, xmlid)  # installer reads the seeded tag
    if state == "bound":
        return True
    if state == "invalid":
        return False
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
