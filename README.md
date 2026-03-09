# ScratchBird Comparative Benchmark Suite

A comprehensive benchmarking framework for comparing ScratchBird database engine against FirebirdSQL, MySQL, and PostgreSQL.

## Overview

This suite provides:
- **Containerized test environments** for consistent, reproducible results
- **Version tracking** - Every benchmark run captures exact engine versions
- **Multiple test categories** - Compatibility, performance, and **upstream regression tests**
- **Automated reporting** - JSON results with trend analysis and HTML reports

## Quick Start

### Prerequisites
- Docker 20.10+
- Docker Compose 2.0+
- Python 3.11+ (for local result analysis)
- Local clones of upstream test repositories:
  - `~/CliWork/fbt-repository/` - Firebird Test Suite
  - `~/CliWork/mysql-server/` - MySQL source (with mysql-test)
  - `~/CliWork/postgresql/` - PostgreSQL source (with pg_regress)

### Start All Engines
```bash
# Start all database engines
docker-compose up -d firebird mysql postgresql

# Wait for engines to be healthy (usually 30-60 seconds)
docker-compose ps

# Collect version information
./scripts/collect-all-versions.sh ./results
```

### Run Upstream Regression Tests

The benchmark suite can run the **complete upstream test suites** from each database engine:

```bash
# Run Firebird FBT tests against original Firebird
docker-compose --profile fbt run --rm fbt-runner \
  --target=original --suite=bugs --limit=100

# Run MySQL mysql-test against original MySQL
docker-compose --profile mysql-test run --rm mysql-test-runner \
  --target=original --suite=funcs_1 --limit=50

# Run PostgreSQL regression tests
docker-compose --profile pg-regress run --rm pg-regress-runner \
  --target=original --schedule=parallel
```

See [regression-suites/README.md](regression-suites/README.md) for detailed documentation.

### Run Performance Benchmarks
```bash
# Run full benchmark suite
docker-compose up benchmark-runner

# Or run specific engine tests
./scripts/run-benchmarks.sh --engine=firebird --suite=micro
./scripts/run-benchmarks.sh --engine=mysql --suite=concurrent
./scripts/run-benchmarks.sh --engine=postgresql --suite=regression
```

### View Results
```bash
# Check version information
cat results/version-summary.txt

# View JSON results
cat results/all-versions.json

# Generate HTML comparison report (after running against both original and ScratchBird)
python3 regression-suites/runners/compare_results.py \
  --original=results/fbt_results_original_*.json \
  --scratchbird=results/fbt_results_scratchbird_*.json \
  --output=results/comparison.html
```

## Engine Versions

The benchmark suite tracks exact versions of each engine:

| Engine | Current Version | Image Tag |
|--------|-----------------|-----------|
| FirebirdSQL | 5.0.1 | `jacobalberty/firebird:v5.0.1` |
| MySQL | 9.0.1 | `mysql:9.0.1` |
| PostgreSQL | 18.0 | `postgres:18.0` |

Version information is collected automatically and stored in:
- `results/all-versions.json` - Full JSON metadata
- `results/version-summary.txt` - Human-readable summary

### Version Collection

Each engine provides detailed version info:

**FirebirdSQL:**
- Engine version (major.minor.patch)
- ODS (On-Disk Structure) version
- Page size
- Database dialect

**MySQL:**
- Server version
- InnoDB version
- SQL mode
- Character set and collation

**PostgreSQL:**
- Server version
- Block size
- Shared buffers
- Locale settings

## Upstream Regression Tests

This benchmark suite integrates with the **official upstream test suites** from each database engine:

| Test Suite | Local Path | Test Count | Runner |
|------------|------------|------------|--------|
| Firebird FBT | `~/CliWork/fbt-repository/` | ~7,000 tests | `fbt_runner.py` |
| MySQL mysql-test | `~/CliWork/mysql-server/mysql-test/` | ~5,000 tests | `mysql_test_runner.py` |
| PostgreSQL pg_regress | `~/CliWork/postgresql/src/test/regress/` | ~200 tests | `pg_regress_runner.py` |

### Key Principle: Use Original Test Harnesses

We use the **original test formats and clients** to ensure:
- **Auditable results** - Anyone can reproduce using upstream tools
- **No test bias** - We're not rewriting tests to favor ScratchBird
- **Real edge cases** - Thousands of community-discovered bugs

### Running Against ScratchBird

Once ScratchBird is running:

```bash
# Run Firebird FBT against ScratchBird in Firebird mode
docker-compose --profile fbt run --rm fbt-runner \
  --target=scratchbird --mode=firebird --suite=all

# Run MySQL tests against ScratchBird in MySQL mode
docker-compose --profile mysql-test run --rm mysql-test-runner \
  --target=scratchbird --mode=mysql --suite=all

# Run PostgreSQL tests against ScratchBird in PostgreSQL mode
docker-compose --profile pg-regress run --rm pg-regress-runner \
  --target=scratchbird --mode=postgresql --schedule=parallel
```

### Test Result Categories

| Result | Meaning |
|--------|---------|
| **PASS** | ScratchBird output matches original exactly |
| **PASS_EQUIVALENT** | Output semantically equivalent (minor formatting) |
| **FAIL_COMPAT** | Different output but acceptable (documented difference) |
| **FAIL_BUG** | ScratchBird bug - needs fixing |
| **SKIP_UNSUPPORTED** | Feature not supported in ScratchBird |

See [regression-suites/README.md](regression-suites/README.md) for full details.

