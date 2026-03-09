# ScratchBird Stress Test Suite

Comprehensive stress testing with **dialect-specific SQL** for fair cross-engine comparison.

## Key Feature: Native Dialect Testing

Unlike generic SQL tests, this suite generates **engine-specific SQL**:

| Feature | FirebirdSQL | MySQL | PostgreSQL |
|---------|-------------|-------|------------|
| String concat | `\|\|` | `CONCAT()` | `\|\|` |
| Date truncation | Extract/Reconstruct | `DATE_FORMAT()` | `DATE_TRUNC()` |
| LIMIT | `ROWS 1 TO n` | `LIMIT offset, count` | `LIMIT count OFFSET offset` |
| Window functions | `OVER()` | `OVER()` | `OVER()` |
| Placeholders | `?` | `%s` | `%s` |
| Decimal type | `DECIMAL` | `DECIMAL` | `NUMERIC` |

This ensures each engine is tested with its **optimal native syntax**.

## Test Categories

### Data Scales

| Scale | Customers | Products | Orders | Order Items | Total Rows |
|-------|-----------|----------|--------|-------------|------------|
| small | 10,000 | 5,000 | 50,000 | 200,000 | 265,000 |
| medium | 100,000 | 50,000 | 500,000 | 2,000,000 | 2,650,000 |
| large | 1,000,000 | 500,000 | 5,000,000 | 20,000,000 | 26,500,000 |
| huge | 10,000,000 | 2,000,000 | 50,000,000 | 200,000,000 | 262,000,000 |

### JOIN Stress Tests (Dialect-Aware)

| Test | Firebird | MySQL | PostgreSQL |
|------|----------|-------|------------|
| inner_join_simple | ✓ | ✓ | ✓ |
| inner_join_large_result | ✓ | ✓ | ✓ |
| left_join_all_customers | `\|\|` concat | `CONCAT()` | `\|\|` concat |
| four_table_join | ✓ | ✓ | ✓ |
| self_join_same_country | `FIRST n` | `LIMIT` | `LIMIT` |
| aggregation_daily_sales | Reconstructed date | `DATE_FORMAT` | `DATE_TRUNC` |
| window_function_ranking | `OVER()` | `OVER()` | `OVER()` |
| multi_dimensional_agg | `EXTRACT()` | `EXTRACT()` | `EXTRACT()` |

### Bulk Operation Tests (Dialect-Aware)

| Test | Description |
|------|-------------|
| bulk_insert_select | INSERT with generated data using dialect-specific functions |
| bulk_update_with_case | UPDATE with CASE using native syntax |
| bulk_update_with_join | UPDATE with subquery (dialect-optimized) |
| agg_full_table_scan | Aggregation with `STDDEV_SAMP` vs `STDDEV` |
| agg_distinct_counts | Count distinct across tables |
| nested_subquery_agg | Nested subqueries with aggregation |

## Quick Start

### Run All Engines with Native Dialects

```bash
cd /home/dcalford/CliWork/ScratchBird-Benchmarks

# Run stress tests for all engines with medium dataset
./stress-tests/scripts/run-dialect-stress-tests.sh all medium

# Run for specific engine
./stress-tests/scripts/run-dialect-stress-tests.sh firebird medium
./stress-tests/scripts/run-dialect-stress-tests.sh mysql large
./stress-tests/scripts/run-dialect-stress-tests.sh postgresql small
```

### Direct Python Execution with Dialect

```bash
cd /home/dcalford/CliWork/ScratchBird-Benchmarks/stress-tests

# Install dependencies
pip install pymysql psycopg2-binary fdb firebird-driver

# Run with dialect-specific SQL
python3 runners/dialect_stress_runner.py \
  --engine=postgresql --host=localhost --port=5432 \
  --database=benchmark --user=benchmark --password=benchmark \
  --scale=medium --output-dir=./results

# The runner automatically uses PostgreSQL dialect for PostgreSQL engine
```

## Dialect System

### SQL Dialect Classes

Located in `generators/sql_dialect.py`:

```python
class FirebirdDialect(SQLDialect):
    def string_concat(self, *args):
        return " || ".join(args)  # Firebird uses ||
    
    def date_trunc(self, field, expression):
        # Firebird reconstructs date from parts
        return "CAST(EXTRACT(YEAR FROM date) || '-' || ... AS DATE)"
    
    def limit_clause(self, count, offset=None):
        return f"ROWS {offset+1} TO {count}"  # Firebird ROWS syntax

class MySQLDialect(SQLDialect):
    def string_concat(self, *args):
        return "CONCAT(" + ", ".join(args) + ")"  # MySQL uses CONCAT()
    
    def date_trunc(self, field, expression):
        return f"DATE_FORMAT({expression}, '%Y-%m-01')"  # MySQL DATE_FORMAT
    
    def limit_clause(self, count, offset=None):
        return f"LIMIT {offset}, {count}"  # MySQL LIMIT syntax
```

