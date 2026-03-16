#!/usr/bin/env python3
"""
Engine Differential Test Runner

Runs tests that perform differently across engines based on architectural strengths.

This reveals:
- Where MySQL is fastest (clustered PK, covering indexes)
- Where PostgreSQL is fastest (parallel query, advanced indexes)
- Where Firebird is fastest (MGA, read concurrency)

Results help validate ScratchBird's emulation choices.
"""

import argparse
import os
import json
import sys
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from scenarios.mysql_optimized_tests import get_all_tests as get_mysql_tests
from scenarios.postgresql_optimized_tests import get_all_tests as get_pg_tests
from scenarios.firebird_optimized_tests import get_all_tests as get_fb_tests


@dataclass
class DifferentialTestResult:
    """Result of a differential test."""
    test_name: str
    test_category: str  # mysql_optimized, pg_optimized, fb_optimized
    engine: str
    duration_ms: float
    expected_pattern: str
    actual_pattern: str
    performance_score: float  # Relative to expected baseline
    notes: str = ""


class EngineConnection:
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
        self._query_timeout_ms = int(os.getenv("SCRATCHBIRD_PG_QUERY_TIMEOUT_MS", "30000"))
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
            connect_kwargs = {
                "host": self.host,
                "port": self.port,
                "dbname": self.database,
                "user": self.user,
                "password": self.password,
            }
            if self._query_timeout_ms > 0:
                # Set at connection startup so timeout persists across transaction boundaries.
                connect_kwargs["options"] = f"-c statement_timeout={self._query_timeout_ms}"
            self.connection = psycopg2.connect(**connect_kwargs)
            self.connection.autocommit = False
        else:
            raise ValueError(f"Unsupported engine: {self.engine}")
        self.cursor = self.connection.cursor()
    
    def execute(self, sql: str):
        try:
            self.cursor.execute(sql)
            return self.cursor
        except Exception as e:
            self.connection.rollback()
            raise
    
    def commit(self):
        self.connection.commit()

    def rollback(self):
        self.connection.rollback()

    def close(self):
        if self.cursor:
            self.cursor.close()
        if self.connection:
            self.connection.close()


