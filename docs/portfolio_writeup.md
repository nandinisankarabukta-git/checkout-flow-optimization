# Checkout Flow Optimization: A/B Testing Framework
A rigorous experimentation platform for data-driven product decisions

## TL;DR
Built a **reproducible A/B testing framework** using **synthetic checkout funnel data, DuckDB, and Streamlit** to evaluate conversion rate improvements safely before launch.  
End-to-end orchestration through a single command (`make pipeline`), producing statistically valid results, dashboards, and executive-ready reports.

## Problem and Motivation

E-commerce checkout abandonment remains a major challenge, industry research shows that **nearly 70% of shoppers abandon their carts** before completing a purchase. Each abandoned cart represents lost revenue and an opportunity to improve user experience.

### The Challenge
Product teams often propose UI and UX improvements (simplified forms, one-click payments, progress indicators), yet lack a **systematic way to validate** whether those changes truly increase conversion rates without negatively impacting other key metrics.

### The Stakes
Launching an untested checkout change can:
- Decrease conversion rates and cost millions in lost revenue  
- Introduce payment errors that reduce customer trust  
- Lower average order value or increase refund rates  

### The Goal
To build a **production-grade A/B testing framework** that allows confident, data-driven ship/no-ship decisions using **statistical evidence**, not intuition.

## Approach Summary

This project implements an **end-to-end experimentation platform** that mirrors enterprise-grade data infrastructure, while remaining lightweight and fully reproducible. It generates synthetic checkout funnel data, performs statistical testing, and produces automated reports and dashboards.

### Key Components
1. **Data Pipeline** – Synthetic event generation with configurable traffic volumes and treatment effects, stored as date-partitioned Parquet files  
2. **Analytical Warehouse** – Embedded **DuckDB** database with SQL views and aggregated marts for high-speed analytical queries  
3. **Statistical Engine** – Two-proportion z-tests, confidence intervals, and guardrail monitoring with rigorous hypothesis testing  
4. **Reporting Layer** – Automated Markdown reports using **Jinja2 templates** with executive summaries  
5. **Interactive Dashboard** – **Streamlit** app featuring key metrics cards, variant comparisons, and a one-click refresh  
6. **CI/CD Integration** – **GitHub Actions** workflow that runs the full pipeline and stores artifacts on every push  

### Workflow Overview
```
make pipeline
  ├─ simulate  → Generate synthetic checkout events
  ├─ build     → Create DuckDB warehouse
  ├─ marts     → Build analytical tables
  ├─ quality   → Validate data integrity
  ├─ results   → Run statistical tests
  └─ report    → Generate executive report
```

Total runtime: under **3 minutes** on a local machine.

## Key Technical Choices

### 1. DuckDB for Analytical Queries
**Why DuckDB?**
- **Embedded** – no separate server, runs in-process  
- **Columnar storage** – optimized for aggregations and filters  
- **SQL interface** – familiar to data analysts  
- **Native Parquet integration** – zero-copy reads from partitioned data lakes  

**Impact:** Provides near-production query performance comparable to tools like Snowflake or BigQuery while remaining lightweight and CI/CD friendly.

### 2. Synthetic Data Generation
**Why synthetic data?**
- **Privacy** – no sensitive user data required  
- **Reproducibility** – *Seeded random generation ensures consistent results across runs, enabling fair metric comparisons and reliable CI/CD testing*  
- **Flexibility** – adjustable uplift, volume, and error rates  
- **Velocity** – immediate generation instead of waiting for real traffic  

**Design:**  
Follows an event-based schema mirroring production instrumentation:
`add_to_cart → begin_checkout → checkout_step_view → form_error → payment_attempt → order_completed`  
Treatment effects simulate changes in success rates, error frequency, and step latency.

### 3. Rigorous Statistical Testing
**Methodology**
- **Primary Metric:** Conditional Conversion Rate (CCR) = Orders / Adders  
- **Test:** Two-proportion z-test with 95% confidence intervals  
- **Significance Level:** α = 0.05  
- **Minimum Detectable Effect (MDE):** 1.5pp lift  
- **Guardrails:** Payment authorization rate, Average Order Value, p95 latency, refund rate  

