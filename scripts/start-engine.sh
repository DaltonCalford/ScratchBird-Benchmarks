#!/bin/bash
#
# Start a Single Database Engine for ScratchBird Benchmarks
#
# This script starts ONE engine at a time to ensure benchmarks
# run in isolation without other engines consuming resources.
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[PASS]${NC} $1"; }
log_error() { echo -e "${RED}[FAIL]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_section() { echo -e "\n${CYAN}========================================${NC}"; echo -e "${CYAN}$1${NC}"; echo -e "${CYAN}========================================${NC}\n"; }

show_help() {
    cat << EOF
Start a Single Database Engine for Benchmarks

Usage: $0 <ENGINE> [COMMAND]

Engines:
  firebird    FirebirdSQL 5.0.1 (port 3050)
  mysql       MySQL 9.0.1 (port 3306)
  postgresql  PostgreSQL 16 (port 5432)

Commands:
  start       Start the engine (default)
  stop        Stop the engine
  restart     Restart the engine
  status      Check engine status
  logs        Show engine logs
  build       Build the Docker image
  connect     Show connection info
  clean       Stop and remove container

Examples:
  $0 firebird start       # Start Firebird only
  $0 mysql status         # Check MySQL status
  $0 postgresql stop      # Stop PostgreSQL
  $0 firebird logs        # View Firebird logs
  $0 mysql connect        # Show MySQL connection info

Notes:
  - Only ONE engine should be running during benchmarks
  - Starting an engine will stop any other running engines
  - Use './run-benchmark.sh' to run tests against the active engine

EOF
}

check_docker() {
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed"
        exit 1
    fi
    
    if ! docker info &> /dev/null; then
        log_error "Cannot connect to Docker daemon"
        echo "Run: sudo usermod -aG docker \$USER && newgrp docker"
        echo "Or use sudo with this script"
        exit 1
    fi
}

stop_all_engines() {
    # Stop any other running benchmark engines to ensure isolation
    for container in sb-benchmark-firebird sb-benchmark-mysql sb-benchmark-postgresql; do
        if docker ps | grep -q "$container"; then
            log_info "Stopping $container for isolation..."
            docker stop "$container" &> /dev/null || true
        fi
    done
}

stop_engine() {
    local engine="$1"
    local container="sb-benchmark-$engine"
    
    if docker ps | grep -q "$container"; then
        log_info "Stopping $engine..."
        docker stop "$container" &> /dev/null || true
        log_success "$engine stopped"
    else
        log_warn "$engine is not running"
    fi
}

build_engine() {
    local engine="$1"
    
    log_section "Building $engine Image"
    
    cd "$PROJECT_DIR"
    
    case "$engine" in
        firebird)
            docker build -t sb-benchmark-firebird:latest engines/firebird/
            ;;
        mysql)
            docker build -t sb-benchmark-mysql:latest engines/mysql/
            ;;
        postgresql)
            docker build -t sb-benchmark-postgresql:latest engines/postgresql/
            ;;
    esac
    
    log_success "$engine image built"
}

start_engine() {
    local engine="$1"
    local container="sb-benchmark-$engine"
    
    log_section "Starting $engine"
    
    # Create results directory
    mkdir -p "$PROJECT_DIR/results"
    
    # Stop all other engines first (isolation)
    stop_all_engines
    
    # Check if image exists
    if ! docker images | grep -q "sb-benchmark-$engine"; then
        log_warn "$engine image not found, building..."
        build_engine "$engine"
    fi
    
    # Create network if it doesn't exist
    if ! docker network ls | grep -q benchmark-net; then
        log_info "Creating benchmark network..."
        docker network create benchmark-net
    fi
    
    # Remove existing container if any
    docker rm -f "$container" 2>/dev/null || true
    
    # Start the specific engine
    case "$engine" in
        firebird)
            docker run -d \
                --name "$container" \
                --network benchmark-net \
                -p 3050:3050 \
                -e FIREBIRD_DATABASE=benchmark.fdb \
                -e FIREBIRD_USER=benchmark \
                -e FIREBIRD_PASSWORD=benchmark \
                -v "$PROJECT_DIR/results:/benchmark-results" \
                --memory="2g" \
                --cpus="2" \
                sb-benchmark-firebird:latest
            log_success "Firebird started on port 3050"
            ;;
        mysql)
            docker run -d \
                --name "$container" \
                --network benchmark-net \
                -p 3306:3306 \
                -e MYSQL_ROOT_PASSWORD=rootpassword \
                -e MYSQL_DATABASE=benchmark \
                -e MYSQL_USER=benchmark \
                -e MYSQL_PASSWORD=benchmark \
                -v "$PROJECT_DIR/results:/benchmark-results" \
                --memory="2g" \
                --cpus="2" \
                sb-benchmark-mysql:latest
            log_success "MySQL started on port 3306"
            ;;
        postgresql)
            docker run -d \
                --name "$container" \
                --network benchmark-net \
                -p 5432:5432 \
                -e POSTGRES_USER=benchmark \
                -e POSTGRES_PASSWORD=benchmark \
                -e POSTGRES_DB=benchmark \
                -v "$PROJECT_DIR/results:/benchmark-results" \
                --memory="2g" \
                --cpus="2" \
                sb-benchmark-postgresql:latest
            log_success "PostgreSQL started on port 5432"
            ;;
    esac
    
    log_info "Waiting for $engine to be ready..."
    
    # Wait for health check
    for i in {1..60}; do
        sleep 2
        if docker exec "$container" /usr/local/bin/collect-version.sh &> /dev/null; then
            log_success "$engine is ready!"
            show_engine_status "$engine"
            show_engine_connect "$engine"
            return 0
        fi
        
        if [ $((i % 10)) -eq 0 ]; then
            echo "  Still waiting for $engine... ($i seconds)"
        fi
    done
    
    log_error "$engine failed to start within 2 minutes"
    docker logs "$container" --tail 50
    return 1
}

