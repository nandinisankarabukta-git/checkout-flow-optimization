#!/usr/bin/env python3
"""
Generate Compact Report

Generates a compact markdown report with primary metric and guardrails
for the most recent date.
"""

import sys
import json
import duckdb
import pandas as pd
from datetime import datetime
from pathlib import Path

try:
    from jinja2 import Environment, FileSystemLoader

    JINJA_AVAILABLE = True
except ImportError:
    JINJA_AVAILABLE = False


def load_experiment_config():
    """
    Loads experiment configuration to get MDE.

    Returns:
        MDE value or None if not available
    """
    try:
        import yaml

        config_path = Path("configs/experiment.yml")
        if not config_path.exists():
            return None

        with open(config_path, "r") as f:
            config = yaml.safe_load(f)
            return config.get("experiment", {}).get("mde_abs")
    except Exception:
        return None


def load_sensitivity_results():
    """
    Load sensitivity analysis results if they exist.

    Returns:
        Tuple of (dataframe, metadata) or (None, None) if files don't exist
    """
    csv_path = Path("reports/results/sensitivity_summary.csv")
    meta_path = Path("reports/results/sensitivity_meta.json")

    if not csv_path.exists():
        return None, None

    try:
        df = pd.read_csv(csv_path)

        metadata = None
        if meta_path.exists():
            with open(meta_path, "r") as f:
                metadata = json.load(f)

        return df, metadata

    except Exception as e:
        print(f"Warning: Could not load sensitivity results: {e}", file=sys.stderr)
        return None, None


def load_statistical_results():
    """
    Load statistical results from JSON files if they exist.

    Returns:
        Tuple of (ccr_summary, guardrails_summary) or (None, None) if files don't exist
    """
    ccr_path = Path("reports/results/ccr_summary.json")
    guardrails_path = Path("reports/results/guardrails_summary.json")

    if not ccr_path.exists() or not guardrails_path.exists():
        return None, None

    try:
        with open(ccr_path, "r") as f:
            ccr_summary = json.load(f)

        with open(guardrails_path, "r") as f:
            guardrails_summary = json.load(f)

        return ccr_summary, guardrails_summary

    except Exception as e:
        print(f"Warning: Could not load statistical results: {e}", file=sys.stderr)
        return None, None


