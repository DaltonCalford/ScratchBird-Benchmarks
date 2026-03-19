#!/usr/bin/env python3
"""Runner for the index comparison benchmark lane."""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter, defaultdict
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

SUITE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SUITE_ROOT))

from adapters.engine_adapters import create_adapter, summarize_latencies
from scenarios.phase1_scenarios import PHASE1_SCENARIOS, phase1_insert_rows


NOISE_BAND_PCT = 5.0


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def make_target_default(engine: str) -> str:
    return f"upstream-{engine}"


def evaluate_expectation(scenario, normalized_plan: Dict[str, Any]) -> tuple[str, int]:
    if normalized_plan["plan_capture_status"] != "ok":
        return "error", 0
    if normalized_plan["fallback_to_scan"]:
        return "fallback", 25
    if not normalized_plan["used_index"]:
        return "mismatch", 50
    expected_indexes = {name.upper() for name in scenario.expected_index_names}
    observed_indexes = {name.upper() for name in normalized_plan["index_names"]}
    if expected_indexes and observed_indexes and not expected_indexes.intersection(observed_indexes):
        return "partial", 70
    if scenario.require_order_from_index and normalized_plan["extra_sort"]:
        return "partial", 75
    if normalized_plan["actual_plan_family"] not in scenario.expected_access_patterns:
        return "partial", 80
    return "matched", 100


