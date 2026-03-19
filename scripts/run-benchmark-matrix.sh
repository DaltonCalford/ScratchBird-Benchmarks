#!/bin/bash
#
# Run a comparable benchmark matrix across all native engines.
#
# The script starts one engine at a time, runs the selected suite set,
# and stores results in a per-engine directory for direct comparison.
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
RUN_ID="$(date -u +"%Y%m%d-%H%M%S")"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[PASS]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[FAIL]${NC} $1"; }
log_section() { echo -e "\n${CYAN}========================================${NC}"; echo -e "${CYAN}$1${NC}"; echo -e "${CYAN}========================================${NC}\n"; }

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

require_python() {
    if ! command -v python3 >/dev/null 2>&1; then
        log_error "python3 is required for benchmark matrix reporting"
        exit 1
    fi
}

show_help() {
    cat << EOF
Run Benchmarks Across All Native Engines

Usage: $0 [OPTIONS]

Options:
  --engines=LIST     Comma-separated engine list (default: firebird,mysql,postgresql)
  --suites=LIST      Comma-separated suite list (default: regression,stress,acid,performance,tpc-c,tpc-h,engine-differential,index-comparison)
  --output=DIR       Output root directory (default: results/matrix-YYYYMMDD-HHMMSS)
                     Can also be set with BENCHMARK_MATRIX_OUTPUT.
                     Also writes matrix-comparison-unified.csv in this directory.
  --report           Enable text report generation in each suite run
  --tags TAGS        Pass tags to run-benchmark report generation
  --notes NOTES      Pass notes to run-benchmark report generation
  --fail-fast        Stop after first failed suite
  --keep-running     Keep each engine running after completion
  --compare          Generate cross-engine comparison text reports after each suite
  -h, --help         Show this help message
EOF
}

split_csv() {
    local value="$1"
    local -n output="$2"

    IFS=',' read -r -a output <<< "$value"
}

validate_suite() {
    case "$1" in
        regression|stress|acid|performance|tpc-c|tpc-h|engine-differential|index-comparison|all)
            return 0
            ;;
        all)
            return 0
            ;;
        *)
            return 1
            ;;
    esac
}

VALID_ENGINES=()
VALID_SUITES=()

ENABLED_ENGINES="${BENCHMARK_ENGINES:-firebird,mysql,postgresql}"
ENABLED_SUITES="${BENCHMARK_SUITES:-regression,stress,acid,performance,tpc-c,tpc-h,engine-differential,index-comparison}"
OUTPUT_ROOT="${BENCHMARK_MATRIX_OUTPUT:-$PROJECT_DIR/results/matrix-$RUN_ID}"
GENERATE_REPORT=false
TAGS=""
NOTES=""
FAIL_FAST=false
KEEP_RUNNING=false
GENERATE_COMPARE_REPORT=false

for arg in "$@"; do
    case "$arg" in
        --engines=*)
            ENABLED_ENGINES="${arg#*=}"
            ;;
        --suites=*)
            ENABLED_SUITES="${arg#*=}"
            ;;
        --output=*)
            OUTPUT_ROOT="${arg#*=}"
            ;;
        --compare)
            GENERATE_COMPARE_REPORT=true
            ;;
        --report)
            GENERATE_REPORT=true
            ;;
        --tags=*)
            TAGS="${arg#*=}"
            ;;
        --notes=*)
            NOTES="${arg#*=}"
            ;;
        --fail-fast)
            FAIL_FAST=true
            ;;
        --keep-running)
            KEEP_RUNNING=true
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            log_error "Unknown option: $arg"
            show_help
            exit 1
            ;;
    esac
done

split_csv "$ENABLED_ENGINES" VALID_ENGINES
split_csv "$ENABLED_SUITES" VALID_SUITES

if [ "${#VALID_ENGINES[@]}" -eq 0 ]; then
    log_error "No engines configured"
    exit 1
fi

if [ "${#VALID_SUITES[@]}" -eq 0 ]; then
    log_error "No suites configured"
    exit 1
fi

require_python

mkdir -p "$OUTPUT_ROOT"

REPORT_ARGS=()
if [ "$GENERATE_REPORT" = true ]; then
    REPORT_ARGS+=(--report)
    [ -n "$TAGS" ] && REPORT_ARGS+=(--tags "$TAGS")
    [ -n "$NOTES" ] && REPORT_ARGS+=(--notes "$NOTES")
fi

TOTAL_FAILURES=0
MATRIX_RUN_LOG="$OUTPUT_ROOT/.matrix-runs.tsv"
: > "$MATRIX_RUN_LOG"

