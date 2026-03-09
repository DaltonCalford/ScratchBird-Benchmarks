# ScratchBird Stress Test Suite

Comprehensive stress testing with data verification, timing, and cross-engine comparison.

## Overview

This stress test suite provides:

- **Data Generation** - Deterministic synthetic data with known properties
- **Bulk Operations** - INSERT/UPDATE/DELETE millions of rows with verification
- **JOIN Stress Tests** - All JOIN types with multi-table scenarios
- **Performance Metrics** - Detailed timing and throughput measurements
- **Result Verification** - Every operation verified for correctness
- **Visual Reports** - Charts comparing engine performance

## Test Categories

### 1. Data Loading Tests

| Scale | Customers | Products | Orders | Order Items | Total Rows |
|-------|-----------|----------|--------|-------------|------------|
| small | 10,000 | 5,000 | 50,000 | 200,000 | 265,000 |
| medium | 100,000 | 50,000 | 500,000 | 2,000,000 | 2,650,000 |
| large | 1,000,000 | 500,000 | 5,000,000 | 20,000,000 | 26,500,000 |
| huge | 10,000,000 | 2,000,000 | 50,000,000 | 200,000,000 | 262,000,000 |

### 2. JOIN Stress Tests

All JOIN types tested with verification:

| Test Category | Count | Description |
|--------------|-------|-------------|
| INNER JOIN | 5 | Simple, multiple conditions, expressions, large results |
| OUTER JOIN | 5 | LEFT, RIGHT, FULL OUTER with aggregations |
| CROSS JOIN | 2 | Limited and with aggregation |
| SELF JOIN | 2 | Hierarchical and pairing scenarios |
| Multi-table (3+) | 5 | 3, 4, 5 table JOINs, mixed INNER/OUTER |
| Complex Conditions | 3 | OR, BETWEEN, CASE expressions |
| Aggregations | 3 | ROLLUP, window functions, complex GROUP BY |
| Subqueries | 3 | Correlated, derived tables, CTEs |

### 3. Bulk Operation Tests

| Test Category | Operations |
|--------------|------------|
| Bulk INSERT | Single transaction, SELECT-based, with aggregation |
| Bulk UPDATE | Simple, with JOIN, complex calculations, correlated subquery |
| Bulk DELETE | Date filters, JOIN-based, cascade simulation |
| Mixed Workload | Read-heavy, write-heavy, concurrent reporting |
| Aggregation | Full scan, multi-dimensional, distinct counts, nested |

## Quick Start

### Run All Stress Tests

```bash
# Run stress tests for all engines with medium dataset
cd /home/dcalford/CliWork/ScratchBird-Benchmarks
./stress-tests/scripts/run-stress-tests.sh all medium

# Run for specific engine
./stress-tests/scripts/run-stress-tests.sh firebird medium
./stress-tests/scripts/run-stress-tests.sh mysql large
./stress-tests/scripts/run-stress-tests.sh postgresql small
```

### Using Docker Compose

```bash
# Start engines
docker-compose up -d firebird mysql postgresql

# Run stress tests (set environment variables)
export STRESS_ENGINE=firebird
export STRESS_SCALE=medium
export STRESS_HOST=firebird
export STRESS_PORT=3050
docker-compose --profile stress run --rm stress-runner

# Or run directly with parameters
docker-compose --profile stress run --rm stress-runner \
  python3 runners/stress_test_runner.py \
  --engine=mysql --host=mysql --port=3306 \
  --database=benchmark --user=benchmark --password=benchmark \
  --scale=large --output-dir=/results
```

### Direct Python Execution

```bash
cd /home/dcalford/CliWork/ScratchBird-Benchmarks/stress-tests

# Install dependencies
pip install pymysql psycopg2-binary fdb firebird-driver pandas matplotlib

# Run tests
python3 runners/stress_test_runner.py \
  --engine=postgresql --host=localhost --port=5432 \
  --database=benchmark --user=benchmark --password=benchmark \
  --scale=medium --output-dir=./results
```