### Dialect-Specific SQL Generation

Example: String concatenation in different dialects:

```python
# Generic test definition
test = {
    'name': 'left_join_all_customers',
    'sql_generator': lambda g: f"""
        SELECT c.customer_id, {g.d.string_concat("c.first_name", "' '", "c.last_name")} as full_name
        FROM customers c
        LEFT JOIN orders o ON c.customer_id = o.customer_id
    """
}

# Generates:
# Firebird: SELECT c.customer_id, c.first_name || ' ' || c.last_name as full_name
# MySQL:    SELECT c.customer_id, CONCAT(c.first_name, ' ', c.last_name) as full_name  
# PostgreSQL: SELECT c.customer_id, c.first_name || ' ' || c.last_name as full_name
```

## Verification

Every test includes dialect-aware verification:

```sql
-- Firebird: Uses || for string concat
SELECT COUNT(*) FROM orders WHERE status || '_test' = 'pending_test';

-- MySQL: Uses CONCAT
SELECT COUNT(*) FROM orders WHERE CONCAT(status, '_test') = 'pending_test';
```

## Output Format

Results include the dialect used:

```json
{
  "metadata": {
    "engine": "mysql",
    "dialect": "mysql",
    "host": "localhost",
    "timestamp": "20240308_143022"
  },
  "test_results": [
    {
      "test_name": "left_join_all_customers",
      "status": "passed",
      "duration_ms": 1245.3,
      "sql_executed": "SELECT c.customer_id, CONCAT(c.first_name, ' ', c.last_name)..."
    }
  ]
}
```

## Comparing Engines Fairly

The dialect-aware testing ensures:

1. **Apples-to-apples comparison** - Each engine uses its optimal syntax
2. **No translation overhead** - No middleware converting SQL
3. **Real-world performance** - Tests match actual production usage
4. **Fair to ScratchBird** - ScratchBird can use native dialect for each mode

## Usage with ScratchBird

When testing ScratchBird:

```bash
# Test ScratchBird in Firebird mode (uses Firebird dialect)
python3 runners/dialect_stress_runner.py \
  --engine=firebird --host=scratchbird --port=3050 \
  --database=benchmark --user=benchmark --password=benchmark \
  --scale=medium

# Test ScratchBird in MySQL mode (uses MySQL dialect)
python3 runners/dialect_stress_runner.py \
  --engine=mysql --host=scratchbird --port=3306 \
  --database=benchmark --user=benchmark --password=benchmark \
  --scale=medium

# Test ScratchBird in PostgreSQL mode (uses PostgreSQL dialect)
python3 runners/dialect_stress_runner.py \
  --engine=postgresql --host=scratchbird --port=5432 \
  --database=benchmark --user=benchmark --password=benchmark \
  --scale=medium
```

## Adding New Dialect-Specific Tests

1. Add SQL generator to `StressTestSQLGenerator` class:

```python
def my_new_test(self) -> str:
    # Use self.d (dialect) for engine-specific syntax
    concat = self.d.string_concat("col1", "col2")
    date_trunc = self.d.date_trunc('MONTH', 'date_col')
    
    return f"""
        SELECT {concat}, {date_trunc}
        FROM my_table
        {self.d.limit_clause(100)}
    """
```

2. Add test definition:

```python
DialectAwareTest(
    name="my_new_test",
    description="My test description",
    sql_generator=lambda g: g.my_new_test(),
    timeout_seconds=300,
)
```

## Troubleshooting

### Dialect Errors

If you see SQL errors like:
- `Unknown function 'DATE_TRUNC'` - Wrong dialect for MySQL/Firebird
- `CONCAT not found` - Wrong dialect for Firebird/PostgreSQL
- `ROWS clause not allowed` - Wrong dialect for MySQL/PostgreSQL

Verify the `--engine` parameter matches your target database.

### Performance Differences

Different dialects may have different performance characteristics:
- Firebird's `ROWS` vs MySQL's `LIMIT`
- String concatenation methods
- Date function implementations

This is expected and reflects real-world usage patterns.

## License

Initial Developer's Public License Version 1.0 (IDPL) - Same as ScratchBird
