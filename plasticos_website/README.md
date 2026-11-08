---
auto_generated: false
authority: derived-index
component_id: plasticos_website
component_name: PlasticOS Website Branding
module_version: 19.0.1.0.0
installable: false
auto_install: false
application: false
depends:
  - website
  - plasticos_base
models_owned: []
models_extended: []
crons: []
---

# PlasticOS Website Branding

The front matter above is a derived index. `__manifest__.py` wins on any conflict. `AGENTS.md` lists this module as UI, not as a numbered layer, so no layer is recorded here.

## What it does

Company branding for the Odoo website and login pages. `installable` is false in the manifest, so Odoo does not load this module and none of the data below is applied on any database.

## How it works

If the module were made installable, its two data files would do this:

- **`data/website_data.xml`**
  - Sets the main company logo from `static/src/img/logo.png`.
  - Sets the default website's name and four social profile URLs.
  - Deletes the shop, event, forum, blog, helpdesk, slides, appointment, and jobs menus for website id 1 (inside `noupdate="0"`, so the deletion would repeat on upgrade).
- **`views/website_templates.xml`**
  - Replaces `website.footer_default` with the company footer. The footer content is in that template.

`__init__.py` states there are no models.

## Models

None.

## Runtime

- `installable` is false. Odoo does not install or load it.
- `auto_install` and `application` are false.
- Tracked files: `__init__.py`, `__manifest__.py`, `data/website_data.xml`, `static/src/img/logo.png`, `views/website_templates.xml`. `.cursorignore` hides this folder from editor search; use the shell to read it.

## Boundaries

- No Python logic, no models, no routes.
- This page does not describe a live website.

## Read next

- [`views/website_templates.xml`](views/website_templates.xml)
- [`data/website_data.xml`](data/website_data.xml)
- [`../plasticos_base/README.md`](../plasticos_base/README.md)
