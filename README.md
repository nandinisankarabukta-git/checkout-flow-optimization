# Checkout Flow Optimization

**A production-grade A/B testing framework that measures the impact of checkout design changes on e-commerce conversion rates using statistical evidence to drive data-backed ship/no-ship decisions.**

## 1. Business Context

E-commerce checkout abandonment remains a critical business challenge across the industry. Research consistently shows that **nearly 70% of shoppers abandon their carts** before completing a purchase, representing millions in lost revenue and missed opportunities.

### The Challenge
Product and engineering teams frequently propose UI/UX improvements such as simplified forms, one-click payments, progress indicators yet lack a **systematic, rigorous way to validate** whether these changes actually increase conversion rates without degrading other key business metrics.

### The Stakes
Launching an untested checkout redesign can have severe consequences:
- **Revenue Loss:** Decreased conversion rates can cost millions annually
- **Trust Erosion:** Payment errors and failed transactions reduce customer confidence
- **Metric Degradation:** Changes may inadvertently lower average order value or increase refund rates

### Business Value
By building a statistically rigorous A/B testing framework, this project enables:
- **Confident Decision-Making:** Ship/no-ship decisions backed by statistical evidence, not intuition
- **Risk Mitigation:** Guardrail metrics protect against unintended negative impacts
- **Scalable Validation:** Repeatable methodology for testing future product changes

## 2. Data Problem 

### Problem Formulation
This is an **A/B testing and causal inference problem** designed to measure the treatment effect of a checkout redesign on user conversion behavior.

**Hypothesis:** A new checkout design (Treatment/Variant B) will increase order completion rates compared to the existing flow (Control/Variant A).

### Target Metrics
- **Primary Metric:** Conditional Conversion Rate = (Orders Completed ÷ Add to Cart Events)
- **Guardrail Metrics:**
  - Payment Authorization Rate (ensures payment quality)
  - Average Order Value (ensures revenue quality)

### Data Sources
Since no real e-commerce data was available for this project, a **synthetic dataset** was engineered to replicate production-scale event logs:

- **Event Types:** `add_to_cart`, `begin_checkout`, `checkout_step_view`, `payment_attempt`, `form_error`, `order_completed`
- **Simulated Users:** ~10,000 user sessions across 4 days of activity
- **Storage Format:** Partitioned Parquet files organized by event type and date
- **Analytics Layer:** DuckDB data warehouse for fast SQL-based analytics

### Key Assumptions
- User assignment to control/treatment is random (proper randomization)
- Sessions are independent (no user overlap between variants)
- Simulated treatment effect: +2 percentage point lift in conversion rate
- Realistic drop-off rates and latency variability at each checkout step

## 3. Approach and Methodology

### 3.1 Data Simulation

**Implementation (`src/data/simulate.py`):**
- Simulated 10,000 user sessions per day over 4 days
- Users deterministically assigned to control or treatment using hash-based randomization
- Modeled realistic funnel drop-offs at each stage: add_to_cart → begin_checkout → checkout_steps → payment_attempt → order_completed
- Injected treatment effect: +2pp lift in conversion probability for treatment group
- Generated correlated events: form errors, payment declines, latency variations
- Stored as partitioned Parquet files by event type and date

### 3.2 Data Warehousing and Transformation
Built an analytical data warehouse to enable efficient querying:

**DuckDB Warehouse (`sql/schema.sql`):**
- Created event views for each event type (add_to_cart, begin_checkout, etc.)
- Registered Parquet files as queryable tables using DuckDB's native file reading

**Analytical Marts (`sql/marts/`):**
- `fct_experiments`: User-level variant assignments and first exposure timestamps
- `fct_checkout_steps`: Aggregated step-through rates by variant
- `fct_orders`: Order-level metrics (order value, payment status, etc.)

### 3.3 Data Quality Validation
Implemented automated data quality checks (`src/quality.py`):

**Validation Tests:**
- **Referential Integrity:** Verified all orders and checkout steps reference valid checkout sessions
- **Sample Ratio Mismatch (SRM):** Confirmed 50/50 traffic split between variants
- **Business Logic:** Validated payment authorization rates fall within expected ranges (85-95%)
- **Event Sequencing:** Checked that funnel events occur in correct chronological order

### 3.4 Exploratory Data Analysis
Conducted systematic exploration through Jupyter notebooks:

**Notebooks:**
- `01_exploration.ipynb`: Event volume analysis, funnel visualization, initial variant comparison
- `02_stats_sanity.ipynb`: Statistical test validation, confidence interval checks
- `03_power_sensitivity.ipynb`: Power analysis and sample size calculations
- `04_experiment_readout.ipynb`: Comprehensive A/B test results analysis and decision framework
- `05_diagnostics_deep_dive.ipynb`: Deep dive into guardrail metrics and outlier investigation

**Key Findings:**
- Highest drop-off between add_to_cart and begin_checkout (~40%)
- Payment authorization failures affect ~8-10% of transactions
- Average order value stable around $250-$260
- No systematic differences in form error rates between variants

