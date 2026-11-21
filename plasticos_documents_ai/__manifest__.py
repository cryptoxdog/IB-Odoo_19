{
    "name": "Plasticos Documents AI",
    "version": "19.0.1.0.0",
    "summary": "DeepSeek Flash provider adapter for Odoo AI server actions used by Documents Auto-Sort",
    # The Apps page renders this text as reStructuredText; the Markdown README carries
    # YAML front matter that is not valid reStructuredText.
    "description": (
        "Adds DeepSeek Flash (non-thinking) as an opt-in model for Odoo AI server actions, "
        "for Plasticos Documents Auto-Sort. Installing it sends nothing and creates no "
        "Auto-Sort rule. See README.md for what is sent to DeepSeek, retention and deletion."
    ),
    "category": "Document Management",
    "author": "Igor Beylin",
    "license": "Other proprietary",
    # DEC-017: a minimal addon isolated from the native Documents bridge. ai_documents
    # brings ai (LLMApiService, ir.actions.server state "ai") and Documents Auto-Sort.
    "depends": [
        "base",  # ir.actions.server
        "plasticos_documents_native",
        "ai",  # LLMApiService and the ir.actions.server AI form this addon extends
        "ai_documents",
    ],
    "data": [
        "views/ir_actions_server_views.xml",
    ],
    "installable": True,
    "application": False,
    # Never installed implicitly: AI activation is an explicit administrator act (GATE-005).
    "auto_install": False,
}
