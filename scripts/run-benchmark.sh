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
SCRATCHBIRD_DRIVER_ROOT_DEFAULT="$(cd "$PROJECT_DIR/.." && pwd)/ScratchBird-driver"
SCRATCHBIRD_DRIVER_PYTHONPATH_DEFAULT="$SCRATCHBIRD_DRIVER_ROOT_DEFAULT/tracks/p3/drivers/python/src"
RUN_BENCHMARK_INVOCATION=("$0" "$@")

load_env_file() {
    local env_file="$PROJECT_DIR/.env"

    if [ -f "$env_file" ]; then
        # shellcheck disable=SC1090
        set -a
        . "$env_file"
        set +a
    fi
}

load_env_file

if [ -d "${SCRATCHBIRD_DRIVER_PYTHONPATH:-$SCRATCHBIRD_DRIVER_PYTHONPATH_DEFAULT}" ]; then
    export PYTHONPATH="${SCRATCHBIRD_DRIVER_PYTHONPATH:-$SCRATCHBIRD_DRIVER_PYTHONPATH_DEFAULT}${PYTHONPATH:+:$PYTHONPATH}"
fi

# Use virtual environment Python if available
if [ -n "$VIRTUAL_ENV" ]; then
    PYTHON="$VIRTUAL_ENV/bin/python3"
elif [ -f "$PROJECT_DIR/.venv/bin/python3" ]; then
    PYTHON="$PROJECT_DIR/.venv/bin/python3"
elif command -v python3 >/dev/null 2>&1; then
    PYTHON="python3"
else
    PYTHON="$PROJECT_DIR/.venv/bin/python3"
fi

