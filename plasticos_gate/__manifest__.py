{
    "name": "PlasticOS Gate Client",
    "version": "19.0.1.6.0",
    "category": "Plasticos/Integration",
    "summary": "Constellation Gate TransportPacket client seam for Odoo intelligence routing.",
    "author": "Igor Beylin",
    "depends": [
        "base",
        "plasticos_base",
    ],
    "data": [
        "data/gate_icp_seed.xml",
    ],
    "external_dependencies": {"python": ["constellation_node_sdk"]},
    "installable": True,
    "application": False,
    "license": "LGPL-3",
}