### 3.5 Experiment Design and Statistical Framework
Designed the experiment following A/B testing best practices:

**Randomization Strategy:**
- Hash-based deterministic assignment (MD5 of user_id) ensures stable variant membership
- 50/50 traffic split between control and treatment
- No overlap between variants (mutually exclusive)

**Statistical Framework (`src/analysis/stats_framework.py`):**
- **Primary Test:** Two-proportion z-test with pooled variance for CCR comparison
- **Confidence Intervals:** 95% CI for absolute and relative effect sizes
- **Guardrail Tests:** Proportion and mean comparison for secondary metrics
- **Alpha Level:** 0.05 (5% false positive rate)

**Metrics Implementation (`src/analysis/metrics_runner.py`):**
- Automated metric calculation from DuckDB warehouse
- Variant comparison with statistical significance testing
- Guardrail threshold evaluation

### 3.6 Power and Sensitivity Analysis
Performed power analysis to understand sample size requirements:

**Sensitivity Analysis (`src/analysis/sensitivity.py`):**
- Simulated experiments across different sample sizes (20k, 50k users per variant)
- Tested detection rates for effect sizes ranging from 0 to 2pp
- Calculated power curves for different MDE (Minimum Detectable Effect) targets
- Results saved to `reports/results/sensitivity_summary.csv`

**Key Finding (`03_power_sensitivity.ipynb`):**
- Detecting a 1.5pp lift requires ~50,000 users per variant for 80% power
- Current sample size (~5,000 per variant) has <50% power for detecting small effects

## 4. Results and Business Impact

### Experiment Results

| Metric | Control | Treatment | Absolute Change | p-value | Significance |
|--------|----------|-----------|-----------------|----------|---------------|
| **Conditional Conversion Rate** | 36.9% | 37.8% | **+0.89pp** | 0.3566 | Not Significant |
| **Payment Auth Rate** | 91.8% | 92.9% | +1.2pp | — | Pass |
| **Avg Order Value** | $256.82 | $259.19 | +$2.37 | — | Pass |

### Interpretation

**Primary Metric:**  
The treatment variant showed a **+0.89 percentage point lift** in conversion rate (37.8% vs. 36.9%), but the result was **not statistically significant** (p = 0.3566). This means the observed difference could have occurred by random chance.

**Guardrail Metrics:**  
Importantly, the treatment did not degrade any guardrail metrics:
- Payment authorization rate remained healthy (92.9% vs. 91.8%)
- Average order value stayed stable ($259.19 vs. $256.82)

### Business Translation

**What This Means for the Business:**
- The new checkout design is **safe to deploy**—it doesn't harm key metrics
- The directional lift is **promising but not yet proven**
- **Recommendation:** Continue the experiment with more traffic or longer runtime to reach statistical confidence

**Projected Impact (if lift holds at scale):**
- A sustained +0.89pp conversion lift on 1M monthly carts would yield ~8,900 additional orders
- At $257 average order value, this represents approximately **$2.3M in incremental annual revenue**

### Power Analysis Findings
To achieve 80% statistical power for detecting a 1.5pp lift, the experiment would need approximately **50,000 users per variant**.

This explains the inconclusive result: the current sample size (~5,000 users per variant) was too small to confidently detect the effect.

## 5. Productionization

### Current Implementation

This project is structured as a **production-ready analytics pipeline** with automation and reproducibility built in:

**Pipeline Architecture:**
```bash
make simulate   # Generate synthetic event data
make build      # Initialize DuckDB warehouse
make marts      # Build analytical fact tables
make quality    # Run data quality checks
make results    # Run statistical tests and save results
make report     # Generate summary reports
make app        # Launch Streamlit dashboard
```

Or run the complete pipeline at once:
```bash
make pipeline   # Runs: simulate → build → marts → quality → results → report
```

**Technology Stack:**
- **Data Storage:** Parquet files + DuckDB warehouse (columnar, fast analytics)
- **Orchestration:** Makefile-based DAG for reproducible execution
- **Analysis Framework:** Python-based statistical testing library
- **Reporting:** Automated Markdown reports + Streamlit dashboard

### Reporting and Visualization

The project includes both static and interactive reporting components:

- Automatically generated **Markdown reports** summarizing metrics and results
- A **Streamlit dashboard** for interactive exploration of conversion funnels, variant comparisons, and sensitivity results

These reports make it easy for both analysts and business teams to interpret results and decide next steps.

**Demo:** [View dashboard walkthrough video](docs/media/dashboard_walkthrough.mov)

## 6. How to Run / Installation

For detailed setup instructions, environment configuration, and step-by-step execution commands, see the **[Getting Started Guide](docs/getting-started.rst)**.

## 7. Acknowledgments

This project structure follows the **Cookiecutter Data Science** template, which promotes reproducible, well-organized analytics projects.