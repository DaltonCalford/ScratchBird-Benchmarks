#!/bin/bash
#
# Run Benchmarks Against a Single Database Engine
#
# This script runs benchmarks against ONE engine at a time,
# ensuring isolation and accurate performance measurements.
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
Run Benchmarks Against a Single Database Engine

Usage: $0 <ENGINE> [SUITE] [OPTIONS]

Engines:
  firebird    Run benchmarks against FirebirdSQL
  mysql       Run benchmarks against MySQL
  postgresql  Run benchmarks against PostgreSQL

Suites:
  all               Run all test suites (default)
  regression        Run upstream regression tests (FBT, mysql-test, pg_regress)
  stress            Stress tests (bulk operations, JOINs)
  acid              ACID compliance tests
  concurrency       Concurrency and locking tests
  data-type         Data type edge case tests
  ddl               DDL operation tests
  optimizer         Query optimizer tests
  protocol          Wire protocol tests
  catalog           System catalog tests
  performance       Performance micro-benchmarks
  tpc-c             TPC-C OLTP benchmark
  tpc-h             TPC-H analytical queries
  fault-tolerance   Fault tolerance tests
  engine-differential   Engine-specific advantage tests

Options:
  --report          Generate text report after tests
  --tags TAGS       Add tags to report (comma-separated)
  --notes NOTES     Add notes to report
  --output DIR      Output directory for results (default: results/)
  -h, --help        Show this help message

Examples:
  $0 firebird all                    # Run all tests on Firebird
  $0 mysql stress                    # Run stress tests on MySQL
  $0 postgresql acid --report        # Run ACID tests with report
  $0 firebird regression             # Run FBT regression suite
  $0 mysql tpc-c --tags production   # Run TPC-C with tags

Prerequisites:
  - Start engine first: ./start-engine.sh <engine> start
  - Only ONE engine should be running during benchmarks

Output:
  Results are saved to: results/<suite>-<engine>-<timestamp>.json
  Reports are saved to: results/reports/ (if --report is used)

EOF
}

detect_running_engine() {
    # Check which engine is currently running
    local engines=("firebird" "mysql" "postgresql")
    local running=""
    local count=0
    
    for engine in "${engines[@]}"; do
        if docker ps | grep -q "sb-benchmark-$engine"; then
            running="$engine"
            ((count++))
        fi
    done
    
    if [ "$count" -eq 0 ]; then
        echo "none"
    elif [ "$count" -eq 1 ]; then
        echo "$running"
    else
        echo "multiple"
    fi
}

verify_engine_running() {
    local expected_engine="$1"
    local running_engine
    
    running_engine=$(detect_running_engine)
    
    case "$running_engine" in
        none)
            log_error "No engine is running"
            echo "Start an engine first: ./start-engine.sh $expected_engine start"
            exit 1
            ;;
        multiple)
            log_warn "Multiple engines detected! Stopping others for isolation..."
            for engine in firebird mysql postgresql; do
                if [ "$engine" != "$expected_engine" ]; then
                    docker stop "sb-benchmark-$engine" 2>/dev/null || true
                fi
            done
            ;;
        *)
            if [ "$running_engine" != "$expected_engine" ]; then
                log_error "Wrong engine running: $running_engine (expected: $expected_engine)"
                echo "Stop current engine: ./start-engine.sh $running_engine stop"
                echo "Start correct engine: ./start-engine.sh $expected_engine start"
                exit 1
            fi
            ;;
    esac
}

collect_system_info() {
    local output_dir="$1"
    
    log_section "Collecting System Information"
    
    if command -v python3 &> /dev/null; then
        python3 "$PROJECT_DIR/system-info/collectors/system_info.py" \
            --output "$output_dir/system-info.json" \
            --quiet 2>/dev/null || log_warn "System info collection failed"
        
        if [ -f "$output_dir/system-info.json" ]; then
            log_success "System info collected"
        fi
    else
        log_warn "Python3 not available, skipping system info"
    fi
}

run_regression_tests() {
    local engine="$1"
    local output_dir="$2"
    
    log_section "Running Regression Tests"
    
    case "$engine" in
        firebird)
            log_info "Running Firebird FBT tests..."
            if [ -d "$PROJECT_DIR/regression-suites" ]; then
                # Run FBT runner if available
                if [ -f "$PROJECT_DIR/regression-suites/runners/fbt_runner.py" ]; then
                    python3 "$PROJECT_DIR/regression-suites/runners/fbt_runner.py" \
                        --fbt-path /fbt-repository \
                        --suite all \
                        --target original \
                        --output-dir "$output_dir" || log_warn "FBT tests had failures"
                else
                    log_warn "FBT runner not found, skipping"
                fi
            fi
            ;;
        mysql)
            log_info "Running MySQL mysql-test..."
            log_warn "MySQL regression tests not yet implemented"
            ;;
        postgresql)
            log_info "Running PostgreSQL pg_regress tests..."
            log_warn "PostgreSQL regression tests not yet implemented"
            ;;
    esac
}