show_engine_status() {
    local engine="$1"
    local container="sb-benchmark-$engine"
    
    echo ""
    echo -e "${CYAN}Container Status:${NC}"
    docker ps --filter "name=$container" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
    
    echo ""
    echo -e "${CYAN}Version:${NC}"
    if [ -f "$PROJECT_DIR/results/${engine}-version.json" ]; then
        cat "$PROJECT_DIR/results/${engine}-version.json" | grep '"version"' | cut -d'"' -f4 || echo "unknown"
    fi
}

show_engine_connect() {
    local engine="$1"
    
    log_section "Connection Information"
    
    case "$engine" in
        firebird)
            cat << EOF
Firebird 5.0.1:
  Host:     localhost:3050
  Database: benchmark.fdb
  User:     benchmark
  Password: benchmark
  
  Command:  isql-fb -u benchmark -p benchmark localhost:benchmark.fdb
  
  Environment for tests:
    export FB_HOST=localhost
    export FB_PORT=3050
    export FB_DATABASE=benchmark.fdb
    export FB_USER=benchmark
    export FB_PASSWORD=benchmark
EOF
            ;;
        mysql)
            cat << EOF
MySQL 9.0.1:
  Host:     localhost:3306
  Database: benchmark
  User:     benchmark
  Password: benchmark
  
  Command:  mysql -u benchmark -pbenchmark -h 127.0.0.1 benchmark
  
  Environment for tests:
    export MYSQL_HOST=localhost
    export MYSQL_PORT=3306
    export MYSQL_DATABASE=benchmark
    export MYSQL_USER=benchmark
    export MYSQL_PASSWORD=benchmark
EOF
            ;;
        postgresql)
            cat << EOF
PostgreSQL 16:
  Host:     localhost:5432
  Database: benchmark
  User:     benchmark
  Password: benchmark
  
  Command:  psql -U benchmark -h 127.0.0.1 -d benchmark
  
  Environment for tests:
    export PGHOST=localhost
    export PGPORT=5432
    export PGDATABASE=benchmark
    export PGUSER=benchmark
    export PGPASSWORD=benchmark
EOF
            ;;
    esac
}

show_logs() {
    local engine="$1"
    local container="sb-benchmark-$engine"
    
    if ! docker ps -a | grep -q "$container"; then
        log_error "$engine container not found"
        return 1
    fi
    
    log_info "Showing logs for $engine (Ctrl+C to exit)..."
    docker logs -f "$container"
}

clean_engine() {
    local engine="$1"
    local container="sb-benchmark-$engine"
    
    stop_engine "$engine"
    
    if docker ps -a | grep -q "$container"; then
        log_info "Removing $container..."
        docker rm "$container" &> /dev/null || true
        log_success "$container removed"
    fi
}

# Main
ENGINE="${1:-}"
COMMAND="${2:-start}"

if [ -z "$ENGINE" ] || [ "$ENGINE" == "--help" ] || [ "$ENGINE" == "-h" ]; then
    show_help
    exit 0
fi

# Validate engine
case "$ENGINE" in
    firebird|mysql|postgresql)
        ;;
    *)
        log_error "Unknown engine: $ENGINE"
        echo "Valid engines: firebird, mysql, postgresql"
        exit 1
        ;;
esac

# Validate and execute command
check_docker

case "$COMMAND" in
    start|up)
        start_engine "$ENGINE"
        ;;
    stop|down)
        stop_engine "$ENGINE"
        ;;
    restart)
        stop_engine "$ENGINE"
        sleep 2
        start_engine "$ENGINE"
        ;;
    status)
        show_engine_status "$ENGINE"
        ;;
    logs)
        show_logs "$ENGINE"
        ;;
    build)
        build_engine "$ENGINE"
        ;;
    connect)
        show_engine_connect "$ENGINE"
        ;;
    clean|remove|rm)
        clean_engine "$ENGINE"
        ;;
    *)
        log_error "Unknown command: $COMMAND"
        show_help
        exit 1
        ;;
esac
