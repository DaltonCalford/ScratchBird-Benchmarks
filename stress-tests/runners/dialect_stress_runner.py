#!/usr/bin/env python3
"""
Dialect-Aware Stress Test Runner

Executes stress tests using engine-specific SQL dialects:
- FirebirdSQL dialect 3
- MySQL 8.0+ dialect  
- PostgreSQL dialect

This ensures fair comparison - each engine is tested with its native SQL.
"""

import argparse
import json
import os
import sys
import time
import traceback
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from generators.data_generator import (
    TableDataGenerator, 
    generate_standard_dataset,
    generate_verification_queries
)
from generators.sql_dialect import SQLDialectFactory, StressTestSQLGenerator
from scenarios.dialect_aware_tests import (
    get_tests_for_engine,
    DialectAwareJoinTests,
    DialectAwareBulkTests
)


@dataclass
class TestMetrics:
    """Metrics collected during test execution."""
    test_name: str
    description: str
    status: str = "pending"
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    duration_ms: float = 0.0
    rows_affected: int = 0
    rows_returned: int = 0
    error_message: str = ""
    verification_passed: bool = False
    sql_executed: str = ""


@dataclass
class DataLoadMetrics:
    """Metrics for data loading phase."""
    table_name: str
    row_count: int
    start_time: float = 0.0
    end_time: float = 0.0
    duration_ms: float = 0.0
    rows_per_second: float = 0.0
    status: str = "pending"
    error_message: str = ""


class DatabaseConnection:
    """Database connection wrapper supporting multiple engines."""
    
    def __init__(self, engine: str, host: str, port: int, database: str,
                 user: str, password: str):
        self.engine = engine
        self.host = host
        self.port = port
        self.database = database
        self.user = user
        self.password = password
        self.connection = None
        self.cursor = None
        
        self._connect()
    
    def _connect(self):
        """Establish database connection."""
        if self.engine == "firebird":
            import fdb
            self.connection = fdb.connect(
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.user,
                password=self.password
            )
        elif self.engine == "mysql":
            import pymysql
            self.connection = pymysql.connect(
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.user,
                password=self.password,
                charset='utf8mb4',
                autocommit=False
            )
        elif self.engine == "postgresql":
            import psycopg2
            self.connection = psycopg2.connect(
                host=self.host,
                port=self.port,
                dbname=self.database,
                user=self.user,
                password=self.password
            )
            self.connection.autocommit = False
        else:
            raise ValueError(f"Unsupported engine: {self.engine}")
        
        self.cursor = self.connection.cursor()
    
    def execute(self, sql: str, params: Optional[Tuple] = None) -> Any:
        """Execute SQL statement."""
        try:
            if params:
                self.cursor.execute(sql, params)
            else:
                self.cursor.execute(sql)
            return self.cursor
        except Exception as e:
            self.connection.rollback()
            raise
    
    def commit(self):
        """Commit transaction."""
        self.connection.commit()
    
    def rollback(self):
        """Rollback transaction."""
        self.connection.rollback()
    
    def fetchall(self) -> List[Tuple]:
        """Fetch all results."""
        return self.cursor.fetchall()
    
    def fetchone(self) -> Optional[Tuple]:
        """Fetch one result."""
        return self.cursor.fetchone()
    
    def rowcount(self) -> int:
        """Get row count from last operation."""
        return self.cursor.rowcount
    
    def close(self):
        """Close connection."""
        if self.cursor:
            self.cursor.close()
        if self.connection:
            self.connection.close()


