#!/usr/bin/env python3
"""
Checkout Flow Optimization Dashboard

A Streamlit dashboard for viewing funnel metrics and diagnostics.
"""

import streamlit as st
import duckdb
import pandas as pd
import json
import subprocess
from pathlib import Path

# Page configuration
st.set_page_config(page_title="Checkout Flow Optimization", layout="wide")

# Title
st.title("Checkout Flow Optimization")


def get_connection():
    """Returns a DuckDB connection to the warehouse."""
    db_path = Path("duckdb/warehouse.duckdb")
    if not db_path.exists():
        st.error(f"Database not found at {db_path.resolve()}")
        st.info("Run `make simulate && make build && make marts` to generate data.")
        st.stop()
    return duckdb.connect(str(db_path))


def get_most_recent_date(conn):
    """Finds the most recent date in the add_to_cart events."""
    result = conn.execute("SELECT MAX(date) FROM events.add_to_cart").fetchone()
    return result[0] if result else None


def load_summary_data(date):
    """Loads variant-level funnel data for the summary tab."""
    conn = get_connection()
    try:
        query = f"""
            WITH adders AS (
                SELECT 
                    variant,
                    COUNT(DISTINCT user_id) as adders
                FROM events.add_to_cart
                WHERE date = '{date}'
                GROUP BY variant
            ),
            checkouts AS (
                SELECT 
                    variant,
                    COUNT(DISTINCT checkout_id) as begin_checkout
                FROM events.begin_checkout
                WHERE date = '{date}'
                GROUP BY variant
            ),
            payments AS (
                SELECT 
                    variant,
                    COUNT(*) as payment_attempts
                FROM events.payment_attempt
                WHERE date = '{date}'
                GROUP BY variant
            ),
            orders AS (
                SELECT 
                    variant,
                    COUNT(*) as orders
                FROM events.order_completed
                WHERE date = '{date}'
                GROUP BY variant
            )
            SELECT 
                a.variant,
                a.adders,
                COALESCE(c.begin_checkout, 0) as begin_checkout,
                COALESCE(p.payment_attempts, 0) as payment_attempts,
                COALESCE(o.orders, 0) as orders,
                ROUND(COALESCE(o.orders, 0) * 100.0 / a.adders, 1) as conditional_conversion_pct
            FROM adders a
            LEFT JOIN checkouts c ON a.variant = c.variant
            LEFT JOIN payments p ON a.variant = p.variant
            LEFT JOIN orders o ON a.variant = o.variant
            ORDER BY a.variant
        """
        return conn.execute(query).df()
    finally:
        conn.close()


def load_step_through_rates():
    """Loads step-through rates grouped by step name."""
    conn = get_connection()
    try:
        query = """
            SELECT 
                step_name,
                step_index,
                COUNT(DISTINCT checkout_id) as checkouts,
                ROUND(AVG(median_latency_ms), 0) as avg_median_latency_ms,
                ROUND(SUM(error_events) * 100.0 / COUNT(DISTINCT checkout_id), 1) as error_rate_pct
            FROM marts.fct_checkout_steps
            GROUP BY step_name, step_index
            ORDER BY step_index
        """
        return conn.execute(query).df()
    finally:
        conn.close()


def load_latency_data(date):
    """Loads latency data for the payment step."""
    conn = get_connection()
    try:
        query = f"""
            SELECT latency_ms
            FROM events.checkout_step_view
            WHERE step_name = 'payment'
            AND date = '{date}'
        """
        return conn.execute(query).df()
    finally:
        conn.close()


