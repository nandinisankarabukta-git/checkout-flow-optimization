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

### 5) Statistical Analysis and Results

Once the data was prepared, the project compared how the control and treatment groups performed.  

| Metric | Control | Treatment | Change | p-value | Significance |
|--------|----------|-----------|---------|----------|---------------|
| Conditional Conversion | 36.9% | 37.8% | +0.89pp | 0.3566 | Not Significant |
| Payment Auth Rate | 91.8% | 92.9% | +1.2pp | — | Pass |
| Avg Order Value | $256.82 | $259.19 | +$2.37 | — | Pass |

In plain terms, the new checkout design showed a **slightly higher conversion rate** (37.8% vs. 36.9%), but the improvement wasn’t large enough to be statistically significant.  
The p-value (0.3566) indicates that the difference could easily have occurred by random chance.  

However, the experiment confirmed something equally important — the treatment didn’t harm any **guardrail metrics**.  
Payment success rates and average order values both stayed healthy, meaning the new design is at least as safe and stable as the existing one.

In real-world terms, this is a valuable result: the team can safely run the test longer or with more traffic before deciding whether to roll out the new design.

### 6) Sensitivity and Power Analysis
To understand how much data would be needed to reach a reliable conclusion, a **power analysis** was performed.  
It found that detecting a 1.5 percentage point lift would require around **50,000 users per variant** to achieve 80% power.  

This explains why the experiment result, while positive, was statistically inconclusive — the sample size was too small to confidently prove the effect.  
This mirrors what often happens in real A/B testing, where promising results need larger datasets or longer run times to reach statistical confidence.

### 7) Visualization and Reporting
The project includes both static and interactive reporting components:

- Automatically generated **Markdown reports** summarizing metrics and results  
- A **Streamlit dashboard** for interactive exploration of conversion funnels, variant comparisons, and sensitivity results  

These reports make it easy for both analysts and business teams to interpret results and decide next steps.

## Dashboard Walkthrough

See the interactive dashboard in action:

<video controls autoplay loop muted>
  <source src="docs/media/dashboard_walkthrough.mov" type="video/quicktime">
  Your browser does not support the video tag.
</video>

*For detailed setup commands and execution steps, see [Getting Started Guide](docs/getting-started.rst).*  
