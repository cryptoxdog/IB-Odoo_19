"""Every installed PlasticOS module page renders without README front matter (C13 OP12-E04).

``ir.module.module.description_html`` is Odoo 19's own rendering of a module
page (``static/description/index.html``, else docutils over the manifest
description or the first README). The pure-Python witness that checks which
source each module resolves to is ``tests/test_module_descriptions.py``.
"""

from odoo.tests.common import TransactionCase, tagged

FRONT_MATTER_KEYS = ("module_version:", "component_id:", "authority: derived-index", "auto_generated:")


@tagged("post_install", "-at_install", "plasticos", "plasticos_export")
class TestModulePages(TransactionCase):
    def test_every_plasticos_module_page_renders_without_front_matter(self):
        modules = self.env["ir.module.module"].search([("name", "=like", "plasticos\\_%")])
        self.assertGreaterEqual(len(modules), 25, "the PlasticOS module census is present")
        installed = modules.filtered(lambda module: module.state == "installed")
        self.assertIn("plasticos_export", installed.mapped("name"))
        for module in modules:
            html = str(module.description_html or "")
            for key in FRONT_MATTER_KEYS:
                self.assertNotIn(key, html, f"{module.name} page shows README front matter ({key})")
            if module.description:
                self.assertFalse(
                    html.lstrip().startswith("<pre><code>"),
                    f"{module.name} description failed to render and fell back to raw text",
                )

    def test_the_check_detects_front_matter_when_a_page_would_show_it(self):
        """Negative witness: README-style front matter in a description does reach the rendered page."""
        module = self.env["ir.module.module"].search([("name", "=", "plasticos_export")])
        module.description = "---\nmodule_version: 19.0.0.0.0\ncomponent_id: plasticos_export\n---\n\nBody\n"
        html = str(module.description_html or "")
        self.assertTrue(any(key in html for key in FRONT_MATTER_KEYS), html)