resolve_repo_path() {
    local default_path="$1"
    local fallback_path="$2"

    if [ -n "$default_path" ] && [ -d "$default_path" ]; then
        echo "$default_path"
        return
    fi

    if [ -n "$fallback_path" ] && [ -d "$fallback_path" ]; then
        echo "$fallback_path"
        return
    fi

    local relative_to_project
    if [ -n "$default_path" ]; then
        relative_to_project="$(cd "$PROJECT_DIR" && cd "$default_path" 2>/dev/null && pwd)"
        if [ -n "$relative_to_project" ] && [ -d "$relative_to_project" ]; then
            echo "$relative_to_project"
            return
        fi
    fi

    if [ -n "$fallback_path" ]; then
        relative_to_project="$(cd "$PROJECT_DIR" && cd "$fallback_path" 2>/dev/null && pwd)"
        if [ -n "$relative_to_project" ] && [ -d "$relative_to_project" ]; then
            echo "$relative_to_project"
            return
        fi
    fi

    echo "$default_path"
}

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# Default clone locations for local regression test suites.
export FIREBIRD_REPO_PATH="${FIREBIRD_REPO_PATH:-$(resolve_repo_path "../fbt-repository" "../firebird")}"
export MYSQL_REPO_PATH="${MYSQL_REPO_PATH:-$(resolve_repo_path "../mysql-server")}"
export POSTGRESQL_REPO_PATH="${POSTGRESQL_REPO_PATH:-$(resolve_repo_path "../postgresql")}"

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[PASS]${NC} $1"; }
log_error() { echo -e "${RED}[FAIL]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_section() { echo -e "\n${CYAN}========================================${NC}"; echo -e "${CYAN}$1${NC}"; echo -e "${CYAN}========================================${NC}\n"; }

validate_regression_repos() {
    local missing=0

    if [ ! -d "$FIREBIRD_REPO_PATH" ] || [ ! -d "$FIREBIRD_REPO_PATH/tests" ]; then
        missing=1
        log_warn "Firebird test clone not found at: $FIREBIRD_REPO_PATH"
        log_info "Set FIREBIRD_REPO_PATH to your local fbt-repository (or firebird) clone."
    fi

    if [ ! -d "$MYSQL_REPO_PATH/mysql-test" ]; then
        missing=1
        log_warn "MySQL test clone not found at: $MYSQL_REPO_PATH"
        log_info "Set MYSQL_REPO_PATH to your local mysql-server clone."
    fi

    if [ ! -d "$POSTGRESQL_REPO_PATH/src/test/regress" ]; then
        missing=1
        log_warn "PostgreSQL test clone not found at: $POSTGRESQL_REPO_PATH"
        log_info "Set POSTGRESQL_REPO_PATH to your local postgresql clone."
    fi

    if [ "$missing" -ne 0 ]; then
        return 1
    fi

    return 0
}

summarize_regression_run() {
    local source_dir="$1"
    local output_file="$2"

    "$PYTHON" - "$source_dir" "$output_file" <<'PY'
import json
import sys
from pathlib import Path

source_dir = Path(sys.argv[1])
output_file = Path(sys.argv[2])

suite_entries = []

for json_file in sorted(source_dir.rglob("*.json")):
    try:
        data = json.loads(json_file.read_text())
    except Exception:
        continue

    summary = data.get("summary", {})
    suite_name = data.get("suite", data.get("engine", json_file.stem))

    suite_entries.append({
        "file": str(json_file),
        "suite": suite_name,
        "engine": data.get("engine"),
        "target": data.get("target"),
        "summary": {
            "total": summary.get("total", 0),
            "passed": summary.get("passed", summary.get("passed_tests", 0)),
            "failed": summary.get("failed", summary.get("failed_tests", 0)),
            "skipped": summary.get("skipped", summary.get("skipped_tests", 0)),
            "errors": summary.get("errors", summary.get("error_tests", 0)),
            "pass_rate": (summary.get("passed", 0) / summary.get("total", 1) * 100) if summary.get("total", 0) else 0.0,
        },
    })

output = {
    "source": str(source_dir),
    "suites": suite_entries,
    "totals": {
        "total": sum(item["summary"]["total"] for item in suite_entries),
        "passed": sum(item["summary"]["passed"] for item in suite_entries),
        "failed": sum(item["summary"]["failed"] for item in suite_entries),
        "skipped": sum(item["summary"]["skipped"] for item in suite_entries),
        "errors": sum(item["summary"]["errors"] for item in suite_entries),
    },
}

if output["totals"]["total"] > 0:
    output["totals"]["pass_rate"] = output["totals"]["passed"] / output["totals"]["total"] * 100
else:
    output["totals"]["pass_rate"] = 0.0

output_file.write_text(json.dumps(output, indent=2))
PY
}

check_python_deps() {
    local engine="$1"
    local missing=()
    
    # Check for psutil (system info)
    if ! $PYTHON -c "import psutil" 2>/dev/null; then
        missing+=("psutil")
    fi
    
    # Check for engine-specific modules
    case "$engine" in
        firebird)
            if ! $PYTHON -c "import fdb" 2>/dev/null; then
                missing+=("fdb")
            fi
            ;;
        mysql)
            if ! $PYTHON -c "import pymysql" 2>/dev/null && ! $PYTHON -c "import mysql.connector" 2>/dev/null; then
                missing+=("pymysql or mysql-connector-python")
            fi
            ;;
        postgresql)
            if ! $PYTHON -c "import psycopg2" 2>/dev/null; then
                missing+=("psycopg2-binary")
            fi
            ;;
        scratchbird)
            if ! $PYTHON -c "import scratchbird" 2>/dev/null; then
                missing+=("scratchbird-python-driver")
            fi
            ;;
    esac
    
    if [ ${#missing[@]} -gt 0 ]; then
        log_warn "Missing Python dependencies: ${missing[*]}"
        log_info "Install with: pip3 install ${missing[*]}"
        log_info "Or: pip3 install -r requirements.txt"
        echo ""
        read -p "Continue anyway? [y/N]: " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
}

show_help() {
    cat << EOF
Run Benchmarks Against a Single Database Engine

Usage: $0 <ENGINE> [SUITE] [OPTIONS]

Engines:
  firebird    Run benchmarks against FirebirdSQL
  mysql       Run benchmarks against MySQL
  postgresql  Run benchmarks against PostgreSQL
  scratchbird Run benchmarks against ScratchBird native

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
  index-comparison  Normalized index-family plan and performance tests

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
  $0 postgresql index-comparison     # Run normalized index tests on PostgreSQL

Prerequisites:
  - Start engine first: ./start-engine.sh <engine> start
  - Only ONE engine should be running during benchmarks
  - Stress-suite transaction variants can be forced with
    BENCHMARK_STRESS_TRANSACTION_MODES=no_transaction,normal_transactional,autocommit

Output:
  Results are saved to: results/<suite>-<engine>-<timestamp>.json
  Reports are saved to: results/reports/ (if --report is used)

EOF
}

detect_running_engine() {
    # Check which engine is currently running
    local engines=("firebird" "mysql" "postgresql" "scratchbird")
    local running=""
    local count=0
    
    for engine in "${engines[@]}"; do
        if [ "$engine" = "scratchbird" ]; then
            local env_file="$PROJECT_DIR/.benchmark-engine-ports/scratchbird.env"
            local pid_file=""
            if [ -f "$env_file" ]; then
                # shellcheck disable=SC1090
                . "$env_file"
                pid_file="${BENCHMARK_SCRATCHBIRD_ROOT}/control/sb_server.pid"
                if [ -f "$pid_file" ] && kill -0 "$(cat "$pid_file" 2>/dev/null)" 2>/dev/null; then
                    running="$engine"
                    ((count++))
                fi
            fi
        elif docker ps | grep -q "sb-benchmark-$engine"; then
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
            for engine in firebird mysql postgresql scratchbird; do
                if [ "$engine" != "$expected_engine" ]; then
                    "$PROJECT_DIR/scripts/start-engine.sh" "$engine" stop >/dev/null 2>&1 || true
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

load_engine_env_file() {
    local engine="$1"
    local port_file="$PROJECT_DIR/.benchmark-engine-ports/${engine}.env"
    if [ -f "$port_file" ]; then
        # shellcheck disable=SC1090
        . "$port_file"
    fi
}

get_engine_host() {
    local engine="$1"
    load_engine_env_file "$engine"
    case "$engine" in
        firebird|mysql|postgresql) echo "localhost" ;;
        scratchbird) echo "${BENCHMARK_SCRATCHBIRD_HOST:-127.0.0.1}" ;;
    esac
}

