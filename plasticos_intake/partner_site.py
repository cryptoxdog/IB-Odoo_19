"""The company a partner belongs to, past its persons and sites (ADR-131).

Odoo's ``commercial_partner_id`` stops at the first record with
``is_company`` set. An ERP site is still a company record parented under a
company until the ADR-131 data phase moves it to a native delivery address, so
for that shape ``commercial_partner_id`` is the site itself. This walk asks the
D1 predicate (``res.partner._plasticos_is_site``) instead, so it lands on the
owning company for both site shapes.

Odoo-free: exercised by pure pytest with stand-in partners.
"""

from __future__ import annotations


def site_company(partner):
    """The first ancestor-or-self that is a company and not a site.

    A top-level company is itself. A site, a person, or a person at a site
    resolves to the company that owns it. A partner with no such ancestor
    returns the empty value its last ``parent_id`` holds (an empty recordset
    under Odoo). Odoo forbids parent cycles (``_check_parent_id``).
    """
    node = partner
    while node:
        if node.is_company and not node._plasticos_is_site():
            return node
        node = node.parent_id
    return node
