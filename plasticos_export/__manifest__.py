{
    "name": "PlasticOS Export",
    "version": "19.0.1.3.0",
    "summary": "Export booking and shipment context over native and PlasticOS owners",
    # The Apps page renders this text as reStructuredText. Without it Odoo renders the
    # Markdown README, whose YAML front matter is not valid reStructuredText.
    "description": (
        "Export booking and shipment context over the native Sale, Purchase and Stock owners "
        "and the PlasticOS Logistics, Documents and Security Base owners. See README.md."
    ),
    "category": "PlasticOS",
    "author": "Igor Beylin",
    "license": "LGPL-3",
    # Export depends on its owners, never the reverse. plasticos_documents_native
    # reaches Enterprise documents/documents_account. The owners Export imports or
    # extends directly are named too: Logistics (J1, load guard, Linda), Documents
    # (obligations), Security Base (roles), native Purchase, Sale and Stock (cargo
    # sources) and base_automation (booking reply trigger).
    "depends": [
        "base_automation",
        "purchase",
        "sale",
        "stock",
        "plasticos_security_base",
        "plasticos_logistics",
        "plasticos_documents",
        "plasticos_documents_native",
    ],
    "data": [
        "security/ir.model.access.csv",
        "security/export_record_rules.xml",
        "views/booking_views.xml",
        "views/allocation_views.xml",
        "views/shipment_views.xml",
        "views/export_analysis_views.xml",
        "views/export_menus.xml",
        "wizard/manual_booking_candidate_views.xml",
        "wizard/slot_command_views.xml",
        "report/export_report_actions.xml",
        "report/report_booking_summary.xml",
        "report/report_container_manifest.xml",
        "data/linda_booking_inbound.xml",
    ],
    "installable": True,
    "application": True,
    "auto_install": False,
}