## Usage Examples

### Run Specific Test Filter

```bash
# Run only INNER JOIN tests
python3 runners/stress_test_runner.py \
  --engine=firebird --user=benchmark --password=benchmark \
  --scale=medium --test-filter=inner_join

# Run only bulk operations
python3 runners/stress_test_runner.py \
  --engine=mysql --user=benchmark --password=benchmark \
  --scale=large --test-filter=bulk
```

### Skip Data Loading (Use Existing Data)

```bash
# If you've already loaded data and want to re-run tests
python3 runners/stress_test_runner.py \
  --engine=postgresql --user=benchmark --password=benchmark \
  --skip-data-load
```

## Verification

Every test includes verification:

1. **Row Count Verification** - Confirms expected rows inserted/updated/deleted
2. **Referential Integrity** - Checks FK constraints
3. **Calculation Verification** - Validates computed values
4. **Aggregation Verification** - Confirms GROUP BY results

Example verification queries:
```sql
-- Verify row counts
SELECT COUNT(*) FROM orders;  -- Should match expected count

-- Verify FK integrity
SELECT COUNT(*) FROM orders o 
LEFT JOIN customers c ON o.customer_id = c.customer_id 
WHERE c.customer_id IS NULL;  -- Should be 0

-- Verify calculations
SELECT COUNT(*) FROM orders 
WHERE ABS(total_amount - calculated_total) > 0.01;  -- Should be 0
```

## Output Format

Results are saved as JSON with the following structure:

```json
{
  "metadata": {
    "engine": "firebird",
    "host": "localhost",
    "port": 3050,
    "timestamp": "20240308_143022"
  },
  "data_loading": [
    {
      "table_name": "customers",
      "row_count": 100000,
      "duration_ms": 5234.5,
      "rows_per_second": 19104.2,
      "status": "success"
    }
  ],
  "test_results": [
    {
      "test_name": "inner_join_simple",
      "description": "Simple INNER JOIN between orders and customers",
      "status": "passed",
      "duration_ms": 1245.3,
      "rows_returned": 500000,
      "verification_passed": true
    }
  ],
  "summary": {
    "total_tests": 40,
    "passed": 38,
    "failed": 1,
    "errors": 1,
    "total_duration_ms": 125000
  }
}
```

## Comparison Reports

Generate HTML comparison reports across engines:

```bash
# After running tests for multiple engines
python3 stress-tests/scripts/compare-stress-results.py \
  --results-dir=./results/stress-20240308-143022 \
  --output=./results/comparison.html
```

The report includes:
- Data loading performance charts
- JOIN test performance comparison
- Test-by-test results table
- Summary statistics

## Test Scenarios Detail

### JOIN Tests

**inner_join_large_result**
```sql
SELECT oi.*, o.order_date, o.status, c.first_name, c.last_name
FROM order_items oi
INNER JOIN orders o ON oi.order_id = o.order_id
INNER JOIN customers c ON o.customer_id = c.customer_id
```
Returns millions of rows - tests streaming/memory handling.

**left_join_all_customers**
```sql
SELECT c.customer_id, c.first_name, 
       COUNT(o.order_id) as order_count,
       COALESCE(SUM(o.total_amount), 0) as total_spent
FROM customers c
LEFT JOIN orders o ON c.customer_id = o.customer_id
GROUP BY c.customer_id, c.first_name
```
Tests OUTER JOIN with aggregation on large datasets.

**four_table_join**
```sql
SELECT c.customer_id, o.order_id, oi.item_id, p.name
FROM customers c
INNER JOIN orders o ON c.customer_id = o.customer_id
INNER JOIN order_items oi ON o.order_id = oi.order_id
INNER JOIN products p ON oi.product_id = p.product_id
```
Tests multi-table JOIN performance.