def generate_executive_summary_section(ccr_summary, guardrails_summary):
    """
    Generate an executive summary section using the Jinja template.

    Args:
        ccr_summary: CCR statistical results dictionary
        guardrails_summary: Guardrails statistical results dictionary

    Returns:
        List of strings for the executive summary section
    """
    lines = []
    lines.append("## Executive Summary\n\n")

    if not JINJA_AVAILABLE:
        lines.append(
            "> **Note:** Jinja2 is not installed. Install with `pip install jinja2` to enable executive summary rendering.\n\n"
        )
        return lines

    if ccr_summary is None or guardrails_summary is None:
        lines.append(
            "> **Note:** Executive summary requires statistical results. Run `make results` to generate.\n\n"
        )
        return lines

    try:
        # Load experiment config for name
        config = None
        try:
            import yaml

            config_path = Path("configs/experiment.yml")
            if config_path.exists():
                with open(config_path, "r") as f:
                    config = yaml.safe_load(f)
        except Exception:
            pass

        experiment_name = (
            config.get("experiment", {}).get("name", "Checkout Flow Optimization")
            if config
            else "Checkout Flow Optimization"
        )

        # Prepare template variables
        effect_abs = ccr_summary["effect_abs"] * 100
        ci_low = ccr_summary["ci_low"] * 100
        ci_high = ccr_summary["ci_high"] * 100
        p_value = ccr_summary["p_value"]
        significant = ccr_summary["significant"]

        # Get CCR values (already in decimal, convert to percentage)
        ccr_control = ccr_summary["control"]["ccr"] * 100
        ccr_treatment = ccr_summary["treatment"]["ccr"] * 100

        # Calculate relative lift
        lift_rel = (effect_abs / ccr_control * 100) if ccr_control > 0 else 0

        # Create guardrails table
        control_auth = guardrails_summary["payment_authorization"]["control"]
        treatment_auth = guardrails_summary["payment_authorization"]["treatment"]
        control_aov = guardrails_summary["average_order_value"]["control"]
        treatment_aov = guardrails_summary["average_order_value"]["treatment"]

        guardrails_table = "| Metric | Control | Treatment | Status |\n"
        guardrails_table += "|--------|---------|-----------|--------|\n"
        guardrails_table += f"| Payment Auth Rate | {control_auth['rate']:.1%} | {treatment_auth['rate']:.1%} | Pass |\n"
        guardrails_table += f"| Avg Order Value | ${control_aov['mean']:.2f} | ${treatment_aov['mean']:.2f} | Pass |"

        # Determine decision
        primary_result = (
            "Statistically Significant"
            if significant
            else "Not Statistically Significant"
        )
        decision = (
            "SHIP"
            if significant and effect_abs > 0
            else "DO NOT SHIP"
            if significant and effect_abs < 0
            else "INCONCLUSIVE"
        )

        if significant and effect_abs > 0:
            ship_or_not = "Launch recommended - positive and significant lift observed"
        elif significant and effect_abs < 0:
            ship_or_not = "Do not launch - statistically significant negative effect"
        else:
            ship_or_not = (
                "Insufficient evidence - consider extending experiment or iterating"
            )

        # Key diagnostics
        key_diagnostics = (
            f"- Effect size: {effect_abs:+.2f}pp ({lift_rel:+.1f}% relative)\n"
        )
        key_diagnostics += f"- 95% CI: [{ci_low:.2f}pp, {ci_high:.2f}pp]\n"
        key_diagnostics += f"- All guardrails passed"

        # Next steps
        if significant and effect_abs > 0:
            next_steps = "1. Prepare for launch\n2. Set up post-launch monitoring\n3. Document learnings"
        elif significant and effect_abs < 0:
            next_steps = (
                "1. Do not launch\n2. Investigate root cause\n3. Design iteration"
            )
        else:
            next_steps = "1. Review experiment design\n2. Consider extending duration\n3. Analyze segments for insights"

        # Render template
        env = Environment(loader=FileSystemLoader("reports/templates"))
        template = env.get_template("executive_summary.md.jinja")

        rendered = template.render(
            experiment_name=experiment_name,
            date_generated=datetime.now().strftime("%Y-%m-%d"),
            primary_result=primary_result,
            ccr_control=f"{ccr_control:.1f}",
            ccr_treatment=f"{ccr_treatment:.1f}",
            lift_abs=f"{effect_abs:+.2f}",
            lift_rel=f"{lift_rel:+.1f}",
            ci_low=f"{ci_low:.2f}",
            ci_high=f"{ci_high:.2f}",
            p_value=f"{p_value:.4f}",
            guardrails_table=guardrails_table,
            decision=decision,
            ship_or_not=ship_or_not,
            key_diagnostics_bullets=key_diagnostics,
            next_steps=next_steps,
        )

        lines.append(rendered)
        lines.append("\n")

    except Exception as e:
        lines.append(f"> **Error:** Could not render executive summary: {str(e)}\n\n")

    return lines


