# Checkout Flow Optimization

**A production-grade A/B testing framework that measures the impact of checkout design changes on e-commerce conversion rates using statistical evidence to drive data-backed ship/no-ship decisions.**

## 1. Business Context

E-commerce checkout abandonment remains a critical business challenge across the industry. Research consistently shows that **nearly 70% of shoppers abandon their carts** before completing a purchase, representing millions in lost revenue and missed opportunities.

### The Challenge
Product and engineering teams frequently propose UI/UX improvements—simplified forms, one-click payments, progress indicators—yet lack a **systematic, rigorous way to validate** whether these changes actually increase conversion rates without degrading other key business metrics.

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

### 3.1 Data Understanding and Simulation
Since no real e-commerce data was available, a synthetic dataset was created to mimic real checkout behavior:

**Data Generation Process:**
- Simulated user journeys through a multi-step checkout funnel
- Introduced realistic variability: drop-offs, form errors, latency, failed payments
- Embedded a small treatment effect (+2pp lift) to test detection capabilities
- Stored data in production-like partitioned Parquet format

**Key Insights from Exploration:**
- Checkout abandonment occurs most frequently between `add_to_cart` and `begin_checkout` (~40% drop-off)
- Payment authorization failures affect ~8-10% of transactions
- Average order value clusters around $250-$260

### 3.2 Exploratory Data Analysis
Exploratory analysis focused on understanding funnel dynamics:

- **Funnel Visualization:** Tracked conversion rates at each step
- **Variant Comparison:** Compared treatment vs. control behavior across all stages
- **Outlier Detection:** Identified anomalous order values and session patterns
- **Data Quality Checks:** Validated event sequencing and timestamp consistency

### 3.3 Feature Engineering
Built analytical features for statistical testing:

- **User-level aggregations:** Sessions per user, total cart value, checkout attempts
- **Funnel metrics:** Conversion rates at each stage, time-to-conversion
- **Behavioral flags:** Form error occurrences, payment retry behavior

### 3.4 Experiment Design and Statistical Framework
The experiment was designed following industry best practices:

**Randomization:**
- Users randomly assigned to Control (Variant A) or Treatment (Variant B)
- 50/50 traffic split

**Statistical Approach:**
- **Test Type:** Two-proportion z-test for conversion rate comparison
- **Significance Level:** α = 0.05
- **Minimum Detectable Effect (MDE):** 1.5 percentage points
- **Power Target:** 80%

**Implementation:**
- Built a reusable `stats_framework.py` module for hypothesis testing
- Automated metric calculation and guardrail evaluation
- Generated sensitivity analysis to determine required sample sizes

### 3.5 Model Training and Validation
While this is primarily an A/B testing project (not a predictive modeling project), the analytical pipeline includes:

- **Validation Strategy:** Historical data used to validate simulation realism
- **Cross-validation:** Ensured consistent treatment effects across date partitions
- **Robustness Checks:** Tested results stability with different random seeds

### 3.6 Statistical Testing and Results Interpretation
Statistical tests were run to compare variants:

1. **Primary Metric Test:** Z-test on conditional conversion rate difference
2. **Guardrail Checks:** Validated that treatment didn't degrade secondary metrics
3. **Power Analysis:** Calculated required sample size for conclusive results

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
make results    # Run statistical tests
make report     # Generate summary reports
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