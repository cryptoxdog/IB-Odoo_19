# SECURITY_MODEL.md — PlasticOS Security Architecture

**Repository**: cryptoxdog/IB-Odoo_19
**Odoo Version**: 19.0
**Security Model**: Role-Based Access Control (RBAC)

## Overview

PlasticOS implements a layered security model aligned with Odoo 19 best practices:
1. **Group-based permissions** (RBAC)
2. **Record rules** (row-level security)
3. **Field-level access control**
4. **Multi-company isolation**
5. **External API security**

---

## 1. Group Hierarchy

**Base Module**: `plasticos_security_base`

### Group Structure (Odoo 19 Privilege Model)

```
plasticos_privilege_manager (Full Access)
    ├── implied_ids → base.group_system
    ├── implied_ids → base.group_erp_manager
    └── Access: All models (CRUD)

plasticos_privilege_user (Standard User)
    ├── implied_ids → base.group_user
    ├── Access: Read all, Write own records
    └── No access to: Security, Technical settings

plasticos_privilege_readonly (Reports Only)
    ├── implied_ids → None
    ├── Access: Read-only all models
    └── No write/create/delete

plasticos_group_sales (Sales Rep)
    ├── implied_ids → plasticos_privilege_user
    ├── Access: Own transactions, intakes, offers
    └── Restricted: Other reps' data

plasticos_group_logistics (Logistics Coordinator)
    ├── implied_ids → plasticos_privilege_user
    ├── Access: Loads, carriers, dispatch
    └── Restricted: Financial data

plasticos_group_compliance (Compliance Officer)
    ├── implied_ids → plasticos_privilege_user
    ├── Access: Documents, validation matrices
    └── Restricted: Transactions without approval

plasticos_group_accounting (Accounting)
    ├── implied_ids → account.group_account_invoice
    ├── Access: Invoices, payments, commissions
    └── Restricted: No edit transactions after invoiced
```

### Group Assignment

**Automatic** (via `implied_ids`):
- User assigned to `plasticos_group_sales` automatically gets `plasticos_privilege_user`

**Manual** (via Users & Companies):
- Navigate to **Settings > Users & Companies > Users**
- Select user
- Go to **Access Rights** tab
- Check appropriate groups

---

## 2. Access Control Lists (ACL)

**Location**: `<module>/security/ir.model.access.csv`

### ACL Format

```csv
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_plasticos_intake_user,plasticos.intake user,model_plasticos_intake,plasticos_security_base.group_plasticos_user,1,1,1,0
access_plasticos_intake_manager,plasticos.intake manager,model_plasticos_intake,plasticos_security_base.group_plasticos_manager,1,1,1,1
access_plasticos_intake_readonly,plasticos.intake readonly,model_plasticos_intake,plasticos_security_base.group_plasticos_readonly,1,0,0,0
```

### Permission Levels

| Permission | Flag | Description |
|-----------|------|-------------|
| Read | `perm_read` | View records |
| Write | `perm_write` | Modify existing records |
| Create | `perm_create` | Create new records |
| Unlink | `perm_unlink` | Delete records |

### ACL Best Practices

1. **Manager gets full access** (1,1,1,1)
2. **User gets CRUD except delete** (1,1,1,0)
3. **Readonly gets read only** (1,0,0,0)
4. **Public user gets no access** (usually omitted)

### Example ACL: `plasticos_transaction/security/ir.model.access.csv`

```csv
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_transaction_manager,plasticos.transaction manager,model_plasticos_transaction,plasticos_security_base.group_plasticos_manager,1,1,1,1
access_transaction_user,plasticos.transaction user,model_plasticos_transaction,plasticos_security_base.group_plasticos_user,1,1,1,0
access_transaction_sales,plasticos.transaction sales,model_plasticos_transaction,plasticos_security_base.group_plasticos_sales,1,1,0,0
access_transaction_readonly,plasticos.transaction readonly,model_plasticos_transaction,plasticos_security_base.group_plasticos_readonly,1,0,0,0
access_commission_manager,plasticos.commission manager,model_plasticos_commission,plasticos_security_base.group_plasticos_manager,1,1,1,1
access_commission_accounting,plasticos.commission accounting,model_plasticos_commission,account.group_account_invoice,1,1,0,0
```

---

## 3. Record Rules (Row-Level Security)

**Location**: `<module>/security/plasticos_<model>_security.xml`

### Record Rule Structure

```xml
<record id="plasticos_intake_sales_rule" model="ir.rule">
    <field name="name">Sales Rep: Own Intakes Only</field>
    <field name="model_id" ref="model_plasticos_intake"/>
    <field name="groups" eval="[(4, ref('plasticos_security_base.group_plasticos_sales'))]"/>
    <field name="domain_force">[('sales_rep_id', '=', user.id)]</field>
    <field name="perm_read" eval="True"/>
    <field name="perm_write" eval="True"/>
    <field name="perm_create" eval="True"/>
    <field name="perm_unlink" eval="False"/>
</record>
```

### Domain Expressions

**Common Patterns**:
```python
# User's own records
[('sales_rep_id', '=', user.id)]

# User's company records
[('company_id', '=', user.company_id.id)]

# Multiple conditions (AND)
[('company_id', '=', user.company_id.id), ('state', '!=', 'cancel')]

# OR conditions
['|', ('sales_rep_id', '=', user.id), ('state', '=', 'draft')]

# Related field filtering
[('buyer_id.commercial_partner_id', '=', user.partner_id.commercial_partner_id)]
```

