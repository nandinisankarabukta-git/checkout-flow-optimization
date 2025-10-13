# A/A Test Validation Plan

**Document Version:** 1.0  
**Last Updated:** 2025-01-12  

---

## Purpose

Validate that the experimentation infrastructure is working correctly by running an A/A test where both variants receive identical treatment. This ensures that any observed differences in a real A/B test are due to actual treatment effects, not systematic biases in randomization, instrumentation, or analysis.

**Key Objectives:**
- Verify random assignment produces balanced variant splits (within 2 percentage points of 50/50)
- Confirm no statistically significant differences appear between identical variants
- Validate data collection pipeline integrity (events, timestamps, referential constraints)
- Establish baseline false positive rate aligns with theoretical expectation (α = 0.05)

---

## Procedure

**1. Configure A/A Test**
- Set `--aa` flag or `uplift=0.0` in simulation parameters
- Run for minimum 4 days with at least 10,000 users per day
- Ensure both variants use identical checkout flow code/configuration

**2. Generate A/A Test Data**
```bash
make clean
python src/data/simulate.py --start 2025-01-01 --days 4 --users 10000 --aa
make build && make marts
```

**3. Run Quality Checks**
```bash
AA_MODE=1 make quality
```
- Verify randomization balance (48-52% split)
- Check referential integrity
- Validate enum values and timestamp ordering

**4. Execute Statistical Analysis**
```bash
make results
make report
```
- Review CCR lift and confidence interval
- Check p-value (should be > 0.05 in most runs)
- Examine guardrail metrics for parity

**5. Document Results**
- Record p-value, effect size, and CI width
- Note any quality check failures
- Archive results in `reports/results/` with timestamp

---

## Expected

**Randomization Balance:**
- Variant split within 48-52% (no more than 2pp deviation)
- Consistent balance across all dates in the experiment window

**Primary Metric (CCR):**
- No statistically significant difference (p-value ≥ 0.05 expected ~95% of runs)
- Effect size close to zero (within ±0.5 percentage points)
- Confidence interval includes zero

**Guardrail Metrics:**
- Payment authorization rate: difference < 0.5pp between variants
- Average order value: difference < $2.00 between variants
- No systematic directional bias (control always higher or always lower)

**Data Quality:**
- All 5 quality checks pass (referential integrity, enums, timestamps)
- No orphaned events or missing join keys
- Event volumes consistent across variants

**False Positive Tolerance:**
- If running multiple A/A tests: expect ~5% to show p < 0.05 by chance
- Single A/A failure does not invalidate infrastructure (rerun to confirm)

---

## Escalation

**Immediate Action Required If:**
- **Randomization imbalance** > 2pp deviation from 50/50 split
  - **Action:** Investigate hash-based assignment logic in `src/data/simulate.py`

- **Statistically significant difference** (p < 0.05) appears in 2+ consecutive A/A runs
  - **Action:** Audit data pipeline for variant-dependent bugs or SRM (Sample Ratio Mismatch)

- **Quality check failures** (referential integrity, enum validation, timestamp violations)
  - **Action:** Fix data generation issues before proceeding to A/B tests

- **Systematic directional bias** observed (e.g., "treatment" always higher even at uplift=0)
  - **Action:** Review computation logic in `src/analysis/metrics_runner.py`

**Resolution Timeline:**
- Critical issues (randomization, data integrity): Fix before proceeding with A/B tests
- Non-critical issues (minor metric drift): Document and monitor in subsequent runs
- All issues should be documented with resolution steps

---

**References:**
- Experimentation setup: `configs/experiment.yml`
- Data quality checks: `src/quality.py`
- Statistical framework: `src/analysis/stats_framework.py`
- Metrics specification: `references/metrics_spec.md`

