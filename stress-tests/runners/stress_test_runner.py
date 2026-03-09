#!/usr/bin/env python3
"""
Stress Test Runner

Executes stress tests with:
- Data generation and loading
- Timed query execution
- Result verification
- Performance metrics collection
- Comparison between engines
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
from scenarios.join_stress_tests import JoinStressTests


@dataclass
class TestMetrics:
    """Metrics collected during test execution."""
    test_name: str
    description: str
    status: str = "pending"  # pending, running, passed, failed, timeout, error
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    duration_ms: float = 0.0
    rows_affected: int = 0
    rows_returned: int = 0
    memory_mb: float = 0.0
    cpu_percent: float = 0.0
    error_message: str = ""
    verification_passed: bool = False
    verification_details: Dict[str, Any] = field(default_factory=dict)


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


class StressTestRunner:
    """Main stress test runner."""
    
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
        self.metrics: List[TestMetrics] = []
        self.load_metrics: List[DataLoadMetrics] = []
        
        # Ensure output directory exists
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def connect(self):
        """Connect to database."""
        print(f"Connecting to {self.engine} at {self.host}:{self.port}...")
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
        """Create database schema for stress test tables."""
        print("\nCreating schema...")
        
        # Drop existing tables
        tables = ["order_items", "orders", "products", "customers"]
        for table in tables:
            try:
                self.db.execute(f"DROP TABLE IF EXISTS {table}")
                self.db.commit()
            except:
                pass
        
        # Create customers table
        if self.engine == "firebird":
            self.db.execute("""
                CREATE TABLE customers (
                    customer_id BIGINT PRIMARY KEY,
                    first_name VARCHAR(50),
                    last_name VARCHAR(50),
                    email VARCHAR(100) UNIQUE,
                    phone VARCHAR(20),
                    registration_date DATE,
                    country_code VARCHAR(2),
                    account_balance DECIMAL(12, 2)
                )
            """)
        elif self.engine == "mysql":
            self.db.execute("""
                CREATE TABLE customers (
                    customer_id BIGINT PRIMARY KEY,
                    first_name VARCHAR(50),
                    last_name VARCHAR(50),
                    email VARCHAR(100) UNIQUE,
                    phone VARCHAR(20),
                    registration_date DATE,
                    country_code VARCHAR(2),
                    account_balance DECIMAL(12, 2)
                )
            """)
        else:  # postgresql
            self.db.execute("""
                CREATE TABLE customers (
                    customer_id BIGINT PRIMARY KEY,
                    first_name VARCHAR(50),
                    last_name VARCHAR(50),
                    email VARCHAR(100) UNIQUE,
                    phone VARCHAR(20),
                    registration_date DATE,
                    country_code VARCHAR(2),
                    account_balance NUMERIC(12, 2)
                )
            """)
        
        # Create products table
        numeric_type = "NUMERIC" if self.engine == "postgresql" else "DECIMAL"
        self.db.execute(f"""
            CREATE TABLE products (
                product_id BIGINT PRIMARY KEY,
                product_code VARCHAR(20) UNIQUE,
                name VARCHAR(200),
                category VARCHAR(50),
                price {numeric_type}(10, 2),
                cost {numeric_type}(10, 2),
                stock_quantity INTEGER,
                is_active INTEGER
            )
        """)
        
        # Create orders table
        self.db.execute(f"""
            CREATE TABLE orders (
                order_id BIGINT PRIMARY KEY,
                customer_id BIGINT,
                order_date TIMESTAMP,
                status VARCHAR(20),
                total_amount {numeric_type}(12, 2),
                shipping_cost {numeric_type}(8, 2),
                discount_amount {numeric_type}(10, 2)
            )
        """)
        
        # Create order_items table
        self.db.execute(f"""
            CREATE TABLE order_items (
                item_id BIGINT PRIMARY KEY,
                order_id BIGINT,
                product_id BIGINT,
                quantity INTEGER,
                unit_price {numeric_type}(10, 2),
                discount_pct {numeric_type}(5, 2)
            )
        """)
        
        self.db.commit()
        print("Schema created.")
    
    def load_data(self, dataset: Dict[str, Any], batch_size: int = 10000):
        """Load generated data into database."""
        print("\nLoading data...")
        
        # Collect FK reference values
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
                
                rows_loaded = 0
                for batch_num, batch in enumerate(generator.generate_rows(batch_size)):
                    if batch_num % 10 == 0:
                        print(f"    Batch {batch_num}: {rows_loaded:,} rows loaded...")
                    
                    # Build INSERT statement
                    columns = [c.name for c in spec.columns]
                    placeholders = self._get_placeholders(len(columns))
                    
                    sql = f"INSERT INTO {table_name} ({', '.join(columns)}) VALUES ({placeholders})"
                    
                    # Insert batch
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
    
    def _get_placeholders(self, count: int) -> str:
        """Get parameter placeholders for the current engine."""
        if self.engine == "mysql":
            return ", ".join(["%s"] * count)
        else:
            return ", ".join(["?"] * count)
    
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
    
    def run_test(self, test: Any, timeout_seconds: int = 300) -> TestMetrics:
        """Run a single stress test."""
        metric = TestMetrics(
            test_name=test.name,
            description=test.description
        )
        
        print(f"\nRunning: {test.name}")
        print(f"  Description: {test.description}")
        print(f"  Timeout: {test.timeout_seconds}s")
        
        metric.start_time = time.time()
        metric.status = "running"
        
        try:
            # Execute the test query
            self.db.execute(test.sql)
            
            # Fetch results (for SELECT queries)
            if self.db.cursor.description:
                rows = self.db.fetchall()
                metric.rows_returned = len(rows)
                print(f"  Rows returned: {metric.rows_returned:,}")
            else:
                metric.rows_affected = self.db.rowcount()
                print(f"  Rows affected: {metric.rows_affected:,}")
            
            metric.end_time = time.time()
            metric.duration_ms = (metric.end_time - metric.start_time) * 1000
            
            # Run verification if provided
            if test.verification_sql:
                self.db.execute(test.verification_sql)
                verify_result = self.db.fetchone()
                metric.verification_details['verification_result'] = verify_result[0] if verify_result else None
            
            # Check row count expectations
            if test.expected_min_rows is not None and metric.rows_returned < test.expected_min_rows:
                metric.status = "failed"
                metric.error_message = f"Too few rows: {metric.rows_returned} < {test.expected_min_rows}"
            elif test.expected_max_rows is not None and metric.rows_returned > test.expected_max_rows:
                metric.status = "failed"
                metric.error_message = f"Too many rows: {metric.rows_returned} > {test.expected_max_rows}"
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
        """Run all stress tests."""
        tests = JoinStressTests.get_all_tests()
        
        if test_filter:
            tests = [t for t in tests if test_filter in t.name]
        
        print(f"\n{'='*60}")
        print(f"Running {len(tests)} stress tests")
        print(f"{'='*60}")
        
        for i, test in enumerate(tests, 1):
            print(f"\n[{i}/{len(tests)}] ", end="")
            self.run_test(test)
        
        print(f"\n{'='*60}")
        print(f"Stress tests complete")
        print(f"{'='*60}")
    
    def save_results(self):
        """Save test results to JSON file."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results_file = self.output_dir / f"stress_test_results_{self.engine}_{timestamp}.json"
        
        results_data = {
            'metadata': {
                'engine': self.engine,
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
    parser = argparse.ArgumentParser(description='Stress Test Runner')
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
    runner = StressTestRunner(
        engine=args.engine,
        host=args.host,
        port=args.port,
        database=args.database,
        user=args.user,
        password=args.password,
        output_dir=args.output_dir
    )
    
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
        
        # Run stress tests
        runner.run_all_tests(args.test_filter)
        
        # Print summary
        runner.print_summary()
        
        # Save results
        results_file = runner.save_results()
        
    finally:
        runner.disconnect()


if __name__ == '__main__':
    main()