class DialectStressTestRunner:
    """Main dialect-aware stress test runner."""
    
    def __init__(self, engine: str, host: str, port: int, database: str,
                 user: str, password: str, output_dir: Path):
        self.engine = engine
        self.host = host
        self.port = port
        self.database = database
        self.user = user
        self.password = password
        self.output_dir = output_dir
        
        self.db: Optional[DatabaseConnection] = None
        self.dialect = SQLDialectFactory.get_dialect(engine)
        self.sql_gen = StressTestSQLGenerator(self.dialect)
        self.metrics: List[TestMetrics] = []
        self.load_metrics: List[DataLoadMetrics] = []
        
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def connect(self):
        """Connect to database."""
        print(f"Connecting to {self.engine} at {self.host}:{self.port}...")
        print(f"Using {self.engine.upper()} SQL dialect")
        self.db = DatabaseConnection(
            self.engine, self.host, self.port, 
            self.database, self.user, self.password
        )
        print("Connected.")
    
    def disconnect(self):
        """Disconnect from database."""
        if self.db:
            self.db.close()
            self.db = None
            print("Disconnected.")
    
    def create_schema(self, dataset: Dict[str, Any]):
        """Create database schema using dialect-specific SQL."""
        print(f"\nCreating schema using {self.engine} dialect...")
        
        # Drop existing tables in dependency-safe order.
        tables = ["bulk_insert_test", "order_items", "orders", "products", "customers"]
        for table in tables:
            try:
                self.db.execute(f"DROP TABLE {table}")
                self.db.commit()
            except:
                pass
        
        # Create tables using dialect-specific DDL
        self.db.execute(self.dialect.create_table_customers())
        self.db.execute(self.dialect.create_table_products())
        self.db.execute(self.dialect.create_table_orders())
        self.db.execute(self.dialect.create_table_order_items())
        self.db.execute("""
            CREATE TABLE bulk_insert_test (
                id BIGINT PRIMARY KEY,
                data VARCHAR(100),
                metric_value DECIMAL(10, 2)
            )
        """)
        
        self.db.commit()
        print("Schema created.")
    
    def load_data(self, dataset: Dict[str, Any], batch_size: int = 10000):
        """Load generated data into database."""
        print(f"\nLoading data using {self.engine} dialect...")
        
        placeholder = self.dialect.get_placeholder()
        fk_references = {}
        
        for table_name, spec in dataset.items():
            print(f"\n  Loading {table_name} ({spec.row_count:,} rows)...")
            
            metric = DataLoadMetrics(
                table_name=table_name,
                row_count=spec.row_count
            )
            metric.start_time = time.time()
            
            try:
                generator = TableDataGenerator(spec, fk_references)
                
                columns = [c.name for c in spec.columns]
                placeholders = ", ".join([placeholder] * len(columns))
                sql = f"INSERT INTO {table_name} ({', '.join(columns)}) VALUES ({placeholders})"
                
                rows_loaded = 0
                for batch_num, batch in enumerate(generator.generate_rows(batch_size)):
                    if batch_num % 10 == 0:
                        print(f"    Batch {batch_num}: {rows_loaded:,} rows loaded...")
                    
                    for row in batch:
                        values = tuple(row[c] for c in columns)
                        self.db.execute(sql, values)
                    
                    self.db.commit()
                    rows_loaded += len(batch)
                
                metric.end_time = time.time()
                metric.duration_ms = (metric.end_time - metric.start_time) * 1000
                metric.rows_per_second = spec.row_count / (metric.duration_ms / 1000)
                metric.status = "success"
                
                print(f"    Loaded {rows_loaded:,} rows in {metric.duration_ms/1000:.2f}s "
                      f"({metric.rows_per_second:,.0f} rows/sec)")
                
                # Store reference values for FK relationships
                pk_col = next((c for c in spec.columns if c.unique and c.distribution == "sequential"), None)
                if pk_col:
                    fk_references[f"{table_name}.{pk_col.name}"] = list(range(1, spec.row_count + 1))
                
            except Exception as e:
                metric.end_time = time.time()
                metric.status = "failed"
                metric.error_message = str(e)
                print(f"    ERROR: {e}")
            
            self.load_metrics.append(metric)
        
        print("\nData loading complete.")
    
    def verify_data(self, dataset: Dict[str, Any]) -> bool:
        """Run verification queries to ensure data integrity."""
        print("\nVerifying data integrity...")
        
        queries = generate_verification_queries(dataset)
        all_passed = True
        
        for vq in queries:
            print(f"  {vq['name']}: ", end="", flush=True)
            
            try:
                self.db.execute(vq['sql'])
                result = self.db.fetchone()
                actual_value = result[0] if result else None
                
                expected = vq['expected']
                tolerance = vq.get('tolerance', 0)
                
                if tolerance == 0:
                    passed = (actual_value == expected)
                else:
                    passed = abs(actual_value - expected) <= tolerance
                
                if passed:
                    print(f"PASS (expected={expected}, actual={actual_value})")
                else:
                    print(f"FAIL (expected={expected}, actual={actual_value})")
                    all_passed = False
                
            except Exception as e:
                print(f"ERROR: {e}")
                all_passed = False
        
        return all_passed
    
    def run_test(self, test_name: str, test_def: Dict[str, Any], 
                 timeout_seconds: int = 300) -> TestMetrics:
        """Run a single stress test with dialect-specific SQL."""
        sql = test_def.get('sql', '')
        if not sql:
            return TestMetrics(
                test_name=test_name,
                description=test_def.get('description', ''),
                status="error",
                error_message="No SQL generated for this test"
            )
        
        metric = TestMetrics(
            test_name=test_name,
            description=test_def.get('description', ''),
            sql_executed=sql[:500]  # Store first 500 chars
        )
        
        print(f"\nRunning: {test_name}")
        print(f"  Description: {test_def.get('description', '')}")
        print(f"  Timeout: {test_def.get('timeout_seconds', 300)}s")
        
        metric.start_time = time.time()
        metric.status = "running"
        
        try:
            self.db.execute(sql)
            
            if self.db.cursor.description:
                rows = self.db.fetchall()
                metric.rows_returned = len(rows)
                print(f"  Rows returned: {metric.rows_returned:,}")
            else:
                metric.rows_affected = self.db.rowcount()
                print(f"  Rows affected: {metric.rows_affected:,}")
            
            metric.end_time = time.time()
            metric.duration_ms = (metric.end_time - metric.start_time) * 1000
            
            # Check expectations
            expected_min = test_def.get('expected_min_rows')
            expected_max = test_def.get('expected_max_rows')
            
            if expected_min is not None and metric.rows_returned < expected_min:
                metric.status = "failed"
                metric.error_message = f"Too few rows: {metric.rows_returned} < {expected_min}"
            elif expected_max is not None and metric.rows_returned > expected_max:
                metric.status = "failed"
                metric.error_message = f"Too many rows: {metric.rows_returned} > {expected_max}"
            else:
                metric.status = "passed"
                metric.verification_passed = True
            
            print(f"  Duration: {metric.duration_ms:.2f}ms")
            print(f"  Status: {metric.status}")
            
        except Exception as e:
            metric.end_time = time.time()
            metric.duration_ms = (metric.end_time - metric.start_time) * 1000
            metric.status = "error"
            metric.error_message = str(e)
            print(f"  ERROR: {e}")
            traceback.print_exc()
        
        self.metrics.append(metric)
        return metric
    
    def run_all_tests(self, test_filter: Optional[str] = None):
        """Run all dialect-aware stress tests."""
        tests = get_tests_for_engine(self.engine)
        
        if test_filter:
            tests = {k: v for k, v in tests.items() if test_filter in k}
        
        print(f"\n{'='*60}")
        print(f"Running {len(tests)} stress tests ({self.engine} dialect)")
        print(f"{'='*60}")
        
        for i, (test_name, test_def) in enumerate(tests.items(), 1):
            print(f"\n[{i}/{len(tests)}] ", end="")
            self.run_test(test_name, test_def)
        
        print(f"\n{'='*60}")
        print(f"Stress tests complete")
        print(f"{'='*60}")
    
    def save_results(self):
        """Save test results to JSON file."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results_file = self.output_dir / f"stress_{self.engine}_{timestamp}.json"
        
        results_data = {
            'metadata': {
                'engine': self.engine,
                'dialect': self.engine,
                'host': self.host,
                'port': self.port,
                'database': self.database,
                'timestamp': timestamp,
            },
            'data_loading': [
                {
                    'table_name': m.table_name,
                    'row_count': m.row_count,
                    'duration_ms': m.duration_ms,
                    'rows_per_second': m.rows_per_second,
                    'status': m.status,
                }
                for m in self.load_metrics
            ],
            'test_results': [
                {
                    'test_name': m.test_name,
                    'description': m.description,
                    'status': m.status,
                    'duration_ms': m.duration_ms,
                    'rows_returned': m.rows_returned,
                    'rows_affected': m.rows_affected,
                    'verification_passed': m.verification_passed,
                    'error_message': m.error_message,
                    'sql_executed': m.sql_executed[:200] if m.sql_executed else "",
                }
                for m in self.metrics
            ],
            'summary': {
                'total_tests': len(self.metrics),
                'passed': sum(1 for m in self.metrics if m.status == 'passed'),
                'failed': sum(1 for m in self.metrics if m.status == 'failed'),
                'errors': sum(1 for m in self.metrics if m.status == 'error'),
                'total_duration_ms': sum(m.duration_ms for m in self.metrics),
            }
        }
        
        results_file.write_text(json.dumps(results_data, indent=2))
        print(f"\nResults saved to: {results_file}")
        return results_file
    
    def print_summary(self):
        """Print summary of test results."""
        print(f"\n{'='*60}")
        print(f"STRESS TEST SUMMARY - {self.engine.upper()}")
        print(f"SQL Dialect: {self.engine}")
        print(f"{'='*60}")
        
        # Data loading summary
        print("\nData Loading:")
        total_rows = sum(m.row_count for m in self.load_metrics)
        total_time = sum(m.duration_ms for m in self.load_metrics)
        avg_rate = total_rows / (total_time / 1000) if total_time > 0 else 0
        
        for m in self.load_metrics:
            status_icon = "✓" if m.status == "success" else "✗"
            print(f"  {status_icon} {m.table_name}: {m.row_count:,} rows "
                  f"in {m.duration_ms/1000:.2f}s ({m.rows_per_second:,.0f} rows/s)")
        
        print(f"\n  Total: {total_rows:,} rows loaded in {total_time/1000:.2f}s "
              f"({avg_rate:,.0f} rows/s avg)")
        
        # Test results summary
        print("\nTest Results:")
        passed = sum(1 for m in self.metrics if m.status == 'passed')
        failed = sum(1 for m in self.metrics if m.status == 'failed')
        errors = sum(1 for m in self.metrics if m.status == 'error')
        
        for m in self.metrics:
            status_icon = "✓" if m.status == 'passed' else "✗"
            print(f"  {status_icon} {m.test_name}: {m.duration_ms:.2f}ms "
                  f"({m.rows_returned:,} rows)")
        
        total_duration = sum(m.duration_ms for m in self.metrics)
        print(f"\n  Total: {len(self.metrics)} tests, {passed} passed, "
              f"{failed} failed, {errors} errors")
        print(f"  Total time: {total_duration/1000:.2f}s")


def main():
    parser = argparse.ArgumentParser(description='Dialect-Aware Stress Test Runner')
    parser.add_argument('--engine', required=True,
                        choices=['firebird', 'mysql', 'postgresql'],
                        help='Database engine to test')
    parser.add_argument('--host', default='localhost',
                        help='Database host')
    parser.add_argument('--port', type=int,
                        help='Database port (default: engine default)')
    parser.add_argument('--database', default='benchmark',
                        help='Database name')
    parser.add_argument('--user', required=True,
                        help='Database user')
    parser.add_argument('--password', required=True,
                        help='Database password')
    parser.add_argument('--scale', default='small',
                        choices=['small', 'medium', 'large', 'huge'],
                        help='Data scale for stress tests')
    parser.add_argument('--output-dir', type=Path, default=Path('./results'),
                        help='Output directory for results')
    parser.add_argument('--test-filter', default=None,
                        help='Filter tests by name substring')
    parser.add_argument('--skip-data-load', action='store_true',
                        help='Skip data loading (use existing data)')
    
    args = parser.parse_args()
    
    # Set default ports
    if args.port is None:
        ports = {'firebird': 3050, 'mysql': 3306, 'postgresql': 5432}
        args.port = ports[args.engine]
    
    # Create runner
    runner = DialectStressTestRunner(
        engine=args.engine,
        host=args.host,
        port=args.port,
        database=args.database,
        user=args.user,
        password=args.password,
        output_dir=args.output_dir
    )
    
    verification_ok = True

    try:
        # Connect
        runner.connect()
        
        # Generate dataset specification
        dataset = generate_standard_dataset(args.scale)
        
        # Create schema and load data
        if not args.skip_data_load:
            runner.create_schema(dataset)
            runner.load_data(dataset)
            
            # Verify data integrity
            if not runner.verify_data(dataset):
                print("\nWARNING: Data verification failed!")
                verification_ok = False
        
        # Run stress tests
        runner.run_all_tests(args.test_filter)
        
        # Print summary
        runner.print_summary()
        
        # Save results
        results_file = runner.save_results()
        
    finally:
        runner.disconnect()

    has_test_failures = any(metric.status in ("failed", "error") for metric in runner.metrics)
    return 1 if has_test_failures or not verification_ok else 0


if __name__ == '__main__':
    sys.exit(main())
