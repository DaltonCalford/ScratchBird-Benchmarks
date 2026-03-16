#!/usr/bin/env python3
"""
ACID Compliance Test Runner

Executes atomicity, consistency, isolation, and durability tests.
"""

import argparse
import json
import sys
import time
import traceback
from decimal import Decimal
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).parent.parent))

from scenarios.transaction_tests import get_all_tests, TransactionTest


@dataclass
class TestResult:
    """Result of a single ACID test."""
    test_name: str
    category: str
    description: str
    status: str = "not_run"  # passed, failed, error, skipped
    duration_ms: float = 0.0
    expected: Any = None
    actual: Any = None
    error_message: str = ""
    sql_executed: str = ""


class DatabaseConnection:
    """Database connection wrapper."""
    
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
        if self.engine == "firebird":
            import fdb
            self.connection = fdb.connect(
                host=self.host, port=self.port, database=self.database,
                user=self.user, password=self.password
            )
        elif self.engine == "mysql":
            import pymysql
            self.connection = pymysql.connect(
                host=self.host, port=self.port, database=self.database,
                user=self.user, password=self.password,
                charset='utf8mb4', autocommit=False
            )
        elif self.engine == "postgresql":
            import psycopg2
            self.connection = psycopg2.connect(
                host=self.host, port=self.port, dbname=self.database,
                user=self.user, password=self.password
            )
            self.connection.autocommit = False
        else:
            raise ValueError(f"Unsupported engine: {self.engine}")
        self.cursor = self.connection.cursor()
    
    def execute(self, sql: str, params: Optional[Tuple] = None):
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
        self.connection.commit()
    
    def rollback(self):
        self.connection.rollback()
    
    def fetchone(self):
        return self.cursor.fetchone()
    
    def fetchall(self):
        return self.cursor.fetchall()
    
    def close(self):
        if self.cursor:
            self.cursor.close()
        if self.connection:
            self.connection.close()


