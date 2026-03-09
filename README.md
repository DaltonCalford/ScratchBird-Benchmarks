# ScratchBird Comparative Benchmark Suite

A comprehensive benchmarking framework for comparing ScratchBird database engine against FirebirdSQL, MySQL, and PostgreSQL.

## Overview

This suite provides:
- **Containerized test environments** for consistent, reproducible results
- **Version tracking** - Every benchmark run captures exact engine versions
- **Multiple test categories** - Compatibility, performance, and regression tests
- **Automated reporting** - JSON results with trend analysis

## Quick Start

### Prerequisites
- Docker 20.10+
- Docker Compose 2.0+
- Python 3.11+ (for local result analysis)

### Start All Engines
```bash
# Start all database engines
docker-compose up -d firebird mysql postgresql

# Wait for engines to be healthy (usually 30-60 seconds)
docker-compose ps

# Collect version information
./scripts/collect-all-versions.sh ./results
```

### Run Benchmarks
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

# Generate HTML report
python3 scripts/generate-report.py results/
```

## Engine Versions

The benchmark suite tracks exact versions of each engine:

| Engine | Current Version | Image Tag |
|--------|-----------------|-----------|
| FirebirdSQL | 4.0.4 | `jacobalberty/firebird:v4.0.4` |
| MySQL | 8.0.36 | `mysql:8.0.36` |
| PostgreSQL | 16.1 | `postgres:16.1` |

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

## Project Structure

```
.
├── engines/                    # Database engine configurations
│   ├── firebird/              # FirebirdSQL 4.0.4
│   ├── mysql/                 # MySQL 8.0.36
│   ├── postgresql/            # PostgreSQL 16.1
│   └── scratchbird/           # ScratchBird (when ready)
├── test-suites/               # Test definitions
│   ├── sql-standard/          # ANSI SQL compatibility
│   ├── performance/           # Performance benchmarks
│   └── concurrent/            # Concurrent workload tests
├── scripts/                   # Benchmark harness
│   ├── collect-all-versions.sh
│   ├── run-benchmarks.sh
│   └── benchmark_runner.py
├── results/                   # Benchmark output (git-ignored)
└── docs/                      # Documentation
```

## Benchmark Categories

### 1. Compatibility Tests
Verify ScratchBird's emulation accuracy:
- Parse compatibility - Does SQL parse correctly?
- Semantic compatibility - Does metadata match?
- Behavioral compatibility - Do queries return same results?

### 2. Performance Tests
Measure and compare performance:
- **Micro-benchmarks** - Single operations (INSERT, SELECT, UPDATE)
- **Macro-benchmarks** - Complex queries (JOINs, aggregations)
- **Concurrent tests** - Multi-user workloads

### 3. Regression Tests
Selected tests from upstream test suites:
- Firebird FBT (Firebird Test Suite)
- MySQL mysql-test
- PostgreSQL pg_regress

## Adding ScratchBird

When ScratchBird is ready for benchmarking:

1. Create `engines/scratchbird/Dockerfile`
2. Add service to `docker-compose.yml`
3. Implement version collection script
4. Run comparative benchmarks

## CI/CD Integration

GitHub Actions workflow (`.github/workflows/benchmark.yml`):

```yaml
name: Weekly Benchmark
on:
  schedule:
    - cron: '0 0 * * 0'  # Weekly on Sunday
  workflow_dispatch:

jobs:
  benchmark:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Start engines
        run: docker-compose up -d
      - name: Run benchmarks
        run: docker-compose up benchmark-runner
      - name: Upload results
        uses: actions/upload-artifact@v3
        with:
          name: benchmark-results
          path: results/
```

## Interpreting Results

Each benchmark run produces:

1. **Version metadata** - Exact engine versions tested
2. **Performance metrics** - Timing, throughput, resource usage
3. **Compatibility scores** - Pass/fail rates by category
4. **Trend analysis** - Comparison with previous runs

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
2. Add test cases to `test-suites/`
3. Ensure tests run in containers
4. Submit pull request with results

## License

Initial Developer's Public License Version 1.0 (IDPL) - Same as ScratchBird

## Contact

- Issues: [GitHub Issues](https://github.com/yourusername/scratchbird-benchmarks/issues)
- Discussions: [GitHub Discussions](https://github.com/yourusername/scratchbird-benchmarks/discussions)
