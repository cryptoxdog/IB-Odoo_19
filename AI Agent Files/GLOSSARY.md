# GLOSSARY.md — PlasticOS Terminology Reference

**For**: New users, developers, business stakeholders

---

## Business Terms

### Core Concepts

**Intake**
: A supplier's offer to sell plastic material. Contains material specs (polymer, form, color, quantity) and pricing expectations. Starting point of every transaction.

**Material Profile**
: A specific type of plastic material defined by polymer, form, color, source type, and quality attributes. Example: "Natural HDPE Regrind Post-Industrial, 0.95 g/cm³ density."

**Facility Profile**
: A buyer's processing facility with equipment capabilities (washline, granulator, extruder) and material acceptance criteria (polymers, forms, lot sizes).

**Buyer Matching**
: The process of finding compatible buyers for a supplier's intake using 14 hard gates (must-haves) and 9 soft signals (preferences).

**Transaction**
: A completed deal between supplier and buyer. Tracks quantity, pricing, commission, and settlement status.

**Load**
: A shipment of material from supplier to buyer. Includes pickup/delivery logistics, BOL (Bill of Lading), and carrier information.

**Offer**
: A buyer's proposal to purchase an intake at a specific price. Can be accepted, rejected, or expired.

**Commission**
: The fee earned by PlasticOS for brokering a transaction. Calculated as percentage of gross profit (buyer price - supplier price).

---

### Material Specifications

**Polymer**
: The base plastic resin type. Examples: HDPE (high-density polyethylene), PP (polypropylene), PET (polyethylene terephthalate).

**Form**
: Physical format of the material. Examples:
- **Bales**: Compressed, wrapped bundles (typically film)
- **Regrind**: Shredded plastic pieces (5-15mm)
- **Pellet**: Extruded uniform pellets (3-5mm)
- **Flake**: Washed, dried flakes (10-20mm)

**Source Type**
: Origin of the material. Examples:
- **PI (Post-Industrial)**: Factory scrap, clean
- **PCR (Post-Consumer Recycled)**: Household/commercial waste
- **Virgin**: New, unused resin

**Color**
: Color designation. Examples:
- **Natural**: Clear/translucent (highest value)
- **White**: Opaque white
- **Mixed**: Multiple colors (lowest value)
- **Black**: Black pigmented

**MFI (Melt Flow Index)**
: Measure of plastic flowability (g/10min). Higher MFI = thinner, easier to process. Critical for matching to buyer equipment.

**Density**
: Mass per unit volume (g/cm³). Distinguishes HDPE (0.94-0.97) from LDPE (0.91-0.94). Critical quality parameter.

---

### Quality Attributes

**Contamination**
: Foreign materials in the plastic (dirt, paper, other polymers). Measured as percentage. Most buyers tolerate < 5%.

**Moisture**
: Water content in the material. Measured as percentage or PPM (parts per million). Critical for extrusion (must be < 0.5%).

**Metal Contamination**
: Presence of metal pieces (screws, nails, wire). Requires metal separation equipment to remove.

**Flame Retardant (FR)**
: Chemical additives to reduce flammability (common in electronics). Some buyers cannot accept FR materials.

**PVC (Polyvinyl Chloride)**
: Polymer that releases toxic chlorine gas when burned. Zero-tolerance for most buyers (critical safety gate).

**Filler**
: Mineral additives (talc, calcium carbonate, glass fiber) that change properties. Affects density, strength, cost.

---

### Facility Capabilities

**Washline**
: Equipment for cleaning dirty plastic (removes dirt, labels, adhesives). Required for PCR materials.

**Granulator / Shredder**
: Size reduction equipment. Converts bales/parts into regrind.

**Extruder**
: Melting and pelletizing equipment. Converts regrind/flake into uniform pellets.

**Dryer**
: Moisture reduction equipment. Required to meet < 0.5% moisture specs for extrusion.

**Metal Separator**
: Magnetic or eddy current equipment to remove metal contamination.

**Compounding**
: Blending virgin resin with recycled material or adding additives. Requires extruder and dosing equipment.

---

## Technical Terms

### Architecture

**Layer Model**
: PlasticOS's 5-layer architecture:
1. **Material**: Master data (polymers, colors, forms)
2. **Capability**: Facility profiles, equipment
3. **Commercial**: Matching, offers, deals
4. **Compliance**: Documents, validations
5. **Transaction**: Revenue recognition, settlement

**Module**
: Self-contained Odoo application. PlasticOS has 93 modules organized by layer.

**Dependency Graph**
: Map of module dependencies. Determines install order and prevents circular dependencies.