collect_system_info() {
    local output_dir="$1"
    
    log_section "Collecting System Information"
    
    if command -v python3 &> /dev/null; then
        $PYTHON "$PROJECT_DIR/system-info/collectors/system_info.py" \
            --output "$output_dir/system-info.json" \
            --quiet 2>/dev/null || log_warn "System info collection failed"
        
        if [ -f "$output_dir/system-info.json" ]; then
            log_success "System info collected"
        fi
    else
        log_warn "Python3 not available, skipping system info"
    fi
}

capture_run_provenance() {
    local engine="$1"
    local suite="$2"
    local output_dir="$3"
    local report_enabled="$4"
    local tags="$5"
    local notes="$6"
    local -a cmd=(
        "$PYTHON" "$PROJECT_DIR/scripts/capture_run_provenance.py"
        --project-dir "$PROJECT_DIR"
        --engine "$engine"
        --suite "$suite"
        --output-dir "$output_dir"
        --runner-script "$PROJECT_DIR/scripts/run-benchmark.sh"
        --runner-cwd "$(pwd)"
        --python-executable "$PYTHON"
        --runtime-option "report_enabled=$report_enabled"
        --runtime-option "tags=$tags"
        --runtime-option "notes=$notes"
        --runtime-option "output_dir=$output_dir"
    )
    local arg
    for arg in "${RUN_BENCHMARK_INVOCATION[@]}"; do
        cmd+=(--runner-argv "$arg")
    done
    "${cmd[@]}" >/dev/null
}

run_regression_tests() {
    local engine="$1"
    local output_dir="$2"
    
    log_section "Running Regression Tests"

    if [ "$engine" = "scratchbird" ]; then
        log_warn "Regression suite is donor-engine only; ScratchBird regression proof stays in the main repo public-beta gate"
        mkdir -p "$output_dir"
        cat > "$output_dir/regression-scratchbird-skipped.json" <<EOF
{
  "suite": "regression",
  "engine": "scratchbird",
  "status": "skipped",
  "reason": "ScratchBird uses the repo-local public beta gate instead of donor regression clones."
}
EOF
        return 0
    fi

    if [ ! -d "$PROJECT_DIR/regression-suites" ] || [ ! -x "$PROJECT_DIR/regression-suites/run-regression-suite.sh" ]; then
        log_warn "Regression suite runner not found"
        return
    fi

    validate_regression_repos || {
        log_warn "Regression source trees are not fully configured. Set env vars and rerun."
        return
    }

    local suite_log="$output_dir/regression-${engine}.log"
    local suite_output_dir=""
    local latest_dir=""

    "$PROJECT_DIR/regression-suites/run-regression-suite.sh" "$engine" original > "$suite_log" 2>&1
    local run_rc=$?

    if [ $run_rc -ne 0 ]; then
        log_warn "Regression suite reported failures for $engine"
    fi

    suite_output_dir="$(awk '/^Results:/ {print $2}' "$suite_log" | tail -n 1)"
    if [ -z "$suite_output_dir" ] || [ ! -d "$suite_output_dir" ]; then
        # Find the most recent regression output directory if command output is missing.
        latest_dir=$(find "$PROJECT_DIR/results" -maxdepth 1 -type d -name "regression-*" 2>/dev/null | sort | tail -n 1)
        suite_output_dir="$latest_dir"
    fi

    if [ -n "$suite_output_dir" ] && [ -d "$suite_output_dir" ]; then
        mkdir -p "$output_dir/regression"
        cp -R "$suite_output_dir" "$output_dir/regression/$engine"
        summarize_regression_run "$output_dir/regression/$engine" "$output_dir/regression-${engine}-summary.json"
        log_success "Regression results saved to $output_dir/regression/$engine"
    else
        log_warn "Could not locate regression result directory for $engine"
    fi

    if [ $run_rc -ne 0 ]; then
        return 1
    fi
}

