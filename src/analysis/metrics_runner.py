"""
Metrics Runner for A/B Testing

Fetches metric aggregates from DuckDB for analysis, providing simple data structures
ready for consumption by statistical functions.
"""

import duckdb
from pathlib import Path
from typing import Dict, Any, Optional
import sys


def connect_warehouse(
    db_path: str = "duckdb/warehouse.duckdb",
) -> duckdb.DuckDBPyConnection:
    """
    Connects to the DuckDB warehouse.

    Args:
        db_path: Path to the DuckDB database file

    Returns:
        DuckDB connection object

    Raises:
        FileNotFoundError: If database file does not exist
        RuntimeError: If connection fails
    """
    db_file = Path(db_path)
    if not db_file.exists():
        raise FileNotFoundError(
            f"DuckDB warehouse not found at {db_path}. "
            "Run 'make build' to create the warehouse."
        )

    try:
        conn = duckdb.connect(str(db_file))
        return conn
    except Exception as e:
        raise RuntimeError(f"Failed to connect to DuckDB: {e}")


def most_recent_date(conn: Optional[duckdb.DuckDBPyConnection] = None) -> str:
    """
    Discover the most recent date present in events.add_to_cart.

    Args:
        conn: Optional DuckDB connection. If None, creates a new connection.

    Returns:
        Most recent date as ISO string (YYYY-MM-DD)

    Raises:
        ValueError: If no data found or query fails
    """
    close_conn = False
    if conn is None:
        conn = connect_warehouse()
        close_conn = True

    try:
        result = conn.execute("""
            SELECT MAX(date) as max_date
            FROM events.add_to_cart
        """).fetchone()

        if not result or result[0] is None:
            raise ValueError(
                "No data found in events.add_to_cart. "
                "Run 'make simulate' to generate data."
            )

        max_date = result[0]
        return str(max_date)

    except duckdb.CatalogException as e:
        raise ValueError(
            f"Schema or table not found: {e}. Run 'make build' to create event views."
        )
    except Exception as e:
        raise ValueError(f"Failed to query most recent date: {e}")
    finally:
        if close_conn:
            conn.close()


def get_variant_counts_for_ccr(
    date: Optional[str] = None,
    conn: Optional[duckdb.DuckDBPyConnection] = None,
) -> Dict[str, Dict[str, int]]:
    """
    Get adders and orders per variant for conditional conversion rate analysis.

    Fetches user-level counts for the primary metric (CCR = orders / adders).
    Uses marts.fct_experiments for adders and marts.fct_orders for orders.

    Args:
        date: Optional date filter (YYYY-MM-DD). If None, uses most recent date.
        conn: Optional DuckDB connection. If None, creates a new connection.

    Returns:
        Dictionary with variant-level counts:
        {
            "control": {"adders": 5000, "orders": 1750},
            "treatment": {"adders": 5000, "orders": 1855}
        }

    Raises:
        ValueError: If no data found or query fails

    Example:
        >>> counts = get_variant_counts_for_ccr()
        >>> control_ccr = counts["control"]["orders"] / counts["control"]["adders"]
    """
    close_conn = False
    if conn is None:
        conn = connect_warehouse()
        close_conn = True

    try:
        if date is None:
            date = most_recent_date(conn)

        # Query adders and orders per variant
        result = conn.execute(f"""
            WITH adders AS (
                SELECT
                    variant,
                    COUNT(DISTINCT user_id) as adders
                FROM marts.fct_experiments
                WHERE DATE(first_exposed_at) = '{date}'
                GROUP BY variant
            ),
            orders AS (
                SELECT
                    variant,
                    COUNT(DISTINCT user_id) as orderers
                FROM marts.fct_orders
                WHERE DATE(ordered_at) = '{date}'
                GROUP BY variant
            )
            SELECT
                a.variant,
                a.adders,
                COALESCE(o.orderers, 0) as orderers
            FROM adders a
            LEFT JOIN orders o ON a.variant = o.variant
            ORDER BY a.variant
        """).fetchall()

        if not result:
            raise ValueError(
                f"No variant data found for date {date}. "
                "Check that data exists and marts are built."
            )

        # Convert to dictionary
        variant_counts = {}
        for row in result:
            variant, adders, orders = row
            variant_counts[variant] = {
                "adders": int(adders),
                "orders": int(orders),
            }

        # Validate we have both variants
        if len(variant_counts) < 2:
            raise ValueError(
                f"Expected 2 variants, found {len(variant_counts)}. "
                f"Date: {date}, Variants: {list(variant_counts.keys())}"
            )

        return variant_counts

    except duckdb.CatalogException as e:
        raise ValueError(
            f"Schema or table not found: {e}. Run 'make marts' to create mart tables."
        )
    except Exception as e:
        if "No variant data found" in str(e) or "Expected 2 variants" in str(e):
            raise
        raise ValueError(f"Failed to fetch variant counts: {e}")
    finally:
        if close_conn:
            conn.close()