**Why it matters:** Prevents “peeking bias,” controls false positives, and ensures product launches are statistically justified, not just intuitively appealing.

### 4. Infrastructure as Code
**Automation Stack**
- **Makefile** – Single source of truth for every pipeline command  
- **GitHub Actions** – Automatic report generation on push  
- **Jinja2 Templates** – Consistent, templated executive reports  
- **Power Analysis** – Sensitivity sweeps to explore detection thresholds  

**Benefit:** Fully reproducible science—clone the repo, run `make pipeline`, and get identical results every time.

## Results and Insights

### Example Experiment: Simplified Checkout Flow

**Scenario:** Testing a redesigned checkout flow with streamlined payment steps.

**Results:**

| Metric | Control | Treatment | Lift | 95% CI | p-value | Significant? |
|--------|---------|-----------|------|---------|---------|--------------|
| CCR (Orders/Adders) | 36.9% | 37.8% | +0.89pp | [-1.00pp, +2.79pp] | 0.3566 | ❌ |

> **Decision:** *Inconclusive — Do not launch.*

**Guardrails:** All passed (no degradation in payment success or AOV).

### Key Insights
1. **Statistical Power Matters** – Even promising relative lifts are inconclusive without sufficient power.  
2. **Guardrails Provide Safety Nets** – Secondary metrics confirm treatment isn’t harmful.  
3. **Sensitivity Analysis Informs Design** – Detecting a 1.5pp lift requires ~50K users/variant for 80% power.  
4. **Executive Summaries Accelerate Decisions** – Stakeholders can quickly interpret results and make launch calls confidently.

## Lessons Learned and Future Work

### What Worked Well
- **DuckDB Performance** – Sub-second analytical queries on millions of rows  
- **Makefile Orchestration** – `make pipeline` reduced onboarding friction  
- **Interactive Dashboard** – Streamlit app transformed raw stats into intuitive visual insights  
- **GitHub Actions Integration** – Auto-generated reports improved transparency and reproducibility  

### What I’d Do Differently
- **Bayesian Inference** – More intuitive probability statements than frequentist tests  
- **Sequential Testing** – Early stopping when evidence is conclusive  
- **Segment-Level Analysis** – Reveal treatment effects across user types  
- **Multi-Armed Bandits** – Adaptive traffic allocation for faster learning  

### Future Enhancements
**Near-term (1–2 sprints):**
- [ ] Add segment analysis (device, geography, user type)  
- [ ] Automate A/A tests for randomization verification  
- [ ] Add Slack notifications for completed runs  
- [ ] Deploy Streamlit dashboard publicly  

**Mid-term (1–2 quarters):**
- [ ] Integrate Bayesian credible intervals  
- [ ] Build experiment registry for metadata tracking  
- [ ] Implement CUPED for variance reduction  

**Aspirational:**
- [ ] Multivariate testing  
- [ ] Real-time dashboard updates  
- [ ] Causal inference (propensity scoring)  
- [ ] SRM and anomaly detection alerts  

## Quick Start
```bash
# Clone and setup
git clone https://github.com/yourusername/checkout-flow-optimization.git
cd checkout-flow-optimization
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Run complete pipeline
make pipeline

# Launch dashboard
make app
```

Runtime: ~3 minutes end-to-end.

## Technical Stack

| Component | Technology | Purpose |
|-----------|-------------|----------|
| **Data Storage** | Parquet | Efficient, columnar event storage |
| **Database** | DuckDB | Embedded analytical warehouse |
| **Statistical Analysis** | SciPy, NumPy | Hypothesis testing and metrics |
| **Reporting** | Markdown + Jinja2 | Version-controlled summaries |
| **Dashboard** | Streamlit | Interactive visual analytics |
| **Orchestration** | Make | Simple declarative pipelines |
| **CI/CD** | GitHub Actions | Auto-report builds on commit |

## Impact and Takeaways

This project demonstrates:
1. **End-to-End Ownership** – From data generation to statistical decisioning  
2. **Production Mindset** – CI/CD, guardrails, reproducibility  
3. **Strong Communication** – Translating analytics into business insights  
4. **Smart Tooling** – Lightweight yet powerful tech choices (DuckDB, Streamlit)  
5. **Scientific Rigor** – Proper hypothesis testing and power analysis  