def build_summary(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    counts = Counter(result["execution_status"] for result in results)
    expectation_counts = Counter(result["expectation_status"] for result in results)
    family_counts: Dict[str, int] = defaultdict(int)
    workload_counts: Dict[str, int] = defaultdict(int)
    plan_capture_success = 0
    quality_scores = []
    for result in results:
        family_counts[result["index_family"]] += 1
        workload_counts[result["workload_family"]] += 1
        if result["plan_capture_status"] == "ok":
            plan_capture_success += 1
        quality_scores.append(result["plan_quality_score"])

    avg_score = round(sum(quality_scores) / len(quality_scores), 2) if quality_scores else 0.0
    return {
        "total_tests": len(results),
        "passed": counts.get("pass", 0),
        "failed": counts.get("fail", 0),
        "errors": counts.get("error", 0),
        "unsupported": counts.get("unsupported", 0),
        "plan_capture_success": plan_capture_success,
        "score": avg_score,
        "verdict_ready": False,
        "by_index_family": dict(family_counts),
        "by_workload_family": dict(workload_counts),
        "by_expectation_status": dict(expectation_counts)
    }


def to_report_test(result: Dict[str, Any]) -> Dict[str, Any]:
    status = result["execution_status"]
    if status == "pass" and result["expectation_status"] in ("fallback", "error"):
        status = "warning"
    return {
        "test_name": result["scenario_id"],
        "name": result["description"],
        "status": status,
        "duration_ms": result["latency_avg_ms"],
        "error_message": result.get("error"),
        "plan_family": result["actual_plan_family"],
        "plan_expectation_status": result["expectation_status"],
        "target": result["benchmark_target"]
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Index comparison benchmark runner")
    parser.add_argument("--engine", required=True, choices=["firebird", "mysql", "postgresql"])
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int)
    parser.add_argument("--database", required=True)
    parser.add_argument("--user", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--target", default=None, help="Logical benchmark target. Defaults to upstream-<engine>.")
    parser.add_argument("--iterations", type=int, default=5)
    parser.add_argument("--output-dir", type=Path, default=Path("./results"))
    args = parser.parse_args()

    target_registry = load_json(SUITE_ROOT / "registry" / "target_registry.json")["targets"]
    capability_registry = load_json(SUITE_ROOT / "registry" / "engine_capabilities.json")["engines"]

    if args.port is None:
        args.port = {"firebird": 3050, "mysql": 3306, "postgresql": 5432}[args.engine]

    target_name = args.target or make_target_default(args.engine)
    target_entry = target_registry.get(target_name)
    if target_entry is None:
        raise SystemExit(f"Unknown target: {target_name}")
    if target_entry.get("engine") != args.engine and target_entry.get("engine") != "scratchbird":
        raise SystemExit(f"Target {target_name} does not map to engine {args.engine}")
    if not target_entry.get("enabled", False):
        raise SystemExit(f"Target {target_name} is registered but disabled")

    capabilities = capability_registry[args.engine]
    adapter = create_adapter(args.engine, args.host, args.port, args.database, args.user, args.password)
    results: List[Dict[str, Any]] = []
    args.output_dir.mkdir(parents=True, exist_ok=True)

    try:
        for scenario in PHASE1_SCENARIOS:
            print(f"Running {scenario.scenario_id} on {target_name}...")
            if scenario.index_family not in capabilities["supported_index_families"]:
                results.append(
                    {
                        "scenario_id": scenario.scenario_id,
                        "description": scenario.description,
                        "index_family": scenario.index_family,
                        "workload_family": scenario.workload_family,
                        "benchmark_target": target_name,
                        "runtime_service": target_entry["runtime_service"],
                        "execution_status": "unsupported",
                        "comparative_verdict": None,
                        "comparison_score": None,
                        "plan_capture_status": "unsupported",
                        "actual_plan_family": "unsupported",
                        "used_index": False,
                        "index_names": [],
                        "fallback_to_scan": False,
                        "extra_sort": False,
                        "order_satisfied_by_index": None,
                        "expectation_status": "unsupported",
                        "plan_quality_score": 0,
                        "latency_avg_ms": 0.0,
                        "latency_p95_ms": 0.0,
                        "latency_p99_ms": 0.0,
                        "throughput_qps": 0.0,
                        "rows_returned": 0,
                        "iterations": 0,
                        "noise_band_pct": NOISE_BAND_PCT,
                        "raw_plan": None,
                        "error": f"Engine {args.engine} does not support {scenario.index_family}"
                    }
                )
                continue

            adapter.drop_table(scenario.table_name)
            adapter.execute(scenario.create_table_sql)
            for statement in scenario.create_index_sql:
                adapter.execute(statement)
            adapter.commit()
            insert_rows = phase1_insert_rows(scenario.scenario_id)
            adapter.execute_many(
                adapter.insert_statement(scenario.table_name, len(insert_rows[0])),
                insert_rows
            )
            adapter.commit()
            adapter.refresh_planner_statistics(scenario.table_name)

            query_sql = scenario.query_sql[args.engine]
            error_message = None
            latencies_ms: List[float] = []
            row_count = 0
            normalized_plan = {
                "plan_capture_status": "error",
                "raw_plan": None,
                "actual_plan_family": "unknown",
                "used_index": False,
                "index_names": [],
                "fallback_to_scan": False,
                "extra_sort": False,
                "order_satisfied_by_index": None
            }
            execution_status = "pass"

            try:
                plan = adapter.explain(query_sql)
                normalized_plan = asdict(plan)
                for _ in range(max(1, args.iterations)):
                    start = time.perf_counter()
                    rows = adapter.query_fetch_all(query_sql)
                    elapsed_ms = (time.perf_counter() - start) * 1000.0
                    latencies_ms.append(round(elapsed_ms, 3))
                    row_count = len(rows)
            except Exception as exc:
                adapter.rollback()
                execution_status = "error"
                error_message = str(exc)

            expectation_status, plan_quality_score = evaluate_expectation(scenario, normalized_plan)
            if execution_status == "pass" and expectation_status == "error":
                execution_status = "error"
            elif execution_status == "pass" and row_count < scenario.expected_row_floor:
                execution_status = "fail"
                error_message = f"Query returned {row_count} rows, expected at least {scenario.expected_row_floor}"

            latency_summary = summarize_latencies(latencies_ms)
            result = {
                "scenario_id": scenario.scenario_id,
                "description": scenario.description,
                "index_family": scenario.index_family,
                "workload_family": scenario.workload_family,
                "benchmark_target": target_name,
                "runtime_service": target_entry["runtime_service"],
                "execution_status": execution_status,
                "comparative_verdict": None,
                "comparison_score": None,
                "plan_capture_status": normalized_plan["plan_capture_status"],
                "actual_plan_family": normalized_plan["actual_plan_family"],
                "used_index": normalized_plan["used_index"],
                "index_names": normalized_plan["index_names"],
                "fallback_to_scan": normalized_plan["fallback_to_scan"],
                "extra_sort": normalized_plan["extra_sort"],
                "order_satisfied_by_index": normalized_plan["order_satisfied_by_index"],
                "expectation_status": expectation_status,
                "plan_quality_score": plan_quality_score,
                "rows_returned": row_count,
                "iterations": len(latencies_ms),
                "noise_band_pct": NOISE_BAND_PCT,
                "raw_plan": normalized_plan["raw_plan"],
                "error": error_message,
                **latency_summary
            }
            results.append(result)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        summary = build_summary(results)
        output = {
            "metadata": {
                "engine": args.engine,
                "suite": "index-comparison",
                "timestamp": timestamp,
                "host": args.host,
                "port": args.port,
                "database": args.database,
                "target": target_name,
                "runtime_service": target_entry["runtime_service"],
                "target_class": target_entry["target_class"],
                "docker_first": True,
                "iterations": args.iterations,
                "noise_band_pct": NOISE_BAND_PCT
            },
            "results": {
                "scenarios": {
                    "tests": [to_report_test(result) for result in results]
                }
            },
            "test_results": results,
            "summary": summary
        }
        output_file = args.output_dir / f"index-comparison-{target_name}-{timestamp}.json"
        output_file.write_text(json.dumps(output, indent=2), encoding="utf-8")
        print(f"Results saved to: {output_file}")
        return 0 if summary["errors"] == 0 and summary["failed"] == 0 else 1
    finally:
        adapter.close()


if __name__ == "__main__":
    raise SystemExit(main())