### Example Record Rules

#### Multi-Company Isolation
```xml
<record id="plasticos_transaction_multi_company_rule" model="ir.rule">
    <field name="name">Transaction: Multi-Company</field>
    <field name="model_id" ref="model_plasticos_transaction"/>
    <field name="domain_force">[('company_id', 'in', company_ids)]</field>
    <field name="global" eval="True"/>
</record>
```

#### Sales Rep Restriction
```xml
<record id="plasticos_transaction_sales_rule" model="ir.rule">
    <field name="name">Transaction: Sales Rep Own</field>
    <field name="model_id" ref="model_plasticos_transaction"/>
    <field name="groups" eval="[(4, ref('group_plasticos_sales'))]"/>
    <field name="domain_force">[('sales_rep_id', '=', user.id)]</field>
</record>
```

#### Buyer Portal Access
```xml
<record id="plasticos_offer_buyer_portal_rule" model="ir.rule">
    <field name="name">Offer: Buyer Portal Access</field>
    <field name="model_id" ref="model_plasticos_offer"/>
    <field name="groups" eval="[(4, ref('base.group_portal'))]"/>
    <field name="domain_force">[('buyer_id.commercial_partner_id', '=', user.partner_id.commercial_partner_id)]</field>
</record>
```

---

## 4. Field-Level Security

### Readonly Fields Based on State

```python
class PlasticosTransaction(models.Model):
    _name = 'plasticos.transaction'

    price_per_lb_buyer = fields.Float(
        readonly=lambda self: self.state in ('invoiced', 'paid')
    )
```

### Groups-Based Field Visibility

```xml
<field name="commission_amount" groups="plasticos_security_base.group_plasticos_manager,account.group_account_invoice"/>
```

### Invisible Fields in UI

```xml
<field name="internal_notes" invisible="1"/>  <!-- Always hidden -->
<field name="cost_price" groups="purchase.group_purchase_manager"/>
```

---

## 5. Multi-Company Security

### Company Field on Models

```python
class PlasticosTransaction(models.Model):
    _name = 'plasticos.transaction'
    _inherit = ['mail.thread']

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
    )
```

### Global Record Rule

```xml
<record id="plasticos_transaction_comp_rule" model="ir.rule">
    <field name="name">Transaction: Multi-Company Global</field>
    <field name="model_id" ref="model_plasticos_transaction"/>
    <field name="domain_force">[('company_id', 'in', company_ids)]</field>
    <field name="global" eval="True"/>
</record>
```

---

## 6. External API Security

### Neo4j Connection Security

**Credentials Storage**:
```python
# Environment variables (never hardcoded)
NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USER = os.getenv("NEO4J_USER")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
```

**Connection Isolation**:
```python
def _connect(self):
    try:
        self.driver = GraphDatabase.driver(
            self.uri,
            auth=(self.user, self.password),
            max_connection_pool_size=50,
            connection_timeout=10.0,
        )
    except Exception as e:
        _logger.error(f"Neo4j connection failed: {e}")
        self.driver = None  # Fail gracefully
```

### OpenAI API Security

**Key Management**:
```python
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    _logger.warning("OPENAI_API_KEY not set, web lead triage will fallback to COLD")
```

**Data Sanitization**:
```python
def _sanitize_for_llm(self, text):
    """Remove PII before sending to OpenAI."""
    # Remove email addresses
    text = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[EMAIL]', text)
    # Remove phone numbers
    text = re.sub(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b', '[PHONE]', text)
    return text
```

---

## 7. Audit Logging

### Odoo Native Audit

**mail.thread** inheritance provides:
- Chatter log of all changes
- User attribution
- Timestamp tracking

```python
class PlasticosTransaction(models.Model):
    _inherit = ['mail.thread', 'mail.activity.mixin']

    state = fields.Selection([...], tracking=True)
    buyer_id = fields.Many2one('res.partner', tracking=True)
```

### Custom Automation Log

**Module**: `plasticos_automation`

```python
class AutomationLog(models.Model):
    _name = 'plasticos.automation.log'

    automation_type = fields.Char(required=True)
    record_id = fields.Integer(required=True)
    model = fields.Char(required=True)
    action_taken = fields.Text()
    result = fields.Selection([('success', 'Success'), ('error', 'Error')])
    timestamp = fields.Datetime(default=fields.Datetime.now)
```

---

## 8. Security Hardening Checklist

### Production Security

- [ ] Change default `admin` password immediately
- [ ] Disable demo/test users
- [ ] Enable SSL/TLS (use reverse proxy)
- [ ] Restrict database access (firewall rules)
- [ ] Rotate API keys every 90 days
- [ ] Review ACL files for each module
- [ ] Test record rules with different user roles
- [ ] Enable MFA for admin accounts
- [ ] Configure backup retention policy
- [ ] Set up monitoring alerts
- [ ] Disable unnecessary modules
- [ ] Review sudo() usage (minimize)

### Password Policy

```python
# Odoo settings
auth_password_policy_minlength = 12
auth_password_policy_upper = True
auth_password_policy_lower = True
auth_password_policy_number = True
auth_password_policy_special = True
```

### Session Security

```python
# odoo.conf
session_timeout = 3600  # 1 hour
```

---

**Security Model Version**: 1.0.0
**Last Updated**: 2026-02-24
**Compliance**: GDPR-aware, PCI-DSS N/A (no payment processing)
