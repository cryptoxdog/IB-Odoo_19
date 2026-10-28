"""Shared VanillaSoft → Odoo CRM mapping constants (SSOT for sync + CSV import)."""

# Approved VanillaSoft Lead Status → crm.stage XML ID.
# COLD, Open, Current Working With, Unqualified, Dead, DNC, Duplicate and
# Wrong # are intentionally absent: those destinations are not approved, and
# the sync must not coerce them onto WARM, Won, or Dead.
STAGE_MAPPING = {
    "2a=Qualified/HOT": "plasticos_crm_bridge.stage_qualified_hot",
    "2b=Qualified/WARM": "plasticos_crm_bridge.stage_qualified_warm",
    "3=Qualified/Resist": "plasticos_crm_bridge.stage_resistant",
    "New": "plasticos_crm_bridge.stage_new",
}

UNAPPROVED_LEAD_STATUSES = (
    "2c=Qualified/COLD",
    "2=Qualified/Open",
    "1= Currently Working With",
    "4=Unqualified",
    "5=Dead Lead",
    "7=Do Not Call",
    "8=Duplicate",
    "6=Wrong #",
)

# VanillaSoft Company Type → res.partner.category XML ID.
# Descriptive classifications only. Not a Buyer/Supplier trade role.
COMPANY_TYPE_MAPPING = {
    "Distribution Center": "plasticos_crm_bridge.categ_distribution_center",
    "Commercial Recycler": "plasticos_crm_bridge.categ_commercial_recycler",
    "Pallet Recycler": "plasticos_crm_bridge.categ_pallet_recycler",
    "Compounder": "plasticos_crm_bridge.categ_compounder",
    "Grinder/Processor": "plasticos_crm_bridge.categ_grinder_processor",
    "E-Waste": "plasticos_crm_bridge.categ_ewaste",
    "MRF": "plasticos_crm_bridge.categ_mrf",
    "Manufacturer": "plasticos_crm_bridge.categ_manufacturer",
    "Broker": "plasticos_crm_bridge.categ_broker",
    "Carrier": "plasticos_crm_bridge.categ_carrier",
}

COMPANY_TYPE_ALIASES = {
    "Grinder_Processor": "Grinder/Processor",
}

# ERP partner categories. VanillaSoft Buyer/Supplier must not write these.
ROLE_TAG_MAPPING = {
    "Buyer": "plasticos_crm_bridge.categ_buyer",
    "Supplier": "plasticos_crm_bridge.categ_supplier",
}

# Native CRM tags. The only approved destination for VanillaSoft Buyer/Supplier.
CRM_ROLE_TAG_MAPPING = {
    "Buyer": "plasticos_crm_bridge.crm_tag_buyer",
    "Supplier": "plasticos_crm_bridge.crm_tag_supplier",
}
