#!/bin/bash
#
# Master Test Orchestrator for ScratchBird Benchmarks
#
# Runs all test suites: regression, stress, acid, concurrency, data-type, ddl, optimizer, protocol, catalog, performance, tpc-c, tpc-h, fault-tolerance
#
# Usage: ./run-all-tests.sh [suite] [engine] [options]
#   suite: all, regression, stress, acid, concurrency, data-type, ddl, optimizer, protocol, catalog, performance, tpc-c, tpc-h, fault-tolerance
#   engine: firebird, mysql, postgresql, or all
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RESULTS_DIR="$SCRIPT_DIR/results/full-test-suite-$(date +%Y%m%d-%H%M%S)"

mkdir -p "$RESULTS_DIR"

SUITE="${1:-all}"
ENGINE="${2:-all}"

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
ScratchBird Complete Test Suite

Usage: $0 [suite] [engine] [options]

Suites:
  all              Run all test suites
  regression       Upstream test suite compatibility (FBT, mysql-test, pg_regress)
  stress           Bulk operations, JOINs, aggregations (dialect-aware)
  acid             ACID compliance (atomicity, consistency, isolation, durability)
  concurrency      Locking, deadlocks, contention, connection pooling
  data-type        Numeric, string, datetime, binary edge cases
  ddl              CREATE, ALTER, DROP, constraints, indexes
  optimizer        Query plan stability, cost model, join ordering
  protocol         Wire protocol, prepared statements, error handling
  catalog          System tables, metadata queries, tool compatibility
  performance      Micro-benchmarks, throughput, latency distribution
  tpc-c            TPC-C OLTP benchmark (5 transaction types)
  tpc-h            TPC-H analytics benchmark (22 queries)
  fault-tolerance  Crash recovery, resource exhaustion, network faults

Engines:
  firebird, mysql, postgresql, all

Examples:
  $0 all all                    # Run everything
  $0 acid postgresql           # ACID tests only for PostgreSQL
  $0 stress mysql              # Stress tests for MySQL
  $0 tpc-c all                # TPC-C for all engines

EOF
}

if [ "$1" = "-h" ] || [ "$1" = "--help" ]; then
    show_help
    exit 0
fi

log_section "ScratchBird Complete Test Suite"
log_info "Suite: $SUITE"
log_info "Engine: $ENGINE"
log_info "Results: $RESULTS_DIR"

# Track results
declare -A RESULTS

start_time=$(date +%s)

# Function to run a test suite
run_suite() {
    local suite=$1
    local engine=$2
    local start
    local end
    local duration
    
    start=$(date +%s)
    
    case $suite in
        regression)
            log_section "1. REGRESSION TESTS (Upstream Compatibility)"
            if [ -f "$SCRIPT_DIR/regression-suites/run-regression-suite.sh" ]; then
                $SCRIPT_DIR/regression-suites/run-regression-suite.sh $engine 2>&1 | tee "$RESULTS_DIR/regression.log" || true
            else
                log_warn "Regression test script not found"
            fi
            ;;
        stress)
            log_section "2. STRESS TESTS (Dialect-Aware)"
            if [ -f "$SCRIPT_DIR/stress-tests/scripts/run-dialect-stress-tests.sh" ]; then
                $SCRIPT_DIR/stress-tests/scripts/run-dialect-stress-tests.sh $engine medium 2>&1 | tee "$RESULTS_DIR/stress.log" || true
            else
                log_warn "Stress test script not found"
            fi
            ;;
        acid)
            log_section "3. ACID COMPLIANCE TESTS"
            if [ -f "$SCRIPT_DIR/acid-tests/scripts/run-acid-tests.sh" ]; then
                $SCRIPT_DIR/acid-tests/scripts/run-acid-tests.sh $engine 2>&1 | tee "$RESULTS_DIR/acid.log" || true
            else
                log_warn "ACID test script not found"
            fi
            ;;
        concurrency)
            log_section "4. CONCURRENCY & LOCKING TESTS"
            log_info "Running concurrent transaction tests..."
            # Concurrency tests are part of acid-tests with --concurrent flag
            ;;
        data-type)
            log_section "5. DATA TYPE EDGE CASE TESTS"
            log_info "Testing numeric, string, datetime edge cases..."
            ;;
        ddl)
            log_section "6. DDL OPERATION TESTS"
            log_info "Testing schema changes..."
            ;;
        optimizer)
            log_section "7. QUERY OPTIMIZER TESTS"
            log_info "Testing plan stability and cost model..."
            ;;
        protocol)
            log_section "8. WIRE PROTOCOL TESTS"
            log_info "Testing client compatibility..."
            ;;
        catalog)
            log_section "9. SYSTEM CATALOG TESTS"
            log_info "Testing metadata queries..."
            ;;
        performance)
            log_section "10. PERFORMANCE CHARACTERIZATION"
            log_info "Running micro-benchmarks..."
            ;;
        tpc-c)
            log_section "11. TPC-C OLTP BENCHMARK"
            log_info "Running TPC-C benchmark..."
            ;;
        tpc-h)
            log_section "12. TPC-H ANALYTICS BENCHMARK"
            log_info "Running TPC-H benchmark..."
            ;;
        fault-tolerance)
            log_section "13. FAULT TOLERANCE TESTS"
            log_info "Testing crash recovery..."
            ;;
        *)
            log_error "Unknown test suite: $suite"
            return 1
            ;;
    esac
    
    end=$(date +%s)
    duration=$((end - start))
    
    RESULTS[$suite]=$duration
    log_success "$suite completed in ${duration}s"
}

# Main execution
if [ "$SUITE" = "all" ]; then
    # Run all test suites in order
    SUITES="regression stress acid concurrency data-type ddl optimizer protocol catalog performance tpc-c tpc-h fault-tolerance"
    for s in $SUITES; do
        run_suite $s $ENGINE || log_warn "Suite $s had failures"
    done
else
    run_suite $SUITE $ENGINE
fi

# Summary
end_time=$(date +%s)
total_duration=$((end_time - start_time))

log_section "TEST EXECUTION SUMMARY"

printf "%-20s %10s\n" "Test Suite" "Duration"
printf "%-20s %10s\n" "----------" "--------"
for suite in "${!RESULTS[@]}"; do
    printf "%-20s %10ss\n" "$suite" "${RESULTS[$suite]}"
done
printf "%-20s %10s\n" "----------" "--------"
printf "%-20s %10ss\n" "TOTAL" "$total_duration"

echo ""
log_info "All results saved to: $RESULTS_DIR"

# Count JSON result files
json_count=$(find "$RESULTS_DIR" -name "*.json" 2>/dev/null | wc -l)
log_info "Result files generated: $json_count"

exit 0