run_stress_tests() {
    local engine="$1"
    local output_dir="$2"
    local scale="${STRESS_SCALE:-medium}"
    local transaction_modes="${BENCHMARK_STRESS_TRANSACTION_MODES:-}"
    local -a modes=()
    
    log_section "Running Stress Tests"

    if [ -z "$transaction_modes" ]; then
        case "$engine" in
            mysql|postgresql)
                modes=("no_transaction" "normal_transactional" "autocommit")
                ;;
            firebird|scratchbird)
                modes=("normal_transactional" "autocommit")
                ;;
            *)
                modes=("engine_default")
                ;;
        esac
    else
        IFS=',' read -r -a modes <<< "$transaction_modes"
    fi
    
    if [ -f "$PROJECT_DIR/stress-tests/runners/dialect_stress_runner.py" ]; then
        local mode
        for mode in "${modes[@]}"; do
            log_info "Stress transaction mode: $mode"
            $PYTHON "$PROJECT_DIR/stress-tests/runners/dialect_stress_runner.py" \
                --engine "$engine" \
                --host "$(get_engine_host "$engine")" \
                --port $(get_engine_port "$engine") \
                --database $(get_engine_database "$engine") \
                --user "$(get_engine_user "$engine")" \
                --password "$(get_engine_password "$engine")" \
                --scale "$scale" \
                --transaction-mode "$mode" \
                --output-dir "$output_dir" \
                || { log_warn "Stress tests had failures in transaction mode $mode"; return 1; }
        done
    else
        log_warn "Stress test runner not found"
        return 1
    fi
    return 0
}

run_acid_tests() {
    local engine="$1"
    local output_dir="$2"
    
    log_section "Running ACID Tests"
    
    if [ -f "$PROJECT_DIR/acid-tests/runners/acid_test_runner.py" ]; then
        $PYTHON "$PROJECT_DIR/acid-tests/runners/acid_test_runner.py" \
            --engine "$engine" \
            --host "$(get_engine_host "$engine")" \
            --port $(get_engine_port "$engine") \
            --database $(get_engine_database "$engine") \
            --user "$(get_engine_user "$engine")" \
            --password "$(get_engine_password "$engine")" \
            --output-dir "$output_dir" \
            || { log_warn "ACID tests had failures"; return 1; }
    else
        log_warn "ACID test runner not found"
        return 1
    fi
    return 0
}

run_performance_tests() {
    local engine="$1"
    local output_dir="$2"
    
    log_section "Running Performance Tests"
    
    if [ -f "$PROJECT_DIR/performance-tests/runners/performance_test_runner.py" ]; then
        $PYTHON "$PROJECT_DIR/performance-tests/runners/performance_test_runner.py" \
            --engine "$engine" \
            --host "$(get_engine_host "$engine")" \
            --port $(get_engine_port "$engine") \
            --database $(get_engine_database "$engine") \
            --user "$(get_engine_user "$engine")" \
            --password "$(get_engine_password "$engine")" \
            --output-dir "$output_dir" \
            || { log_warn "Performance tests had failures"; return 1; }
    else
        log_warn "Performance test runner not found"
        return 1
    fi
    return 0
}

