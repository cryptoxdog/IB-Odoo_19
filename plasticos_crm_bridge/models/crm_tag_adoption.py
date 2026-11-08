"""Adopt one existing Buyer or Supplier crm.tag before XML seed records.

A second row is not created when the XML id already names a live tag, and a
stale or wrong-model XML id is left untouched. Native ``crm.tag`` name
uniqueness is the database rule; this helper does not merge ambiguous rows.
"""

# No ir.model.data row. Distinct from None, which means a row exists and is unusable.
MISSING_ROLE_TAG_BINDING = object()


def role_tag_binding(env, name, xmlid):
    """Return the live ``crm.tag`` named by ``xmlid``, or a miss.

    Returns the tag when that row points at the tag named ``name``.
    Returns ``MISSING_ROLE_TAG_BINDING`` when no ``ir.model.data`` row exists.
    Returns ``None`` when a row exists but does not name that tag.
    Does not create, rebind, or search by name. A foreign model that happens
    to use the same numeric id is a miss, not a tag.
    """
    module, xml_name = xmlid.split(".", 1)
    data = (
        env["ir.model.data"]
        .sudo()  # sudo: sync reads one ir.model.data row; core grants it to group_erp_manager
        .search([("module", "=", module), ("name", "=", xml_name)])
    )
    if not data:
        return MISSING_ROLE_TAG_BINDING
    if len(data) != 1 or data.model != "crm.tag":
        return None
    tag = env["crm.tag"].sudo().browse(data.res_id).exists()  # sudo: sync reads the role tag named by the XML id
    if len(tag) != 1 or tag._name != "crm.tag" or tag.name != name:
        return None
    return tag


def adopt_role_tag(env, name, xmlid) -> bool:
    """Bind ``xmlid`` to the one ``crm.tag`` named ``name``, or create that tag."""
    module, xml_name = xmlid.split(".", 1)
    found = role_tag_binding(env, name, xmlid)
    if found is None:
        return False
    if found is not MISSING_ROLE_TAG_BINDING:
        return True
    tags = env["crm.tag"].search([("name", "=", name)])  # installer reads role tags
    if len(tags) != 1:
        if tags:
            return False
        tags = env["crm.tag"].create({"name": name})  # installer creates the only role tag
    env["ir.model.data"].create(  # installer binds the XML id to that tag
        {
            "module": module,
            "name": xml_name,
            "model": "crm.tag",
            "res_id": tags.id,
            "noupdate": True,
        }
    )
    return True
