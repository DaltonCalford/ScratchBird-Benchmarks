#!/usr/bin/env python3
"""
ScratchBird Benchmark Runner

Orchestrates benchmark execution across multiple database engines.
"""

import argparse
import json
import sys
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class BenchmarkResult:
    """Single benchmark test result"""
    test_name: str
    engine: str
    duration_ms: float
    iterations: int
    rows_affected: int
    error: Optional[str] = None


@dataclass
class EngineConnection:
    """Database engine connection info"""
    name: str
    host: str
    port: int
    database: str
    user: str
    password: str


class EngineConnector:
    """Base class for database engine connections"""
    
    def __init__(self, conn_info: EngineConnection):
        self.conn_info = conn_info
        self.connection = None
    
    def connect(self):
        raise NotImplementedError
    
    def execute(self, sql: str, params=None) -> tuple:
        """Execute SQL and return (row_count, error)"""
        raise NotImplementedError
    
    def close(self):
        if self.connection:
            self.connection.close()


class FirebirdConnector(EngineConnector):
    """FirebirdSQL connector using fdb"""
    
    def connect(self):
        import fdb
        self.connection = fdb.connect(
            host=self.conn_info.host,
            port=self.conn_info.port,
            database=self.conn_info.database,
            user=self.conn_info.user,
            password=self.conn_info.password
        )
    
    def execute(self, sql: str, params=None):
        try:
            cursor = self.connection.cursor()
            cursor.execute(sql, params or ())
            row_count = cursor.rowcount
            self.connection.commit()
            return row_count, None
        except Exception as e:
            return 0, str(e)


class MySQLConnector(EngineConnector):
    """MySQL connector using pymysql"""
    
    def connect(self):
        import pymysql
        self.connection = pymysql.connect(
            host=self.conn_info.host,
            port=self.conn_info.port,
            database=self.conn_info.database,
            user=self.conn_info.user,
            password=self.conn_info.password,
            autocommit=True
        )
    
    def execute(self, sql: str, params=None):
        try:
            with self.connection.cursor() as cursor:
                cursor.execute(sql, params or ())
                row_count = cursor.rowcount
                return row_count, None
        except Exception as e:
            return 0, str(e)


class PostgreSQLConnector(EngineConnector):
    """PostgreSQL connector using psycopg2"""
    
    def connect(self):
        import psycopg2
        self.connection = psycopg2.connect(
            host=self.conn_info.host,
            port=self.conn_info.port,
            dbname=self.conn_info.database,
            user=self.conn_info.user,
            password=self.conn_info.password
        )
    
    def execute(self, sql: str, params=None):
        try:
            cursor = self.connection.cursor()
            cursor.execute(sql, params or ())
            row_count = cursor.rowcount
            self.connection.commit()
            return row_count, None
        except Exception as e:
            return 0, str(e)


# Engine connection configurations
ENGINE_CONFIGS = {
    "firebird": EngineConnection(
        name="firebird",
        host="firebird",
        port=3050,
        database="/firebird/data/benchmark.fdb",
        user="benchmark",
        password="benchmark"
    ),
    "mysql": EngineConnection(
        name="mysql",
        host="mysql",
        port=3306,
        database="benchmark",
        user="benchmark",
        password="benchmark"
    ),
    "postgresql": EngineConnection(
        name="postgresql",
        host="postgresql",
        port=5432,
        database="benchmark",
        user="benchmark",
        password="benchmark"
    ),
}


def get_connector(engine_name: str) -> EngineConnector:
    """Get appropriate connector for engine"""
    config = ENGINE_CONFIGS[engine_name]
    connectors = {
        "firebird": FirebirdConnector,
        "mysql": MySQLConnector,
        "postgresql": PostgreSQLConnector,
    }
    return connectors[engine_name](config)


# Micro-benchmark test definitions
MICRO_BENCHMARKS = {
    "single_insert": {
        "description": "Single row INSERT performance",
        "sql": {
            "firebird": "INSERT INTO perf_test (id, name, value) VALUES (GEN_ID(gen_perf_test, 1), 'test', 123.45)",
            "mysql": "INSERT INTO perf_test (name, value) VALUES ('test', 123.45)",
            "postgresql": "INSERT INTO perf_test (name, value) VALUES ('test', 123.45)",
        },
        "iterations": 1000,
    },
    "point_select": {
        "description": "Primary key lookup",
        "sql": {
            "firebird": "SELECT * FROM perf_test WHERE id = 1",
            "mysql": "SELECT * FROM perf_test WHERE id = 1",
            "postgresql": "SELECT * FROM perf_test WHERE id = 1",
        },
        "iterations": 1000,
    },
    "simple_aggregate": {
        "description": "Simple COUNT(*) aggregation",
        "sql": {
            "firebird": "SELECT COUNT(*) FROM perf_test",
            "mysql": "SELECT COUNT(*) FROM perf_test",
            "postgresql": "SELECT COUNT(*) FROM perf_test",
        },
        "iterations": 100,
    },
}