run_single_suite() {
    local engine="$1"
    local suite="$2"
    local output_dir="$3"
    local suite_start
    local port_file="${PROJECT_DIR}/.benchmark-engine-ports/${engine}.env"

    suite_start="$(date +%s)"
    suite_started_at="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
    log_section "Engine=$engine Suite=$suite"

    if [ -f "$port_file" ]; then
        # Export discovered engine ports so run-benchmark receives the exact host
        # ports chosen during engine startup.
        set -a
        # shellcheck disable=SC1090
        . "$port_file"
        set +a
    fi

    log_info "Output: $output_dir"
    set +e
    "$PROJECT_DIR/scripts/run-benchmark.sh" "$engine" "$suite" --output "$output_dir" "${REPORT_ARGS[@]}"
    suite_rc=$?
    set -e

    suite_elapsed=$(( $(date +%s) - suite_start ))
    if [ $suite_rc -ne 0 ]; then
        status="failed"
        log_error "Suite '$suite' failed on $engine (exit $suite_rc) after ${suite_elapsed}s"
        TOTAL_FAILURES=$((TOTAL_FAILURES + 1))
        echo "${engine}|${suite}|${suite_started_at}|${suite_elapsed}|${suite_rc}|${status}|${output_dir}" >> "$MATRIX_RUN_LOG"
        return "$suite_rc"
    fi
    status="passed"
    log_success "Suite '$suite' done on $engine in ${suite_elapsed}s"
    echo "${engine}|${suite}|${suite_started_at}|${suite_elapsed}|0|${status}|${output_dir}" >> "$MATRIX_RUN_LOG"
    return 0
}

