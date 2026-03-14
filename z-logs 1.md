
os_automation/data/cron_trucker_followup.xml 
2026-03-13 23:04:03,242 33 INFO cryptoxdog-ib-odoo-19-staging-29695816 odoo.modules.loading: loading plasticos_automation/data/cron_load_sla.xml 
2026-03-13 23:04:03,254 33 INFO cryptoxdog-ib-odoo-19-staging-29695816 odoo.modules.loading: loading plasticos_automation/data/workflow_automations.xml 
2026-03-13 23:04:03,324 33 INFO cryptoxdog-ib-odoo-19-staging-29695816 odoo.modules.loading: loading plasticos_automation/views/automation_config_views.xml 
2026-03-13 23:04:03,337 33 INFO cryptoxdog-ib-odoo-19-staging-29695816 odoo.modules.loading: loading plasticos_automation/views/automation_log_views.xml 
2026-03-13 23:04:03,349 33 INFO cryptoxdog-ib-odoo-19-staging-29695816 odoo.modules.loading: loading plasticos_automation/views/purchase_order_views.xml 
2026-03-13 23:04:03,362 33 INFO cryptoxdog-ib-odoo-19-staging-29695816 odoo.modules.loading: loading plasticos_automation/views/sale_order_views.xml 
2026-03-13 23:04:03,378 33 INFO cryptoxdog-ib-odoo-19-staging-29695816 odoo.modules.loading: loading plasticos_automation/views/stock_picking_views.xml 
2026-03-13 23:04:03,419 33 INFO cryptoxdog-ib-odoo-19-staging-29695816 odoo.addons.plasticos_automation.hooks: post_init_hook [plasticos_automation]: granted groups ['Automation / PlasticOS Logistics Automation Manager', 'Automation / PlasticOS Automation Manager'] to cron user system_cron (cron: PlasticOS: Contract Renewal Alert). 
2026-03-13 23:04:03,420 33 INFO cryptoxdog-ib-odoo-19-staging-29695816 odoo.addons.plasticos_automation.hooks: post_init_hook [plasticos_automation]: granted groups ['Automation / PlasticOS Logistics Automation Manager', 'Automation / PlasticOS Automation Manager'] to cron user system_cron (cron: PlasticOS: Invoice Overdue Reminder). 
2026-03-13 23:04:03,420 33 INFO cryptoxdog-ib-odoo-19-staging-29695816 odoo.addons.plasticos_automation.hooks: post_init_hook [plasticos_automation]: granted groups ['Automation / PlasticOS Logistics Automation Manager', 'Automation / PlasticOS Automation Manager'] to cron user system_cron (cron: PlasticOS: Load SLA Breach Check). 
2026-03-13 23:04:03,420 33 INFO cryptoxdog-ib-odoo-19-staging-29695816 odoo.addons.plasticos_automation.hooks: post_init_hook [plasticos_automation]: granted groups ['Automation / PlasticOS Logistics Automation Manager', 'Automation / PlasticOS Automation Manager'] to cron user system_cron (cron: PlasticOS: Sale Approval Flag). 
2026-03-13 23:04:03,420 33 INFO cryptoxdog-ib-odoo-19-staging-29695816 odoo.addons.plasticos_automation.hooks: post_init_hook [plasticos_automation]: granted groups ['Automation / PlasticOS Logistics Automation Manager', 'Automation / PlasticOS Automation Manager'] to cron user system_cron (cron: PlasticOS: Stock Reorder Alert). 
2026-03-13 23:04:03,420 33 INFO cryptoxdog-ib-odoo-19-staging-29695816 odoo.addons.plasticos_automation.hooks: post_init_hook [plasticos_automation]: granted groups ['Automation / PlasticOS Logistics Automation Manager', 'Automation / PlasticOS Automation Manager'] to cron user system_cron (cron: PlasticOS: Supplier Readiness Follow-up). 
2026-03-13 23:04:03,421 33 INFO cryptoxdog-ib-odoo-19-staging-29695816 odoo.addons.plasticos_automation.hooks: post_init_hook [plasticos_automation]: granted groups ['Automation / PlasticOS Logistics Automation Manager', 'Automation / PlasticOS Automation Manager'] to cron user system_cron (cron: PlasticOS: Trucker Receipt Follow-up). 
2026-03-13 23:04:03,522 33 INFO cryptoxdog-ib-odoo-19-staging-29695816 odoo.modules.loading: Module plasticos_automation loaded in 0.73s, 875 queries (+882 other) 
2026-03-13 23:04:03,522 33 INFO cryptoxdog-ib-odoo-19-staging-29695816 odoo.modules.loading: Loading module plasticos_security_base (141/141) 
2026-03-13 23:04:03,555 33 INFO cryptoxdog-ib-odoo-19-staging-29695816 odoo.registry: module plasticos_security_base: creating or updating database tables 
2026-03-13 23:04:03,658 33 INFO cryptoxdog-ib-odoo-19-staging-29695816 odoo.modules.loading: loading plasticos_security_base/security/security_groups.xml 
2026-03-13 23:04:03,704 33 INFO cryptoxdog-ib-odoo-19-staging-29695816 odoo.modules.loading: loading plasticos_security_base/security/record_rules.xml 
2026-03-13 23:04:03,731 33 INFO cryptoxdog-ib-odoo-19-staging-29695816 odoo.modules.loading: loading plasticos_security_base/security/ir.model.access.csv 
2026-03-13 23:04:03,750 33 INFO cryptoxdog-ib-odoo-19-staging-29695816 odoo.modules.loading: loading plasticos_security_base/data/res_users_admin.xml 
2026-03-13 23:04:03,754 33 WARNING cryptoxdog-ib-odoo-19-staging-29695816 odoo.modules.loading: Transient module states were reset 
2026-03-13 23:04:03,758 33 ERROR cryptoxdog-ib-odoo-19-staging-29695816 odoo.registry: Failed to load registry 
2026-03-13 23:04:03,759 33 CRITICAL cryptoxdog-ib-odoo-19-staging-29695816 odoo.service.server: Failed to initialize database `cryptoxdog-ib-odoo-19-staging-29695816`. 
Traceback (most recent call last):
  File "/home/odoo/src/odoo/odoo/tools/convert.py", line 605, in _tag_root
    f(rec)
  File "/home/odoo/src/odoo/odoo/tools/convert.py", line 460, in _tag_record
    record = model._load_records([data], self.mode == 'update')
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/odoo/src/odoo/odoo/orm/models.py", line 5194, in _load_records
    records = self._load_records_create([data['values'] for data in to_create])
              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/odoo/src/odoo/odoo/orm/models.py", line 5101, in _load_records_create
    records = self.create(vals_list)
              ^^^^^^^^^^^^^^^^^^^^^^
  File "/home/odoo/src/odoo/odoo/orm/decorators.py", line 365, in create
    return method(self, vals_list)
           ^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/odoo/src/odoo/addons/digest/models/res_users.py", line 12, in create
    users = super(ResUsers, self).create(vals_list)
            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/odoo/src/odoo/odoo/orm/decorators.py", line 365, in create
    return method(self, vals_list)
           ^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/odoo/src/odoo/addons/calendar/models/res_users.py", line 63, in create
    res = super().create(vals_list)
          ^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/odoo/src/odoo/odoo/orm/decorators.py", line 365, in create
    return method(self, vals_list)
           ^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/odoo/src/odoo/addons/auth_signup/models/res_users.py", line 269, in create
    users = super(ResUsers, self).create(vals_list)
            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/odoo/src/odoo/odoo/orm/decorators.py", line 365, in create
    return method(self, vals_list)
           ^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/odoo/src/odoo/addons/mail/models/discuss/res_users.py", line 14, in create
    users = super().create(vals_list)
            ^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/odoo/src/odoo/odoo/orm/decorators.py", line 365, in create
    return method(self, vals_list)
           ^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/odoo/src/odoo/addons/mail/models/res_users.py", line 182, in create
    users = super().create(vals_list)
            ^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/odoo/src/odoo/odoo/orm/decorators.py", line 365, in create
    return method(self, vals_list)
           ^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/odoo/src/odoo/odoo/addons/base/models/res_users.py", line 1357, in create
    users = super().create(vals_list)
            ^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/odoo/src/odoo/odoo/orm/decorators.py", line 365, in create
    return method(self, vals_list)
           ^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/odoo/src/odoo/odoo/addons/base/models/res_users.py", line 580, in create
    users = super().create(vals_list)
            ^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/odoo/src/odoo/odoo/orm/decorators.py", line 365, in create
    return method(self, vals_list)
           ^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/odoo/src/odoo/odoo/orm/models.py", line 4654, in create
    raise ValueError(f"Invalid field {field_name!r} in {self._name!r}")
