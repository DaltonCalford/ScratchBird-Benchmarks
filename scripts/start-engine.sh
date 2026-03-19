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

is_port_in_use() {
    local candidate="$1"
    ss -ltn | awk '{print $4}' | grep -Eq "(:|\\])${candidate}\$"
}

resolve_host_port() {
    local default_port="$1"
    local requested_port="${2:-}"
    local engine="${3:-engine}"
    local candidate
    local attempts=0
    local max_attempts=20

    if [ -n "$requested_port" ]; then
        candidate="$requested_port"
    else
        candidate="$default_port"
    fi

    candidate="${candidate//[^0-9]/}"
    if [ -z "$candidate" ]; then
        echo "$default_port"
        return
    fi

    while [ "$attempts" -lt "$max_attempts" ]; do
        if ! is_port_in_use "$candidate"; then
            echo "$candidate"
            return
        fi

        log_warn "$engine host port $candidate is occupied; trying next port" >&2
        candidate=$((candidate + 1))
        attempts=$((attempts + 1))
    done

    echo "$default_port"
}

show_help() {
    cat << EOF
Start a Single Database Engine for Benchmarks

Usage: $0 <ENGINE> [COMMAND]

Engines:
  firebird    FirebirdSQL 5.0.1 (port 3050)
  mysql       MySQL 8.4 (port 3306)
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
    local container_name
    for container_name in sb-benchmark-firebird sb-benchmark-mysql sb-benchmark-postgresql; do
        if docker ps | grep -q "$container_name"; then
            log_info "Stopping $container_name for isolation..."
            docker stop "$container_name" &> /dev/null || true
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

write_engine_port_file() {
    local engine="$1"
    local port_value="$2"
    local port_file="$PROJECT_DIR/.benchmark-engine-ports/${engine}.env"

    mkdir -p "$PROJECT_DIR/.benchmark-engine-ports"
    printf 'BENCHMARK_%s_PORT=%s\n' "$(printf "%s" "$engine" | tr '[:lower:]' '[:upper:]')" "$port_value" > "$port_file"
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
    local results_dir="${BENCHMARK_RESULTS_DIR:-$PROJECT_DIR/results}"
    local port
    
    log_section "Starting $engine"
    
    # Create and expose a writable results directory for in-container health checks.
    mkdir -p "$results_dir"
    chmod a+rwX "$results_dir"
    rm -f \
        "$results_dir/firebird-version.json" \
        "$results_dir/mysql-version.json" \
        "$results_dir/postgresql-version.json"
    
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
            port=$(resolve_host_port "${BENCHMARK_FIREBIRD_PORT:-3050}" "$BENCHMARK_FIREBIRD_PORT" "firebird")
            write_engine_port_file "firebird" "$port"
            docker run -d \
                --name "$container" \
                --network benchmark-net \
                -p "$port:3050" \
                -e FIREBIRD_DATABASE=benchmark.fdb \
                -e FIREBIRD_USER=benchmark \
                -e FIREBIRD_PASSWORD=benchmark \
                -v "$results_dir:/benchmark-results" \
                --memory="2g" \
                --cpus="2" \
                sb-benchmark-firebird:latest
            log_success "Firebird started on host port $port (container 3050)"
            ;;
        mysql)
            port=$(resolve_host_port "${BENCHMARK_MYSQL_PORT:-3306}" "$BENCHMARK_MYSQL_PORT" "mysql")
            write_engine_port_file "mysql" "$port"
            docker run -d \
                --name "$container" \
                --network benchmark-net \
                -p "$port:3306" \
                -e MYSQL_ROOT_PASSWORD=rootpassword \
                -e MYSQL_DATABASE=benchmark \
                -e MYSQL_USER=benchmark \
                -e MYSQL_PASSWORD=benchmark \
                -v "$results_dir:/benchmark-results" \
                --memory="2g" \
                --cpus="2" \
                sb-benchmark-mysql:latest
            log_success "MySQL started on host port $port (container 3306)"
            ;;
        postgresql)
            port=$(resolve_host_port "${BENCHMARK_POSTGRESQL_PORT:-5432}" "$BENCHMARK_POSTGRESQL_PORT" "postgresql")
            write_engine_port_file "postgresql" "$port"
            docker run -d \
                --name "$container" \
                --network benchmark-net \
                -p "$port:5432" \
                -e POSTGRES_USER=benchmark \
                -e POSTGRES_PASSWORD=benchmark \
                -e POSTGRES_DB=benchmark \
                -v "$results_dir:/benchmark-results" \
                --memory="2g" \
                --cpus="2" \
                sb-benchmark-postgresql:latest
            log_success "PostgreSQL started on host port $port (container 5432)"
            ;;
    esac

    case "$engine" in
        firebird)
            export BENCHMARK_FIREBIRD_PORT="$port"
            ;;
        mysql)
            export BENCHMARK_MYSQL_PORT="$port"
            ;;
        postgresql)
            export BENCHMARK_POSTGRESQL_PORT="$port"
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

get_engine_host_port() {
    case "$1" in
        firebird) echo "${BENCHMARK_FIREBIRD_PORT:-3050}" ;;
        mysql) echo "${BENCHMARK_MYSQL_PORT:-3306}" ;;
        postgresql) echo "${BENCHMARK_POSTGRESQL_PORT:-5432}" ;;
    esac
}

show_engine_connect() {
    local engine="$1"
    
    log_section "Connection Information"
    
    case "$engine" in
        firebird)
            cat << EOF
Firebird 5.0.1:
  Host:     localhost:$(get_engine_host_port firebird)
  Database: /firebird/data/benchmark.fdb
  User:     benchmark
  Password: benchmark
  
  Command:  isql-fb -u benchmark -p benchmark localhost:/firebird/data/benchmark.fdb
  
  Environment for tests:
    export FB_HOST=localhost
    export FB_PORT=$(get_engine_host_port firebird)
    export FB_DATABASE=/firebird/data/benchmark.fdb
    export FB_USER=benchmark
    export FB_PASSWORD=benchmark
EOF
            ;;
        mysql)
            cat << EOF
MySQL 8.4:
  Host:     localhost:$(get_engine_host_port mysql)
  Database: benchmark
  User:     benchmark
  Password: benchmark
  
  Command:  mysql -u benchmark -pbenchmark -h 127.0.0.1 benchmark
  
  Environment for tests:
    export MYSQL_HOST=localhost
    export MYSQL_PORT=$(get_engine_host_port mysql)
    export MYSQL_DATABASE=benchmark
    export MYSQL_USER=benchmark
    export MYSQL_PASSWORD=benchmark
EOF
            ;;
        postgresql)
            cat << EOF
PostgreSQL 16:
  Host:     localhost:$(get_engine_host_port postgresql)
  Database: benchmark
  User:     benchmark
  Password: benchmark
  
  Command:  psql -U benchmark -h 127.0.0.1 -d benchmark
  
  Environment for tests:
    export PGHOST=localhost
    export PGPORT=$(get_engine_host_port postgresql)
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