run_suite_comparison() {
    local suite="$1"
    local output_root="$2"
    local report_dir

    local comparisons=()
    for engine in "${VALID_ENGINES[@]}"; do
        for result_file in "$output_root/$engine/$suite"/*.json; do
            [ -f "$result_file" ] || continue
            case "$(basename "$result_file")" in
                *system-info.json|*summary.json|*regression-*-summary.json)
                    continue
                    ;;
            esac
            comparisons+=("$result_file")
        done
    done

    if [ "${#comparisons[@]}" -lt 2 ]; then
        return 0
    fi

    report_dir="$output_root/comparison-$suite"
    mkdir -p "$report_dir"
    python3 "$PROJECT_DIR/system-info/submit/result_formatter.py" \
        --compare "${comparisons[@]}" \
        --output "$report_dir" \
        >/dev/null 2>&1 || true
    if [ "$suite" = "index-comparison" ] && [ -f "$PROJECT_DIR/index-comparison-tests/scripts/compare_index_results.py" ]; then
        python3 "$PROJECT_DIR/index-comparison-tests/scripts/compare_index_results.py" \
            --results "${comparisons[@]}" \
            --output-dir "$report_dir" \
            >/dev/null 2>&1 || true
    fi
    return 0
}

run_engine_matrix() {
    local engine="$1"
    local engine_root="$OUTPUT_ROOT/$engine"
    mkdir -p "$engine_root"

    log_section "Running $engine matrix"
    if ! "$PROJECT_DIR/scripts/start-engine.sh" "$engine" start; then
        log_error "Failed to start $engine"
        return 1
    fi

    for suite in "${VALID_SUITES[@]}"; do
        if [ "$suite" = "all" ]; then
            continue
        fi

        if ! validate_suite "$suite"; then
            log_warn "Skipping unknown suite '$suite'"
            continue
        fi

        if ! run_single_suite "$engine" "$suite" "$engine_root/$suite"; then
            if [ "$FAIL_FAST" = true ]; then
                [ "$KEEP_RUNNING" = false ] && "$PROJECT_DIR/scripts/start-engine.sh" "$engine" stop
                return 1
            fi
        fi
    done

    if [ "$KEEP_RUNNING" = false ]; then
        "$PROJECT_DIR/scripts/start-engine.sh" "$engine" stop
    fi
}

generate_matrix_summary() {
    local started_at="$1"
    local completed_at="$2"
    local started_ts="$3"
    local completed_ts="$4"
    local log_file="$5"
    local output_json="$6"

    python3 - "$OUTPUT_ROOT" "$RUN_ID" "$started_at" "$completed_at" "$started_ts" "$completed_ts" "$TOTAL_FAILURES" "$ENABLED_ENGINES" "$ENABLED_SUITES" "$FAIL_FAST" "$KEEP_RUNNING" "$GENERATE_REPORT" "$GENERATE_COMPARE_REPORT" "$log_file" <<'PY'
import csv
import json
import pathlib
import sys
from datetime import datetime, timezone

output_root, run_id, started_at, completed_at, started_ts, completed_ts, total_failures, engines_raw, suites_raw, fail_fast, keep_running, generate_report, generate_compare, log_file = (
    sys.argv[1],
    sys.argv[2],
    sys.argv[3],
    sys.argv[4],
    float(sys.argv[5]),
    float(sys.argv[6]),
    int(sys.argv[7]),
    sys.argv[8],
    sys.argv[9],
    sys.argv[10].lower() == "true",
    sys.argv[11].lower() == "true",
    sys.argv[12].lower() == "true",
    sys.argv[13].lower() == "true",
    sys.argv[14],
)

engines_requested = [item.strip() for item in engines_raw.split(",") if item.strip()]
suites_requested = [item.strip() for item in suites_raw.split(",") if item.strip()]

def parse_suite_runs(path):
    suite_runs = []
    if not pathlib.Path(path).exists():
        return suite_runs
    with open(path, newline="", encoding="utf-8") as handle:
        for row in csv.reader(handle, delimiter="|"):
            if len(row) != 7:
                continue
            engine, suite, started, duration_s, exit_code, status, output_dir = row
            suite_runs.append({
                "engine": engine,
                "suite": suite,
                "started_at": started,
                "duration_seconds": int(duration_s),
                "status": status,
                "exit_code": int(exit_code),
                "output_dir": output_dir,
            })
    return suite_runs

suite_runs = parse_suite_runs(log_file)
duration_seconds = int(completed_ts - started_ts)

summary = {
    "run_id": run_id,
    "started_at_utc": started_at,
    "completed_at_utc": completed_at,
    "duration_seconds": duration_seconds,
    "engines_requested": engines_requested,
    "suites_requested": suites_requested,
    "keep_running": keep_running,
    "fail_fast": fail_fast,
    "generate_report": generate_report,
    "generate_comparison_report": generate_compare,
    "total_suite_runs": len(suite_runs),
    "failed_suite_runs": total_failures,
    "result": "passed" if total_failures == 0 else "failed",
    "suite_runs": suite_runs,
    "output_root": output_root,
}

path = pathlib.Path(output_root) / "matrix-summary.json"
path.write_text(json.dumps(summary, indent=2))

print(path)
PY
}

log_section "Benchmark Matrix"
log_info "Engines: ${VALID_ENGINES[*]}"
log_info "Suites: ${VALID_SUITES[*]}"
log_info "Output root: $OUTPUT_ROOT"
log_info "Comparison report generation: $GENERATE_COMPARE_REPORT"
log_info "Output summary: $OUTPUT_ROOT/matrix-summary.json"

RUN_STARTED_AT_UTC="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
RUN_START_TS="$(date -u +%s)"

for engine in "${VALID_ENGINES[@]}"; do
    if ! run_engine_matrix "$engine"; then
        log_warn "Matrix run encountered failures for $engine"
    fi
done

if [ "$GENERATE_COMPARE_REPORT" = true ]; then
    for suite in "${VALID_SUITES[@]}"; do
        if [ "$suite" = "all" ]; then
            continue
        fi
        run_suite_comparison "$suite" "$OUTPUT_ROOT"
    done
fi

RUN_COMPLETED_AT_UTC="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
RUN_COMPLETED_TS="$(date -u +%s)"
GENERATED_SUMMARY=$(generate_matrix_summary "$RUN_STARTED_AT_UTC" "$RUN_COMPLETED_AT_UTC" "$RUN_START_TS" "$RUN_COMPLETED_TS" "$MATRIX_RUN_LOG" "$OUTPUT_ROOT/matrix-summary.json")
log_info "Matrix summary: $GENERATED_SUMMARY"

UNIFIED_CSV_PATH="$OUTPUT_ROOT/matrix-comparison-unified.csv"
if python3 "$PROJECT_DIR/scripts/generate-unified-comparison-csv.py" --summary "$GENERATED_SUMMARY" --output "$UNIFIED_CSV_PATH" >/dev/null 2>&1; then
    log_info "Unified comparison CSV: $UNIFIED_CSV_PATH"
else
    log_warn "Failed to generate unified comparison CSV"
fi

if [ "$TOTAL_FAILURES" -eq 0 ]; then
    log_success "Benchmark matrix complete"
    exit 0
fi

log_warn "Benchmark matrix completed with $TOTAL_FAILURES suite failures"
exit 1
