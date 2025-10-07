#!/usr/bin/env python3
"""
Data Quality Checks for Checkout Flow Optimization

Validates data integrity, referential constraints, and business rules
across DuckDB events and marts tables.

Exit codes:
    0: All checks passed
    1: One or more checks failed
"""

import os
import sys
import math
from pathlib import Path
from typing import Tuple, List, Dict, Any

try:
    import duckdb
except ImportError:
    print("ERROR: duckdb module not found. Install with: pip install duckdb")
    sys.exit(1)


def connect_warehouse() -> duckdb.DuckDBPyConnection:
    """Connects to the warehouse database."""
    db_path = Path(__file__).parent.parent / "duckdb" / "warehouse.duckdb"
    if not db_path.exists():
        print(f"ERROR: Database not found at {db_path}")
        print("Run 'make build' to create the database.")
        sys.exit(1)

    conn = duckdb.connect()
    # Attach the warehouse database
    conn.execute(f"ATTACH '{db_path}' AS warehouse")
    conn.execute("USE warehouse")
    return conn


def check_orders_referential_integrity(
    conn: duckdb.DuckDBPyConnection,
) -> Tuple[bool, str]:
    """
    Check that every order_completed.checkout_id exists in begin_checkout.

    Returns:
        (passed, message): Boolean success status and descriptive message
    """
    result = conn.execute("""
        SELECT 
            o.checkout_id,
            o.order_id
        FROM events.order_completed o
        LEFT JOIN events.begin_checkout b ON o.checkout_id = b.checkout_id
        WHERE b.checkout_id IS NULL
        LIMIT 10
    """).fetchall()

    if not result:
        total_orders = conn.execute(
            "SELECT COUNT(*) FROM events.order_completed"
        ).fetchone()[0]
        return True, f"All {total_orders:,} orders have valid checkout_id references"

    orphaned_count = conn.execute("""
        SELECT COUNT(*)
        FROM events.order_completed o
        LEFT JOIN events.begin_checkout b ON o.checkout_id = b.checkout_id
        WHERE b.checkout_id IS NULL
    """).fetchone()[0]

    sample_ids = [row[1] for row in result[:5]]
    return False, f"Found {orphaned_count} orphaned orders. Sample: {sample_ids}"


def check_steps_referential_integrity(
    conn: duckdb.DuckDBPyConnection,
) -> Tuple[bool, str]:
    """
    Check that every checkout_step_view.checkout_id exists in begin_checkout.

    Returns:
        (passed, message): Boolean success status and descriptive message
    """
    result = conn.execute("""
        SELECT 
            c.checkout_id,
            c.step_name
        FROM events.checkout_step_view c
        LEFT JOIN events.begin_checkout b ON c.checkout_id = b.checkout_id
        WHERE b.checkout_id IS NULL
        LIMIT 10
    """).fetchall()

    if not result:
        total_steps = conn.execute(
            "SELECT COUNT(*) FROM events.checkout_step_view"
        ).fetchone()[0]
        return True, f"All {total_steps:,} step views have valid checkout_id references"

    orphaned_count = conn.execute("""
        SELECT COUNT(*)
        FROM events.checkout_step_view c
        LEFT JOIN events.begin_checkout b ON c.checkout_id = b.checkout_id
        WHERE b.checkout_id IS NULL
    """).fetchone()[0]

    sample_ids = [row[0][:20] for row in result[:5]]
    return False, f"Found {orphaned_count} orphaned step views. Sample: {sample_ids}"


def check_enum_validation(conn: duckdb.DuckDBPyConnection) -> Tuple[bool, str]:
    """
    Check that step_name and variant contain only valid enum values.

    Valid values:
        step_name: {address, shipping, payment, review}
        variant: {control, treatment}

    Returns:
        (passed, message): Boolean success status and descriptive message
    """
    valid_steps = {"address", "shipping", "payment", "review"}
    valid_variants = {"control", "treatment"}

    issues = []

    # Check step_name in checkout_step_view
    result = conn.execute("""
        SELECT DISTINCT step_name
        FROM events.checkout_step_view
    """).fetchall()

    actual_steps = {row[0] for row in result}
    invalid_steps = actual_steps - valid_steps

    if invalid_steps:
        issues.append(f"Invalid step_name values: {invalid_steps}")

    # Check variant across all relevant tables
    for table in [
        "events.add_to_cart",
        "events.begin_checkout",
        "events.checkout_step_view",
        "events.order_completed",
    ]:
        result = conn.execute(f"""
            SELECT DISTINCT variant
            FROM {table}
        """).fetchall()

        actual_variants = {row[0] for row in result}
        invalid_variants = actual_variants - valid_variants

        if invalid_variants:
            table_name = table.split(".")[-1]
            issues.append(f"Invalid variant in {table_name}: {invalid_variants}")

    if not issues:
        return True, "All enum values valid (step_name, variant)"

    return False, "; ".join(issues)