**Manifest**
: `__manifest__.py` file declaring module metadata (name, version, dependencies, data files).

---

### Database

**Model**
: Python class representing a database table. Example: `plasticos.intake` → `plasticos_intake` table.

**Field**
: Column in a database table. Types: Char, Integer, Float, Boolean, Many2one, Many2many, etc.

**Record**
: Single row in a database table. Example: One intake record.

**External ID**
: Unique identifier for data records. Format: `module.record_id`. Used for seed data and migrations.

**ORM (Object-Relational Mapping)**
: Odoo's system for translating Python objects to database queries.

**Computed Field**
: Field calculated dynamically from other fields. Example: `total_price = quantity * price_per_lb`.

**Related Field**
: Field pulled from a related record. Example: `partner_name = partner_id.name`.

---

### Security

**RBAC (Role-Based Access Control)**
: Security model where permissions are assigned to groups (roles), and users inherit group permissions.

**ACL (Access Control List)**
: `ir.model.access.csv` file defining CRUD permissions (read, write, create, delete) per model per group.

**Record Rule**
: Row-level security constraint. Example: "Sales reps can only see their own transactions."

**Multi-Company**
: Isolation of data by company. Users can only access records for their assigned companies.

**Sudo**
: Elevated permissions (bypass security). Use sparingly, typically for system operations.

---

### Graph Database (Neo4j)

**Node**
: Entity in the graph. PlasticOS nodes: Facility, Material, Intake.

**Relationship**
: Connection between nodes. PlasticOS relationships: SOLD_TO (Material → Facility).

**Property**
: Attribute on a node or relationship. Example: `Facility.density_min`.

**Cypher**
: Neo4j's query language (similar to SQL). Used for graph traversal and matching.

**Index**
: Data structure for fast lookups. Example: Index on `Facility.partner_id`.

**Graph Sync**
: Process of copying data from Odoo (PostgreSQL) to Neo4j. Triggered by write hooks.

---

### Buyer Matching

**Hard Gate**
: Must-have requirement. Material rejected if gate fails. Example: "Polymer must match."

**Soft Signal**
: Preference that affects ranking but doesn't reject. Example: "Prefer natural color."

**Two-Stage Matching**
: PlasticOS v2.0 approach:
1. **Stage 1 (Capability Matcher)**: Fast Python filtering using deterministic gates
2. **Stage 2 (Graph Service)**: Neo4j ranking using soft signals and transaction history

**Match Score**
: Composite score (0-1000) ranking buyer suitability. Weighted by geography (40%), transaction history (25%), color (15%), packaging (10%), base (10%).

**Proven Buyer**
: Buyer with transaction history for this material. Gets bonus in match score.

**Geo Filter**
: Distance constraint (miles/km). Most buyers limit to 300-mile radius for freight economics.

---

### Logistics

**BOL (Bill of Lading)**
: Legal document for freight shipment. Lists shipper, consignee, carrier, material description, weight.

**Pickup**
: Collection of material from supplier facility by carrier.

**Delivery**
: Drop-off of material at buyer facility by carrier.

**Trucker / Carrier**
: Third-party logistics provider who transports material.

**Load**
: Single shipment. May contain multiple transactions (LTL = Less Than Truckload, FTL = Full Truckload).

**Dispatch**
: Process of assigning carrier to load and scheduling pickup/delivery.

**SLA (Service Level Agreement)**
: Contracted delivery timeframes. Example: "Pickup within 48 hours of transaction confirmation."

---

### Compliance

**Document Validation Matrix**
: Rules defining required documents per transaction type, material type, or buyer requirement.

**COA (Certificate of Analysis)**
: Lab test results for material quality (MFI, density, contamination, etc.).

**SDS (Safety Data Sheet)**
: Chemical safety information (required for hazardous materials).

**ISO Certification**
: International quality standards (ISO 9001, ISO 14001, ISO 13485 for medical).

**Food Grade Certification**
: FDA/FSMA approval for materials contacting food (stringent purity requirements).

---

### Automation

**Cron Job**
: Scheduled task that runs automatically. Examples:
- Expire old offers (daily)
- Check document expiry (weekly)
- Send invoice reminders (daily)

**Workflow Automation**
: Business rules that trigger actions. Examples:
- "When offer accepted → create transaction"
- "When load delivered → create invoice"

**AI Triage**
: GPT-4o classification of web leads as HOT/WARM/COLD based on inquiry quality.

**Normalization**
: AI extraction of structured data from unstructured text. Example: "LDPE film scrap" → polymer=LDPE, form=film, source_type=scrap.

---

## Development Terms

### Odoo Patterns

