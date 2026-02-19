{
    "name": "Plasticos Logistics Engine",
    "version": "19.0.1.0.0",
    "summary": "Load management and dispatch",
    "author": "PlasticOS",
    "license": "LGPL-3",
    "depends": ["sale_management", "plasticos_security_base", "stock", "mail"],
    "data": [
        "security/ir.model.access.csv",
        "views/load_views.xml",
        "views/sale_order_button.xml",
        "data/cron.xml",
    ],
    "installable": True,
    "application": False,
}
