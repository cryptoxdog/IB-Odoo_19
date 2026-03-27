{
    "name": "PlasticOS Accounting",
    "version": "19.0.1.6.0",
    "summary": "Accounting seed data: payment terms, chart of accounts, incoterms",
    "license": "LGPL-3",
    "author": "Igor Beylin",
    "category": "Accounting/Accounting",
    "depends": [
        "account",
    ],
    "data": [
        "data/payment_terms.xml",
        "data/accounts.xml",
    ],
    "pre_init_hook": "pre_init_hook",
    "installable": True,
    "auto_install": True,
    "application": False,
}