**Inheritance**
: Extending existing models. Example: `_inherit = 'res.partner'` adds fields to Partner model.

**Decorator**
: Python function wrapper. Examples:
- `@api.model`: Class method
- `@api.depends('field')`: Computed field dependency
- `@api.constrains('field')`: Validation rule

**Chatter**
: Activity feed showing record history. Requires `_inherit = ['mail.thread']`.

**Wizard**
: Temporary popup form for data collection. Example: Import wizard, bulk update wizard.

**View**
: XML definition of UI layout. Types: form, tree (list), kanban (cards), search.

**Action**
: Button that opens a view or runs code. Example: "Match to Buyers" button.

---

### Testing

**TransactionCase**
: Odoo test class with database rollback after each test.

**Test Coverage**
: Percentage of code executed by tests. Target: 80% for core modules.

**Unit Test**
: Test of single function/method in isolation.

**Integration Test**
: Test of multiple modules working together.

**E2E Test (End-to-End)**
: Test of full user workflow (intake → match → transaction → settlement).

---

### DevOps

**Docker**
: Containerization platform. Packages application + dependencies into portable image.

**Docker Compose**
: Tool for defining multi-container applications (Odoo + PostgreSQL + Neo4j).

**CI/CD**
: Continuous Integration / Continuous Deployment. Automated testing and deployment pipeline.

**Odoo.sh**
: Managed Odoo hosting platform with built-in CI/CD.

**Staging Environment**
: Pre-production environment for testing before production deployment.

---

## Acronyms

| Acronym | Full Term | Meaning |
|---------|-----------|---------|
| **ACL** | Access Control List | Security permissions file |
| **API** | Application Programming Interface | Programmatic access to system |
| **BOL** | Bill of Lading | Shipping document |
| **CI/CD** | Continuous Integration/Deployment | Automated testing/deployment |
| **COA** | Certificate of Analysis | Lab test results |
| **CRUD** | Create, Read, Update, Delete | Basic database operations |
| **ERP** | Enterprise Resource Planning | Business management software |
| **ESG** | Environmental, Social, Governance | Sustainability metrics |
| **FR** | Flame Retardant | Chemical additive |
| **HDPE** | High-Density Polyethylene | Rigid plastic (milk jugs, detergent bottles) |
| **LDPE** | Low-Density Polyethylene | Flexible plastic (bags, film) |
| **MFI** | Melt Flow Index | Plastic flowability measure |
| **OCA** | Odoo Community Association | Open-source Odoo developer community |
| **ORM** | Object-Relational Mapping | Database abstraction layer |
| **PCR** | Post-Consumer Recycled | Recycled household waste |
| **PET** | Polyethylene Terephthalate | Clear plastic (water bottles) |
| **PI** | Post-Industrial | Factory scrap |
| **PP** | Polypropylene | Rigid plastic (yogurt containers, caps) |
| **PVC** | Polyvinyl Chloride | Chlorinated plastic (pipes, window frames) |
| **RBAC** | Role-Based Access Control | Security model |
| **SDS** | Safety Data Sheet | Chemical safety info |
| **SLA** | Service Level Agreement | Performance guarantee |
| **UI** | User Interface | Visual interface |
| **XML** | Extensible Markup Language | Data format for views |

---

## Common Confusion

### Polymer vs Form vs Grade

- **Polymer**: Chemical type (HDPE, PP, PET) — ❌ NOT interchangeable
- **Form**: Physical format (bales, regrind, pellet) — ✅ Can be converted (bales → regrind → pellet)
- **Grade**: Specific resin specification (injection molding grade, blow molding grade) — ❌ Property of the material

### Supplier vs Buyer

- **Supplier**: Sells plastic material (source)
- **Buyer**: Purchases plastic material (destination)
- **PlasticOS**: Broker in the middle (earns commission)

### Intake vs Transaction

- **Intake**: Supplier's offer to sell (potential deal)
- **Transaction**: Confirmed purchase (actual deal)
- **Relationship**: Intake → Match → Offer → Accept → Transaction

### Material Profile vs Intake

- **Material Profile**: Reusable template for a supplier's recurring material
- **Intake**: One-time offer with specific quantity and pricing
- **Relationship**: Intake references Material Profile for specs

### Facility Profile vs Partner

- **Partner** (`res.partner`): Generic contact (company or person)
- **Facility Profile**: Buyer's physical location with equipment and capabilities
- **Relationship**: Facility Profile has `partner_id` (Many2one to res.partner)

---

**Questions?** Open a [GitHub Discussion](https://github.com/cryptoxdog/IB-Odoo_19/discussions) with your question!

*Last Updated: 2026-02-24*