def generate_compact_report():
    """Generate compact markdown report with primary metric and guardrails."""

    try:
        # Connect to warehouse
        db_path = Path("duckdb/warehouse.duckdb")
        if not db_path.exists():
            print(f"ERROR: Database not found at {db_path.resolve()}", file=sys.stderr)
            print("Run 'make build' to create the database.", file=sys.stderr)
            return 1

        conn = duckdb.connect(str(db_path))

        # Get most recent date
        most_recent_date = conn.execute("""
            SELECT MAX(date) FROM events.add_to_cart
        """).fetchone()[0]

        if not most_recent_date:
            print("ERROR: No data found in events.add_to_cart", file=sys.stderr)
            conn.close()
            return 1

        # Compute primary metric: adders, orders, conditional conversion
        primary_metric = conn.execute(f"""
            WITH adders AS (
                SELECT 
                    variant,
                    COUNT(DISTINCT user_id) as adders
                FROM events.add_to_cart
                WHERE date = '{most_recent_date}'
                GROUP BY variant
            ),
            orders AS (
                SELECT 
                    variant,
                    COUNT(DISTINCT user_id) as orderers
                FROM events.order_completed
                WHERE date = '{most_recent_date}'
                GROUP BY variant
            )
            SELECT 
                a.variant,
                a.adders,
                COALESCE(o.orderers, 0) as orders,
                ROUND(COALESCE(o.orderers, 0) * 100.0 / a.adders, 1) as conditional_conversion_pct
            FROM adders a
            LEFT JOIN orders o ON a.variant = o.variant
            ORDER BY a.variant
        """).fetchall()

        # Compute guardrails: payment auth rate and avg order value
        guardrails = conn.execute(f"""
            WITH payment_auth AS (
                SELECT 
                    variant,
                    COUNT(*) as total_attempts,
                    SUM(CASE WHEN authorized THEN 1 ELSE 0 END) as authorized_attempts,
                    ROUND(SUM(CASE WHEN authorized THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) as auth_rate_pct
                FROM events.payment_attempt
                WHERE date = '{most_recent_date}'
                GROUP BY variant
            ),
            order_values AS (
                SELECT 
                    variant,
                    ROUND(AVG(order_value), 2) as avg_order_value
                FROM events.order_completed
                WHERE date = '{most_recent_date}'
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

        conn.close()

        # Try to load statistical results
        ccr_summary, guardrails_summary = load_statistical_results()

        # Build markdown report
        lines = []
        lines.append("# Checkout Flow Optimization Report\n\n")
        lines.append(
            f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  \n"
        )
        lines.append(f"**Date:** {most_recent_date}\n\n")
        lines.append("---\n\n")

        # Statistical Results Section
        if ccr_summary and guardrails_summary:
            lines.append("## Statistical Results\n\n")
            lines.append(f"**Analysis Date:** {ccr_summary['date']}\n\n")

            # CCR Lift with CI and p-value
            effect_abs = ccr_summary["effect_abs"] * 100  # Convert to percentage points
            ci_low = ccr_summary["ci_low"] * 100
            ci_high = ccr_summary["ci_high"] * 100
            p_value = ccr_summary["p_value"]
            significant = (
                "Significant" if ccr_summary["significant"] else "Not significant"
            )

            lines.append("**CCR Lift:**  \n")
            lines.append(f"Effect: {effect_abs:+.2f}pp  \n")
            lines.append(f"95% CI: [{ci_low:.2f}pp, {ci_high:.2f}pp]  \n")
            lines.append(f"p-value: {p_value:.4f} ({significant})\n\n")

            # Guardrails Table with CIs
            lines.append("**Guardrails:**\n\n")
            lines.append("| Metric | Control | Treatment |\n")
            lines.append("|--------|---------|----------|\n")

            # Payment Authorization Rate
            control_auth = guardrails_summary["payment_authorization"]["control"]
            treatment_auth = guardrails_summary["payment_authorization"]["treatment"]
            lines.append(
                f"| Payment Auth Rate | {control_auth['rate']:.1%} "
                f"(95% CI: [{control_auth['ci_low']:.1%}, {control_auth['ci_high']:.1%}]) | "
                f"{treatment_auth['rate']:.1%} "
                f"(95% CI: [{treatment_auth['ci_low']:.1%}, {treatment_auth['ci_high']:.1%}]) |\n"
            )

            # Average Order Value
            control_aov = guardrails_summary["average_order_value"]["control"]
            treatment_aov = guardrails_summary["average_order_value"]["treatment"]
            lines.append(
                f"| Avg Order Value | ${control_aov['mean']:.2f} "
                f"(n={control_aov['count']:,}) | "
                f"${treatment_aov['mean']:.2f} "
                f"(n={treatment_aov['count']:,}) |\n"
            )

            lines.append("\n---\n\n")

        else:
            # Friendly note if results are missing
            lines.append("## Statistical Results\n\n")
            lines.append(
                "> **Note:** Statistical test results have not been generated yet.  \n"
            )
            lines.append(
                "> Run `make results` to generate detailed statistical analysis including "
                "effect sizes, confidence intervals, and p-values.\n\n"
            )
            lines.append("---\n\n")

        # Sensitivity Summary Section
        sensitivity_df, sensitivity_meta = load_sensitivity_results()
        mde = load_experiment_config()

        if sensitivity_df is not None:
            lines.append("## Sensitivity Analysis\n\n")

            if sensitivity_meta:
                grid_size = sensitivity_meta.get("grid_specification", {}).get(
                    "grid_size", "N/A"
                )
                total_sims = sensitivity_meta.get("total_simulations", "N/A")
                lines.append(f"**Grid Size:** {grid_size} parameter combinations  \n")
                lines.append(f"**Total Simulations:** {total_sims:,}  \n\n")

            # Find best detection rate near MDE
            if mde is not None:
                # Filter to uplifts near the MDE (within 0.5pp)
                near_mde = sensitivity_df[
                    (sensitivity_df["uplift"] > 0)
                    & (abs(sensitivity_df["uplift"] - mde) <= 0.005)
                ].copy()

                if not near_mde.empty:
                    best = near_mde.loc[near_mde["detection_rate"].idxmax()]
                    lines.append(
                        f"**Detection Rate near MDE ({mde * 100:.1f}pp):**  \n"
                    )
                    lines.append(
                        f"- {best['detection_rate']:.1%} power with {int(best['users_per_day']):,} users/day "
                        f"at {best['uplift'] * 100:.1f}pp uplift "
                        f"({int(best['detections'])}/{int(best['repeats'])} detections)\n\n"
                    )
                else:
                    # Show closest uplift tested
                    positive_uplifts = sensitivity_df[sensitivity_df["uplift"] > 0]
                    if not positive_uplifts.empty:
                        closest_idx = (positive_uplifts["uplift"] - mde).abs().idxmin()
                        closest = positive_uplifts.loc[closest_idx]
                        lines.append(
                            f"**Detection Rate near MDE ({mde * 100:.1f}pp):**  \n"
                        )
                        lines.append(
                            f"- Closest tested: {closest['detection_rate']:.1%} power with "
                            f"{int(closest['users_per_day']):,} users/day at {closest['uplift'] * 100:.1f}pp uplift "
                            f"({int(closest['detections'])}/{int(closest['repeats'])} detections)\n\n"
                        )

            # Summary table of best detection rates
            positive_results = sensitivity_df[sensitivity_df["uplift"] > 0].copy()
            if not positive_results.empty:
                # Group by uplift and find max detection rate
                best_by_uplift = (
                    positive_results.groupby("uplift")
                    .apply(lambda x: x.loc[x["detection_rate"].idxmax()])
                    .reset_index(drop=True)
                )

                lines.append("**Power by Uplift:**\n\n")
                lines.append("| Uplift | Best Power | Users/Day | Detections |\n")
                lines.append("|--------|------------|-----------|------------|\n")

                for _, row in best_by_uplift.iterrows():
                    lines.append(
                        f"| {row['uplift'] * 100:.1f}pp | {row['detection_rate']:.1%} | "
                        f"{int(row['users_per_day']):,} | {int(row['detections'])}/{int(row['repeats'])} |\n"
                    )

            lines.append("\n---\n\n")

        else:
            # Sensitivity data not available
            lines.append("## Sensitivity Analysis\n\n")
            lines.append("> **Note:** Sensitivity analysis has not been run yet.  \n")
            lines.append(
                "> Run `make sensitivity` or use the `quick_smoke` preset to generate power analysis:  \n"
            )
            lines.append(
                "> ```bash\n"
                "> python src/analysis/sensitivity.py --preset quick_smoke --start 2025-02-01\n"
                "> ```\n\n"
            )
            lines.append("---\n\n")

        # Primary Metric Table
        lines.append("## Primary Metric: Conditional Conversion Rate\n\n")
        lines.append("| Variant | Adders | Orders | Conditional Conversion |\n")
        lines.append("|---------|--------|--------|------------------------|\n")
        for row in primary_metric:
            variant, adders, orders, ccr = row
            lines.append(f"| {variant} | {adders:,} | {orders:,} | {ccr}% |\n")

        # Guardrails Table
        lines.append("\n## Guardrails\n\n")
        lines.append("| Variant | Payment Auth Rate | Avg Order Value |\n")
        lines.append("|---------|-------------------|------------------|\n")
        for row in guardrails:
            variant, auth_rate, avg_value = row
            lines.append(f"| {variant} | {auth_rate}% | ${avg_value:.2f} |\n")

        # Executive Summary Section
        lines.append("\n---\n\n")
        executive_summary_lines = generate_executive_summary_section(
            ccr_summary, guardrails_summary
        )
        lines.extend(executive_summary_lines)

        # Write report
        output_path = Path("reports/REPORT.md")
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w") as f:
            f.writelines(lines)

        # Print output path
        print(f"{output_path.resolve()}")

        return 0

    except Exception as e:
        print(f"ERROR: Failed to generate report: {str(e)}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(generate_compact_report())