def setup_schema(connector: EngineConnector, engine: str):
    """Create benchmark schema"""
    schemas = {
        "firebird": """
            CREATE GENERATOR gen_perf_test IF NOT EXISTS;
            CREATE TABLE perf_test (
                id INTEGER PRIMARY KEY,
                name VARCHAR(100),
                value DOUBLE PRECISION,
                created TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """,
        "mysql": """
            CREATE TABLE IF NOT EXISTS perf_test (
                id INTEGER AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(100),
                value DOUBLE,
                created TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """,
        "postgresql": """
            CREATE TABLE IF NOT EXISTS perf_test (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100),
                value DOUBLE PRECISION,
                created TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """,
    }
    
    sql = schemas.get(engine, schemas["postgresql"])
    for statement in sql.split(';'):
        statement = statement.strip()
        if statement:
            connector.execute(statement)


def run_micro_benchmarks(engines: List[str]) -> List[BenchmarkResult]:
    """Run micro-benchmark suite"""
    results = []
    
    for engine in engines:
        print(f"\nRunning micro-benchmarks on {engine}...")
        
        try:
            connector = get_connector(engine)
            connector.connect()
            
            # Setup schema
            setup_schema(connector, engine)
            
            # Run each benchmark
            for test_name, test_config in MICRO_BENCHMARKS.items():
                sql = test_config["sql"].get(engine, test_config["sql"]["postgresql"])
                iterations = test_config["iterations"]
                
                # Warmup
                for _ in range(min(10, iterations)):
                    connector.execute(sql)
                
                # Benchmark
                start = time.perf_counter()
                error = None
                rows_total = 0
                
                for _ in range(iterations):
                    rows, err = connector.execute(sql)
                    if err:
                        error = err
                        break
                    rows_total += rows
                
                duration_ms = (time.perf_counter() - start) * 1000
                
                result = BenchmarkResult(
                    test_name=test_name,
                    engine=engine,
                    duration_ms=duration_ms,
                    iterations=iterations,
                    rows_affected=rows_total,
                    error=error
                )
                results.append(result)
                
                status = "✓" if not error else "✗"
                print(f"  {status} {test_name}: {duration_ms:.2f}ms ({iterations} iterations)")
            
            connector.close()
            
        except Exception as e:
            print(f"  ✗ Failed to connect to {engine}: {e}")
    
    return results


def main():
    parser = argparse.ArgumentParser(description="ScratchBird Benchmark Runner")
    parser.add_argument("--suite", choices=["micro", "concurrent", "regression", "all"],
                        default="micro", help="Benchmark suite to run")
    parser.add_argument("--engine", default="all",
                        help="Engine to test (firebird,mysql,postgresql, or all)")
    parser.add_argument("--output", default="./results/benchmark.json",
                        help="Output file for results")
    
    args = parser.parse_args()
    
    # Determine engines to test
    if args.engine == "all":
        engines = ["firebird", "mysql", "postgresql"]
    else:
        engines = args.engine.split(",")
    
    print("ScratchBird Benchmark Runner")
    print("=" * 50)
    print(f"Suite: {args.suite}")
    print(f"Engines: {', '.join(engines)}")
    print(f"Output: {args.output}")
    print()
    
    # Run benchmarks
    all_results = []
    
    if args.suite in ["micro", "all"]:
        results = run_micro_benchmarks(engines)
        all_results.extend(results)
    
    # Generate report
    report = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "suite": args.suite,
        "engines": engines,
        "results": [asdict(r) for r in all_results],
    }
    
    # Save results
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w') as f:
        json.dump(report, f, indent=2)
    
    print(f"\nResults saved to: {args.output}")
    
    # Print summary
    print("\nSummary:")
    print("-" * 50)
    for engine in engines:
        engine_results = [r for r in all_results if r.engine == engine]
        passed = sum(1 for r in engine_results if not r.error)
        failed = len(engine_results) - passed
        print(f"  {engine}: {passed} passed, {failed} failed")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
