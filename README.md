# Checkout Flow Optimization

This project helps product and data teams understand how changes to the checkout process affect customer behavior. It simulates real user journeys, runs A/B tests, and measures how design updates impact conversion rates and revenue. The goal is to help teams make data-backed decisions instead of relying on guesswork.

## Main Objective

The main objective of this project is to figure out whether a new checkout design actually helps more customers complete their orders. It builds a realistic A/B testing setup that tracks user behavior through each checkout step and measures how design changes impact conversion rates and key business metrics.

## Problem and Motivation

E-commerce checkout abandonment remains a major challenge. Industry research shows that **nearly 70% of shoppers abandon their carts** before completing a purchase. Each abandoned cart represents lost revenue and an opportunity to improve user experience.

### The Challenge
Product teams often propose UI and UX improvements (simplified forms, one-click payments, progress indicators), yet lack a **systematic way to validate** whether those changes truly increase conversion rates without negatively impacting other key metrics.

### The Stakes
Launching an untested checkout change can:
- Decrease conversion rates and cost millions in lost revenue  
- Introduce payment errors that reduce customer trust  
- Lower average order value or increase refund rates  

### The Goal
To build a **production-grade A/B testing framework** that allows confident, data-driven ship/no-ship decisions using **statistical evidence**, not intuition.

---

## Project Steps

### 1) Defining the Problem
The project starts with a common e-commerce issue: many users add products to their cart but never finish checking out. This drop-off directly affects conversion rates and revenue. The goal was to test whether a redesigned checkout flow could improve order completion rates.

### 2) Translating It into a Data Problem
To measure improvement objectively, the problem was framed as an A/B testing setup.

- **Variant A (Control):** Existing checkout flow  
- **Variant B (Treatment):** New checkout design  

The main metric tracked was **Conditional Conversion Rate (Orders ÷ Add to Cart events)**.  
Guardrail metrics like **payment authorization rate** and **average order value** ensured that conversion improvements didn’t come at the cost of user experience or transaction quality.

### 3) Data Sourcing and Simulation
Since no real e-commerce data was available, a **synthetic dataset** was created to mimic real checkout behavior.

- Simulated user sessions going through key stages: *add_to_cart → begin_checkout → payment → order_completed*  
- Introduced randomness for realism, including drop-offs, form errors, and latency at each step  
- Added a small **treatment effect** to reflect how the new design might improve conversions  
- Stored results as **Parquet files** and used **DuckDB** for fast analytics  

This approach produced data that was reproducible, realistic, and aligned with how real event logs work in production systems.

*See [`src/data/simulate.py`](src/data/simulate.py) for implementation details.*

### 4) Building the Pipeline
The project followed the **Cookiecutter Data Science** structure to keep everything organized and reproducible.  
Each step of the pipeline was automated using a `Makefile`:

```bash
make simulate   # Generate synthetic data
make build      # Create DuckDB warehouse
make marts      # Build analytical tables
make results    # Run statistical tests
make report     # Generate summary report
```

This setup mirrors how production-grade data pipelines are managed — modular, consistent, and version-controlled.

*See [`docs/commands.rst`](docs/commands.rst) for detailed command explanations.*

### 5) Statistical Analysis and Experiment Evaluation
A statistical comparison was performed between the control and treatment variants using a **two-proportion z-test**.

| Metric | Control | Treatment | Change | p-value | Significance |
|--------|----------|-----------|---------|----------|---------------|
| Conditional Conversion | 36.9% | 37.8% | +0.89pp | 0.3566 | Not Significant |
| Payment Auth Rate | 91.8% | 92.9% | +1.2pp | — | Pass |
| Avg Order Value | $256.82 | $259.19 | +$2.37 | — | Pass |

Even though the treatment showed a higher conversion rate, the difference was not statistically significant at a 95% confidence level.  
However, all **guardrails passed**, meaning the new checkout design did not negatively impact other business metrics.

### 6) Sensitivity and Power Analysis
To understand data requirements for future experiments, a **power analysis** was run.  
It showed that detecting a 1.5 percentage point lift would require roughly **50,000 users per variant** to achieve 80% statistical power.  
This step demonstrated the real-world trade-off between traffic volume, experiment duration, and confidence level.

### 7) Visualization and Reporting
The project includes both static and interactive reporting components:

- Automatically generated **Markdown reports** summarizing metrics and results  
- A **Streamlit dashboard** for interactive exploration of conversion funnels, variant comparisons, and sensitivity results  

This made the insights accessible both for technical reviewers and business stakeholders.

### 8) Deployment and Reproducibility
The project is fully reproducible and designed to mimic enterprise-grade experimentation setups:

- **Automation:** All processes are orchestrated with `make`  
- **Database:** DuckDB serves as a local analytical warehouse  
- **Dashboard:** Deployable on Streamlit Community Cloud for sharing  
- **Reproducibility:** Every stage (from data generation to reporting) can be re-run with the same outcome  

### 9) Insights and Learnings
- Even small changes in conversion rates can create significant business impact.  
- Proper statistical rigor is essential; a positive trend isn’t enough without confidence.  
- Most experiments are *inconclusive* early on — success lies in the process, not just the result.  
- The framework can be reused for any A/B test scenario, not just checkout flows.  

---

*For detailed setup commands and execution steps, see [Getting Started Guide](docs/getting-started.rst).*  
