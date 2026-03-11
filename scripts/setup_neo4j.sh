#!/usr/bin/env bash
# ==============================================================================
# PlasticOS Neo4j Setup Script
# ==============================================================================
# Automates Neo4j setup for the plasticos_buyer_match_engine graph matching.
#
# Usage:
#   ./scripts/setup_neo4j.sh              # Interactive setup
#   ./scripts/setup_neo4j.sh --check      # Check Neo4j status only
#   ./scripts/setup_neo4j.sh --init-schema # Initialize graph schema in Odoo
#
# Prerequisites:
#   - Docker and Docker Compose installed
#   - .env file with NEO4J_PASSWORD set (or script will prompt)
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
COMPOSE_FILE="$PROJECT_ROOT/docker-compose.prod.yml"
ENV_FILE="$PROJECT_ROOT/.env"
COMPOSE_PROJECT="plasticos_prod"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[OK]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# ==============================================================================
# Check prerequisites
# ==============================================================================
check_prerequisites() {
    log_info "Checking prerequisites..."

    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed. Please install Docker first."
        exit 1
    fi

    if ! docker compose version &> /dev/null; then
        log_error "Docker Compose is not available. Please install Docker Compose."
        exit 1
    fi

    if [[ ! -f "$COMPOSE_FILE" ]]; then
        log_error "docker-compose.prod.yml not found at $COMPOSE_FILE"
        exit 1
    fi

    log_success "Prerequisites OK"
}

