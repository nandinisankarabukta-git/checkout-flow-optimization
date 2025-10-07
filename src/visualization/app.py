#!/usr/bin/env python3
"""
Checkout Flow Optimization Dashboard
=====================================
Streamlit dashboard for exploring checkout funnel metrics and A/B test results.
"""

import streamlit as st
import duckdb
from pathlib import Path

# Page configuration
st.set_page_config(page_title="Checkout Flow Optimization", layout="wide")

# Title
st.title("Checkout Flow Optimization Dashboard")
st.markdown("---")

# Sidebar
with st.sidebar:
    st.header("Configuration")
    st.info("This is a placeholder dashboard. Full implementation coming soon!")

    st.markdown("### Data Pipeline")
    st.markdown("""
    - **Simulate:** `make simulate`
    - **Build Schema:** `make build`
    - **Build Marts:** `make marts`
    - **Quality Checks:** `make quality`
    - **Generate Report:** `make report`
    """)

# Main content
st.markdown("## Dashboard Placeholder")

st.info("""
**Coming Soon:**
- Real-time funnel metrics
- Variant comparison charts
- Statistical significance testing
- Guardrail monitoring
- Step-level performance analysis
""")

# Connection test
st.markdown("### Database Connection")
try:
    db_path = Path("duckdb/warehouse.duckdb")
    if db_path.exists():
        conn = duckdb.connect(str(db_path))

        # Get basic stats
        result = conn.execute("""
            SELECT COUNT(DISTINCT user_id) as users,
                   COUNT(DISTINCT variant) as variants
            FROM marts.fct_experiments
        """).fetchone()

        conn.close()

        st.success(
            f"Connected to warehouse! Users: {result[0]:,}, Variants: {result[1]}"
        )

        st.markdown("### Quick Stats Preview")
        st.markdown("""
        Run `make report` to generate a full markdown report, or explore the data
        in the Jupyter notebook at `notebooks/exploration.ipynb`.
        """)
    else:
        st.warning(
            "Database not found. Run `make simulate && make build && make marts` to generate data."
        )

except Exception as e:
    st.error(f"❌ Error connecting to database: {str(e)}")

# Footer
st.markdown("---")
st.markdown("*For full analysis, see `notebooks/exploration.ipynb`*")
