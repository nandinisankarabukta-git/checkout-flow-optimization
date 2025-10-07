#!/usr/bin/env python3
"""
Generate Markdown Report
========================
Generates a markdown summary report with key checkout funnel metrics.
"""

import duckdb
from datetime import datetime
from pathlib import Path


def generate_report(output_path: str = "reports/metrics_summary.md"):
    """Generate markdown report with funnel metrics."""

    # Connect to warehouse
    conn = duckdb.connect("duckdb/warehouse.duckdb")

    # Start building report
    lines = []
    lines.append("# Checkout Flow Optimization: Metrics Summary\n")
    lines.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    lines.append("---\n")

    # Overall Funnel
    lines.append("## Overall Funnel\n")
    funnel = conn.execute("""
        WITH adders AS (
            SELECT variant, COUNT(DISTINCT user_id) as adders
            FROM marts.fct_experiments
            GROUP BY variant
        ),
        orders AS (
            SELECT variant, COUNT(DISTINCT user_id) as orderers
            FROM marts.fct_orders
            GROUP BY variant
        )
        SELECT 
            a.variant, 
            a.adders, 
            COALESCE(o.orderers, 0) as orderers,
            ROUND(COALESCE(o.orderers, 0) * 100.0 / a.adders, 1) as conv_rate
        FROM adders a
        LEFT JOIN orders o ON a.variant = o.variant
        ORDER BY a.variant
    """).fetchall()

    lines.append("| Variant | Adders | Orders | Conversion Rate |\n")
    lines.append("|---------|--------|--------|-----------------|\n")
    for row in funnel:
        lines.append(f"| {row[0]} | {row[1]:,} | {row[2]:,} | {row[3]}% |\n")

    # Step Progression
    lines.append("\n## Step Progression\n")
    steps = conn.execute("""
        SELECT 
            step_name, 
            COUNT(DISTINCT checkout_id) as checkouts,
            ROUND(AVG(median_latency_ms), 0) as avg_latency
        FROM marts.fct_checkout_steps
        GROUP BY step_name, step_index
        ORDER BY step_index
    """).fetchall()

    lines.append("| Step | Checkouts | Avg Latency (ms) |\n")
    lines.append("|------|-----------|------------------|\n")
    for row in steps:
        lines.append(f"| {row[0]} | {row[1]:,} | {row[2]:.0f} |\n")

    # Guardrail Metrics
    lines.append("\n## Guardrail Metrics (Most Recent Date)\n")
    guardrails = conn.execute("""
        WITH most_recent_date AS (
            SELECT MAX(date) as max_date FROM events.add_to_cart
        ),
        payment_auth AS (
            SELECT 
                variant,
                COUNT(*) as total_attempts,
                ROUND(SUM(CASE WHEN authorized THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) as auth_rate_pct
            FROM events.payment_attempt, most_recent_date
            WHERE date = most_recent_date.max_date
            GROUP BY variant
        ),
        order_values AS (
            SELECT 
                variant,
                ROUND(AVG(order_value), 2) as avg_order_value
            FROM events.order_completed, most_recent_date
            WHERE date = most_recent_date.max_date
            GROUP BY variant
        )
        SELECT 
            p.variant,
            p.auth_rate_pct,
            o.avg_order_value
        FROM payment_auth p
        JOIN order_values o ON p.variant = o.variant
        ORDER BY p.variant
    """).fetchall()

    lines.append("| Variant | Payment Auth Rate | Avg Order Value |\n")
    lines.append("|---------|-------------------|------------------|\n")
    for row in guardrails:
        lines.append(f"| {row[0]} | {row[1]}% | ${row[2]:.2f} |\n")

    conn.close()

    # Write report
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w") as f:
        f.writelines(lines)

    return str(output_path.resolve())


if __name__ == "__main__":
    output = generate_report()
    print(f"Report generated: {output}")
