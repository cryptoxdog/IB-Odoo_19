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

==============