def check_randomization_balance(conn: duckdb.DuckDBPyConnection) -> Tuple[bool, str]:
    """
    Check that treatment share is between 48% and 52% in fct_experiments.

    Returns:
        (passed, message): Boolean success status and descriptive message
    """
    result = conn.execute("""
        SELECT 
            variant,
            COUNT(*) as count,
            ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) as percentage
        FROM marts.fct_experiments
        GROUP BY variant
        ORDER BY variant
    """).fetchall()

    variant_pcts = {row[0]: row[2] for row in result}

    if "treatment" not in variant_pcts:
        return False, "No treatment variant found in fct_experiments"

    treatment_pct = variant_pcts["treatment"]

    if 48.0 <= treatment_pct <= 52.0:
        control_pct = variant_pcts.get("control", 0)
        return (
            True,
            f"Balanced: control={control_pct:.2f}%, treatment={treatment_pct:.2f}%",
        )

    return False, f"Imbalanced: treatment={treatment_pct:.2f}% (expected 48-52%)"


def check_timestamp_sanity(conn: duckdb.DuckDBPyConnection) -> Tuple[bool, str]:
    """
    Check that for each checkout, first step timestamp >= begin_checkout timestamp.

    Returns:
        (passed, message): Boolean success status and descriptive message
    """
    result = conn.execute("""
        WITH first_steps AS (
            SELECT 
                checkout_id,
                MIN(timestamp) as first_step_ts
            FROM events.checkout_step_view
            GROUP BY checkout_id
        )
        SELECT 
            b.checkout_id,
            b.timestamp as begin_ts,
            f.first_step_ts
        FROM events.begin_checkout b
        JOIN first_steps f ON b.checkout_id = f.checkout_id
        WHERE f.first_step_ts < b.timestamp
        LIMIT 10
    """).fetchall()

    if not result:
        total_checkouts = conn.execute("""
            SELECT COUNT(DISTINCT checkout_id) 
            FROM events.checkout_step_view
        """).fetchone()[0]
        return True, f"All {total_checkouts:,} checkouts have valid timestamp ordering"

    violation_count = conn.execute("""
        WITH first_steps AS (
            SELECT 
                checkout_id,
                MIN(timestamp) as first_step_ts
            FROM events.checkout_step_view
            GROUP BY checkout_id
        )
        SELECT COUNT(*)
        FROM events.begin_checkout b
        JOIN first_steps f ON b.checkout_id = f.checkout_id
        WHERE f.first_step_ts < b.timestamp
    """).fetchone()[0]

    sample_ids = [row[0][:20] for row in result[:5]]
    return False, f"Found {violation_count} timestamp violations. Sample: {sample_ids}"