# ==============================================================================
# Load or prompt for Neo4j credentials
# ==============================================================================
load_env() {
    if [[ -f "$ENV_FILE" ]]; then
        log_info "Loading environment from .env..."
        set -a
        # shellcheck source=/dev/null
        source "$ENV_FILE"
        set +a
    fi

    # Check if Neo4j password is set
    if [[ -z "${NEO4J_PASSWORD:-}" ]]; then
        log_warn "NEO4J_PASSWORD not set in .env"
        echo ""
        read -sp "Enter Neo4j password (min 8 characters): " NEO4J_PASSWORD
        echo ""

        if [[ ${#NEO4J_PASSWORD} -lt 8 ]]; then
            log_error "Password must be at least 8 characters"
            exit 1
        fi

        # Offer to save to .env
        echo ""
        read -p "Save password to .env? (y/n): " save_choice
        if [[ "$save_choice" =~ ^[Yy]$ ]]; then
            echo "" >> "$ENV_FILE"
            echo "# Neo4j credentials (added by setup_neo4j.sh)" >> "$ENV_FILE"
            echo "NEO4J_USER=neo4j" >> "$ENV_FILE"
            echo "NEO4J_PASSWORD=$NEO4J_PASSWORD" >> "$ENV_FILE"
            echo "NEO4J_URI=bolt://neo4j:7687" >> "$ENV_FILE"
            log_success "Credentials saved to .env"
        fi
    fi

    export NEO4J_USER="${NEO4J_USER:-neo4j}"
    export NEO4J_PASSWORD
    export NEO4J_URI="${NEO4J_URI:-bolt://neo4j:7687}"
}

# ==============================================================================
# Start Neo4j container
# ==============================================================================
start_neo4j() {
    log_info "Starting Neo4j container..."

    cd "$PROJECT_ROOT"
    docker compose -p "$COMPOSE_PROJECT" -f docker-compose.prod.yml up -d neo4j

    log_info "Waiting for Neo4j to be ready (this may take 30-60 seconds)..."

    local max_attempts=30
    local attempt=1

    while [[ $attempt -le $max_attempts ]]; do
        if docker compose -p "$COMPOSE_PROJECT" -f docker-compose.prod.yml exec -T neo4j wget -q --spider http://localhost:7474 2>/dev/null; then
            log_success "Neo4j is ready!"
            return 0
        fi

        echo -n "."
        sleep 2
        ((attempt++))
    done

    echo ""
    log_error "Neo4j failed to start within expected time"
    log_info "Check logs with: docker compose -f docker-compose.prod.yml logs neo4j"
    exit 1
}

# ==============================================================================
# Check Neo4j status
# ==============================================================================
check_neo4j_status() {
    log_info "Checking Neo4j status..."

    cd "$PROJECT_ROOT"

    # Check if container is running (look for "Up" in status)
    if ! docker compose -p "$COMPOSE_PROJECT" -f docker-compose.prod.yml ps neo4j 2>/dev/null | grep -qE "(Up|running)"; then
        log_warn "Neo4j container is not running"
        return 1
    fi

    # Check if Neo4j is responding
    if docker compose -p "$COMPOSE_PROJECT" -f docker-compose.prod.yml exec -T neo4j wget -q --spider http://localhost:7474 2>/dev/null; then
        log_success "Neo4j is running and healthy"

        # Show connection info
        echo ""
        log_info "Connection details:"
        echo "  Browser UI: http://localhost:7474"
        echo "  Bolt URI:   bolt://localhost:7687 (external)"
        echo "  Bolt URI:   bolt://neo4j:7687 (from Docker network)"
        echo "  Username:   ${NEO4J_USER:-neo4j}"
        return 0
    else
        log_warn "Neo4j container is running but not responding"
        return 1
    fi
}

# ==============================================================================
# Initialize Odoo graph schema
# ==============================================================================
init_odoo_schema() {
    log_info "Initializing graph schema in Odoo..."

    cd "$PROJECT_ROOT"

    # Check if Odoo container is running
    if ! docker compose -p "$COMPOSE_PROJECT" -f docker-compose.prod.yml ps odoo 2>/dev/null | grep -q "running"; then
        log_warn "Odoo container is not running. Start it first:"
        echo "  docker compose -p $COMPOSE_PROJECT -f docker-compose.prod.yml up -d"
        exit 1
    fi

    # Run schema initialization via Odoo shell
    log_info "Running schema initialization..."

    docker compose -p "$COMPOSE_PROJECT" -f docker-compose.prod.yml exec -T odoo \
        odoo shell -d "${POSTGRES_DB:-odoo}" --no-http <<'PYTHON'
try:
    graph_service = env["plasticos.graph.service"]
    print("Initializing Neo4j schema...")
    graph_service.initialize_schema()
    print("Schema initialized.")

    print("Syncing facility nodes...")
    graph_service.sync_facility_nodes(trigger="setup_script")

    print("Syncing material nodes...")
    graph_service.sync_material_nodes(trigger="setup_script")

    env.cr.commit()
    print("Graph sync complete!")
except Exception as e:
    print(f"Error: {e}")
    raise
PYTHON

    if [[ $? -eq 0 ]]; then
        log_success "Graph schema initialized and data synced"
    else
        log_error "Schema initialization failed"
        exit 1
    fi
}

# ==============================================================================
# Test Neo4j connection from Odoo
# ==============================================================================
test_connection() {
    log_info "Testing Neo4j connection from Odoo..."

    cd "$PROJECT_ROOT"

    docker compose -p "$COMPOSE_PROJECT" -f docker-compose.prod.yml exec -T odoo \
        odoo shell -d "${POSTGRES_DB:-odoo}" --no-http <<'PYTHON'
try:
    graph_service = env["plasticos.graph.service"]
    cfg = graph_service._get_config()
    print(f"Neo4j URI: {cfg.get('uri', 'NOT SET')}")
    print(f"Neo4j User: {cfg.get('user', 'NOT SET')}")
    print(f"Password configured: {'Yes' if cfg.get('password') else 'No'}")

    # Try to get a connection
    pool = graph_service._get_driver()
    if pool and pool.driver:
        print("Connection pool: OK")
        if pool.health_check():
            print("Health check: PASSED")
        else:
            print("Health check: FAILED")
    else:
        print("Connection pool: NOT AVAILABLE")
except Exception as e:
    print(f"Connection test failed: {e}")
PYTHON
}

# ==============================================================================
# Show usage
# ==============================================================================
show_usage() {
    echo "PlasticOS Neo4j Setup Script"
    echo ""
    echo "Usage: $0 [option]"
    echo ""
    echo "Options:"
    echo "  (none)        Full setup: start Neo4j, wait for ready, show status"
    echo "  --check       Check Neo4j status only"
    echo "  --init-schema Initialize graph schema in Odoo (requires Odoo running)"
    echo "  --test        Test Neo4j connection from Odoo"
    echo "  --help        Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                    # Start Neo4j and verify it's running"
    echo "  $0 --check            # Check if Neo4j is healthy"
    echo "  $0 --init-schema      # Sync Odoo data to Neo4j graph"
}

# ==============================================================================
# Main
# ==============================================================================
main() {
    case "${1:-}" in
        --help|-h)
            show_usage
            exit 0
            ;;
        --check)
            load_env
            check_neo4j_status
            ;;
        --init-schema)
            load_env
            init_odoo_schema
            ;;
        --test)
            load_env
            test_connection
            ;;
        "")
            echo "=============================================="
            echo "  PlasticOS Neo4j Setup"
            echo "=============================================="
            echo ""
            check_prerequisites
            load_env
            start_neo4j
            echo ""
            check_neo4j_status
            echo ""
            log_info "Next steps:"
            echo "  1. Start Odoo: docker compose -p $COMPOSE_PROJECT -f docker-compose.prod.yml up -d"
            echo "  2. Initialize schema: $0 --init-schema"
            echo "  3. Test matching: Use 'Match To Buyers' button on an intake"
            ;;
        *)
            log_error "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
}

main "$@"