run_tpc_c() {
    local engine="$1"
    local output_dir="$2"
    
    log_section "Running TPC-C Benchmark"
    
    if [ -f "$PROJECT_DIR/tpc-c/runners/tpc_c_runner.py" ]; then
        $PYTHON "$PROJECT_DIR/tpc-c/runners/tpc_c_runner.py" \
            --engine "$engine" \
            --host "$(get_engine_host "$engine")" \
            --port $(get_engine_port "$engine") \
            --database $(get_engine_database "$engine") \
            --user "$(get_engine_user "$engine")" \
            --password "$(get_engine_password "$engine")" \
            --warehouses 10 \
            --duration 300 \
            --output-dir "$output_dir" \
            || { log_warn "TPC-C had failures"; return 1; }
    else
        log_warn "TPC-C runner not found"
        return 1
    fi
    return 0
}

run_tpc_h() {
    local engine="$1"
    local output_dir="$2"
    
    log_section "Running TPC-H Benchmark"
    
    if [ -f "$PROJECT_DIR/tpc-h/runners/tpc_h_runner.py" ]; then
        $PYTHON "$PROJECT_DIR/tpc-h/runners/tpc_h_runner.py" \
            --engine "$engine" \
            --host "$(get_engine_host "$engine")" \
            --port $(get_engine_port "$engine") \
            --database $(get_engine_database "$engine") \
            --user "$(get_engine_user "$engine")" \
            --password "$(get_engine_password "$engine")" \
            --scale 1 \
            --output-dir "$output_dir" \
            || { log_warn "TPC-H had failures"; return 1; }
    else
        log_warn "TPC-H runner not found"
        return 1
    fi
    return 0
}

run_engine_differential() {
    local engine="$1"
    local output_dir="$2"
    
    log_section "Running Engine Differential Tests"
    
    if [ -f "$PROJECT_DIR/engine-differential-tests/runners/differential_test_runner.py" ]; then
        $PYTHON "$PROJECT_DIR/engine-differential-tests/runners/differential_test_runner.py" \
            --engine "$engine" \
            --host "$(get_engine_host "$engine")" \
            --port $(get_engine_port "$engine") \
            --database $(get_engine_database "$engine") \
            --user "$(get_engine_user "$engine")" \
            --password "$(get_engine_password "$engine")" \
            --output-dir "$output_dir" \
            || { log_warn "Differential tests had failures"; return 1; }
    else
        log_warn "Differential test runner not found"
        return 1
    fi
    return 0
}

run_index_comparison() {
    local engine="$1"
    local output_dir="$2"

    log_section "Running Index Comparison Tests"

    if [ -f "$PROJECT_DIR/index-comparison-tests/runners/index_comparison_runner.py" ]; then
        $PYTHON "$PROJECT_DIR/index-comparison-tests/runners/index_comparison_runner.py" \
            --engine "$engine" \
            --host "$(get_engine_host "$engine")" \
            --port "$(get_engine_port "$engine")" \
            --database "$(get_engine_database "$engine")" \
            --user "$(get_engine_user "$engine")" \
            --password "$(get_engine_password "$engine")" \
            --target "$(get_engine_target "$engine")" \
            --output-dir "$output_dir" \
            || { log_warn "Index comparison tests had failures"; return 1; }
    else
        log_warn "Index comparison runner not found"
        return 1
    fi
    return 0
}

get_engine_port() {
    local engine="$1"
    load_engine_env_file "$engine"

    case "$engine" in
        firebird) echo "${BENCHMARK_FIREBIRD_PORT:-3050}" ;;
        mysql) echo "${BENCHMARK_MYSQL_PORT:-3306}" ;;
        postgresql) echo "${BENCHMARK_POSTGRESQL_PORT:-5432}" ;;
        scratchbird) echo "${BENCHMARK_SCRATCHBIRD_PORT:-17092}" ;;
    esac
}

get_engine_database() {
    load_engine_env_file "$1"
    case "$1" in
        firebird) echo "/firebird/data/benchmark.fdb" ;;
        mysql) echo "benchmark" ;;
        postgresql) echo "benchmark" ;;
        scratchbird) echo "${BENCHMARK_SCRATCHBIRD_DB:-main}" ;;
    esac
}

get_engine_user() {
    load_engine_env_file "$1"
    case "$1" in
        firebird|mysql|postgresql) echo "benchmark" ;;
        scratchbird) echo "${BENCHMARK_SCRATCHBIRD_USER:-bootstrap_admin}" ;;
    esac
}

get_engine_password() {
    load_engine_env_file "$1"
    case "$1" in
        firebird|mysql|postgresql) echo "benchmark" ;;
        scratchbird) echo "${BENCHMARK_SCRATCHBIRD_PASSWORD:-SbExampleBootstrap_2026!}" ;;
    esac
}

