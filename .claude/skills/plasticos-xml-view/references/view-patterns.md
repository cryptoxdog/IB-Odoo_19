<!-- L9_META
skill_schema: 1
parent: plasticos-xml-view
layer: reference
role: view_patterns
tags: [plasticos, odoo, xml, form, list, xpath]
owner: igor_beylin
status: active
version: 1.1.0
updated: 2026-06-06
/L9_META -->

# View Patterns

## New View File

1. Path: `plasticos_{module}/views/{model}_views.xml`
2. Add to `__manifest__.py` `data` list
3. External IDs: `plasticos_{module}.{model}_tree`, `_form`, `_search`

## List + Form Template

```xml
<odoo>
  <record id="plasticos_{module}.{model}_tree" model="ir.ui.view">
    <field name="name">plasticos.{model}.list</field>
    <field name="model">plasticos.{model}</field>
    <field name="arch" type="xml">
      <list>
        <field name="name"/>
        <field name="state" widget="badge"
               decoration-info="state == 'draft'"
               decoration-success="state == 'active'"/>
      </list>
    </field>
  </record>

  <record id="plasticos_{module}.{model}_form" model="ir.ui.view">
    <field name="name">plasticos.{model}.form</field>
    <field name="model">plasticos.{model}</field>
    <field name="arch" type="xml">
      <form>
        <header>
          <field name="state" widget="statusbar"/>
        </header>
        <sheet>
          <group>
            <field name="name"/>
          </group>
        </sheet>
        <chatter/>
      </form>
    </field>
  </record>
</odoo>
```

## XPath Extension

- Target stable anchors: `//field[@name='partner_id']`
- Prefer `position="after"` or `position="inside"` over `replace`
- Avoid `//group[2]/field[3]` position-based XPath
- Run: `python3 ci/check_xpath_stability.py`

## Search View

- No `string=` on `<search>` element
- No `string=` on `<group>` inside search
- Use named filters and group-by fields

## Accessibility

- Font Awesome `<i>` tags MUST have `title="..."` for CI check #21
- Alert elements need `role="alert"`
