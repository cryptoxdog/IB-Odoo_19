Web Lead (HOT)
    │
    ▼
┌─────────────────────────────────────┐
│ Intake Created                      │
│ • pending_company_name = "Acme Inc" │
│ • partner_id = NULL                 │
│ • polymer, form, qty, etc. filled   │
└─────────────────────────────────────┘
    │
    ▼
Admin gets notification → Reviews intake
    │
    ├─► "This is legit" → Click "Match to Buyers"
    │       │
    │       ▼
    │   Partner "Acme Inc" created NOW (lazy)
    │   pending_company_name cleared
    │   Matching runs
    │
    └─► "This is spam" → Delete intake
            │
            ▼
        No partner ever created ✅

=========================================

equipment_type_data.xml ──────> plasticos.equipment.type (LOADED)
                                        │
                                        │ Many2many
                                        v
res.partner ──────────────────> plasticos.facility.profile
                                        │
                                        │ equipment_type_ids → computed Booleans
                                        │ has_shredder = computed from M2M
                                        v
                              buyer_match_engine
                              (queries Boolean flags — unchanged)

=========================================
