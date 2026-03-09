# Engine Differential Tests

Tests that exploit architectural differences between database engines to reveal where each performs best and worst.

## Why Differential Tests?

Different database engines have fundamentally different architectures:

| Engine | Core Architecture | Key Strengths |
|--------|------------------|---------------|
| **MySQL/InnoDB** | Clustered indexes, buffer pool | PK scans, covering indexes, caching |
| **PostgreSQL** | Heap tables, parallel execution | Parallel query, advanced indexes, hash joins |
| **Firebird** | Multi-generational (MGA) | Read concurrency, compact storage, versioning |

These tests are designed to:
- **Exploit strengths** - Run queries that are optimal for each engine's architecture
- **Reveal weaknesses** - Show where each engine struggles compared to others
- **Validate emulation** - Ensure ScratchBird matches native behavior in each mode

## Test Categories

### MySQL-Optimized Tests (scenarios/mysql_optimized_tests.py)

Tests where MySQL should win big due to its clustered primary key design:

| Test | MySQL Advantage | Expected Factor |
|------|-----------------|-----------------|
| `clustered_pk_range_scan` | Data stored in PK order = sequential I/O | **5-20x** faster |
| `clustered_pk_prefix_scan` | Recent data physically together | **3-10x** faster |
| `covering_index_lookup` | Secondary indexes include PK (no heap access) | **2-5x** faster |
| `secondary_index_covering_count` | COUNT(*) via any secondary index | **3-8x** faster |
| `repeated_hot_page_access` | Buffer pool + adaptive hash index | **2-4x** faster |
| `point_select_pk_buffer_efficiency` | Adaptive hash index acceleration | **2-3x** faster |
| `secondary_index_insert_buffering` | Change buffer defers index updates | **3-10x** faster |
| `sequential_pk_insert_performance` | Append-only clustered index | **2-5x** faster |

**Why PostgreSQL/Firebird are slower:**
- PostgreSQL: Heap tables require random I/O for PK lookups
- Firebird: Pointer-based record access for index lookups

### PostgreSQL-Optimized Tests (scenarios/postgresql_optimized_tests.py)

Tests where PostgreSQL wins due to parallel execution and advanced features:

| Test | PostgreSQL Advantage | Expected Factor |
|------|---------------------|-----------------|
| `parallel_seq_scan_large_table` | 4-8 workers scan table simultaneously | **4-8x** faster |
| `parallel_hash_join` | Parallel hash table build | **3-6x** faster |
| `parallel_bitmap_heap_scan` | Parallel bitmap index access | **3-5x** faster |
| `gin_fulltext_search` | GIN index for tsvector | **50-100x** faster |
| `gist_range_queries` | GiST index for range overlap | **10-50x** faster |
| `brin_warehouse_scan` | Block Range Index (tiny size) | **5-20x** smaller index |
| `partial_index_selective` | Index only active rows (tiny) | **10-20x** smaller |
| `hash_join_large_tables` | O(n+m) hash join vs O(n*m) nested loop | **10-100x** faster |
| `merge_join_sorted` | Merge join on sorted data | **5-10x** faster |
| `toast_large_column_scan` | Out-of-line large column storage | **2-5x** faster |
| `hot_update_frequent` | Heap-only tuple updates | **3-10x** faster |

**Why MySQL/Firebird are slower:**
- MySQL: Limited parallel query, mostly nested loop joins
- Firebird: No parallel execution, nested loop only

### Firebird-Optimized Tests (scenarios/firebird_optimized_tests.py)

Tests where Firebird wins due to multi-generational architecture:

| Test | Firebird Advantage | Expected Factor |
|------|-------------------|-----------------|
| `mga_readers_dont_block` | No read locks, consistent snapshot | **10-100x** under contention |
| `mga_long_running_read` | Snapshot isolated, writes proceed | No blocking vs vacuum blocking |
| `mga_rollback_performance` | Discard versions = instant rollback | **100-1000x** faster |
| `concurrent_read_heavy` | Linear scaling with readers | **5-10x** at 100+ readers |
| `concurrent_write_heavy` | Versioning handles conflicts | **2-5x** concurrent writes |
| `storage_compact_nulls` | Bitmap NULLs + RLE compression | **30-50%** smaller |
| `storage_index_compression` | Prefix compression in indexes | **50-70%** smaller indexes |
| `index_selective_bitmap` | Bitmap AND of compressed indexes | **2-3x** faster |
| `index_navigational` | Bidirectional index cursors | **5-10x** for pagination |

**Why MySQL/PostgreSQL are slower:**
- MySQL: Read locks (even shared) have overhead
- PostgreSQL: Long queries block vacuum, cause bloat

## Running Tests

### Run All Differential Tests

```bash
./engine-differential-tests/scripts/run-differential-tests.sh all all
```

### Run for Specific Engine