def get_guardrails(
    date: Optional[str] = None,
    conn: Optional[duckdb.DuckDBPyConnection] = None,
) -> Dict[str, Dict[str, Any]]:
    """
    Get guardrail metrics per variant for the specified date.

    Fetches:
    - Payment authorization rate (authorized / total_attempts)
    - Average order value (AOV)

    Args:
        date: Optional date filter (YYYY-MM-DD). If None, uses most recent date.
        conn: Optional DuckDB connection. If None, creates a new connection.

    Returns:
        Dictionary with variant-level guardrail metrics:
        {
            "control": {
                "payment_auth": {
                    "authorized": 1800,
                    "total_attempts": 1950,
                    "rate": 0.923
                },
                "aov": {
                    "mean": 256.47,
                    "count": 1750
                }
            },
            "treatment": { ... }
        }

    Raises:
        ValueError: If no data found or query fails

    Example:
        >>> guardrails = get_guardrails()
        >>> control_auth_rate = guardrails["control"]["payment_auth"]["rate"]
    """
    close_conn = False
    if conn is None:
        conn = connect_warehouse()
        close_conn = True

    try:
        if date is None:
            date = most_recent_date(conn)

        # Query payment authorization counts
        payment_result = conn.execute(f"""
            SELECT
                variant,
                COUNT(*) as total_attempts,
                SUM(CASE WHEN authorized THEN 1 ELSE 0 END) as authorized_attempts
            FROM events.payment_attempt
            WHERE DATE(timestamp) = '{date}'
            GROUP BY variant
            ORDER BY variant
        """).fetchall()

        if not payment_result:
            raise ValueError(
                f"No payment data found for date {date}. Check that data exists."
            )

        # Query average order value
        aov_result = conn.execute(f"""
            SELECT
                variant,
                COUNT(*) as order_count,
                AVG(order_value) as avg_order_value
            FROM events.order_completed
            WHERE DATE(timestamp) = '{date}'
            GROUP BY variant
            ORDER BY variant
        """).fetchall()

        if not aov_result:
            raise ValueError(
                f"No order data found for date {date}. Check that data exists."
            )

        # Build payment auth dictionary
        payment_dict = {}
        for row in payment_result:
            variant, total, authorized = row
            rate = authorized / total if total > 0 else 0
            payment_dict[variant] = {
                "authorized": int(authorized),
                "total_attempts": int(total),
                "rate": float(rate),
            }

        # Build AOV dictionary
        aov_dict = {}
        for row in aov_result:
            variant, count, mean = row
            aov_dict[variant] = {
                "mean": float(mean),
                "count": int(count),
            }

        # Combine into final structure
        guardrails = {}
        for variant in payment_dict.keys():
            guardrails[variant] = {
                "payment_auth": payment_dict.get(variant, {}),
                "aov": aov_dict.get(variant, {}),
            }

        # Validate we have both variants
        if len(guardrails) < 2:
            raise ValueError(
                f"Expected 2 variants, found {len(guardrails)}. "
                f"Date: {date}, Variants: {list(guardrails.keys())}"
            )

        return guardrails

    except duckdb.CatalogException as e:
        raise ValueError(
            f"Schema or table not found: {e}. Run 'make build' to create event views."
        )
    except Exception as e:
        if (
            "No payment data found" in str(e)
            or "No order data found" in str(e)
            or "Expected 2 variants" in str(e)
        ):
            raise
        raise ValueError(f"Failed to fetch guardrail metrics: {e}")
    finally:
        if close_conn:
            conn.close()


def get_summary_stats(
    date: Optional[str] = None,
    conn: Optional[duckdb.DuckDBPyConnection] = None,
) -> Dict[str, Any]:
    """
    Get summary statistics for a complete analysis snapshot.

    Convenience function that fetches CCR counts and guardrails in one call.

    Args:
        date: Optional date filter (YYYY-MM-DD). If None, uses most recent date.
        conn: Optional DuckDB connection. If None, creates a new connection.

    Returns:
        Dictionary with:
        {
            "date": "2025-01-14",
            "variant_counts": { ... },
            "guardrails": { ... }
        }

    Example:
        >>> stats = get_summary_stats()
        >>> print(f"Analysis date: {stats['date']}")
    """
    close_conn = False
    if conn is None:
        conn = connect_warehouse()
        close_conn = True

    try:
        if date is None:
            date = most_recent_date(conn)

        variant_counts = get_variant_counts_for_ccr(date, conn)
        guardrails = get_guardrails(date, conn)

        return {
            "date": date,
            "variant_counts": variant_counts,
            "guardrails": guardrails,
        }

    finally:
        if close_conn:
            conn.close()