get_engine_target() {
    case "$1" in
        scratchbird) echo "scratchbird-native" ;;
        *) echo "upstream-$1" ;;
    esac
}

generate_report() {
    local output_dir="$1"
    local tags="$2"
    local notes="$3"
    
    log_section "Generating Text Report"
    
    if [ -f "$PROJECT_DIR/system-info/submit/result_formatter.py" ]; then
        shopt -s nullglob
        local result_files=()
        local result_file
        for result_file in "$output_dir"/*.json; do
            local basename_file
            basename_file="$(basename "$result_file")"
            case "$basename_file" in
                system-info.json|*summary.json|regression-*-summary.json)
                    continue
                    ;;
            esac
            result_files+=("$result_file")
        done
        shopt -u nullglob

        if [ "${#result_files[@]}" -eq 0 ]; then
            log_warn "No suite result files found for report generation in $output_dir"
            return
        fi

        local args=(
            --compare
            "${result_files[@]}"
            --output "$output_dir/reports"
        )
        
        if [ -f "$output_dir/system-info.json" ]; then
            args+=(--system-info "$output_dir/system-info.json")
        fi
        
        if [ -n "$tags" ]; then
            args+=(--tags "$tags")
        fi
        
        if [ -n "$notes" ]; then
            args+=(--notes "$notes")
        fi
        
        $PYTHON "$PROJECT_DIR/system-info/submit/result_formatter.py" "${args[@]}" || log_warn "Report generation failed"
        
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
    firebird|mysql|postgresql|scratchbird)
        ;;
    --help|-h)
        show_help
        exit 0
        ;;
    *)
        log_error "Unknown engine: $ENGINE"
        echo "Valid engines: firebird, mysql, postgresql, scratchbird"
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

# Check Python dependencies
check_python_deps "$ENGINE"

# Show banner
log_section "ScratchBird Benchmark"
log_info "Engine: $ENGINE"
log_info "Suite:  $SUITE"
log_info "Output: $OUTPUT_DIR"

capture_run_provenance "$ENGINE" "$SUITE" "$OUTPUT_DIR" "$GENERATE_REPORT" "$TAGS" "$NOTES"

# Collect system info first
collect_system_info "$OUTPUT_DIR"

# Run tests based on suite
START_TIME=$(date +%s)
SUITE_FAILED=0

case "$SUITE" in
    all)
        run_regression_tests "$ENGINE" "$OUTPUT_DIR" || SUITE_FAILED=1
        run_stress_tests "$ENGINE" "$OUTPUT_DIR" || SUITE_FAILED=1
        run_acid_tests "$ENGINE" "$OUTPUT_DIR" || SUITE_FAILED=1
        run_performance_tests "$ENGINE" "$OUTPUT_DIR" || SUITE_FAILED=1
        run_tpc_c "$ENGINE" "$OUTPUT_DIR" || SUITE_FAILED=1
        run_tpc_h "$ENGINE" "$OUTPUT_DIR" || SUITE_FAILED=1
        run_engine_differential "$ENGINE" "$OUTPUT_DIR" || SUITE_FAILED=1
        run_index_comparison "$ENGINE" "$OUTPUT_DIR" || SUITE_FAILED=1
        ;;
    regression)
        run_regression_tests "$ENGINE" "$OUTPUT_DIR" || SUITE_FAILED=1
        ;;
    stress)
        run_stress_tests "$ENGINE" "$OUTPUT_DIR" || SUITE_FAILED=1
        ;;
    acid)
        run_acid_tests "$ENGINE" "$OUTPUT_DIR" || SUITE_FAILED=1
        ;;
    performance)
        run_performance_tests "$ENGINE" "$OUTPUT_DIR" || SUITE_FAILED=1
        ;;
    tpc-c)
        run_tpc_c "$ENGINE" "$OUTPUT_DIR" || SUITE_FAILED=1
        ;;
    tpc-h)
        run_tpc_h "$ENGINE" "$OUTPUT_DIR" || SUITE_FAILED=1
        ;;
    engine-differential)
        run_engine_differential "$ENGINE" "$OUTPUT_DIR" || SUITE_FAILED=1
        ;;
    index-comparison)
        run_index_comparison "$ENGINE" "$OUTPUT_DIR" || SUITE_FAILED=1
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

if [ "$SUITE_FAILED" -ne 0 ]; then
    exit 1
fi
