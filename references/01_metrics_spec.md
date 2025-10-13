# Metrics Specification: Checkout Flow Optimization

**Version:** 1.0  
**Date:** 2025-01-12  
**Experiment:** Checkout Flow Optimization

---

## 1. Primary Objective

Increase conditional conversion from Add to Cart to Order Completion.

---

## 2. Primary Metric

**Name:** Conditional Conversion Rate (CCR)

**Definition:** Orders divided by AddToCart among exposed users

**Unit of Analysis:** User

**Aggregation Window:**
- Experiment window (full duration)
- Daily rollups (for interim monitoring)

**Direction of Improvement:** Higher is better

**Practical Significance Threshold:** Uplift at least the MDE set in `configs/experiment.yml`

---

## 3. Secondary Metrics

**Gross Conversion:**
- Session to Order conversion rate
- Measures end-to-end funnel performance

**Step-Through Rates:**
- AddToCart → BeginCheckout
- BeginCheckout → Payment
- Payment → Order
- Identifies specific funnel bottlenecks

**Median Time in Step:**
- Per checkout step (address, shipping, payment, review)
- Indicates user friction or confusion

**Form Error Rate:**
- Errors per checkout session
- Signals validation or UX issues

---

## 4. Guardrail Metrics

**Payment Authorization Success Rate:**
- No meaningful drop allowed
- Ensures payment processing integrity

**Average Order Value (AOV):**
- Must not decrease beyond threshold
- Protects revenue quality

**Refund or Cancellation Rate:**
- Must not increase beyond threshold
- Ensures order quality and customer satisfaction

**Latency of Payment Step (p95):**
- Must not regress beyond threshold
- Maintains acceptable user experience

---

## 5. Diagnostic Metrics

**Error Mix by Step and Field:**
- Distribution of errors across form fields
- Helps identify specific problem areas

**Revisits or Backtracks Between Steps:**
- Users returning to previous steps
- Indicates navigation or clarity issues

**Device or Country Breakdowns:**
- Performance segmentation by device type
- Regional differences in behavior
- Identifies segment-specific effects

---

## 6. Hypotheses

**H1:** Treatment increases CCR by at least the MDE

**H2:** Treatment does not breach any guardrails

---

## 7. Decision Rule

**Ship if:**
- CCR lift is statistically significant at alpha = 0.05
- CCR lift meets or exceeds MDE (practical significance)
- All guardrails are within preset bounds

**Do not ship if:**
- CCR is not statistically significant
- CCR does not meet practical significance (MDE)
- Any guardrail is breached

---

## 8. Analysis Plan

**Unit:** User

**Exposure:** First Add to Cart event in experiment window

**Estimator:**
- Difference in proportions for CCR
- Two-sample z-test with pooled variance
- 95% confidence interval

**Stratifications:**
- Device type (mobile, desktop, tablet)
- Country or region
- Traffic source (organic, paid, direct)
- Note: Reporting only unless pre-specified for powered analysis

**Missing Data:**
- Exclude obvious bots or staff traffic (pre-defined filters)
- Keep intent-to-treat otherwise (no post-assignment exclusions)
- Handle missing fields with appropriate defaults or flags

---

## 9. Reporting Cadence

**Daily Interim Readouts:**
- Monitor for guardrail breaches
- Track metric trends
- Enable early stopping if needed

**Final Report:**
- Delivered at end of experiment window
- Includes full statistical analysis
- Provides ship/no-ship recommendation

---

## 10. Assumptions and Multiple Testing

**Primary Test:**
- Controls family-wise error rate at α = 0.05
- One pre-specified primary metric (CCR) ensures no multiple testing correction is needed

**Guardrails:**
- Monitored for practical regressions (e.g., payment authorization rate, AOV)
- Are **not** the basis for claiming improvement
- Serve as safety constraints, not hypothesis tests
- If many guardrails are added, consider Holm or Benjamini-Hochberg adjustments for their alerting logic to control false alarms

**Statistical Assumptions:**
- Independence of observations (enforced by random variant assignment)
- Large sample assumptions apply to proportion z-tests (n > 30 per variant typically sufficient)
- If assumptions are violated (e.g., small samples, clustering, non-independence), consider:
  - Permutation tests for exact p-values
  - Bootstrap methods for robust confidence intervals
  - Mixed-effects models for clustered data

**Recommendation:** Validate assumptions during analysis. Document any deviations and their remediation in the final report.

---

## References

- Experiment configuration: `configs/experiment.yml`
- Tracking plan: `configs/tracking_plan.yml`
- Data quality checks: `src/quality.py`
- Analytical marts: `sql/marts/`

