# Benchmark Test Strategy

This strategy defines how benchmark runs are produced and how they are interpreted for native baseline and ScratchBird comparison.

## Primary Goal

Produce comparable, repeatable outputs across:

- FirebirdSQL
- MySQL
- PostgreSQL

Then use the same harness and metric model to evaluate ScratchBird in each dialect mode.

## Primary Execution Path

Canonical command:

```bash
SCRATCHBIRD_PG_QUERY_TIMEOUT_MS=30000 \
./scripts/run-benchmark-matrix.sh \
  --engines=firebird,mysql,postgresql \
  --suites=regression,stress,acid,performance,tpc-c,tpc-h,engine-differential \
  --report --compare
```

Rationale:

- Runs one engine at a time for isolation and reproducibility.
- Produces deterministic per-suite outputs and matrix metadata.
- Emits a consolidated CSV (`matrix-comparison-unified.csv`) for direct cross-engine decisions.

## Suite Set In Scope (Matrix Default)

- `regression`
- `stress`
- `acid`
- `performance`
- `tpc-c`
- `tpc-h`
- `engine-differential`

These are the suites used for official matrix comparisons.

## Comparison Model

Decisions are made using the following hierarchy:

1. Run integrity:
   - `matrix-summary.json` result, failed suite count, exit codes.
2. Correctness:
   - regression `totals.*`
   - suite `summary.passed`, `summary.failed`, `summary.errors`
3. Runtime:
   - `matrix.duration_seconds`
   - suite timing fields in `summary.*`
4. Artifact drill-down:
   - inspect source JSON indicated by `artifact.result_json`

## Reporting Outputs Required Per Matrix Run

- `matrix-summary.json`
- `.matrix-runs.tsv`
- `matrix-comparison-unified.csv`
- raw suite JSON under `<engine>/<suite>/`
- optional text reports when `--report` and `--compare` are enabled

## ScratchBird Evaluation Plan

1. Produce native baseline matrix output.
2. Produce ScratchBird-mode runs using equivalent suite configuration.
3. Generate consolidated CSV for each run set.
4. Compare run health, correctness, and runtime by `suite + metric`.
5. Track deltas over time in CI.

## Quality Controls

- Pin output directories by setting `BENCHMARK_MATRIX_OUTPUT`.
- Keep PostgreSQL differential query timeout bounded (`SCRATCHBIRD_PG_QUERY_TIMEOUT_MS`).
- Validate artifact completeness before analysis.
- Avoid mixing partial and complete runs in one comparison set.

## Related Docs

- [README.md](/home/dcalford/CliWork/ScratchBird-Benchmarks/README.md)
- [docs/OPERATIONS_RUNBOOK.md](/home/dcalford/CliWork/ScratchBird-Benchmarks/docs/OPERATIONS_RUNBOOK.md)
- [docs/REPORTS_AND_CONSOLIDATED_CSV.md](/home/dcalford/CliWork/ScratchBird-Benchmarks/docs/REPORTS_AND_CONSOLIDATED_CSV.md)