### Bulk Operation Tests

**bulk_insert_single_transaction**
- Inserts 100K rows in single transaction
- Measures INSERT throughput

**bulk_update_with_join**
```sql
UPDATE orders
SET total_amount = total_amount * 0.95
WHERE customer_id IN (
    SELECT customer_id FROM customers WHERE account_balance > 10000
)
```
Tests UPDATE with subquery on millions of rows.

**agg_complex_aggregation**
```sql
SELECT 
    DATE_TRUNC('month', o.order_date) as month,
    p.category,
    COUNT(DISTINCT c.customer_id) as unique_customers,
    SUM(oi.quantity) as units_sold,
    SUM(oi.quantity * oi.unit_price) as gross_revenue,
    AVG(oi.quantity * oi.unit_price) as avg_line_value,
    PERCENTILE_CONT(0.5) WITHIN GROUP (
        ORDER BY oi.quantity * oi.unit_price
    ) as median_line_value
FROM orders o
JOIN customers c ON o.customer_id = c.customer_id
JOIN order_items oi ON o.order_id = oi.order_id
JOIN products p ON oi.product_id = p.product_id
GROUP BY DATE_TRUNC('month', o.order_date), p.category
```
Tests complex analytical queries.

## Performance Expectations

Based on typical hardware (8 cores, 32GB RAM, SSD):

| Operation | Expected Rate |
|-----------|--------------|
| Bulk INSERT | 10K-50K rows/sec |
| Bulk UPDATE | 5K-20K rows/sec |
| Simple JOIN | 100K-500K rows/sec |
| Complex 4-table JOIN | 10K-50K rows/sec |
| Aggregation | 50K-200K rows/sec |

Lower rates indicate potential issues.

## Troubleshooting

### Connection Errors
```bash
# Verify engine is running
docker-compose ps

# Check logs
docker-compose logs firebird
```

### Out of Memory
- Reduce scale (use `small` instead of `large`)
- Reduce batch size in data generator
- Increase Docker memory limit

### Timeout Errors
- Increase `--timeout` parameter
- Check if engine is properly indexed
- Monitor engine resource usage

### Verification Failures
- Check data loading completed successfully
- Verify schema matches expected structure
- Review engine-specific SQL compatibility

## Extending Tests

### Add New Test Scenario

1. Add test definition to `scenarios/join_stress_tests.py` or `scenarios/bulk_operation_tests.py`:

```python
JoinTest(
    name="my_new_test",
    description="Description of what this test does",
    sql="""
        SELECT ...
        FROM ...
        JOIN ...
    """,
    verification_sql="SELECT COUNT(*) FROM ...",
    expected_min_rows=1000,
    timeout_seconds=300,
)
```

2. Run with filter to test:
```bash
python3 runners/stress_test_runner.py --test-filter=my_new_test ...
```

### Add Custom Data Generator

1. Extend `generators/data_generator.py` with new column types
2. Add new distribution methods
3. Update `TableDataGenerator` to use new generators

## CI/CD Integration

```yaml
name: Stress Tests
on:
  schedule:
    - cron: '0 2 * * 0'  # Weekly on Sunday at 2am

jobs:
  stress-test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        engine: [firebird, mysql, postgresql]
        scale: [small, medium]
    steps:
      - uses: actions/checkout@v4
      
      - name: Start engine
        run: docker-compose up -d ${{ matrix.engine }}
      
      - name: Run stress tests
        run: |
          docker-compose --profile stress run --rm stress-runner \
            --engine=${{ matrix.engine }} \
            --scale=${{ matrix.scale }} \
            --output-dir=/results
      
      - name: Upload results
        uses: actions/upload-artifact@v4
        with:
          name: stress-results-${{ matrix.engine }}-${{ matrix.scale }}
          path: results/*.json
```

## License

Initial Developer's Public License Version 1.0 (IDPL) - Same as ScratchBird