```bash
./engine-differential-tests/scripts/run-differential-tests.sh mysql all
./engine-differential-tests/scripts/run-differential-tests.sh postgresql all
./engine-differential-tests/scripts/run-differential-tests.sh firebird all
```

### Run Specific Category

```bash
# Test only MySQL-optimized scenarios
./engine-differential-tests/scripts/run-differential-tests.sh all mysql

# Test only PostgreSQL-optimized scenarios  
./engine-differential-tests/scripts/run-differential-tests.sh all postgresql

# Test only Firebird-optimized scenarios
./engine-differential-tests/scripts/run-differential-tests.sh all firebird
```

### Direct Python Execution

```bash
python3 engine-differential-tests/runners/differential_test_runner.py \
  --engine=mysql --host=localhost --port=3306 \
  --database=benchmark --user=benchmark --password=benchmark \
  --category=mysql --output-dir=./results
```

## Testing ScratchBird

When ScratchBird is ready, run these tests to validate emulation:

```bash
# Test ScratchBird in Firebird mode
# Expected: Should match Firebird's performance characteristics
./engine-differential-tests/scripts/run-differential-tests.sh firebird all
# (Against ScratchBird:3050, --engine=firebird)

# Test ScratchBird in MySQL mode
# Expected: Should match MySQL's performance characteristics
./engine-differential-tests/scripts/run-differential-tests.sh mysql all
# (Against ScratchBird:3306, --engine=mysql)

# Test ScratchBird in PostgreSQL mode
# Expected: Should match PostgreSQL's performance characteristics
./engine-differential-tests/scripts/run-differential-tests.sh postgresql all
# (Against ScratchBird:5432, --engine=postgresql)
```

## Interpreting Results

### Good ScratchBird Emulation

If ScratchBird properly emulates an engine, it should show:
- **Similar relative performance** - Fast on same tests as native engine
- **Similar access patterns** - Same query plans and I/O patterns
- **Similar scaling** - Same behavior under concurrency

### Warning Signs

If ScratchBird shows these patterns, emulation needs work:
- **Uniform performance** - Same speed on all tests (indicates generic implementation)
- **Opposite pattern** - Fast where native is slow, slow where native is fast
- **No advantage** - Missing the architectural advantages of the emulated engine

## Example Results

### MySQL Test on Native MySQL
```
clustered_pk_range_scan: 450ms  ✓ (expected: fast)
covering_index_lookup: 120ms    ✓ (expected: fast)
parallel_seq_scan: 8200ms       ✓ (expected: slow - no parallelism)
```

### PostgreSQL Test on Native PostgreSQL
```
parallel_seq_scan: 1100ms       ✓ (expected: fast - parallel workers)
gin_fulltext_search: 85ms       ✓ (expected: fast - GIN index)
clustered_pk_range_scan: 3200ms ✓ (expected: slower - heap tables)
```

### Firebird Test on Native Firebird
```
mga_readers_dont_block: 450ms   ✓ (expected: fast - no read locks)
storage_compact_nulls: 30% smaller ✓ (expected: compact)
parallel_seq_scan: 8500ms       ✓ (expected: slow - no parallelism)
```

## Test Files

```
engine-differential-tests/
├── scenarios/
│   ├── mysql_optimized_tests.py      # 10 MySQL-specific tests
│   ├── postgresql_optimized_tests.py # 11 PostgreSQL-specific tests
│   └── firebird_optimized_tests.py   # 12 Firebird-specific tests
├── runners/
│   └── differential_test_runner.py   # Test execution engine
├── scripts/
│   └── run-differential-tests.sh     # Orchestration script
└── README.md                          # This file
```

## Architecture Comparison Summary

| Feature | MySQL | PostgreSQL | Firebird |
|---------|-------|------------|----------|
| **Table Storage** | Clustered (PK order) | Heap (unordered) | Heap + pointer pages |
| **Index Type** | B+tree (clustered) | B-tree (heap ref) | B-tree (compressed) |
| **Parallel Query** | Limited | Extensive | None |
| **Join Types** | Nested loop, Hash | Hash, Merge, Nested | Nested loop only |
| **Advanced Indexes** | Full-text | GiST, GIN, BRIN, SP-GiST | Standard B-tree |
| **Concurrency** | MVCC with locks | MVCC with snapshots | MGA (versioning) |
| **Read Blocking** | Possible (gap locks) | None | Never |
| **Compact Storage** | Good | Moderate | Excellent |
| **Large Objects** | External pages | TOAST | Blob segments |
| **Rollback Speed** | Undo log replay | Mark dead tuples | Discard versions |

## References

- MySQL/InnoDB: https://dev.mysql.com/doc/refman/8.0/en/innodb-index-types.html
- PostgreSQL: https://www.postgresql.org/docs/current/indexes-types.html
- Firebird: https://firebirdsql.org/file/documentation/html/en/refdocs/fblangref40/firebird-40-language-reference.html