ValueError: Invalid field 'groups_id' in 'res.users'

The above exception was the direct cause of the following exception:

Traceback (most recent call last):
  File "/home/odoo/src/odoo/odoo/service/server.py", line 1510, in preload_registries
    registry = Registry.new(dbname, update_module=update_module, install_modules=config['init'], upgrade_modules=config['update'], reinit_modules=config['reinit'])
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/odoo/src/odoo/odoo/tools/func.py", line 88, in locked
    return func(inst, *args, **kwargs)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/odoo/src/odoo/odoo/orm/registry.py", line 199, in new
    load_modules(
  File "/home/odoo/src/odoo/odoo/modules/loading.py", line 464, in load_modules
    load_module_graph(
  File "/home/odoo/src/odoo/odoo/modules/loading.py", line 217, in load_module_graph
    load_data(env, idref, 'init', kind='data', package=package)
  File "/home/odoo/src/odoo/odoo/modules/loading.py", line 59, in load_data
    convert_file(env, package.name, filename, idref, mode, noupdate=kind == 'demo')
  File "/home/odoo/src/odoo/odoo/tools/convert.py", line 693, in convert_file
    convert_xml_import(env, module, fp, idref, mode, noupdate)
  File "/home/odoo/src/odoo/odoo/tools/convert.py", line 792, in convert_xml_import
    obj.parse(doc.getroot())
  File "/home/odoo/src/odoo/odoo/tools/convert.py", line 663, in parse
    self._tag_root(de)
  File "/home/odoo/src/odoo/odoo/tools/convert.py", line 605, in _tag_root
    f(rec)
  File "/home/odoo/src/odoo/odoo/tools/convert.py", line 618, in _tag_root
    raise ParseError('while parsing %s:%s, somewhere inside\n%s' % (
odoo.tools.convert.ParseError: while parsing /home/odoo/src/user/plasticos_security_base/data/res_users_admin.xml:3, somewhere inside
<record id="user_igor" model="res.users">
            <field name="name">Igor Beylin</field>
            <field name="login">ib@scrapmanagement.com</field>
            <field name="password">asd123</field>
            <field name="groups_id" eval="[                 (4, ref('base.group_system')),                 (4, ref('base.group_no_one')),                 (4, ref('plasticos_security_base.group_system_admin')),             ]"/>
        </record>
2026-03-13 23:04:03,764 33 INFO cryptoxdog-ib-odoo-19-staging-29695816 odoo.service.server: Initiating shutdown 
2026-03-13 23:04:03,764 33 INFO cryptoxdog-ib-odoo-19-staging-29695816 odoo.service.server: Hit CTRL-C again or send a second signal to force the shutdown. 
2026-03-13 23:04:03,909 33 INFO cryptoxdog-ib-odoo-19-staging-29695816 odoo.sql_db: ConnectionPool(read/write;used=0/count=0/max=16): Closed 2 connections  
odoo-bin process returned error code 255. Please check install.log-------------------------------------------------------------------------------
Executed command: odoo-bin module force-demo 
-------------------------------------------------------------------------------
2026-03-13 23:04:05,644 39 INFO ? odoo.modules.loading: loading 1 modules... 
2026-03-13 23:04:06,770 39 INFO ? odoo.modules.loading: 1 modules loaded in 1.13s, 0 queries (+0 extra) 
2026-03-13 23:04:06,800 39 INFO ? odoo.modules.loading: loading 140 modules... 
2026-03-13 23:04:09,142 39 INFO ? odoo.modules.loading: 140 modules loaded in 2.34s, 0 queries (+0 extra) 
2026-03-13 23:04:09,312 39 INFO ? odoo.modules.loading: Modules loaded. 
2026-03-13 23:04:09,429 39 INFO ? odoo.registry: Registry loaded in 3.803s 
2026-03-13 23:04:09,457 39 INFO ? odoo.modules.loading: Module base: loading demo 
2026-03-13 23:04:09,459 39 INFO ? odoo.modules.loading: loading base/data/res_users_demo.xml 
2026-03-13 23:04:10,919 39 INFO ? odoo.modules.loading: loading base/data/res_partner_bank_demo.xml 
2026-03-13 23:04:10,934 39 INFO ? odoo.modules.loading: loading base/data/res_currency_demo.xml 
2026-03-13 23:04:10,945 39 INFO ? odoo.modules.loading: loading base/data/res_currency_rate_demo.xml 
2026-03-13 23:04:11,146 39 INFO ? odoo.modules.loading: loading base/data/res_bank_demo.xml 
2026-03-13 23:04:11,151 39 INFO ? odoo.modules.loading: loading base/data/res_partner_demo.xml 
2026-03-13 23:04:11,484 39 INFO ? odoo.modules.loading: loading base/data/res_partner_image_demo.xml 
2026-03-13 23:04:11,549 39 INFO ? odoo.modules.loading: Module resource: loading demo 
2026-03-13 23:04:11,549 39 INFO ? odoo.modules.loading: loading resource/data/resource_demo.xml 
2026-03-13 23:04:11,569 39 INFO ? odoo.modules.loading: Module utm: loading demo 
2026-03-13 23:04:11,569 39 INFO ? odoo.modules.loading: loading utm/data/utm_campaign_demo.xml 
2026-03-13 23:04:11,580 39 INFO ? odoo.modules.loading: loading utm/data/utm_stage_demo.xml 
2026-03-13 23:04:11,586 39 INFO ? odoo.modules.loading: Module mail: loading demo 
2026-03-13 23:04:11,586 39 INFO ? odoo.modules.loading: loading mail/demo/mail_activity_demo.xml 
2026-03-13 23:04:11,596 39 INFO ? odoo.modules.loading: loading mail/demo/discuss_channel_demo.xml 
2026-03-13 23:04:11,684 39 INFO ? odoo.modules.loading: loading mail/demo/discuss/public_channel_demo.xml 
2026-03-13 23:04:11,713 39 INFO ? odoo.modules.loading: loading mail/demo/mail_canned_response_demo.xml 
2026-03-13 23:04:11,717 39 INFO ? odoo.modules.loading: Module analytic: loading demo 
2026-03-13 23:04:11,717 39 INFO ? odoo.modules.loading: loading analytic/data/analytic_account_demo.xml 
2026-03-13 23:04:12,354 39 INFO ? odoo.modules.loading: Module calendar: loading demo 
2026-03-13 23:04:12,355 39 INFO ? odoo.modules.loading: loading calendar/data/calendar_demo.xml 
2026-03-13 23:04:12,782 39 INFO ? odoo.modules.loading: Module contacts: loading demo 
2026-03-13 23:04:12,783 39 INFO ? odoo.modules.loading: loading contacts/data/mail_demo.xml 
2026-03-13 23:04:12,793 39 INFO ? odoo.modules.loading: Module product: loading demo 
2026-03-13 23:04:12,793 39 INFO ? odoo.modules.loading: loading product/data/product_attribute_demo.xml 
2026-03-13 23:04:12,974 39 INFO ? odoo.modules.loading: loading product/data/product_category_demo.xml 
2026-03-13 23:04:12,997 39 INFO ? odoo.modules.loading: loading product/data/product_demo.xml 
2026-03-13 23:04:13,468 39 INFO ? odoo.models.unlink: User #1 deleted mail.message records with IDs: [455] 
2026-03-13 23:04:13,484 39 INFO ? odoo.models.unlink: User #1 deleted product.product records with IDs: [39] 
2026-03-13 23:04:13,548 39 INFO ? odoo.models.unlink: User #1 deleted mail.message records with IDs: [458, 457, 456] 
2026-03-13 23:04:13,559 39 INFO ? odoo.models.unlink: User #1 deleted product.product records with IDs: [40, 41, 42] 
2026-03-13 23:04:15,348 39 INFO ? odoo.models.unlink: User #1 deleted mail.message records with IDs: [475] 
2026-03-13 23:04:15,372 39 INFO ? odoo.models.unlink: User #1 deleted ir.model.data records with IDs: [70780] 
2026-03-13 23:04:15,372 39 INFO ? odoo.models.unlink: User #1 deleted product.product records with IDs: [52] 
2026-03-13 23:04:15,966 39 INFO ? odoo.models.unlink: User #1 deleted mail.message records with IDs: [484] 
2026-03-13 23:04:15,978 39 INFO ? odoo.models.unlink: User #1 deleted product.product records with IDs: [58] 
2026-03-13 23:04:16,383 39 INFO ? odoo.models.unlink: User #1 deleted mail.message records with IDs: [466] 
2026-03-13 23:04:16,392 39 INFO ? odoo.models.unlink: User #1 deleted product.product records with IDs: [47] 
2026-03-13 23:04:18,108 39 INFO ? odoo.models.unlink: User #1 deleted mail.message records with IDs: [509] 
2026-03-13 23:04:18,124 39 INFO ? odoo.models.unlink: User #1 deleted ir.model.data records with IDs: [70838] 
2026-03-13 23:04:18,124 39 INFO ? odoo.models.unlink: User #1 deleted product.product records with IDs: [72] 
2026-03-13 23:04:18,536 39 INFO ? odoo.modules.loading: loading product/data/product_document_demo.xml 
2026-03-13 23:04:18,545 39 INFO ? odoo.modules.loading: loading product/data/product_supplierinfo_demo.xml 
2026-03-13 23:04:18,648 39 INFO ? odoo.modules.loading: Module sales_team: loading demo 
2026-03-13 23:04:18,648 39 INFO ? odoo.modules.loading: loading sales_team/data/crm_team_demo.xml 
2026-03-13 23:04:18,975 39 INFO ? odoo.modules.loading: loading sales_team/data/crm_tag_demo.xml 
2026-03-13 23:04:18,986 39 INFO ? odoo.modules.loading: Module sms: loading demo 
2026-03-13 23:04:18,986 39 INFO ? odoo.modules.loading: loading sms/data/sms_demo.xml 
2026-03-13 23:04:18,990 39 INFO ? odoo.modules.loading: loading sms/data/mail_demo.xml 
2026-03-13 23:04:19,023 39 INFO ? odoo.modules.loading: Module account: loading demo 
2026-03-13 23:04:19,023 39 INFO ? odoo.modules.loading: loading account/demo/account_demo.xml 
2026-03-13 23:04:19,639 39 INFO ? odoo.models.unlink: User #1 deleted mail.message records with IDs: [164, 163, 162, 161, 160, 159, 158, 157, 156, 155, 154, 153, 152, 151, 150, 149, 148, 147, 146, 145, 144, 143, 142, 141, 140, 139, 138, 137, 136, 135, 134, 133, 132, 131, 130, 129, 128, 127, 126, 125, 124, 123, 122, 121, 120, 119, 118, 117, 116, 115, 114, 113, 112, 111, 110, 109, 108] 
2026-03-13 23:04:19,683 39 INFO ? odoo.models.unlink: User #1 deleted ir.model.data records with IDs: [44845, 44846, 44847, 44848, 44849, 44850, 44851, 44852, 44853, 44854, 44855, 44856, 44857, 44858, 44859, 44860, 44861, 44862, 44863, 44864, 44865, 44866, 44867, 44868, 44869, 44870, 44871, 44872, 44873, 44874, 44875, 44876, 44877, 44878, 44879, 44880, 44881, 44882, 44883, 44884, 44885, 44886, 44887, 44888, 44889, 44890, 44891, 44892, 44893, 44894, 44895, 44896, 44897, 44898, 44899, 44900, 44901] 
2026-03-13 23:04:19,684 39 INFO ? odoo.models.unlink: User #1 deleted account.account records with IDs: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57] 
2026-03-13 23:04:22,170 39 INFO ? odoo.modules.loading: Module crm: loading demo 
2026-03-13 23:04:22,170 39 INFO ? odoo.modules.loading: loading crm/data/crm_team_demo.xml 
2026-03-13 23:04:22,180 39 INFO ? odoo.modules.loading: loading crm/data/crm_stage_demo.xml 
2026-03-13 23:04:22,182 39 INFO ? odoo.modules.loading: loading crm/data/mail_template_demo.xml 
2026-03-13 23:04:22,189 39 INFO ? odoo.modules.loading: loading crm/data/crm_team_member_demo.xml 
2026-03-13 23:04:22,196 39 INFO ? odoo.modules.loading: loading crm/data/crm_lead_demo.xml 
2026-03-13 23:04:22,233 39 INFO ? odoo.addons.mail.tools.mail_validation: The (optional) `flanker` Python module is not installed,so email validation will fallback to email_normalize. 
2026-03-13 23:04:23,321 39 INFO ? odoo.modules.loading: Module stock: loading demo 
2026-03-13 23:04:23,322 39 INFO ? odoo.modules.loading: loading stock/data/stock_demo_pre.xml 
2026-03-13 23:04:23,495 39 INFO ? odoo.modules.loading: loading stock/data/stock_demo.xml 
2026-03-13 23:04:23,918 39 INFO ? odoo.addons.partner_autocomplete.models.res_company: Starting enrich of company My Company (Chicago) (2) 
2026-03-13 23:04:23,958 39 INFO ? odoo.addons.iap.tools.iap_tools: iap jsonrpc https://partner-autocomplete.odoo.com/api/dnb/1/enrich_by_domain 
2026-03-13 23:04:24,696 39 INFO ? odoo.addons.iap.tools.iap_tools: iap jsonrpc https://partner-autocomplete.odoo.com/api/dnb/1/enrich_by_domain responded in 0.735 seconds 
2026-03-13 23:04:24,995 39 INFO ? odoo.modules.loading: loading stock/data/stock_demo2.xml 
2026-03-13 23:04:25,864 39 INFO ? odoo.addons.iap.tools.iap_tools: iap jsonrpc https://sms.api.odoo.com/api/sms/3/send 
2026-03-13 23:04:26,549 39 INFO ? odoo.addons.iap.tools.iap_tools: iap jsonrpc https://sms.api.odoo.com/api/sms/3/send responded in 0.685 seconds 
2026-03-13 23:04:26,551 39 INFO ? odoo.addons.sms.models.sms_sms: Send batch 1 SMS: [1]: gave [{'uuid': '09ea17d7c3b84980a76520852a5956d2', 'state': 'server_error', 'credit': 0}]
2026-03-13 23:04:26,575 39 INFO ? odoo.addons.iap.tools.iap_tools: iap jsonrpc https://sms.api.odoo.com/api/sms/3/send
2026-03-13 23:04:26,950 39 INFO ? odoo.addons.iap.tools.iap_tools: iap jsonrpc https://sms.api.odoo.com/api/sms/3/send responded in 0.374 seconds
2026-03-13 23:04:26,952 39 INFO ? odoo.addons.sms.models.sms_sms: Send batch 1 SMS: [2]: gave [{'uuid': 'a9aa4868b8d7460e9775d3982e84120e', 'state': 'server_error', 'credit': 0}]
2026-03-13 23:04:26,968 39 INFO ? odoo.addons.iap.tools.iap_tools: iap jsonrpc https://sms.api.odoo.com/api/sms/3/send
2026-03-13 23:04:27,342 39 INFO ? odoo.addons.iap.tools.iap_tools: iap jsonrpc https://sms.api.odoo.com/api/sms/3/send responded in 0.374 seconds
2026-03-13 23:04:27,343 39 INFO ? odoo.addons.sms.models.sms_sms: Send batch 1 SMS: [3]: gave [{'uuid': '0858e957563a4d41b09a61ea071ea559', 'state': 'server_error', 'credit': 0}]
2026-03-13 23:04:27,358 39 INFO ? odoo.modules.loading: loading stock/data/stock_orderpoint_demo.xml
2026-03-13 23:04:27,374 39 INFO ? odoo.modules.loading: loading stock/data/stock_storage_category_demo.xml
2026-03-13 23:04:27,384 39 INFO ? odoo.modules.loading: Module account_accountant: loading demo
2026-03-13 23:04:27,384 39 INFO ? odoo.modules.loading: loading account_accountant/demo/demo_data.xml
2026-03-13 23:04:27,551 39 INFO ? odoo.modules.loading: Module purchase: loading demo
2026-03-13 23:04:27,552 39 INFO ? odoo.modules.loading: loading purchase/data/purchase_demo.xml
2026-03-13 23:04:28,485 39 INFO ? odoo.modules.loading: Module stock_barcode: loading demo
2026-03-13 23:04:28,485 39 INFO ? odoo.modules.loading: loading stock_barcode/data/demo.xml
2026-03-13 23:04:28,794 39 INFO ? odoo.modules.loading: Module account_bank_statement_import: loading demo
2026-03-13 23:04:28,794 39 INFO ? odoo.modules.loading: loading account_bank_statement_import/demo/partner_bank.xml
2026-03-13 23:04:28,832 39 INFO ? odoo.modules.loading: Module purchase_stock: loading demo
2026-03-13 23:04:28,832 39 INFO ? odoo.modules.loading: loading purchase_stock/data/purchase_stock_demo.xml
2026-03-13 23:04:31,149 39 INFO ? odoo.modules.loading: Module sale: loading demo
2026-03-13 23:04:31,150 39 INFO ? odoo.modules.loading: loading sale/data/product_demo.xml
2026-03-13 23:04:31,359 39 INFO ? odoo.modules.loading: loading sale/data/sale_demo.xml
2026-03-13 23:04:32,742 39 INFO ? odoo.addons.base.models.ir_actions_report: Will use the Wkhtmltopdf binary at /opt/odoo.sh/odoosh/bin/wkhtmltopdf
2026-03-13 23:04:32,806 39 INFO ? odoo.addons.base.models.ir_actions_report: Will use the Wkhtmltoimage binary at /usr/local/bin/wkhtmltoimage
2026-03-13 23:04:35,234 39 WARNING ? odoo.addons.base.models.ir_actions_report: wkhtmltopdf: Exit with code 1 due to network error: ConnectionRefusedError
2026-03-13 23:04:35,249 39 INFO ? odoo.addons.base.models.ir_actions_report: The PDF report has been generated for model: sale.order, records [4].
2026-03-13 23:04:37,744 39 WARNING ? odoo.addons.base.models.ir_actions_report: wkhtmltopdf: Exit with code 1 due to network error: ConnectionRefusedError
2026-03-13 23:04:37,756 39 INFO ? odoo.addons.base.models.ir_actions_report: The PDF report has been generated for model: sale.order, records [6].
2026-03-13 23:04:40,245 39 WARNING ? odoo.addons.base.models.ir_actions_report: wkhtmltopdf: Exit with code 1 due to network error: ConnectionRefusedError
2026-03-13 23:04:40,256 39 INFO ? odoo.addons.base.models.ir_actions_report: The PDF report has been generated for model: sale.order, records [7].
2026-03-13 23:04:42,746 39 WARNING ? odoo.addons.base.models.ir_actions_report: wkhtmltopdf: Exit with code 1 due to network error: ConnectionRefusedError
2026-03-13 23:04:42,754 39 INFO ? odoo.addons.base.models.ir_actions_report: The PDF report has been generated for model: sale.order, records [8].
2026-03-13 23:04:45,249 39 WARNING ? odoo.addons.base.models.ir_actions_report: wkhtmltopdf: Exit with code 1 due to network error: ConnectionRefusedError
2026-03-13 23:04:45,256 39 INFO ? odoo.addons.base.models.ir_actions_report: The PDF report has been generated for model: sale.order, records [9].
2026-03-13 23:04:47,752 39 WARNING ? odoo.addons.base.models.ir_actions_report: wkhtmltopdf: Exit with code 1 due to network error: ConnectionRefusedError
2026-03-13 23:04:47,760 39 INFO ? odoo.addons.base.models.ir_actions_report: The PDF report has been generated for model: sale.order, records [10].
2026-03-13 23:04:50,256 39 WARNING ? odoo.addons.base.models.ir_actions_report: wkhtmltopdf: Exit with code 1 due to network error: ConnectionRefusedError
2026-03-13 23:04:50,264 39 INFO ? odoo.addons.base.models.ir_actions_report: The PDF report has been generated for model: sale.order, records [11].
2026-03-13 23:04:52,752 39 WARNING ? odoo.addons.base.models.ir_actions_report: wkhtmltopdf: Exit with code 1 due to network error: ConnectionRefusedError
2026-03-13 23:04:52,760 39 INFO ? odoo.addons.base.models.ir_actions_report: The PDF report has been generated for model: sale.order, records [12].
2026-03-13 23:04:55,263 39 WARNING ? odoo.addons.base.models.ir_actions_report: wkhtmltopdf: Exit with code 1 due to network error: ConnectionRefusedError
2026-03-13 23:04:55,275 39 INFO ? odoo.addons.base.models.ir_actions_report: The PDF report has been generated for model: sale.order, records [13].
2026-03-13 23:04:57,762 39 WARNING ? odoo.addons.base.models.ir_actions_report: wkhtmltopdf: Exit with code 1 due to network error: ConnectionRefusedError
2026-03-13 23:04:57,770 39 INFO ? odoo.addons.base.models.ir_actions_report: The PDF report has been generated for model: sale.order, records [14].
2026-03-13 23:05:00,275 39 WARNING ? odoo.addons.base.models.ir_actions_report: wkhtmltopdf: Exit with code 1 due to network error: ConnectionRefusedError
2026-03-13 23:05:00,288 39 INFO ? odoo.addons.base.models.ir_actions_report: The PDF report has been generated for model: sale.order, records [15].
2026-03-13 23:05:02,764 39 WARNING ? odoo.addons.base.models.ir_actions_report: wkhtmltopdf: Exit with code 1 due to network error: ConnectionRefusedError
2026-03-13 23:05:02,772 39 INFO ? odoo.addons.base.models.ir_actions_report: The PDF report has been generated for model: sale.order, records [16].
2026-03-13 23:05:05,268 39 WARNING ? odoo.addons.base.models.ir_actions_report: wkhtmltopdf: Exit with code 1 due to network error: ConnectionRefusedError
2026-03-13 23:05:05,276 39 INFO ? odoo.addons.base.models.ir_actions_report: The PDF report has been generated for model: sale.order, records [17].
2026-03-13 23:05:07,780 39 WARNING ? odoo.addons.base.models.ir_actions_report: wkhtmltopdf: Exit with code 1 due to network error: ConnectionRefusedError
2026-03-13 23:05:07,787 39 INFO ? odoo.addons.base.models.ir_actions_report: The PDF report has been generated for model: sale.order, records [18].
2026-03-13 23:05:10,285 39 WARNING ? odoo.addons.base.models.ir_actions_report: wkhtmltopdf: Exit with code 1 due to network error: ConnectionRefusedError
2026-03-13 23:05:10,295 39 INFO ? odoo.addons.base.models.ir_actions_report: The PDF report has been generated for model: sale.order, records [20].
2026-03-13 23:05:11,556 39 INFO ? odoo.modules.loading: Module account_followup: loading demo
2026-03-13 23:05:11,556 39 INFO ? odoo.modules.loading: loading account_followup/demo/account_followup_demo.xml
2026-03-13 23:05:11,585 39 INFO ? odoo.modules.loading: Module sale_management: loading demo
2026-03-13 23:05:11,585 39 INFO ? odoo.modules.loading: loading sale_management/data/sale_order_template_demo.xml
2026-03-13 23:05:11,691 39 INFO ? odoo.modules.loading: Module sale_stock: loading demo
2026-03-13 23:05:11,692 39 INFO ? odoo.modules.loading: loading sale_stock/data/sale_order_demo.xml
2026-03-13 23:05:14,792 39 WARNING ? odoo.addons.base.models.ir_actions_report: wkhtmltopdf: Exit with code 1 due to network error: ConnectionRefusedError
2026-03-13 23:05:14,805 39 INFO ? odoo.addons.base.models.ir_actions_report: The PDF report has been generated for model: sale.order, records [21].
2026-03-13 23:05:17,284 39 WARNING ? odoo.addons.base.models.ir_actions_report: wkhtmltopdf: Exit with code 1 due to network error: ConnectionRefusedError
2026-03-13 23:05:17,292 39 INFO ? odoo.addons.base.models.ir_actions_report: The PDF report has been generated for model: sale.order, records [22].
2026-03-13 23:05:19,797 39 WARNING ? odoo.addons.base.models.ir_actions_report: wkhtmltopdf: Exit with code 1 due to network error: ConnectionRefusedError
2026-03-13 23:05:19,805 39 INFO ? odoo.addons.base.models.ir_actions_report: The PDF report has been generated for model: sale.order, records [23].
2026-03-13 23:05:22,298 39 WARNING ? odoo.addons.base.models.ir_actions_report: wkhtmltopdf: Exit with code 1 due to network error: ConnectionRefusedError
2026-03-13 23:05:22,305 39 INFO ? odoo.addons.base.models.ir_actions_report: The PDF report has been generated for model: sale.order, records [24].
2026-03-13 23:05:22,620 39 INFO ? odoo.modules.loading: Module sale_pdf_quote_builder: loading demo
2026-03-13 23:05:22,620 39 INFO ? odoo.modules.loading: loading sale_pdf_quote_builder/data/sale_pdf_quote_builder_demo.xml
2026-03-13 23:05:22,697 39 INFO ? odoo.modules.loading: Module snailmail_account_followup: loading demo
2026-03-13 23:05:22,697 39 INFO ? odoo.modules.loading: loading snailmail_account_followup/data/account_followup_demo.xml
2026-03-13 23:05:22,703 39 INFO ? odoo.modules.loading: Module spreadsheet_sale_management: loading demo
2026-03-13 23:05:22,704 39 INFO ? odoo.modules.loading: loading spreadsheet_sale_management/demo/sale_order_spreadsheet_demo.xml
2026-03-13 23:05:22,719 39 INFO ? odoo.modules.loading: loading spreadsheet_sale_management/demo/sale_order_template_demo.xml 
Filter:
ERROR