run_stress_tests() {
    local engine="$1"
    local output_dir="$2"
    
    log_section "Running Stress Tests"
    
    if [ -f "$PROJECT_DIR/stress-tests/runners/dialect_stress_runner.py" ]; then
        python3 "$PROJECT_DIR/stress-tests/runners/dialect_stress_runner.py" \
            --engine "$engine" \
            --host localhost \
            --port $(get_engine_port "$engine") \
            --database $(get_engine_database "$engine") \
            --user benchmark \
            --password benchmark \
            --scale medium \
            --output-dir "$output_dir" || log_warn "Stress tests had failures"
    else
        log_warn "Stress test runner not found"
    fi
}

run_acid_tests() {
    local engine="$1"
    local output_dir="$2"
    
    log_section "Running ACID Tests"
    
    if [ -f "$PROJECT_DIR/acid-tests/runners/acid_test_runner.py" ]; then
        python3 "$PROJECT_DIR/acid-tests/runners/acid_test_runner.py" \
            --engine "$engine" \
            --host localhost \
            --port $(get_engine_port "$engine") \
            --database $(get_engine_database "$engine") \
            --user benchmark \
            --password benchmark \
            --output-dir "$output_dir" || log_warn "ACID tests had failures"
    else
        log_warn "ACID test runner not found"
    fi
}

run_performance_tests() {
    local engine="$1"
    local output_dir="$2"
    
    log_section "Running Performance Tests"
    
    if [ -f "$PROJECT_DIR/performance-tests/runners/performance_test_runner.py" ]; then
        python3 "$PROJECT_DIR/performance-tests/runners/performance_test_runner.py" \
            --engine "$engine" \
            --host localhost \
            --port $(get_engine_port "$engine") \
            --database $(get_engine_database "$engine") \
            --user benchmark \
            --password benchmark \
            --output-dir "$output_dir" || log_warn "Performance tests had failures"
    else
        log_warn "Performance test runner not found"
    fi
}

run_tpc_c() {
    local engine="$1"
    local output_dir="$2"
    
    log_section "Running TPC-C Benchmark"
    
    if [ -f "$PROJECT_DIR/tpc-c/runners/tpc_c_runner.py" ]; then
        python3 "$PROJECT_DIR/tpc-c/runners/tpc_c_runner.py" \
            --engine "$engine" \
            --host localhost \
            --port $(get_engine_port "$engine") \
            --database $(get_engine_database "$engine") \
            --user benchmark \
            --password benchmark \
            --warehouses 10 \
            --duration 300 \
            --output-dir "$output_dir" || log_warn "TPC-C had failures"
    else
        log_warn "TPC-C runner not found"
    fi
}

run_tpc_h() {
    local engine="$1"
    local output_dir="$2"
    
    log_section "Running TPC-H Benchmark"
    
    if [ -f "$PROJECT_DIR/tpc-h/runners/tpc_h_runner.py" ]; then
        python3 "$PROJECT_DIR/tpc-h/runners/tpc_h_runner.py" \
            --engine "$engine" \
            --host localhost \
            --port $(get_engine_port "$engine") \
            --database $(get_engine_database "$engine") \
            --user benchmark \
            --password benchmark \
            --scale 1 \
            --output-dir "$output_dir" || log_warn "TPC-H had failures"
    else
        log_warn "TPC-H runner not found"
    fi
}

run_engine_differential() {
    local engine="$1"
    local output_dir="$2"
    
    log_section "Running Engine Differential Tests"
    
    if [ -f "$PROJECT_DIR/engine-differential-tests/runners/differential_test_runner.py" ]; then
        python3 "$PROJECT_DIR/engine-differential-tests/runners/differential_test_runner.py" \
            --engine "$engine" \
            --host localhost \
            --port $(get_engine_port "$engine") \
            --database $(get_engine_database "$engine") \
            --user benchmark \
            --password benchmark \
            --output-dir "$output_dir" || log_warn "Differential tests had failures"
    else
        log_warn "Differential test runner not found"
    fi
}

get_engine_port() {
    case "$1" in
        firebird) echo "3050" ;;
        mysql) echo "3306" ;;
        postgresql) echo "5432" ;;
    esac
}

get_engine_database() {
    case "$1" in
        firebird) echo "benchmark.fdb" ;;
        mysql) echo "benchmark" ;;
        postgresql) echo "benchmark" ;;
    esac
}

