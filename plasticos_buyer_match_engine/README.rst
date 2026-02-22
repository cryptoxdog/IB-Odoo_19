PlasticOS Buyer Match Engine
############################

Advanced buyer capability matching based on facility profiles and material requirements.

**Features:**

* Odoo 19.0 compatible
* Integrated with PlasticOS ecosystem
* Deterministic matching (capability lanes, quality/volume/geo gates)
* Neo4j graph traversal for relationship-based matching (optional)

Neo4j Setup (Optional)
======================

The module can use Neo4j for graph-based buyer matching. If Neo4j is not configured,
the module falls back to deterministic matching only.

**1. Start Neo4j:**

Using docker-compose.prod.yml::

    docker compose -f docker-compose.prod.yml up -d neo4j

Or standalone::

    docker run -d --name neo4j \
      -p 7474:7474 -p 7687:7687 \
      -e NEO4J_AUTH=neo4j/your_password_here \
      -v neo4j_data:/data \
      neo4j:5-community

**2. Configure Odoo:**

Option A - Environment variables (recommended for Docker)::

    NEO4J_URI=bolt://neo4j:7687
    NEO4J_USER=neo4j
    NEO4J_PASSWORD=your_password_here

Option B - System Parameters (Settings → Technical → Parameters)::

    plasticos_graph.neo4j_uri = bolt://localhost:7687
    plasticos_graph.neo4j_user = neo4j
    plasticos_graph.neo4j_password = your_password_here

**3. Initialize the graph schema:**

From Odoo shell or a scheduled action::

    env["plasticos.graph.service"].initialize_schema()
    env["plasticos.graph.service"].sync_all()

**4. Verify connection:**

The "Match To Buyers" button on intakes will use Neo4j if available.
If Neo4j is down, a notification appears and deterministic matching proceeds.

For detailed documentation, see the module's technical docs.
