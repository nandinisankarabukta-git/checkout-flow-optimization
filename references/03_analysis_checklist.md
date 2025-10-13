# Analysis Checklist: Checkout Flow Optimization

Use this checklist to ensure thorough and consistent experiment analysis throughout the lifecycle.

---

## Pre-run

- [ ] Confirm experiment window and exposure rule match configs
- [ ] AA sanity check passed in recent data
- [ ] Traffic splits balanced within 2 percentage points

---

## During run

- [ ] Daily CCR and guardrails reported
- [ ] No data quality alerts

---

## Post-run

- [ ] Final CCR lift computed with 95 percent CI and p-value
- [ ] Guardrails compared to thresholds (auth rate, AOV, latency p95, refund rate)
- [ ] Segment cuts reviewed (device, country, traffic source)
- [ ] Decision documented per ship rule

---

## References

- Metrics specification: [metrics_spec.md](metrics_spec.md)
- Experiment configuration: `configs/experiment.yml`
- Quality checks: `src/quality.py`
- Reporting: `make report` or `make app`

