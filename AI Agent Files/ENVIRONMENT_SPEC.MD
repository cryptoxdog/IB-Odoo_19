# ENVIRONMENT_SPEC.yaml — PlasticOS Environment Configuration Specification
# Extracted from: cryptoxdog/IB-Odoo_19 @ staging (2026-02-24)

meta:
  repo: cryptoxdog/IB-Odoo_19
  branch: staging
  extraction_date: "2026-02-24"
  odoo_version: "19.0"
  python_version: "3.12"

# ==============================================================================
# Required Environment Variables
# ==============================================================================
required_variables:
  - name: POSTGRES_USER
    description: "PostgreSQL database username"
    default: "odoo"
    required_for:
      - docker
      - odoo_sh
    validation: "^[a-zA-Z][a-zA-Z0-9_]{2,}$"
    example: "odoo"

  - name: POSTGRES_PASSWORD
    description: "PostgreSQL database password"
    default: null
    required_for:
      - docker
      - odoo_sh
    validation: "^.{8,}$"
    security_level: "critical"
    example: "strong_password_123"

  - name: POSTGRES_DB
    description: "PostgreSQL database name"
    default: "odoo"
    required_for:
      - docker
      - odoo_sh
    validation: "^[a-zA-Z][a-zA-Z0-9_]{2,}$"
    example: "odoo"

  - name: NEO4J_URI
    description: "Neo4j connection URI (Bolt protocol)"
    default: "bolt://localhost:7687"
    required_for:
      - docker
    validation: "^bolt://[a-zA-Z0-9.-]+(:[0-9]+)?$"
    example: "bolt://neo4j:7687"
    notes: |
      - Use 'bolt://neo4j:7687' from Docker network (container-to-container)
      - Use 'bolt://localhost:7687' from host machine
      - Use external URI for Odoo.sh (e.g., Neo4j Aura)

  - name: NEO4J_USER
    description: "Neo4j username"
    default: "neo4j"
    required_for:
      - docker
    validation: "^[a-zA-Z][a-zA-Z0-9_]{2,}$"
    example: "neo4j"

  - name: NEO4J_PASSWORD
    description: "Neo4j password"
    default: null
    required_for:
      - docker
    validation: "^.{8,}$"
    security_level: "critical"
    example: "neo4j_secure_password"
    notes: "Minimum 8 characters enforced by Neo4j"

# ==============================================================================
# Optional Environment Variables
# ==============================================================================
optional_variables:
  - name: OPENAI_API_KEY
    description: "OpenAI API key for web lead triage (GPT-4)"
    default: null
    required_for: []
    modules:
      - plasticos_web_leads
    validation: "^sk-[a-zA-Z0-9]{32,}$"
    security_level: "high"
    example: "sk-abc123..."
    fallback_behavior: "Web leads marked 'COLD' for manual review"

  - name: ODOO_DB_HOST
    description: "Database host (Docker service name or IP)"
    default: "db"
    required_for:
      - docker
    validation: "^[a-zA-Z0-9.-]+$"
    example: "db"

  - name: ODOO_DB_PORT
    description: "Database port"
    default: "5432"
    required_for: []
    validation: "^[0-9]{4,5}$"
    example: "5432"

  - name: ODOO_REBUILD_MODULES
    description: "Comma-separated module list for rebuild script"
    default: null
    required_for: []
    validation: "^plasticos_[a-z_]+(,plasticos_[a-z_]+)*$"
    example: "plasticos_transaction,plasticos_buyer_match_engine"
    usage: "./scripts/rebuild-odoo-modules.sh"

  - name: ODOO_TEST_MODULES
    description: "Comma-separated module list for test script"
    default: "plasticos_transaction,plasticos_buyer_match_engine"
    required_for: []
    validation: "^plasticos_[a-z_]+(,plasticos_[a-z_]+)*$"
    example: "plasticos_transaction,plasticos_intake"
    usage: "./scripts/run-odoo-tests.sh"

  - name: ODOO_TEST_DB
    description: "Test database name (isolated from production)"
    default: "odoo_test"
    required_for: []
    validation: "^[a-zA-Z][a-zA-Z0-9_]{2,}$"
    example: "odoo_test"

# ==============================================================================
# Development Environment
# ==============================================================================
development:
  docker_compose_file: "docker-compose.prod.yml"
  env_file: ".env"
  volumes:
    - "./plasticos_*:/mnt/extra-addons"
    - "odoo-web-data:/var/lib/odoo"
    - "odoo-config:/etc/odoo"
  ports:
    odoo: "8069:8069"
    neo4j_browser: "7474:7474"
    neo4j_bolt: "7687:7687"
    postgres: "5432:5432"  # Optional, for direct DB access

# ==============================================================================
# Staging Environment
# ==============================================================================
staging:
  platform: "odoo_sh"
  branch: "staging"
  auto_deploy: true
  run_tests: true
  environment_variables:
    - NEO4J_URI
    - NEO4J_USER
    - NEO4J_PASSWORD
    - OPENAI_API_KEY
  external_services:
    neo4j:
      provider: "neo4j_aura"
      connection_string_format: "neo4j+s://<instance>.databases.neo4j.io"
      notes: "Odoo.sh does not support Docker containers; use external Neo4j"

