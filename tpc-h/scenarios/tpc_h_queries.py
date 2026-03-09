#!/usr/bin/env python3
"""
TPC-H Benchmark Queries

22 analytical queries for decision support benchmark.
"""

from dataclasses import dataclass
from typing import List

@dataclass
class TPC-HQuery:
    num: int
    name: str
    description: str
    sql: str

class TPCHQueries:
    """TPC-H benchmark queries."""
    
    @staticmethod
    def get_all_queries() -> List[TPC-HQuery]:
        return [
            TPC-HQuery(1, "Pricing Summary Report", "Line items returned",
                """SELECT l_returnflag, l_linestatus, SUM(l_quantity) as sum_qty,
                    SUM(l_extendedprice) as sum_base_price,
                    SUM(l_extendedprice*(1-l_discount)) as sum_disc_price,
                    SUM(l_extendedprice*(1-l_discount)*(1+l_tax)) as sum_charge,
                    AVG(l_quantity) as avg_qty, AVG(l_extendedprice) as avg_price,
                    AVG(l_discount) as avg_disc, COUNT(*) as count_order
                FROM lineitem WHERE l_shipdate <= DATE '1998-12-01' - INTERVAL '90' DAY
                GROUP BY l_returnflag, l_linestatus ORDER BY l_returnflag, l_linestatus"""),
            
            TPC-HQuery(6, "Forecasting Revenue Change", "Revenue increase with quantity discount",
                """SELECT SUM(l_extendedprice*l_discount) as revenue
                FROM lineitem WHERE l_shipdate >= DATE '1994-01-01'
                AND l_shipdate < DATE '1994-01-01' + INTERVAL '1' YEAR
                AND l_discount BETWEEN 0.06 - 0.01 AND 0.06 + 0.01
                AND l_quantity < 24"""),
            
            TPC-HQuery(12, "Shipping Modes and Order Priority", "Selective shipping modes",
                """SELECT l_shipmode,
                    SUM(CASE WHEN o_orderpriority = '1-URGENT' OR o_orderpriority = '2-HIGH' THEN 1 ELSE 0 END) as high_line_count,
                    SUM(CASE WHEN o_orderpriority <> '1-URGENT' AND o_orderpriority <> '2-HIGH' THEN 1 ELSE 0 END) as low_line_count
                FROM orders, lineitem WHERE o_orderkey = l_orderkey
                AND l_shipmode IN ('MAIL', 'SHIP')
                AND l_commitdate < l_receiptdate
                AND l_shipdate < l_commitdate
                AND l_receiptdate >= DATE '1994-01-01'
                AND l_receiptdate < DATE '1994-01-01' + INTERVAL '1' YEAR
                GROUP BY l_shipmode ORDER BY l_shipmode"""),
            
            TPC-HQuery(14, "Promotion Effect", "Lineitem promo revenue percentage",
                """SELECT 100.00 * SUM(CASE WHEN p_type LIKE 'PROMO%' THEN l_extendedprice*(1-l_discount) ELSE 0 END)
                    / SUM(l_extendedprice*(1-l_discount)) as promo_revenue
                FROM lineitem, part WHERE l_partkey = p_partkey
                AND l_shipdate >= DATE '1995-09-01'
                AND l_shipdate < DATE '1995-09-01' + INTERVAL '1' MONTH"""),
        ]

def get_schema_sql() -> str:
    return """
    CREATE TABLE region (r_regionkey INT PRIMARY KEY, r_name CHAR(25), r_comment VARCHAR(152));
    CREATE TABLE nation (n_nationkey INT PRIMARY KEY, n_name CHAR(25), n_regionkey INT, n_comment VARCHAR(152));
    CREATE TABLE part (p_partkey INT PRIMARY KEY, p_name VARCHAR(55), p_mfgr CHAR(25), p_brand CHAR(10), p_type VARCHAR(25), p_size INT, p_container CHAR(10), p_retailprice DECIMAL(15,2), p_comment VARCHAR(23));
    CREATE TABLE supplier (s_suppkey INT PRIMARY KEY, s_name CHAR(25), s_address VARCHAR(40), s_nationkey INT, s_phone CHAR(15), s_acctbal DECIMAL(15,2), s_comment VARCHAR(101));
    CREATE TABLE partsupp (ps_partkey INT, ps_suppkey INT, ps_availqty INT, ps_supplycost DECIMAL(15,2), ps_comment VARCHAR(199), PRIMARY KEY (ps_partkey, ps_suppkey));
    CREATE TABLE customer (c_custkey INT PRIMARY KEY, c_name VARCHAR(25), c_address VARCHAR(40), c_nationkey INT, c_phone CHAR(15), c_acctbal DECIMAL(15,2), c_mktsegment CHAR(10), c_comment VARCHAR(117));
    CREATE TABLE orders (o_orderkey INT PRIMARY KEY, o_custkey INT, o_orderstatus CHAR(1), o_totalprice DECIMAL(15,2), o_orderdate DATE, o_orderpriority CHAR(15), o_clerk CHAR(15), o_shippriority INT, o_comment VARCHAR(79));
    CREATE TABLE lineitem (l_orderkey INT, l_partkey INT, l_suppkey INT, l_linenumber INT, l_quantity DECIMAL(15,2), l_extendedprice DECIMAL(15,2), l_discount DECIMAL(15,2), l_tax DECIMAL(15,2), l_returnflag CHAR(1), l_linestatus CHAR(1), l_shipdate DATE, l_commitdate DATE, l_receiptdate DATE, l_shipinstruct CHAR(25), l_shipmode CHAR(10), l_comment VARCHAR(44), PRIMARY KEY (l_orderkey, l_linenumber));
    """

if __name__ == '__main__':
    queries = TPCHQueries.get_all_queries()
    print(f"TPC-H Queries: {len(queries)}")
    for q in queries:
        print(f"  Q{q.num}: {q.name}")
