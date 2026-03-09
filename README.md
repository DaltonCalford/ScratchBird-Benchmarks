# ScratchBird Benchmarks

> Comprehensive benchmarking and compatibility testing suite for the ScratchBird multi-engine database emulator.

## Overview

**ScratchBird** is a multi-protocol database engine that emulates FirebirdSQL, MySQL, and PostgreSQL. This repository contains the official benchmark suite used to validate ScratchBird's compatibility, performance, and behavioral accuracy against the native database engines it emulates.

### Purpose

- **Validate Compatibility**: Ensure ScratchBird passes the same tests as native engines
- **Measure Performance**: Compare throughput, latency, and resource usage
- **Verify ACID Compliance**: Test transactional integrity across all modes
- **Detect Emulation Gaps**: Identify where behavior differs from native engines
- **Track Progress**: Monitor improvement over time with versioned results

## Project Status

| Component | Status | Tests |
|-----------|--------|-------|
| Regression Tests | ✅ Complete | 12,000+ |
| Stress Tests | ✅ Complete | 50+ |
| ACID Tests | ✅ Complete | 20 |
| Data Type Tests | ✅ Complete | 30+ |
| DDL Tests | ✅ Complete | 5+ |
| Optimizer Tests | ✅ Complete | 4 |
| Protocol Tests | ✅ Complete | 5 |
| Catalog Tests | ✅ Complete | 5 |
| Performance Tests | ✅ Complete | 6 |
| TPC-C Benchmark | ✅ Complete | 5 transactions |
| TPC-H Benchmark | ✅ Complete | 4 queries |
| Fault Tolerance | ✅ Complete | 9 |
| Engine Differential | ✅ Complete | 33 |
| System Info | ✅ Complete | Auto-collect |
| **Total** | **✅ Ready** | **12,200+** |

## Quick Start

### Prerequisites

- Docker 20.10+
- Docker Compose 2.0+
- Python 3.8+ (for local analysis)
- 8GB+ RAM recommended for large-scale tests

### Start All Engines

```bash
# Clone repository
git clone https://github.com/DaltonCalford/ScratchBird-Benchmarks.git
cd ScratchBird-Benchmarks

# Start all database engines
docker-compose up -d firebird mysql postgresql

# Wait for healthy status
docker-compose ps
```

### Run All Tests

```bash
# Run complete test suite with system info collection
./run-all-tests.sh all all

# Results saved to: ./results/full-test-suite-{timestamp}/
```

### Run with Result Submission

```bash
# Submit results to project server (anonymous)
SUBMIT=true ./run-all-tests.sh all all

# With tags for categorization
SUBMIT=true TAGS="production,aws,r5.xlarge" ./run-all-tests.sh all all

# Authenticated submission
SUBMIT=true API_KEY=your_api_key ./run-all-tests.sh all all
```

## Project Structure