generate_report() {
    local output_dir="$1"
    local tags="$2"
    local notes="$3"
    
    log_section "Generating Text Report"
    
    if [ -f "$PROJECT_DIR/system-info/submit/result_formatter.py" ]; then
        local format_args="--compare $output_dir/*.json --output $output_dir/reports"
        
        if [ -f "$output_dir/system-info.json" ]; then
            format_args="$format_args --system-info $output_dir/system-info.json"
        fi
        
        if [ -n "$tags" ]; then
            format_args="$format_args --tags $tags"
        fi
        
        if [ -n "$notes" ]; then
            format_args="$format_args --notes '$notes'"
        fi
        
        python3 "$PROJECT_DIR/system-info/submit/result_formatter.py" $format_args || log_warn "Report generation failed"
        
        if [ -d "$output_dir/reports" ]; then
            log_success "Reports saved to $output_dir/reports/"
            ls -la "$output_dir/reports/"
        fi
    else
        log_warn "Report formatter not found"
    fi
}

show_summary() {
    local engine="$1"
    local output_dir="$2"
    
    log_section "Benchmark Complete"
    
    echo -e "${CYAN}Results saved to:${NC} $output_dir"
    echo ""
    
    if [ -d "$output_dir" ]; then
        echo -e "${CYAN}Result files:${NC}"
        ls -la "$output_dir"/*.json 2>/dev/null || echo "  No JSON results found"
        
        if [ -d "$output_dir/reports" ]; then
            echo ""
            echo -e "${CYAN}Reports:${NC}"
            ls -la "$output_dir/reports/"/*.txt 2>/dev/null || echo "  No reports found"
        fi
    fi
    
    echo ""
    log_info "To share results:"
    echo "  1. View report: cat $output_dir/reports/*.txt"
    echo "  2. Copy contents to GitHub issue:"
    echo "     https://github.com/DaltonCalford/ScratchBird-Benchmarks/issues"
}

# Main
ENGINE="${1:-}"
SUITE="${2:-all}"

# Parse options
GENERATE_REPORT=false
TAGS=""
NOTES=""
OUTPUT_DIR=""

shift 2 || true

while [[ $# -gt 0 ]]; do
    case "$1" in
        --report)
            GENERATE_REPORT=true
            shift
            ;;
        --tags)
            TAGS="$2"
            shift 2
            ;;
        --notes)
            NOTES="$2"
            shift 2
            ;;
        --output)
            OUTPUT_DIR="$2"
            shift 2
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Validate required arguments
if [ -z "$ENGINE" ]; then
    log_error "No engine specified"
    show_help
    exit 1
fi

case "$ENGINE" in
    firebird|mysql|postgresql)
        ;;
    --help|-h)
        show_help
        exit 0
        ;;
    *)
        log_error "Unknown engine: $ENGINE"
        echo "Valid engines: firebird, mysql, postgresql"
        exit 1
        ;;
esac

# Set default output directory
if [ -z "$OUTPUT_DIR" ]; then
    OUTPUT_DIR="$PROJECT_DIR/results/${SUITE}-${ENGINE}-$(date +%Y%m%d-%H%M%S)"
fi

mkdir -p "$OUTPUT_DIR"

# Verify isolation
verify_engine_running "$ENGINE"

# Show banner
log_section "ScratchBird Benchmark"
log_info "Engine: $ENGINE"
log_info "Suite:  $SUITE"
log_info "Output: $OUTPUT_DIR"

# Collect system info first
collect_system_info "$OUTPUT_DIR"

# Run tests based on suite
START_TIME=$(date +%s)

case "$SUITE" in
    all)
        run_regression_tests "$ENGINE" "$OUTPUT_DIR"
        run_stress_tests "$ENGINE" "$OUTPUT_DIR"
        run_acid_tests "$ENGINE" "$OUTPUT_DIR"
        run_performance_tests "$ENGINE" "$OUTPUT_DIR"
        run_tpc_c "$ENGINE" "$OUTPUT_DIR"
        run_tpc_h "$ENGINE" "$OUTPUT_DIR"
        run_engine_differential "$ENGINE" "$OUTPUT_DIR"
        ;;
    regression)
        run_regression_tests "$ENGINE" "$OUTPUT_DIR"
        ;;
    stress)
        run_stress_tests "$ENGINE" "$OUTPUT_DIR"
        ;;
    acid)
        run_acid_tests "$ENGINE" "$OUTPUT_DIR"
        ;;
    performance)
        run_performance_tests "$ENGINE" "$OUTPUT_DIR"
        ;;
    tpc-c)
        run_tpc_c "$ENGINE" "$OUTPUT_DIR"
        ;;
    tpc-h)
        run_tpc_h "$ENGINE" "$OUTPUT_DIR"
        ;;
    engine-differential)
        run_engine_differential "$ENGINE" "$OUTPUT_DIR"
        ;;
    *)
        log_warn "Suite '$SUITE' not yet implemented, skipping"
        ;;
esac

END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

log_info "Total duration: ${DURATION}s"

# Generate report if requested
if [ "$GENERATE_REPORT" = true ]; then
    generate_report "$OUTPUT_DIR" "$TAGS" "$NOTES"
fi

# Show summary
show_summary "$ENGINE" "$OUTPUT_DIR"
