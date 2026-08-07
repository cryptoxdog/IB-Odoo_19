"""Shared VanillaSoft → Odoo CRM mapping constants (SSOT for sync + CSV import)."""

# VanillaSoft Lead Status → crm.stage XML ID
STAGE_MAPPING = {
    "2a=Qualified/HOT": "plasticos_crm_bridge.stage_qualified_hot",
    "2b=Qualified/WARM": "plasticos_crm_bridge.stage_qualified_warm",
    "2c=Qualified/COLD": "plasticos_crm_bridge.stage_qualified_warm",
    "2=Qualified/Open": "plasticos_crm_bridge.stage_qualified_warm",
    "3=Qualified/Resist": "plasticos_crm_bridge.stage_resistant",
    "1= Currently Working With": "plasticos_crm_bridge.stage_active_supplier",
    "4=Unqualified": "plasticos_crm_bridge.stage_dead_lead",
    "7=Do Not Call": "plasticos_crm_bridge.stage_dead_lead",
    "8=Duplicate": "plasticos_crm_bridge.stage_dead_lead",
    "6=Wrong #": "plasticos_crm_bridge.stage_dead_lead",
    "New": "plasticos_crm_bridge.stage_new",
}

# VanillaSoft Company Type → res.partner.category XML ID
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

ROLE_TAG_MAPPING = {
    "Buyer": "plasticos_crm_bridge.categ_buyer",
    "Supplier": "plasticos_crm_bridge.categ_supplier",
}