class ACIDTestRunner:
    """ACID test runner."""
    
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
        self.results: List[TestResult] = []
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def connect(self):
        print(f"Connecting to {self.engine}...")
        self.db = DatabaseConnection(
            self.engine, self.host, self.port,
            self.database, self.user, self.password
        )
        print("Connected.")
    
    def disconnect(self):
        if self.db:
            self.db.close()
            print("Disconnected.")
    
    def setup_test_table(self, setup_sql: str):
        """Setup test tables."""
        if not setup_sql:
            return
        
        statements = [s.strip() for s in setup_sql.split(';') if s.strip()]
        for stmt in statements:
            try:
                self.db.execute(stmt)
                self.db.commit()
            except Exception as e:
                # Table might already exist
                self.db.rollback()
    
    def run_test(self, test: TransactionTest) -> TestResult:
        """Run a single ACID test."""
        start_time = time.time()
        
        result = TestResult(
            test_name=test.name,
            category=test.category,
            description=test.description
        )
        
        print(f"\n  Running: {test.name}")
        print(f"    Description: {test.description}")
        
        try:
            # Setup
            if test.setup_sql:
                self.setup_test_table(test.setup_sql)
            
            # Skip concurrent tests in single-threaded mode
            if test.requires_concurrent:
                result.status = "skipped"
                result.error_message = "Requires concurrent execution mode"
                print(f"    Status: SKIPPED (requires concurrent mode)")
                return result
            
            # Execute test SQL
            result.sql_executed = test.test_sql[:200] if test.test_sql else ""
            
            # Try to execute - some tests expect errors
            error_occurred = False
            try:
                self.db.execute(test.test_sql)
                self.db.commit()
            except Exception as e:
                error_occurred = True
                self.db.rollback()
                # Some tests expect errors (like constraint violations)
                if "violation" in test.name or "_error" in test.name:
                    pass  # Expected
                else:
                    raise
            
            # Verify result
            self.db.execute(test.verification_sql)
            actual = self.db.fetchone()
            result.actual = actual[0] if actual else None
            result.expected = test.expected_result
            
            # Check if test passed
            if result.expected == result.actual:
                result.status = "passed"
            elif test.name.endswith("_error") and error_occurred:
                # For error tests, the error itself is success
                result.status = "passed"
                result.actual = "error_occurred"
            else:
                result.status = "failed"
                result.error_message = f"Expected {result.expected}, got {result.actual}"
            
            end_time = time.time()
            result.duration_ms = (end_time - start_time) * 1000
            
            print(f"    Status: {result.status.upper()}")
            if result.status == "passed":
                print(f"    Result: {result.actual}")
            else:
                print(f"    Error: {result.error_message}")
            
        except Exception as e:
            end_time = time.time()
            result.duration_ms = (end_time - start_time) * 1000
            result.status = "error"
            result.error_message = str(e)
            print(f"    Status: ERROR - {e}")
            traceback.print_exc()
        
        self.results.append(result)
        return result
    
    def run_all_tests(self, category_filter: Optional[str] = None):
        """Run all ACID tests."""
        all_tests = get_all_tests()
        
        categories_to_run = [category_filter] if category_filter else all_tests.keys()
        
        total_tests = sum(len(all_tests.get(c, [])) for c in categories_to_run)
        
        print(f"\n{'='*60}")
        print(f"Running ACID Tests for {self.engine}")
        print(f"{'='*60}")
        print(f"Total tests: {total_tests}")
        
        test_num = 0
        for category in categories_to_run:
            tests = all_tests.get(category, [])
            if not tests:
                continue
            
            print(f"\n{category.upper()} ({len(tests)} tests)")
            print("-" * 40)
            
            for test in tests:
                test_num += 1
                print(f"[{test_num}/{total_tests}]", end="")
                self.run_test(test)
        
        print(f"\n{'='*60}")
        print("ACID tests complete")
        print(f"{'='*60}")
    
    def save_results(self):
        """Save results to JSON."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results_file = self.output_dir / f"acid_{self.engine}_{timestamp}.json"

        def _serialize_value(value: Any) -> Any:
            if isinstance(value, Decimal):
                return float(value)
            if isinstance(value, dict):
                return {k: _serialize_value(v) for k, v in value.items()}
            if isinstance(value, (list, tuple)):
                return [_serialize_value(item) for item in value]
            return value
        
        # Group by category
        categories = {}
        for r in self.results:
            if r.category not in categories:
                categories[r.category] = []
            categories[r.category].append({
                'test_name': r.test_name,
                'description': r.description,
                'status': r.status,
                'duration_ms': r.duration_ms,
                'expected': _serialize_value(r.expected),
                'actual': _serialize_value(r.actual),
                'error_message': r.error_message,
            })
        
        results_data = {
            'metadata': {
                'engine': self.engine,
                'host': self.host,
                'port': self.port,
                'database': self.database,
                'timestamp': timestamp,
            },
            'results': categories,
            'summary': {
                'total': len(self.results),
                'passed': sum(1 for r in self.results if r.status == 'passed'),
                'failed': sum(1 for r in self.results if r.status == 'failed'),
                'errors': sum(1 for r in self.results if r.status == 'error'),
                'skipped': sum(1 for r in self.results if r.status == 'skipped'),
                'by_category': {
                    cat: {
                        'total': len(tests),
                        'passed': sum(1 for t in tests if t['status'] == 'passed'),
                    }
                    for cat, tests in categories.items()
                }
            }
        }
        
        results_file.write_text(json.dumps(results_data, indent=2))
        print(f"\nResults saved to: {results_file}")
        return results_file
    
    def print_summary(self):
        """Print summary."""
        print(f"\n{'='*60}")
        print(f"ACID TEST SUMMARY - {self.engine.upper()}")
        print(f"{'='*60}")
        
        passed = sum(1 for r in self.results if r.status == 'passed')
        failed = sum(1 for r in self.results if r.status == 'failed')
        errors = sum(1 for r in self.results if r.status == 'error')
        skipped = sum(1 for r in self.results if r.status == 'skipped')
        total = len(self.results)
        
        # By category
        categories = {}
        for r in self.results:
            if r.category not in categories:
                categories[r.category] = {'total': 0, 'passed': 0}
            categories[r.category]['total'] += 1
            if r.status == 'passed':
                categories[r.category]['passed'] += 1
        
        for cat, stats in sorted(categories.items()):
            status = "✓" if stats['passed'] == stats['total'] else "✗"
            print(f"  {status} {cat.capitalize()}: {stats['passed']}/{stats['total']} passed")
        
        print(f"\n  Total: {total} tests")
        print(f"  Passed: {passed}")
        print(f"  Failed: {failed}")
        print(f"  Errors: {errors}")
        print(f"  Skipped: {skipped}")
        
        score = (passed / total * 100) if total > 0 else 0
        print(f"\n  Score: {score:.1f}%")
        
        if failed > 0 or errors > 0:
            print("\n  FAILED TESTS:")
            for r in self.results:
                if r.status in ('failed', 'error'):
                    print(f"    - {r.test_name}: {r.error_message}")


def main():
    parser = argparse.ArgumentParser(description='ACID Compliance Test Runner')
    parser.add_argument('--engine', required=True, choices=['firebird', 'mysql', 'postgresql'])
    parser.add_argument('--host', default='localhost')
    parser.add_argument('--port', type=int)
    parser.add_argument('--database', default='benchmark')
    parser.add_argument('--user', required=True)
    parser.add_argument('--password', required=True)
    parser.add_argument('--category', choices=['atomicity', 'consistency', 'isolation', 'durability'])
    parser.add_argument('--output-dir', type=Path, default=Path('./results'))
    
    args = parser.parse_args()
    
    if args.port is None:
        ports = {'firebird': 3050, 'mysql': 3306, 'postgresql': 5432}
        args.port = ports[args.engine]
    
    runner = ACIDTestRunner(
        engine=args.engine, host=args.host, port=args.port,
        database=args.database, user=args.user, password=args.password,
        output_dir=args.output_dir
    )
    
    try:
        runner.connect()
        runner.run_all_tests(args.category)
        runner.print_summary()
        runner.save_results()
    finally:
        runner.disconnect()


if __name__ == '__main__':
    main()