def check_aa_test(conn: duckdb.DuckDBPyConnection) -> Tuple[bool, str]:
    """
    Check A/A test validity using two-sample proportion test.

    Computes conditional conversion rate (orders/adders) for control vs treatment
    for the most recent date. Runs two-sample proportion test with pooled variance.

    Returns:
        (passed, message): Boolean success status and descriptive message
    """
    # Get most recent date
    result = conn.execute("""
        SELECT MAX(date) as max_date
        FROM events.add_to_cart
    """).fetchone()

    if not result or not result[0]:
        return False, "No data found in events.add_to_cart"

    max_date = result[0]

    # Get conversion counts by variant for most recent date
    result = conn.execute(f"""
        WITH adders AS (
            SELECT DISTINCT user_id, variant
            FROM events.add_to_cart
            WHERE date = '{max_date}'
        ),
        orderers AS (
            SELECT DISTINCT user_id, variant
            FROM events.order_completed
            WHERE date = '{max_date}'
        )
        SELECT 
            a.variant,
            COUNT(DISTINCT a.user_id) as adders,
            COUNT(DISTINCT o.user_id) as orderers
        FROM adders a
        LEFT JOIN orderers o ON a.user_id = o.user_id AND a.variant = o.variant
        GROUP BY a.variant
        ORDER BY a.variant
    """).fetchall()

    if len(result) != 2:
        return False, f"Expected 2 variants, found {len(result)}"

    # Extract metrics
    control_data = [r for r in result if r[0] == "control"][0]
    treatment_data = [r for r in result if r[0] == "treatment"][0]

    control_adders = control_data[1]
    control_orderers = control_data[2]
    treatment_adders = treatment_data[1]
    treatment_orderers = treatment_data[2]

    # Calculate conversion rates
    p1 = control_orderers / control_adders if control_adders > 0 else 0
    p2 = treatment_orderers / treatment_adders if treatment_adders > 0 else 0

    # Pooled proportion
    p_pooled = (control_orderers + treatment_orderers) / (
        control_adders + treatment_adders
    )

    # Standard error with pooled variance
    se_pooled = math.sqrt(
        p_pooled * (1 - p_pooled) * (1 / control_adders + 1 / treatment_adders)
    )

    # Z-statistic
    z_stat = (p2 - p1) / se_pooled if se_pooled > 0 else 0

    # Two-tailed p-value (approximate using standard normal)
    # P-value = 2 * P(Z > |z|)
    # Using error function approximation
    p_value = 2 * (1 - 0.5 * (1 + math.erf(abs(z_stat) / math.sqrt(2))))

    # Format message
    msg = (
        f"Date={max_date}, Control: {control_orderers}/{control_adders} ({p1:.1%}), "
        f"Treatment: {treatment_orderers}/{treatment_adders} ({p2:.1%}), "
        f"p={p_value:.4f}"
    )

    # A/A test should NOT show significant difference (p >= 0.05)
    if p_value < 0.05:
        return False, f"Significant difference detected (FAIL A/A test). {msg}"
    else:
        return True, f"No significant difference (A/A valid). {msg}"


def run_all_checks(conn: duckdb.DuckDBPyConnection) -> List[Dict[str, Any]]:
    """
    Run all data quality checks.

    Returns:
        List of check results with name, passed status, and message
    """
    checks = [
        ("Referential: orders → checkouts", check_orders_referential_integrity),
        ("Referential: steps → checkouts", check_steps_referential_integrity),
        ("Enum validation", check_enum_validation),
        ("Randomization balance", check_randomization_balance),
        ("Timestamp sanity", check_timestamp_sanity),
    ]

    # Add A/A test check if AA_MODE=1 environment variable is set
    if os.environ.get("AA_MODE") == "1":
        checks.append(("A/A test validation", check_aa_test))

    results = []
    for check_name, check_func in checks:
        try:
            passed, message = check_func(conn)
            results.append({"name": check_name, "passed": passed, "message": message})
        except Exception as e:
            results.append(
                {"name": check_name, "passed": False, "message": f"ERROR: {str(e)}"}
            )

    return results


def print_results(results: List[Dict[str, Any]]) -> None:
    """Print check results in a formatted table."""
    print()
    print("=" * 80)
    print("DATA QUALITY CHECKS")
    print("=" * 80)
    print()

    # Calculate column widths
    max_name_len = max(len(r["name"]) for r in results)
    col_width = max(max_name_len + 2, 30)

    # Print header
    print(f"{'CHECK':<{col_width}} {'STATUS':<10} {'DETAILS'}")
    print("-" * 80)

    # Print each result
    for result in results:
        status = "PASS" if result["passed"] else "FAIL"
        status_colored = status

        # Truncate message if too long
        message = result["message"]
        if len(message) > 60:
            message = message[:57] + "..."

        print(f"{result['name']:<{col_width}} {status_colored:<10} {message}")

    print()


def main() -> int:
    """
    Main entry point: run all checks and return exit code.

    Returns:
        0 if all checks passed, 1 otherwise
    """
    try:
        # Connect to warehouse
        conn = connect_warehouse()

        # Run all checks
        results = run_all_checks(conn)

        # Print results
        print_results(results)

        # Calculate summary
        total_checks = len(results)
        passed_checks = sum(1 for r in results if r["passed"])
        failed_checks = total_checks - passed_checks

        # Print summary
        print("=" * 80)
        if failed_checks == 0:
            print(f"SUMMARY: All {total_checks} checks PASSED")
            print("=" * 80)
            print()
            return 0
        else:
            print(f"SUMMARY: {failed_checks} of {total_checks} checks FAILED")
            print("=" * 80)
            print()
            return 1

    except Exception as e:
        print(f"\nFATAL ERROR: {e}", file=sys.stderr)
        return 1
    finally:
        if "conn" in locals():
            conn.close()


if __name__ == "__main__":
    sys.exit(main())