## Project Structure

```
.
├── engines/                    # Database engine configurations
│   ├── firebird/              # FirebirdSQL 5.0.1
│   ├── mysql/                 # MySQL 9.0.1
│   ├── postgresql/            # PostgreSQL 18.0
│   └── scratchbird/           # ScratchBird (when ready)
├── test-suites/               # Custom test definitions
│   ├── sql-standard/          # ANSI SQL compatibility
│   ├── performance/           # Performance benchmarks
│   └── concurrent/            # Concurrent workload tests
├── regression-suites/         # Upstream test integration
│   ├── runners/               # Test runners (fbt_runner.py, etc.)
│   ├── config/                # Exclusion lists
│   ├── README.md              # Detailed documentation
│   └── run-regression-suite.sh # Orchestration script
├── scripts/                   # Benchmark harness
│   ├── collect-all-versions.sh
│   ├── run-benchmarks.sh
│   └── benchmark_runner.py
├── results/                   # Benchmark output (git-ignored)
└── docs/                      # Documentation
```

## Benchmark Categories

### 1. Upstream Regression Tests
Run the complete upstream test suites:
- **Firebird FBT** - Bug regression and functional tests
- **MySQL mysql-test** - Official MySQL test suite
- **PostgreSQL pg_regress** - PostgreSQL regression tests

### 2. Compatibility Tests
Verify ScratchBird's emulation accuracy:
- Parse compatibility - Does SQL parse correctly?
- Semantic compatibility - Does metadata match?
- Behavioral compatibility - Do queries return same results?

### 3. Performance Tests
Measure and compare performance:
- **Micro-benchmarks** - Single operations (INSERT, SELECT, UPDATE)
- **Macro-benchmarks** - Complex queries (JOINs, aggregations)
- **Concurrent tests** - Multi-user workloads

## Adding ScratchBird

When ScratchBird is ready for benchmarking:

1. Create `engines/scratchbird/Dockerfile`
2. Add service to `docker-compose.yml`
3. Implement version collection script
4. Run regression tests to establish baseline
5. Run comparative benchmarks

### ScratchBird Configuration

```yaml
scratchbird:
  build:
    context: ./engines/scratchbird
  container_name: sb-benchmark-scratchbird
  ports:
    - "3050:3050"  # Firebird wire protocol
    - "3306:3306"  # MySQL protocol
    - "5432:5432"  # PostgreSQL protocol
  environment:
    - SB_MODE=auto  # Auto-detect from client
    - SB_DATABASE=benchmark
  networks:
    - benchmark-net
```

## CI/CD Integration

GitHub Actions workflow (`.github/workflows/benchmark.yml`):

```yaml
name: Weekly Benchmark
on:
  schedule:
    - cron: '0 0 * * 0'  # Weekly on Sunday
  workflow_dispatch:

jobs:
  regression-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Start engines
        run: docker-compose up -d firebird mysql postgresql
      
      - name: Run Firebird FBT
        run: |
          docker-compose --profile fbt run --rm fbt-runner \
            --target=original --suite=all --output-dir=/results
      
      - name: Run MySQL Tests
        run: |
          docker-compose --profile mysql-test run --rm mysql-test-runner \
            --target=original --suite=all --output-dir=/results
      
      - name: Run PostgreSQL Tests
        run: |
          docker-compose --profile pg-regress run --rm pg-regress-runner \
            --target=original --schedule=parallel --output-dir=/results
      
      - name: Upload results
        uses: actions/upload-artifact@v4
        with:
          name: regression-results
          path: results/
```

## Interpreting Results

Each benchmark run produces:

1. **Version metadata** - Exact engine versions tested
2. **Test results** - Pass/fail status for each test
3. **Performance metrics** - Timing, throughput, resource usage
4. **Comparison reports** - Original vs ScratchBird differences

### Regression Test Comparison

Results show how ScratchBird compares to original engines:

```
Test Suite: Firebird FBT (1,000 tests sampled)
┌───────────────┬──────────┬─────────────┐
│ Category      │ Count    │ Percentage  │
├───────────────┼──────────┼─────────────┤
│ PASS          │ 847      │ 84.7%       │
│ PASS_EQUIVALENT│ 89      │ 8.9%        │
│ FAIL_BUG      │ 42       │ 4.2%        │
│ SKIP_UNSUPPORTED│ 22     │ 2.2%        │
└───────────────┴──────────┴─────────────┘
Success Rate: 93.6%
```

### Performance Comparison

Results are normalized to show relative performance:

```
Operation         | Firebird | MySQL | PostgreSQL | ScratchBird-FB
------------------|----------|-------|------------|---------------
Single INSERT     | 1.00x    | 0.95x | 0.88x      | 0.92x
Point SELECT      | 1.00x    | 1.12x | 1.05x      | 0.98x
Simple JOIN       | 1.00x    | 0.89x | 1.15x      | 0.94x
```

A value of `0.92x` means ScratchBird-Firebird mode is 92% as fast as native Firebird (8% overhead).

## Contributing

1. Fork the repository
2. Add test cases to `test-suites/` or upstream test integrations
3. Ensure tests run in containers
4. Submit pull request with results

## License

Initial Developer's Public License Version 1.0 (IDPL) - Same as ScratchBird

## Contact

- Issues: [GitHub Issues](https://github.com/DaltonCalford/ScratchBird-Benchmarks/issues)
- Discussions: [GitHub Discussions](https://github.com/DaltonCalford/ScratchBird-Benchmarks/discussions)