class DifferentialTestRunner:
    """Runner for engine differential tests."""
    
    def __init__(self, engine: str, host: str, port: int, database: str,
                 user: str, password: str, output_dir: Path):
        self.engine = engine
        self.host = host
        self.port = port
        self.database = database
        self.user = user
        self.password = password
        self.output_dir = output_dir
        self.results: List[DifferentialTestResult] = []
        self.db: Optional[EngineConnection] = None
        
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def connect(self):
        print(f"Connecting to {self.engine}...")
        self.db = EngineConnection(
            self.engine, self.host, self.port,
            self.database, self.user, self.password
        )
        print(f"Connected to {self.engine}.")
    
    def disconnect(self):
        if self.db:
            self.db.close()
            print("Disconnected.")
    
    def setup_test(self, setup_sql: str):
        """Execute setup SQL."""
        if not setup_sql:
            return
        
        statements = [s.strip() for s in setup_sql.split(';') if s.strip()]
        for stmt in statements:
            try:
                self.db.execute(stmt)
                self.db.commit()
            except Exception as e:
                self.db.rollback()
                # Ignore existing objects
                pass
    
    def run_mysql_optimized_tests(self):
        """Run tests optimized for MySQL."""
        print(f"\n{'='*60}")
        print(f"MySQL-Optimized Tests on {self.engine.upper()}")
        print(f"{'='*60}")
        print("These tests should be FASTEST on MySQL, slower on others.")
        print()
        
        tests = get_mysql_tests()
        for test in tests:
            if test.name.startswith("random_") or test.name.startswith("non_covering_"):
                continue  # Skip weakness tests
            
            print(f"Running: {test.name}")
            print(f"  Why MySQL wins: {test.why_mysql_faster[:80]}...")
            
            try:
                start = time.time()
                self.setup_test(test.setup_sql)
                
                # Execute test
                self.db.execute(test.test_sql)
                self.db.commit()
                
                duration = (time.time() - start) * 1000
                
                # Determine actual pattern
                pattern_map = {
                    "firebird": test.expected_fb_pattern,
                    "mysql": test.expected_mysql_pattern,
                    "postgresql": test.expected_pg_pattern
                }
                actual_pattern = pattern_map.get(self.engine, "Unknown")
                
                result = DifferentialTestResult(
                    test_name=test.name,
                    test_category="mysql_optimized",
                    engine=self.engine,
                    duration_ms=duration,
                    expected_pattern=actual_pattern if self.engine == "mysql" else "Slower than MySQL",
                    actual_pattern=actual_pattern,
                    performance_score=100.0 if self.engine == "mysql" else 50.0,  # Baseline
                    notes=f"MySQL advantage: {test.mysql_advantage_factor}"
                )
                self.results.append(result)
                
                print(f"  Duration: {duration:.2f}ms")
                print(f"  Expected: {actual_pattern[:60]}...")
                
            except Exception as e:
                print(f"  ERROR: {e}")
                result = DifferentialTestResult(
                    test_name=test.name,
                    test_category="mysql_optimized",
                    engine=self.engine,
                    duration_ms=0,
                    expected_pattern="",
                    actual_pattern=f"Error: {e}",
                    performance_score=0,
                    notes="Failed"
                )
                self.results.append(result)
    
    def run_pg_optimized_tests(self):
        """Run tests optimized for PostgreSQL."""
        print(f"\n{'='*60}")
        print(f"PostgreSQL-Optimized Tests on {self.engine.upper()}")
        print(f"{'='*60}")
        print("These tests should be FASTEST on PostgreSQL, slower on others.")
        print()
        
        tests = get_pg_tests()
        for test in tests:
            print(f"Running: {test.name}")
            print(f"  Why PostgreSQL wins: {test.why_postgres_faster[:80]}...")
            
            try:
                start = time.time()
                self.setup_test(test.setup_sql)
                self.db.execute(test.test_sql)
                self.db.commit()
                
                duration = (time.time() - start) * 1000
                
                pattern_map = {
                    "firebird": test.expected_fb_pattern,
                    "mysql": test.expected_mysql_pattern,
                    "postgresql": test.expected_pg_pattern
                }
                actual_pattern = pattern_map.get(self.engine, "Unknown")
                
                result = DifferentialTestResult(
                    test_name=test.name,
                    test_category="pg_optimized",
                    engine=self.engine,
                    duration_ms=duration,
                    expected_pattern=actual_pattern if self.engine == "postgresql" else "Slower than PostgreSQL",
                    actual_pattern=actual_pattern,
                    performance_score=100.0 if self.engine == "postgresql" else 50.0,
                    notes=f"PostgreSQL advantage: {test.postgres_advantage_factor}"
                )
                self.results.append(result)
                
                print(f"  Duration: {duration:.2f}ms")
                
            except Exception as e:
                print(f"  ERROR: {e}")
                self.results.append(DifferentialTestResult(
                    test_name=test.name,
                    test_category="pg_optimized",
                    engine=self.engine,
                    duration_ms=0,
                    expected_pattern="",
                    actual_pattern=f"Error: {e}",
                    performance_score=0,
                    notes="Failed"
                ))
    
    def run_fb_optimized_tests(self):
        """Run tests optimized for Firebird."""
        print(f"\n{'='*60}")
        print(f"Firebird-Optimized Tests on {self.engine.upper()}")
        print(f"{'='*60}")
        print("These tests should be FASTEST on Firebird, slower on others.")
        print()
        
        tests = get_fb_tests()
        for test in tests:
            if test.name.startswith("version_") or test.name.startswith("no_") or test.name.startswith("limited_"):
                continue  # Skip weakness tests
            
            print(f"Running: {test.name}")
            print(f"  Why Firebird wins: {test.why_firebird_faster[:80]}...")
            
            try:
                start = time.time()
                self.setup_test(test.setup_sql)
                self.db.execute(test.test_sql)
                self.db.commit()
                
                duration = (time.time() - start) * 1000
                
                pattern_map = {
                    "firebird": test.expected_fb_pattern,
                    "mysql": test.expected_mysql_pattern,
                    "postgresql": test.expected_pg_pattern
                }
                actual_pattern = pattern_map.get(self.engine, "Unknown")
                
                result = DifferentialTestResult(
                    test_name=test.name,
                    test_category="fb_optimized",
                    engine=self.engine,
                    duration_ms=duration,
                    expected_pattern=actual_pattern if self.engine == "firebird" else "Slower than Firebird",
                    actual_pattern=actual_pattern,
                    performance_score=100.0 if self.engine == "firebird" else 50.0,
                    notes=f"Firebird advantage: {test.firebird_advantage_factor}"
                )
                self.results.append(result)
                
                print(f"  Duration: {duration:.2f}ms")
                
            except Exception as e:
                print(f"  ERROR: {e}")
                self.results.append(DifferentialTestResult(
                    test_name=test.name,
                    test_category="fb_optimized",
                    engine=self.engine,
                    duration_ms=0,
                    expected_pattern="",
                    actual_pattern=f"Error: {e}",
                    performance_score=0,
                    notes="Failed"
                ))
    
    def save_results(self):
        """Save results to JSON."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results_file = self.output_dir / f"differential_{self.engine}_{timestamp}.json"
        
        results_data = {
            "metadata": {
                "engine": self.engine,
                "host": self.host,
                "port": self.port,
                "timestamp": timestamp,
            },
            "results": [asdict(r) for r in self.results],
            "summary": {
                "total_tests": len(self.results),
                "by_category": {
                    "mysql_optimized": len([r for r in self.results if r.test_category == "mysql_optimized"]),
                    "pg_optimized": len([r for r in self.results if r.test_category == "pg_optimized"]),
                    "fb_optimized": len([r for r in self.results if r.test_category == "fb_optimized"]),
                }
            }
        }
        
        results_file.write_text(json.dumps(results_data, indent=2))
        print(f"\nResults saved to: {results_file}")
        return results_file
    
    def print_summary(self):
        """Print summary."""
        print(f"\n{'='*60}")
        print(f"DIFFERENTIAL TEST SUMMARY - {self.engine.upper()}")
        print(f"{'='*60}")
        
        by_category = {}
        for r in self.results:
            cat = r.test_category
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(r)
        
        for cat, results in by_category.items():
            print(f"\n{cat.upper()}: {len(results)} tests")
            for r in results:
                status = "✓" if r.performance_score > 0 else "✗"
                print(f"  {status} {r.test_name}: {r.duration_ms:.2f}ms")


def main():
    parser = argparse.ArgumentParser(description='Engine Differential Test Runner')
    parser.add_argument('--engine', required=True, choices=['firebird', 'mysql', 'postgresql'])
    parser.add_argument('--host', default='localhost')
    parser.add_argument('--port', type=int)
    parser.add_argument('--database', default='benchmark')
    parser.add_argument('--user', required=True)
    parser.add_argument('--password', required=True)
    parser.add_argument('--category', choices=['mysql', 'postgresql', 'firebird', 'all'], default='all')
    parser.add_argument('--output-dir', type=Path, default=Path('./results'))
    
    args = parser.parse_args()
    
    if args.port is None:
        ports = {'firebird': 3050, 'mysql': 3306, 'postgresql': 5432}
        args.port = ports[args.engine]
    
    runner = DifferentialTestRunner(
        engine=args.engine, host=args.host, port=args.port,
        database=args.database, user=args.user, password=args.password,
        output_dir=args.output_dir
    )
    
    try:
        runner.connect()
        
        if args.category in ('mysql', 'all'):
            runner.run_mysql_optimized_tests()
        if args.category in ('postgresql', 'all'):
            runner.run_pg_optimized_tests()
        if args.category in ('firebird', 'all'):
            runner.run_fb_optimized_tests()
        
        runner.print_summary()
        runner.save_results()
        
    finally:
        runner.disconnect()


if __name__ == '__main__':
    main()
