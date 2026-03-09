# ACID Compliance & Concurrency Tests

Comprehensive transactional integrity testing for ScratchBird.

## Why ACID Tests Are Critical

ScratchBird must guarantee the same transactional properties as native engines:
- **Atomicity**: All-or-nothing transactions
- **Consistency**: Constraint enforcement
- **Isolation**: Proper concurrency control
- **Durability**: Committed data survives

A single ACID violation = data corruption = unusable database.

## Test Coverage

### 1. Atomicity Tests (6 tests)

| Test | Description | Criticality |
|------|-------------|-------------|
| atomic_commit_success | All statements commit together | 🔴 Critical |
| atomic_rollback_on_error | PK violation rolls back entire transaction | 🔴 Critical |
| atomic_explicit_rollback | ROLLBACK undoes all changes | 🔴 Critical |
| atomic_multi_table_commit | Multi-table transaction atomic | 🔴 Critical |
| atomic_savepoint_rollback | Partial rollback via savepoint | 🟡 High |

**Example - Rollback on Error:**
```sql
BEGIN;
INSERT INTO test VALUES (1, 'first');
INSERT INTO test VALUES (1, 'duplicate'); -- PK violation
COMMIT;
-- Result: Table should be EMPTY (transaction rolled back)
```

### 2. Consistency Tests (6 tests)

| Test | Description |
|------|-------------|
| consistency_pk_violation | Primary key prevents duplicates |
| consistency_fk_violation | Foreign key prevents orphans |
| consistency_check_constraint | CHECK constraints enforced |
| consistency_unique_constraint | UNIQUE prevents duplicates |
| consistency_not_null | NOT NULL enforced |
| consistency_invariant_maintenance | Invariants preserved |

**Example - FK Violation:**
```sql
-- Parent table has id=1
INSERT INTO child (child_id, parent_id) VALUES (1, 999);
-- Should FAIL - parent_id 999 doesn't exist
```

### 3. Isolation Tests (5 tests)

| Test | Description | Isolation Level |
|------|-------------|-----------------|
| isolation_dirty_read_prevention | Uncommitted data not visible | READ COMMITTED |
| isolation_non_repeatable_read | Repeatable read guarantees | REPEATABLE READ |
| isolation_phantom_read | Phantom prevention | SERIALIZABLE |
| isolation_lost_update | Concurrent updates safe | Depends |
| isolation_read_committed_default | Default is READ COMMITTED | - |

**Example - Dirty Read Prevention:**
```
Time  Thread 1              Thread 2
----  --------              --------
T1    BEGIN                 
T2    UPDATE row=1          
T3                          BEGIN
T4                          SELECT row=1
T5                          -- Should see OLD value, not UPDATE
T6    ROLLBACK
```

### 4. Durability Tests (3 tests)

| Test | Description |
|------|-------------|
| durability_commit_persistence | Committed data persists |
| durability_rollback_not_persisted | Rolled back data gone |
| durability_visibility_after_commit | New transactions see committed data |

### 5. Locking Tests (5 tests)

| Test | Description |
|------|-------------|
| select_for_update_locking | Exclusive row locks |
| select_for_share_locking | Shared locks |
| nowait_locking | Non-blocking lock attempts |
| skip_locked | Skip locked rows |
| concurrent_reads_no_blocking | Reads don't block reads |

### 6. Deadlock Tests (2 tests)

| Test | Description |
|------|-------------|
| deadlock_two_resources | Classic deadlock detection |
| deadlock_timeout_resolution | Lock timeout handling |

**Example - Deadlock:**
```
Thread 1: Lock A → wait for B
Thread 2: Lock B → wait for A
Result: One thread aborted, other completes
```

### 7. Contention Tests (3 tests)

| Test | Threads | Description |
|------|---------|-------------|
| contention_hot_row | 20 | Single row updated concurrently |
| contention_insert_burst | 10 | High-rate concurrent inserts |
| contention_mixed_workload | 10 | Read/write mix |

### 8. Connection Tests (2 tests)

| Test | Description |
|------|-------------|
| connection_pool_exhaustion | Graceful max connections handling |
| connection_leak_detection | Idle connection cleanup |

## Running ACID Tests

### Single Engine

```bash
cd /home/dcalford/CliWork/ScratchBird-Benchmarks

# Run ACID tests for Firebird
python3 acid-tests/runners/acid_test_runner.py \
  --engine=firebird --host=localhost --port=3050 \
  --database=benchmark --user=benchmark --password=benchmark

# Run for MySQL
python3 acid-tests/runners/acid_test_runner.py \
  --engine=mysql --host=localhost --port=3306 \
  --database=benchmark --user=benchmark --password=benchmark

# Run for PostgreSQL
python3 acid-tests/runners/acid_test_runner.py \
  --engine=postgresql --host=localhost --port=5432 \
  --database=benchmark --user=benchmark --password=benchmark
```

### Concurrent Tests

Some tests require multiple concurrent connections:

```bash
# Run concurrent isolation tests
python3 acid-tests/runners/acid_test_runner.py \
  --engine=postgresql --category=isolation \
  --concurrent-mode --threads=5
```

### All Engines

```bash
# Run all ACID tests for all engines
./acid-tests/scripts/run-acid-tests.sh all
```

## Testing ScratchBird

When ScratchBird is ready:

```bash
# Test SB in Firebird mode
python3 acid-tests/runners/acid_test_runner.py \
  --engine=firebird --host=scratchbird --port=3050 \
  --database=benchmark --user=benchmark --password=benchmark

# Test SB in MySQL mode
python3 acid-tests/runners/acid_test_runner.py \
  --engine=mysql --host=scratchbird --port=3306 \
  --database=benchmark --user=benchmark --password=benchmark

# Test SB in PostgreSQL mode
python3 acid-tests/runners/acid_test_runner.py \
  --engine=postgresql --host=scratchbird --port=5432 \
  --database=benchmark --user=benchmark --password=benchmark
```

## Expected Results

### Passing Criteria

| Category | Tests | Must Pass | Tolerance |
|----------|-------|-----------|-----------|
| Atomicity | 6 | 6 (100%) | Zero tolerance |
| Consistency | 6 | 6 (100%) | Zero tolerance |
| Isolation | 5 | 5 (100%) | Zero tolerance |
| Durability | 3 | 3 (100%) | Zero tolerance |
| Locking | 5 | 4+ (80%) | Minor differences acceptable |
| Deadlock | 2 | 2 (100%) | Zero tolerance |
| Contention | 3 | 2+ (66%) | Performance variance ok |

**ACID failures = Critical bugs that must be fixed.**

## Output Format

```json
{
  "metadata": {
    "engine": "postgresql",
    "host": "localhost",
    "timestamp": "20240308_143022"
  },
  "results": {
    "atomicity": {
      "passed": 6,
      "failed": 0,
      "tests": [
        {
          "name": "atomic_commit_success",
          "status": "passed",
          "duration_ms": 45.2
        }
      ]
    },
    "consistency": { ... },
    "isolation": { ... },
    "durability": { ... }
  },
  "concurrency": {
    "locking": { ... },
    "deadlock": { ... },
    "contention": { ... }
  },
  "summary": {
    "acid_tests_total": 20,
    "acid_tests_passed": 20,
    "concurrency_tests_total": 10,
    "concurrency_tests_passed": 9,
    "overall_score": "96%"
  }
}
```

## Common ACID Failures in Emulation Layers

### 1. Partial Transaction Commit
**Symptom**: Some statements in failed transaction persist.
**Cause**: Auto-commit mode or missing rollback on error.

### 2. Dirty Reads
**Symptom**: Uncommitted data visible to other transactions.
**Cause**: Wrong isolation level or MVCC implementation bug.

### 3. Lost Updates
**Symptom**: Concurrent updates lose data.
**Cause**: Missing row-level locking or optimistic locking failure.

### 4. Constraint Violations
**Symptom**: Duplicate keys, orphaned rows exist.
**Cause**: Constraints not enforced or deferred incorrectly.

### 5. Deadlock Not Detected
**Symptom**: Transactions hang forever.
**Cause**: Missing deadlock detection or timeout.

## Debugging Failed Tests

```bash
# Run single test with verbose output
python3 acid-tests/runners/acid_test_runner.py \
  --engine=postgresql --test=atomic_rollback_on_error --verbose

# Run with transaction logging
python3 acid-tests/runners/acid_test_runner.py \
  --engine=postgresql --log-transactions
```

## CI Integration

```yaml
name: ACID Compliance Tests
on: [push, pull_request]

jobs:
  acid-tests:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        engine: [firebird, mysql, postgresql]
    steps:
      - uses: actions/checkout@v4
      - name: Start engine
        run: docker-compose up -d ${{ matrix.engine }}
      - name: Run ACID tests
        run: |
          python3 acid-tests/runners/acid_test_runner.py \
            --engine=${{ matrix.engine }} \
            --host=localhost \
            --output=results/acid-${{ matrix.engine }}.json
      - name: Check results
        run: |
          PASSED=$(jq '.summary.acid_tests_passed' results/acid-${{ matrix.engine }}.json)
          TOTAL=$(jq '.summary.acid_tests_total' results/acid-${{ matrix.engine }}.json)
          if [ "$PASSED" -ne "$TOTAL" ]; then
            echo "ACID tests failed: $PASSED/$TOTAL passed"
            exit 1
          fi
```

## References

- [ACID Properties (Wikipedia)](https://en.wikipedia.org/wiki/ACID)
- [SQL Isolation Levels (PostgreSQL)](https://www.postgresql.org/docs/current/transaction-iso.html)
- [InnoDB Transaction Model (MySQL)](https://dev.mysql.com/doc/refman/8.0/en/innodb-transaction-model.html)
- [Firebird Transactions](https://firebirdsql.org/file/documentation/html/en/refdocs/fblangref40/firebird-40-language-reference.html#fblangref40-transacs)
