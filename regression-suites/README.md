# Upstream Regression Test Integration

This directory contains the integration with upstream database test suites.

## Principle

**Use the original test harnesses, clients, and scripts.**

This ensures:
- **Auditable results** - Anyone can reproduce using upstream tools
- **No test bias** - We're not rewriting tests to favor ScratchBird
- **Real edge cases** - Thousands of community-discovered bugs
- **Version tracking** - Tests match specific engine versions

## Test Suite Locations (Local Clones)

| Engine | Local Path | Test Count | Format |
|--------|------------|------------|--------|
| FirebirdSQL | `~/CliWork/fbt-repository/` | ~7,000 | .fbt (JSON) |
| MySQL | `~/CliWork/mysql-server/mysql-test/` | ~5,000 | .test (custom) |
| PostgreSQL | `~/CliWork/postgresql/src/test/regress/` | ~200 | .sql (pg_regress) |

## Architecture

### Container Strategy

```
┌─────────────────────────────────────────────────────────────┐
│  Benchmark Container (Test Orchestrator)                    │
│  - Python harness                                           │
│  - Mounts local test suites as read-only                    │
│  - Uses original clients (isql, mysql, psql)                │
└────────────────────┬────────────────────────────────────────┘
                     │
         ┌───────────┼───────────┐
         ▼           ▼           ▼
   ┌─────────┐ ┌─────────┐ ┌─────────┐
   │Firebird │ │  MySQL  │ │PostgreSQL│
   │  5.0.1  │ │  9.0.1  │ │  18.0   │
   └─────────┘ └─────────┘ └─────────┘
         │           │           │
         ▼           ▼           ▼
   ┌─────────┐ ┌─────────┐ ┌─────────┐
   │ ScratchBird │Firebird │   MySQL   │
   │Emulation│ │  Mode   │ │  Mode   │
   └─────────┘ └─────────┘ └─────────┘
```

### Test Execution Flow

1. **Select test suite** (e.g., Firebird FBT)
2. **Run against original engine** - Baseline/expected results
3. **Run against ScratchBird** (in Firebird mode) - Compare results
4. **Diff analysis** - Categorize failures
5. **Report generation** - Auditable comparison

## Test Categories

### Firebird FBT (Firebird Test Suite)

Location: `~/CliWork/fbt-repository/tests/`

```
bugs/           - Regression tests for specific bug reports
functional/     - Feature tests organized by area:
  ├── gtcs/     - General Test Cases
  ├── basic/    - Basic operations
  ├── intfunc/  - Internal functions
  └── ...
```

Test format (`.fbt` files):
```json
{
  'id': 'bugs.core_0903',
  'tracker_id': 'CORE-903',
  'title': 'New value of column is accessible before update',
  'versions': [{
    'firebird_version': '2.5.0',
    'init_script': 'CREATE TABLE...',
    'test_script': 'SELECT...',
    'expected_stdout': '...'
  }]
}
```

### MySQL mysql-test

Location: `~/CliWork/mysql-server/mysql-test/`

```
t/              - Test files (.test)
r/              - Result files (.result)
suite/          - Test suites:
  ├── sys_vars/ - System variable tests
  ├── funcs_1/  - Function tests
  └── ...
```

Test format (`.test` files):
```sql
--echo # Test INSERT
CREATE TABLE t1 (a INT);
INSERT INTO t1 VALUES (1), (2);
SELECT * FROM t1;
DROP TABLE t1;
```

### PostgreSQL pg_regress

Location: `~/CliWork/postgresql/src/test/regress/`

```
sql/            - Test SQL files
expected/       - Expected output files
parallel/       - Parallel test schedules
serial/         - Serial test schedules
```

Test format: Pure SQL with expected output files.

## Running Tests

### Run Firebird FBT Against Original Firebird
```bash
docker-compose run --rm fbt-runner \
  --engine=firebird \
  --suite=bugs \
  --target=original
```

### Run Firebird FBT Against ScratchBird (Firebird Mode)
```bash
docker-compose run --rm fbt-runner \
  --engine=firebird \
  --suite=bugs \
  --target=scratchbird \
  --mode=firebird
```

### Run MySQL Test Suite
```bash
docker-compose run --rm mysql-test-runner \
  --suite=funcs_1 \
  --target=original
```

### Run PostgreSQL Regression Tests
```bash
docker-compose run --rm pg-regress-runner \
  --schedule=parallel \
  --target=scratchbird \
  --mode=postgresql
```

## Result Interpretation

### Pass Categories

| Result | Meaning |
|--------|---------|
| **PASS** | ScratchBird output matches original exactly |
| **PASS_EQUIVALENT** | Output semantically equivalent (minor formatting) |
| **FAIL_COMPAT** | Different output but acceptable (documented difference) |
| **FAIL_BUG** | ScratchBird bug - needs fixing |
| **SKIP_UNSUPPORTED** | Feature not supported in ScratchBird |

### Example Diff Report

```
Test: bugs.core_0903 (Firebird)
Status: PASS

Test: bugs.core_1234 (Firebird)
Status: FAIL_BUG
Diff:
  Original:  ERROR: arithmetic exception, numeric overflow
  ScratchBird: ERROR: numeric value out of range
  
  Note: Error message differs but same exception class
  
Test: functional.gtcs.proc_basic (Firebird)
Status: SKIP_UNSUPPORTED
Reason: PSQL stored procedures not yet implemented
```

## Version Correlation

Each test run records:
- Original engine version (e.g., Firebird 5.0.1)
- Test suite version (git commit hash of fbt-repository)
- ScratchBird version and emulation mode
- Date/time of test run

This allows:
- Reproducing exact test conditions
- Tracking compatibility over time
- Auditing by third parties

## Exclusions

Some tests are excluded for valid reasons:

1. **Engine-specific features** - ScratchBird doesn't implement (e.g., Firebird generators vs PostgreSQL sequences)
2. **System tables** - Different metadata schemas
3. **Extensions** - Non-core features (PostGIS, etc.)
4. **Known limitations** - Documented in ScratchBird docs

Excluded tests are tracked in:
- `config/firebird-fbt-exclude.txt`
- `config/mysql-test-exclude.txt`
- `config/postgresql-regress-exclude.txt`

## CI/CD Integration

GitHub Actions runs regression tests weekly:

```yaml
- name: Run Firebird FBT
  run: |
    docker-compose run --rm fbt-runner \
      --suite=all \
      --target=scratchbird \
      --output=/results/fbt-results.json
      
- name: Compare Results
  run: |
    python3 scripts/compare-regression-results.py \
      --baseline=/results/fbt-original.json \
      --scratchbird=/results/fbt-results.json \
      --output=/results/comparison.html
```

## Adding New Tests

To add tests from upstream:

1. Update local clone: `git pull` in `~/CliWork/fbt-repository/`
2. Rebuild test index: `python3 scripts/index-fbt-tests.py`
3. Run new tests: `docker-compose run --rm fbt-runner --new-only`
4. Review failures and update exclusions if needed

## Audit Trail

All test runs produce:
- **Raw results** - Complete test output
- **Diffs** - Line-by-line comparison
- **Metadata** - Versions, timestamps, exclusions
- **Logs** - Full execution logs

Stored in: `results/regression/{date}/{engine}/`