def load_statistical_results():
    """
    Loads statistical results from JSON files.

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

    except Exception:
        return None, None


def load_sensitivity_results():
    """
    Loads sensitivity analysis results.

    Returns:
        DataFrame or None if CSV doesn't exist
    """
    csv_path = Path("reports/results/sensitivity_summary.csv")

    if not csv_path.exists():
        return None

    try:
        return pd.read_csv(csv_path)
    except Exception:
        return None


# Connect to database
conn = get_connection()
try:
    most_recent_date = get_most_recent_date(conn)

    if not most_recent_date:
        st.error("No data found in the database.")
        st.stop()
finally:
    conn.close()

# Sidebar
st.sidebar.header("Data Information")
st.sidebar.write(f"**Most Recent Date:** {most_recent_date}")
st.sidebar.markdown("---")
st.sidebar.markdown("### Quick Actions")

# Refresh button in sidebar
if st.sidebar.button(
    "Refresh Results", help="Run `make results` to regenerate statistical analysis"
):
    with st.spinner("Running `make results`... This may take a minute."):
        try:
            # Small delay to ensure database lock is released
            import time

            time.sleep(1)

            result = subprocess.run(
                ["make", "results"],
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
            )
            if result.returncode == 0:
                st.sidebar.success("Results refreshed successfully!")
                st.rerun()
            else:
                st.sidebar.error(f"Error running `make results`: {result.stderr}")
        except subprocess.TimeoutExpired:
            st.sidebar.error("Command timed out after 5 minutes.")
        except Exception as e:
            st.sidebar.error(f"Error: {str(e)}")

# Create tabs
tab0, tab1, tab2, tab3 = st.tabs(["Overview", "Summary", "Diagnostics", "Sensitivity"])

# Add some spacing between sections
st.markdown("<br>", unsafe_allow_html=True)

# Tab 0: Overview
with tab0:
    st.markdown("<div style='margin-top: 20px;'></div>", unsafe_allow_html=True)
    st.header("Welcome to the Checkout Flow Optimization Dashboard")

    st.markdown("""
    This dashboard provides real-time insights into the A/B test evaluating a redesigned checkout flow. 
    The primary metric is **Conditional Conversion Rate (CCR)**, the percentage of users who add items 
    to cart and successfully complete their order.
    
    **Goal:** Increase CCR by at least 1.5pp (the Minimum Detectable Effect) without harming guardrail metrics.
    """)

    st.markdown("---")
    st.markdown("<div style='margin: 30px 0;'></div>", unsafe_allow_html=True)

    # Load statistical results for key metrics
    ccr_summary, guardrails_summary = load_statistical_results()

    if ccr_summary and guardrails_summary:
        st.subheader("Key Metrics at a Glance")

        # Top row: Primary metrics
        col1, col2 = st.columns(2)

        control_ccr = ccr_summary["control"]["ccr"] * 100
        treatment_ccr = ccr_summary["treatment"]["ccr"] * 100
        effect_abs = ccr_summary["effect_abs"] * 100
        p_value = ccr_summary["p_value"]
        significant = ccr_summary["significant"]

        with col1:
            st.metric(
                "Control CCR", f"{control_ccr:.2f}%", help="Baseline conversion rate"
            )

        with col2:
            st.metric(
                "Treatment CCR",
                f"{treatment_ccr:.2f}%",
                delta=f"{effect_abs:+.2f}pp",
                help="New checkout flow conversion rate",
            )

        # Second row: Statistical metrics
        col3, col4 = st.columns(2)

        with col3:
            sig_status = "Significant" if significant else "Not Significant"
            st.metric(
                "Statistical Significance",
                sig_status,
                delta=f"p = {p_value:.4f}",
                delta_color="normal",
            )

        with col4:
            ci_low = ccr_summary["ci_low"] * 100
            ci_high = ccr_summary["ci_high"] * 100
            st.metric(
                "95% Confidence Interval",
                f"[{ci_low:.2f}, {ci_high:.2f}]pp",
                help="Range of plausible effect sizes",
            )

        st.markdown("---")
        st.markdown("<div style='margin: 30px 0;'></div>", unsafe_allow_html=True)

        # Bottom section: Guardrails
        st.subheader("Guardrail Status")

        # Payment Authorization Rate
        col1, col2 = st.columns(2)
        control_auth = guardrails_summary["payment_authorization"]["control"]
        treatment_auth = guardrails_summary["payment_authorization"]["treatment"]

        with col1:
            st.metric(
                "Payment Auth - Control",
                f"{control_auth['rate']:.2%}",
                help="Control variant payment authorization rate",
            )

        with col2:
            st.metric(
                "Payment Auth - Treatment",
                f"{treatment_auth['rate']:.2%}",
                help="Treatment variant payment authorization rate",
            )

        # Average Order Value
        col3, col4 = st.columns(2)
        control_aov = guardrails_summary["average_order_value"]["control"]
        treatment_aov = guardrails_summary["average_order_value"]["treatment"]

        with col3:
            st.metric(
                "AOV - Control",
                f"${control_aov['mean']:.2f}",
                help="Control variant average order value",
            )

        with col4:
            st.metric(
                "AOV - Treatment",
                f"${treatment_aov['mean']:.2f}",
                help="Treatment variant average order value",
            )

    else:
        st.info("""
        **Statistical analysis not yet available.**
        
        Click **"Refresh Results"** in the sidebar or run `make results` to generate the latest analysis.
        """)

    st.markdown("---")

    st.caption("""
    **About the data:** All data are synthetic, generated by `src/data/simulate.py`, stored as Parquet in `data/raw/`, 
    and queried via DuckDB views (`sql/schema.sql`) and marts (`sql/marts/*`).
    """)

# Tab 1: Summary
with tab1:
    st.markdown("<div style='margin-top: 20px;'></div>", unsafe_allow_html=True)
    st.header("Variant-Level Funnel Summary")
    st.caption(f"Data for: {most_recent_date}")

    try:
        summary_data = load_summary_data(most_recent_date)

        # Display as formatted table
        st.dataframe(
            summary_data,
            column_config={
                "variant": st.column_config.TextColumn("Variant", width="small"),
                "adders": st.column_config.NumberColumn("Adders", format="%d"),
                "begin_checkout": st.column_config.NumberColumn(
                    "Begin Checkout", format="%d"
                ),
                "payment_attempts": st.column_config.NumberColumn(
                    "Payment Attempts", format="%d"
                ),
                "orders": st.column_config.NumberColumn("Orders", format="%d"),
                "conditional_conversion_pct": st.column_config.NumberColumn(
                    "Conditional Conversion", format="%.1f%%"
                ),
            },
            hide_index=True,
            use_container_width=True,
        )

        # Key metrics
        st.subheader("Key Metrics Comparison")
        col1, col2, col3 = st.columns(3)

        control_data = summary_data[summary_data["variant"] == "control"].iloc[0]
        treatment_data = summary_data[summary_data["variant"] == "treatment"].iloc[0]

        with col1:
            st.metric(
                "Control Conversion",
                f"{control_data['conditional_conversion_pct']:.1f}%",
                delta=None,
            )

        with col2:
            st.metric(
                "Treatment Conversion",
                f"{treatment_data['conditional_conversion_pct']:.1f}%",
                delta=None,
            )

        with col3:
            delta = (
                treatment_data["conditional_conversion_pct"]
                - control_data["conditional_conversion_pct"]
            )
            st.metric(
                "Difference",
                f"{abs(delta):.1f}pp",
                delta=f"{delta:.1f}pp" if delta != 0 else "0pp",
            )

        # Statistical Results Panel
        st.markdown("---")
        st.subheader("Statistical Analysis")

        ccr_summary, guardrails_summary = load_statistical_results()

        if ccr_summary and guardrails_summary:
            # CCR Lift with CI and p-value
            st.markdown("**CCR Lift (Treatment - Control):**")

            col1, col2, col3 = st.columns(3)

            effect_abs = ccr_summary["effect_abs"] * 100  # Convert to percentage points
            ci_low = ccr_summary["ci_low"] * 100
            ci_high = ccr_summary["ci_high"] * 100
            p_value = ccr_summary["p_value"]
            significant = ccr_summary["significant"]

            with col1:
                st.metric("Effect Size", f"{effect_abs:+.2f}pp")

            with col2:
                st.metric("95% CI", f"[{ci_low:.2f}, {ci_high:.2f}]pp")

            with col3:
                sig_label = "Significant" if significant else "Not Significant"
                st.metric("p-value", f"{p_value:.4f}", delta=sig_label)

            # Guardrails
            st.markdown("**Guardrails:**")

            # Payment Authorization Rate
            st.markdown("*Payment Authorization Rate*")
            col1, col2 = st.columns(2)

            control_auth = guardrails_summary["payment_authorization"]["control"]
            treatment_auth = guardrails_summary["payment_authorization"]["treatment"]

            with col1:
                st.metric(
                    "Control",
                    f"{control_auth['rate']:.1%}",
                    delta=f"CI: [{control_auth['ci_low']:.1%}, {control_auth['ci_high']:.1%}]",
                )

            with col2:
                st.metric(
                    "Treatment",
                    f"{treatment_auth['rate']:.1%}",
                    delta=f"CI: [{treatment_auth['ci_low']:.1%}, {treatment_auth['ci_high']:.1%}]",
                )

            # Average Order Value
            st.markdown("*Average Order Value*")
            col1, col2 = st.columns(2)

            control_aov = guardrails_summary["average_order_value"]["control"]
            treatment_aov = guardrails_summary["average_order_value"]["treatment"]

            with col1:
                st.metric(
                    "Control",
                    f"${control_aov['mean']:.2f}",
                    delta=f"n={control_aov['count']:,}",
                )

            with col2:
                st.metric(
                    "Treatment",
                    f"${treatment_aov['mean']:.2f}",
                    delta=f"n={treatment_aov['count']:,}",
                )

        else:
            # Friendly message when results are missing
            st.info(
                """
                **Statistical test results not available.**
                
                Run `make results` to generate detailed statistical analysis including:
                - CCR lift with 95% confidence interval
                - p-value and significance test
                - Guardrail metrics with confidence intervals
                """
            )

    except Exception as e:
        st.error(f"Error loading summary data: {str(e)}")

# Tab 2: Diagnostics
with tab2:
    st.markdown("<div style='margin-top: 20px;'></div>", unsafe_allow_html=True)
    st.header("Diagnostics")

    # Step-through rates
    st.subheader("Step-Through Rates")
    try:
        step_data = load_step_through_rates()
        st.dataframe(
            step_data,
            column_config={
                "step_name": st.column_config.TextColumn("Step Name", width="small"),
                "step_index": st.column_config.NumberColumn("Index", width="small"),
                "checkouts": st.column_config.NumberColumn("Checkouts", format="%d"),
                "avg_median_latency_ms": st.column_config.NumberColumn(
                    "Avg Median Latency (ms)", format="%.0f"
                ),
                "error_rate_pct": st.column_config.NumberColumn(
                    "Error Rate", format="%.1f%%"
                ),
            },
            hide_index=True,
            use_container_width=True,
        )
    except Exception as e:
        st.error(f"Error loading step-through data: {str(e)}")

    # Latency distribution
    st.subheader("Payment Step Latency Distribution")
    st.caption(f"Data for: {most_recent_date}")

    try:
        latency_data = load_latency_data(most_recent_date)

        if not latency_data.empty:
            # Show histogram
            st.bar_chart(
                latency_data["latency_ms"].value_counts().sort_index(),
                use_container_width=True,
            )

            # Summary statistics
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Count", f"{len(latency_data):,}")
            with col2:
                st.metric("Mean", f"{latency_data['latency_ms'].mean():.0f} ms")
            with col3:
                st.metric("Median", f"{latency_data['latency_ms'].median():.0f} ms")
            with col4:
                st.metric("Std Dev", f"{latency_data['latency_ms'].std():.0f} ms")
        else:
            st.warning("No latency data available for the payment step.")

    except Exception as e:
        st.error(f"Error loading latency data: {str(e)}")

# Tab 3: Sensitivity
with tab3:
    st.markdown("<div style='margin-top: 20px;'></div>", unsafe_allow_html=True)
    st.header("Sensitivity Analysis")
    st.caption("Power analysis across sample size and uplift parameters")

    sensitivity_df = load_sensitivity_results()

    if sensitivity_df is not None:
        try:
            # Summary metrics
            st.subheader("Grid Summary")
            col1, col2, col3 = st.columns(3)

            with col1:
                grid_size = len(sensitivity_df)
                st.metric("Grid Points", f"{grid_size}")

            with col2:
                unique_users = sorted(sensitivity_df["users_per_day"].unique())
                st.metric("Sample Sizes", f"{len(unique_users)}")

            with col3:
                unique_uplifts = sorted(sensitivity_df["uplift"].unique())
                st.metric("Uplifts Tested", f"{len(unique_uplifts)}")

            # Table: Full results
            st.subheader("Detection Rates")
            st.caption("All grid points with power/detection rates")

            # Format table for display
            display_df = sensitivity_df.copy()
            display_df["uplift_pct"] = display_df["uplift"] * 100
            display_df["detection_rate_pct"] = display_df["detection_rate"] * 100
            display_df["alpha_pct"] = display_df["alpha"] * 100

            st.dataframe(
                display_df[
                    [
                        "users_per_day",
                        "uplift_pct",
                        "detection_rate_pct",
                        "detections",
                        "repeats",
                        "alpha_pct",
                    ]
                ],
                column_config={
                    "users_per_day": st.column_config.NumberColumn(
                        "Users/Day", format="%d"
                    ),
                    "uplift_pct": st.column_config.NumberColumn(
                        "Uplift", format="%.1f%%"
                    ),
                    "detection_rate_pct": st.column_config.NumberColumn(
                        "Detection Rate (Power)", format="%.1f%%"
                    ),
                    "detections": st.column_config.NumberColumn(
                        "Detections", format="%d"
                    ),
                    "repeats": st.column_config.NumberColumn("Repeats", format="%d"),
                    "alpha_pct": st.column_config.NumberColumn(
                        "Alpha", format="%.1f%%"
                    ),
                },
                hide_index=True,
                use_container_width=True,
            )

            # Chart: Detection rate by uplift for smallest and largest sample sizes
            st.subheader("Power Curves")
            st.caption("Detection rate by uplift for smallest and largest sample sizes")

            # Filter to positive uplifts only (exclude A/A test at 0)
            positive_uplifts = sensitivity_df[sensitivity_df["uplift"] > 0].copy()

            if not positive_uplifts.empty and len(unique_users) > 0:
                # Get smallest and largest users_per_day
                smallest_users = min(unique_users)
                largest_users = max(unique_users)

                # Filter data for chart
                chart_data = positive_uplifts[
                    positive_uplifts["users_per_day"].isin(
                        [smallest_users, largest_users]
                    )
                ].copy()

                if not chart_data.empty:
                    # Prepare data for line chart
                    chart_data["users_label"] = chart_data["users_per_day"].apply(
                        lambda x: f"{int(x):,} users/day"
                    )
                    chart_data["uplift_pct"] = chart_data["uplift"] * 100

                    # Pivot for plotting
                    pivot_data = chart_data.pivot(
                        index="uplift_pct",
                        columns="users_label",
                        values="detection_rate",
                    )

                    st.line_chart(pivot_data, use_container_width=True)

                    # Show specific data points
                    st.markdown("**Data Points:**")
                    for users in [smallest_users, largest_users]:
                        subset = chart_data[chart_data["users_per_day"] == users]
                        if not subset.empty:
                            st.markdown(f"*{int(users):,} users/day:*")
                            for _, row in subset.iterrows():
                                st.markdown(
                                    f"- {row['uplift'] * 100:.1f}pp uplift → {row['detection_rate']:.1%} power "
                                    f"({int(row['detections'])}/{int(row['repeats'])} detections)"
                                )
                else:
                    st.warning("Not enough data points for chart visualization.")
            else:
                st.warning("No positive uplift data available for chart.")

        except Exception as e:
            st.error(f"Error displaying sensitivity results: {str(e)}")

    else:
        # Instructions when CSV doesn't exist
        st.info(
            """
            **Sensitivity analysis has not been run yet.**
            
            Run the sensitivity analysis to generate power curves and sample size recommendations:
            
            **Quick smoke test:**
            ```bash
            make sensitivity
            ```
            
            **Or use a preset:**
            ```bash
            python src/analysis/sensitivity.py --preset quick_smoke --start 2025-02-01
            python src/analysis/sensitivity.py --preset full_demo --start 2025-02-01
            ```
            
            This will analyze detection rates across different sample sizes and effect sizes,
            helping you understand the statistical power of your experiment design.
            """
        )

# Footer
st.markdown("---")
st.markdown(
    """
<div style='text-align: center; color: #666; padding: 20px;'>
    <p><strong>Checkout Flow Optimization Dashboard</strong></p>
    <p style='font-size: 0.8em;'>Generated with synthetic data | Powered by DuckDB & Streamlit</p>
</div>
""",
    unsafe_allow_html=True,
)