# ==============================================================================
# Production Environment
# ==============================================================================
production:
  platform: "odoo_sh"
  branch: "main"
  auto_deploy: true
  run_tests: true
  backup_retention: "30 days"
  monitoring:
    enabled: true
    alerts:
      - error_rate_threshold: 0.01
      - response_time_threshold_ms: 500
  security:
    ssl_enabled: true
    mfa_required: true
    password_rotation_days: 90
  environment_variables:
    - NEO4J_URI
    - NEO4J_USER
    - NEO4J_PASSWORD
    - OPENAI_API_KEY
  external_services:
    neo4j:
      provider: "neo4j_aura_professional"
      connection_string_format: "neo4j+s://<instance>.databases.neo4j.io"
      backup_enabled: true

# ==============================================================================
# Environment Validation Rules
# ==============================================================================
validation_rules:
  - rule: "NEO4J_PASSWORD must be at least 8 characters"
    enforcement: "pre_deployment"
    blocker: true

  - rule: "OPENAI_API_KEY must start with 'sk-' if provided"
    enforcement: "runtime"
    blocker: false

  - rule: "POSTGRES_PASSWORD must not be 'admin' or 'password'"
    enforcement: "pre_deployment"
    blocker: true

  - rule: "All *_PASSWORD variables must not be logged"
    enforcement: "runtime"
    blocker: true

  - rule: "NEO4J_URI must use 'bolt://' or 'neo4j+s://' protocol"
    enforcement: "runtime"
    blocker: false

# ==============================================================================
# External Service Dependencies
# ==============================================================================
external_services:
  postgresql:
    version: "15+"
    required: true
    connection_string: "postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@${ODOO_DB_HOST}:${ODOO_DB_PORT}/${POSTGRES_DB}"
    health_check: "SELECT 1"

  neo4j:
    version: "5.0+"
    required: false
    fallback: "Python-only 10-gate filtering (no graph scoring)"
    connection_string: "${NEO4J_URI}"
    health_check: "CALL dbms.ping()"
    modules_dependent:
      - plasticos_buyer_match_engine

  openai:
    api_version: "v1"
    required: false
    fallback: "Manual web lead classification"
    base_url: "https://api.openai.com/v1"
    models_used:
      - "gpt-4o"  # Text normalization
      - "gpt-4o-vision-preview"  # Image analysis
    modules_dependent:
      - plasticos_web_leads

# ==============================================================================
# Docker Compose Service Configuration
# ==============================================================================
docker_services:
  db:
    image: "postgres:15"
    environment:
      POSTGRES_USER: "${POSTGRES_USER}"
      POSTGRES_PASSWORD: "${POSTGRES_PASSWORD}"
      POSTGRES_DB: "${POSTGRES_DB}"
    volumes:
      - "odoo-db-data:/var/lib/postgresql/data"
    restart: "unless-stopped"

  odoo:
    build: "."
    image: "plasticos-odoo:19"
    depends_on:
      - "db"
      - "neo4j"
    ports:
      - "8069:8069"
    environment:
      HOST: "db"
      USER: "${POSTGRES_USER}"
      PASSWORD: "${POSTGRES_PASSWORD}"
      DATABASE: "${POSTGRES_DB}"
      NEO4J_URI: "${NEO4J_URI}"
      NEO4J_USER: "${NEO4J_USER}"
      NEO4J_PASSWORD: "${NEO4J_PASSWORD}"
      OPENAI_API_KEY: "${OPENAI_API_KEY}"
    volumes:
      - "./plasticos_*:/mnt/extra-addons"
      - "odoo-web-data:/var/lib/odoo"
      - "odoo-config:/etc/odoo"
    restart: "unless-stopped"

  neo4j:
    image: "neo4j:5.15-community"
    ports:
      - "7474:7474"
      - "7687:7687"
    environment:
      NEO4J_AUTH: "neo4j/${NEO4J_PASSWORD}"
      NEO4J_PLUGINS: '["apoc", "graph-data-science"]'
    volumes:
      - "neo4j-data:/data"
      - "neo4j-logs:/logs"
    restart: "unless-stopped"

# ==============================================================================
# Security Guidelines
# ==============================================================================
security:
  secret_management:
    - "Store secrets in .env (never commit)"
    - "Use environment variables (not hardcoded)"
    - "Rotate passwords every 90 days"
    - "Use strong passwords (16+ characters, mixed case, symbols)"
  
  access_control:
    - "Restrict database access to Odoo service only"
    - "Use firewall rules to limit Neo4j access"
    - "Enable SSL/TLS for production"
    - "Require MFA for admin accounts"
  
  audit_logging:
    - "Enable Odoo audit log"
    - "Log all database changes"
    - "Monitor failed login attempts"
    - "Alert on suspicious activity"

# ==============================================================================
# Troubleshooting Reference
# ==============================================================================
troubleshooting:
  connection_errors:
    neo4j_connection_failed:
      check:
        - "Verify NEO4J_URI format (bolt://host:port)"
        - "Verify NEO4J_PASSWORD (min 8 chars)"
        - "Check Neo4j container running: docker ps"
        - "Wait 60 seconds for Neo4j startup"
      fix:
        - "./scripts/setup_neo4j.sh --check"
        - "./scripts/setup_neo4j.sh --test"
    
    database_connection_failed:
      check:
        - "Verify POSTGRES_PASSWORD set"
        - "Check database container running: docker ps"
        - "Verify ODOO_DB_HOST correct"
      fix:
        - "docker compose logs db"
        - "Restart database: docker compose restart db"
  
  api_errors:
    openai_rate_limit:
      behavior: "Web leads marked 'COLD' for manual review"
      fix: "Implement exponential backoff (already in code)"
    
    openai_invalid_key:
      behavior: "Web leads marked 'COLD' for manual review"
      fix: "Verify OPENAI_API_KEY starts with 'sk-'"
