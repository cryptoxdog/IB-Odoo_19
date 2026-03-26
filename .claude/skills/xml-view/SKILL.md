---
name: xml-view
description: Create or modify Odoo XML views following PlasticOS conventions
---

# XML View Development

## Creating a New View

1. Create file in `plasticos_{module}/views/{model}_views.xml`
2. Add to `__manifest__.py` `data` list
3. Include form, tree, and search views:

```xml
<odoo>
  <!-- Tree View -->
  <record id="plasticos_{module}.{model}_tree" model="ir.ui.view">
    <field name="name">plasticos.{model}.tree</field>
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

  <!-- Form View -->
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

## Extending Existing Views (XPath)

- Target stable anchors (field names, not positions)
- ✅ `<xpath expr="//field[@name='partner_id']" position="after">`
- ❌ `<xpath expr="//group[2]/field[3]" position="replace">` (fragile)
- Prefer `position="after"` or `position="inside"` over `position="replace"`
- Run: `python3 ci/check_xpath_stability.py`

## Validation
- `xmllint --noout` on all XML files (checked in CI)
- `python3 ci/check_odoo19_xml.py` for Odoo 19 compatibility