```
ScratchBird-Benchmarks/
│
├── run-all-tests.sh                    # Master test orchestrator
├── docker-compose.yml                  # Engine orchestration
├── TEST_STRATEGY.md                    # Detailed test strategy
├── TEST_COVERAGE.md                    # Complete coverage matrix
│
├── engines/                            # Database engine containers
│   ├── firebird/                       # FirebirdSQL 5.0.1
│   ├── mysql/                          # MySQL 9.0.1
│   ├── postgresql/                     # PostgreSQL 18.0
│   └── scratchbird/                    # Placeholder for SB
│
├── regression-suites/                  # Upstream compatibility tests
│   ├── runners/
│   │   ├── fbt_runner.py              # Firebird FBT test runner
│   │   ├── mysql_test_runner.py       # MySQL mysql-test runner
│   │   ├── pg_regress_runner.py       # PostgreSQL pg_regress runner
│   │   └── compare_results.py         # Cross-engine comparison
│   ├── config/
│   │   ├── firebird-fbt-exclude.txt   # Known failure exclusions
│   │   ├── mysql-test-exclude.txt
│   │   └── postgresql-regress-exclude.txt
│   └── run-regression-suite.sh
│
├── stress-tests/                       # Performance & load tests
│   ├── generators/
│   │   ├── data_generator.py          # Synthetic data generation
│   │   └── sql_dialect.py             # Engine-specific SQL
│   ├── scenarios/
│   │   ├── join_stress_tests.py       # JOIN performance tests
│   │   ├── bulk_operation_tests.py    # INSERT/UPDATE/DELETE stress
│   │   └── dialect_aware_tests.py     # Dialect-specific tests
│   ├── runners/
│   │   ├── stress_test_runner.py
│   │   └── dialect_stress_runner.py   # Uses native SQL dialects
│   └── scripts/
│       ├── run-stress-tests.sh
│       └── run-dialect-stress-tests.sh
│
├── acid-tests/                         # Transaction integrity
│   ├── scenarios/
│   │   ├── transaction_tests.py       # ACID compliance tests
│   │   └── concurrency_tests.py       # Locking & deadlock tests
│   ├── runners/
│   │   └── acid_test_runner.py
│   └── scripts/
│       └── run-acid-tests.sh
│
├── data-type-tests/                    # Edge case testing
│   └── scenarios/
│       └── edge_case_tests.py         # Numeric, string, datetime edge cases
│
├── ddl-tests/                          # Schema operations
│   └── scenarios/
│       └── ddl_tests.py               # CREATE, ALTER, DROP tests
│
├── optimizer-tests/                    # Query optimizer
│   └── scenarios/
│       └── optimizer_tests.py         # Plan stability, cost model
│
├── protocol-tests/                     # Wire protocol
│   └── scenarios/
│       └── protocol_tests.py          # Prepared statements, metadata
│
├── catalog-tests/                      # System tables
│   └── scenarios/
│       └── catalog_tests.py           # information_schema, pg_catalog
│
├── performance-tests/                  # Benchmarking
│   └── scenarios/
│       └── performance_tests.py       # Latency, throughput, scaling
│
├── tpc-c/                              # OLTP benchmark
│   └── scenarios/
│       └── tpc_c_workload.py          # Complete TPC-C implementation
│
├── tpc-h/                              # Analytics benchmark
│   └── scenarios/
│       └── tpc_h_queries.py           # TPC-H analytical queries
│
├── fault-tolerance-tests/              # Recovery testing
│   └── scenarios/
│       └── fault_tests.py             # Crash recovery, resource exhaustion
│
├── engine-differential-tests/          # NEW: Architectural exploitation
│   ├── scenarios/
│   │   ├── mysql_optimized_tests.py   # Tests MySQL excels at
│   │   ├── postgresql_optimized_tests.py # Tests PostgreSQL excels at
│   │   └── firebird_optimized_tests.py   # Tests Firebird excels at
│   ├── runners/
│   │   └── differential_test_runner.py
│   └── scripts/
│       └── run-differential-tests.sh
│
└── system-info/                        # NEW: System collection & submission
    ├── collectors/
    │   └── system_info.py             # Hardware/OS detection
    ├── submit/
    │   └── result_submitter.py        # Result upload to server
    └── README.md
```

## Test Suites Explained

### 1. Regression Tests (`regression-suites/`)

Runs the actual upstream test suites from each database engine:

- **Firebird FBT**: ~7,000 tests from Firebird Test repository
- **MySQL mysql-test**: ~5,000 tests from MySQL source
- **PostgreSQL pg_regress**: ~200 regression tests

Uses the **original test harnesses** to ensure no test bias.

```bash
# Run Firebird FBT
docker-compose --profile fbt run --rm fbt-runner --suite=bugs

# Run MySQL tests
docker-compose --profile mysql-test run --rm mysql-test-runner --suite=funcs_1

# Run PostgreSQL regress
docker-compose --profile pg-regress run --rm pg-regress-runner --schedule=parallel
```

### 2. Stress Tests (`stress-tests/`)

Dialect-aware performance tests using each engine's native SQL:

| Test Category | Count | Description |
|--------------|-------|-------------|
| INNER JOIN | 5 | Simple, conditions, expressions, large results |
| OUTER JOIN | 5 | LEFT, RIGHT, FULL with aggregations |
| CROSS JOIN | 2 | Limited cartesian, aggregated analysis |
| SELF JOIN | 2 | Hierarchical, pairing scenarios |
| Multi-table | 5 | 3, 4, 5 table JOINs |
| Bulk INSERT | 3 | Single transaction, SELECT-based, aggregated |
| Bulk UPDATE | 4 | Simple, JOIN-based, complex calculations |
| Aggregation | 4 | Full scan, multi-dimensional, distinct counts |

```bash
# Run with native dialects
./stress-tests/scripts/run-dialect-stress-tests.sh mysql medium
```

### 3. ACID Tests (`acid-tests/`)

Transactional integrity validation:

| Property | Tests | Key Scenarios |
|----------|-------|---------------|
| **Atomicity** | 6 | Commit/rollback, multi-table, savepoints |
| **Consistency** | 6 | PK, FK, CHECK, UNIQUE, NOT NULL constraints |
| **Isolation** | 5 | Dirty reads, phantom reads, lost updates |
| **Durability** | 3 | Commit persistence, visibility |

```bash
./acid-tests/scripts/run-acid-tests.sh postgresql
```

### 4. Engine Differential Tests (`engine-differential-tests/`)

Tests designed to perform very differently on each engine, exploiting architectural strengths:

**MySQL Wins On:**
- `clustered_pk_range_scan` - Sequential I/O via clustered index (5-20x)
- `covering_index_lookup` - Index-only access (2-5x)
- `secondary_index_insert_buffering` - Change buffer (3-10x)

**PostgreSQL Wins On:**
- `parallel_seq_scan_large_table` - Parallel workers (4-8x)
- `gin_fulltext_search` - GIN index (50-100x)
- `hash_join_large_tables` - O(n+m) vs O(n*m) (10-100x)

**Firebird Wins On:**
- `mga_readers_dont_block` - No read locks (10-100x)
- `mga_rollback_performance` - Instant rollback (100-1000x)
- `storage_compact_nulls` - Bitmap storage (30-50% smaller)

```bash
./engine-differential-tests/scripts/run-differential-tests.sh all all
```

### 5. System Information (`system-info/`)

Automatically collects:

- **CPU**: Model, cores, frequency, cache, flags, virtualization
- **GPU**: Vendor, model, VRAM, CUDA support
- **Memory**: Total/available, type (DDR4/DDR5), speed, swap
- **Disk**: Device, filesystem, space, type (SSD/HDD/NVMe)
- **OS**: Name, version, distribution, kernel, timezone
- **Container**: Docker/Podman/Kubernetes detection
- **Network**: Hostname, IP, MAC address

```bash
# Collect system info
python3 system-info/collectors/system_info.py --output system.json

# Submit results
python3 system-info/submit/result_submitter.py \
  --benchmark results/test.json \
  --system-info system.json \
  --tags production,aws
```

## Usage Examples

### Test Individual Engines

```bash
# Test only MySQL
./run-all-tests.sh all mysql

# Test only ACID compliance on PostgreSQL
./run-all-tests.sh acid postgresql

# Test only TPC-C on all engines
./run-all-tests.sh tpc-c all
```

### Compare Engine Performance

```bash
# Run stress tests on all engines
for engine in firebird mysql postgresql; do
    ./stress-tests/scripts/run-dialect-stress-tests.sh $engine medium
done

# Generate comparison report
python3 stress-tests/scripts/compare-stress-results.py \
  --results-dir ./results/ \
  --output ./comparison.html
```

### Test ScratchBird (When Ready)

```bash
# Test ScratchBird in Firebird mode
./run-all-tests.sh all firebird
# (Tests connect to scratchbird:3050, use Firebird dialect)

# Test ScratchBird in MySQL mode
./run-all-tests.sh all mysql
# (Tests connect to scratchbird:3306, use MySQL dialect)

# Test ScratchBird in PostgreSQL mode
./run-all-tests.sh all postgresql
# (Tests connect to scratchbird:5432, use PostgreSQL dialect)
```

## Interpreting Results

### Result Files

Each test suite generates JSON results:

```json
{
  "metadata": {
    "engine": "postgresql",
    "suite": "acid",
    "timestamp": "20240308_143022",
    "system_info": { ... }
  },
  "results": {
    "atomicity": {"passed": 6, "failed": 0},
    "consistency": {"passed": 6, "failed": 0},
    "isolation": {"passed": 5, "failed": 0},
    "durability": {"passed": 3, "failed": 0}
  },
  "summary": {
    "total_tests": 20,
    "passed": 20,
    "failed": 0,
    "score": "100%"
  }
}
```

### Good ScratchBird Emulation

A properly emulating ScratchBird should show:

- ✅ **Similar pass/fail patterns** on regression tests
- ✅ **Similar relative performance** on stress tests
- ✅ **Same architectural advantages** on differential tests
- ✅ **Identical ACID behavior** on transaction tests

### Warning Signs

If ScratchBird shows these patterns, emulation needs work:

- ⚠️ **Uniform performance** - Same speed on all tests (generic implementation)
- ⚠️ **Opposite patterns** - Fast where native is slow, slow where native is fast
- ⚠️ **Missing advantages** - No exploitation of engine-specific features

## CI/CD Integration

### GitHub Actions

```yaml
name: Benchmark & Submit
on: [push, pull_request]

jobs:
  benchmark:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Start engines
        run: docker-compose up -d firebird mysql postgresql
      
      - name: Run benchmarks
        run: ./run-all-tests.sh all all
        env:
          SUBMIT: true
          API_KEY: ${{ secrets.SCRATCHBIRD_API_KEY }}
          TAGS: "ci,github-actions,${{ matrix.os }}"
      
      - name: Upload artifacts
        uses: actions/upload-artifact@v4
        with:
          name: benchmark-results
          path: results/
```

### GitLab CI

```yaml
benchmark:
  script:
    - docker-compose up -d firebird mysql postgresql
    - ./run-all-tests.sh all all
  variables:
    SUBMIT: "true"
    API_KEY: $SCRATCHBIRD_API_KEY
    TAGS: "ci,gitlab,production"
  artifacts:
    paths:
      - results/
```

## Architecture

### Container Strategy

```
┌─────────────────────────────────────────────────────────────┐
│                    Test Orchestrator                        │
│         (Python harness with engine clients)                │
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
   │ScratchBird│Firebird │   MySQL   │
   │Firebird │ │  Mode   │ │  Mode   │
   │  Mode   │ └─────────┘ └─────────┘
   └─────────┘
```

### Dialect Awareness

Each engine is tested with its **native SQL dialect**:

| Feature | Firebird | MySQL | PostgreSQL |
|---------|----------|-------|------------|
| String concat | `\|\|` | `CONCAT()` | `\|\|` |
| LIMIT | `ROWS 1 TO n` | `LIMIT offset,count` | `LIMIT n OFFSET offset` |
| Date truncation | Extract/reconstruct | `DATE_FORMAT()` | `DATE_TRUNC()` |
| Placeholders | `?` | `%s` | `%s` |
| Boolean | `1/0` | `TRUE/FALSE` | `TRUE/FALSE` |

This ensures fair comparison - each engine uses its optimal syntax.

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-test`)
3. Add your test to the appropriate suite
4. Ensure tests run in containers
5. Submit a pull request with baseline results

See [TEST_STRATEGY.md](TEST_STRATEGY.md) for detailed guidelines.

## License

Initial Developer's Public License Version 1.0 (IDPL) - Same as ScratchBird

## Links

- **Repository**: https://github.com/DaltonCalford/ScratchBird-Benchmarks
- **ScratchBird Project**: [Link when available]
- **Test Results Dashboard**: https://benchmarks.scratchbird.io
- **Issue Tracker**: https://github.com/DaltonCalford/ScratchBird-Benchmarks/issues

## Contact

- **Issues**: [GitHub Issues](https://github.com/DaltonCalford/ScratchBird-Benchmarks/issues)
- **Discussions**: [GitHub Discussions](https://github.com/DaltonCalford/ScratchBird-Benchmarks/discussions)

---

**Status**: ✅ **12,200+ tests ready for ScratchBird validation**
