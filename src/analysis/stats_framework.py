"""
Statistical Framework for A/B Testing

Provides functions for proportion and mean comparisons, confidence intervals,
guardrail evaluation, and report-friendly formatting.
"""

import math
from typing import Tuple, Dict, Any, Union
import statistics


def two_proportion_test(
    successes_a: int,
    total_a: int,
    successes_b: int,
    total_b: int,
    alpha: float = 0.05,
) -> Dict[str, float]:
    """
    Two-sample proportion test with pooled variance.

    Compares two proportions (e.g., control vs treatment conversion rates) using
    a z-test with pooled standard error. Returns p-value, confidence interval,
    and effect sizes (absolute and relative).

    Args:
        successes_a: Number of successes in group A (e.g., control)
        total_a: Total observations in group A
        successes_b: Number of successes in group B (e.g., treatment)
        total_b: Total observations in group B
        alpha: Significance level for confidence interval (default 0.05 for 95% CI)

    Returns:
        Dictionary with keys:
            - p_value: Two-tailed p-value
            - ci_low: Lower bound of effect CI (absolute difference)
            - ci_high: Upper bound of effect CI (absolute difference)
            - effect_abs: Absolute difference (p_b - p_a)
            - effect_rel: Relative difference ((p_b - p_a) / p_a)

    Raises:
        ValueError: If inputs are invalid (negative counts, zero totals, etc.)

    Example:
        >>> result = two_proportion_test(100, 1000, 120, 1000, alpha=0.05)
        >>> print(f"p-value: {result['p_value']:.4f}")
        >>> print(f"Effect: {result['effect_abs']:.3f}")
    """
    # Input validation
    if total_a <= 0 or total_b <= 0:
        raise ValueError("Total observations must be positive")
    if successes_a < 0 or successes_b < 0:
        raise ValueError("Successes cannot be negative")
    if successes_a > total_a or successes_b > total_b:
        raise ValueError("Successes cannot exceed total observations")
    if not 0 < alpha < 1:
        raise ValueError("Alpha must be between 0 and 1")

    # Compute proportions
    p_a = successes_a / total_a
    p_b = successes_b / total_b

    # Effect sizes
    effect_abs = p_b - p_a
    effect_rel = (p_b - p_a) / p_a if p_a > 0 else float("inf")

    # Pooled proportion for standard error
    p_pooled = (successes_a + successes_b) / (total_a + total_b)

    # Standard error (pooled)
    se_pooled = math.sqrt(p_pooled * (1 - p_pooled) * (1 / total_a + 1 / total_b))

    # Z-statistic
    z_stat = effect_abs / se_pooled if se_pooled > 0 else 0

    # Two-tailed p-value using error function approximation
    # P(|Z| > |z|) = 2 * (1 - Phi(|z|))
    p_value = 2 * (1 - 0.5 * (1 + math.erf(abs(z_stat) / math.sqrt(2))))

    # Confidence interval for difference (unpooled SE for CI)
    se_unpooled = math.sqrt(p_a * (1 - p_a) / total_a + p_b * (1 - p_b) / total_b)
    z_crit = 1.96 if alpha == 0.05 else abs(_inverse_normal_cdf(alpha / 2))

    ci_low = effect_abs - z_crit * se_unpooled
    ci_high = effect_abs + z_crit * se_unpooled

    return {
        "p_value": p_value,
        "ci_low": ci_low,
        "ci_high": ci_high,
        "effect_abs": effect_abs,
        "effect_rel": effect_rel,
    }


def proportion_ci(
    successes: int,
    total: int,
    alpha: float = 0.05,
) -> Dict[str, float]:
    """
    Confidence interval for a single proportion.

    Uses normal approximation (Wald interval) for computing confidence intervals
    around a sample proportion.

    Args:
        successes: Number of successes
        total: Total observations
        alpha: Significance level (default 0.05 for 95% CI)

    Returns:
        Dictionary with keys:
            - rate: Sample proportion (successes / total)
            - ci_low: Lower bound of CI
            - ci_high: Upper bound of CI

    Raises:
        ValueError: If inputs are invalid

    Example:
        >>> result = proportion_ci(350, 1000, alpha=0.05)
        >>> print(f"Rate: {result['rate']:.1%} [{result['ci_low']:.1%}, {result['ci_high']:.1%}]")
    """
    # Input validation
    if total <= 0:
        raise ValueError("Total observations must be positive")
    if successes < 0:
        raise ValueError("Successes cannot be negative")
    if successes > total:
        raise ValueError("Successes cannot exceed total observations")
    if not 0 < alpha < 1:
        raise ValueError("Alpha must be between 0 and 1")

    # Compute rate
    rate = successes / total

    # Standard error
    se = math.sqrt(rate * (1 - rate) / total)

    # Critical value (z-score)
    z_crit = 1.96 if alpha == 0.05 else abs(_inverse_normal_cdf(alpha / 2))

    # Confidence interval
    ci_low = max(0, rate - z_crit * se)
    ci_high = min(1, rate + z_crit * se)

    return {
        "rate": rate,
        "ci_low": ci_low,
        "ci_high": ci_high,
    }


def mean_ci(
    values: Union[list, tuple],
    alpha: float = 0.05,
) -> Dict[str, float]:
    """
    Confidence interval for a mean using normal approximation.

    Computes mean and confidence interval using sample variance and normal
    approximation. Suitable for large samples (n > 30).

    Note: For small samples or non-normal distributions, consider using
    bootstrap methods instead.

    Args:
        values: Array-like of numeric values
        alpha: Significance level (default 0.05 for 95% CI)

    Returns:
        Dictionary with keys:
            - mean: Sample mean
            - ci_low: Lower bound of CI
            - ci_high: Upper bound of CI

    Raises:
        ValueError: If inputs are invalid

    Example:
        >>> result = mean_ci([250, 260, 255, 248, 262], alpha=0.05)
        >>> print(f"Mean: ${result['mean']:.2f} [${result['ci_low']:.2f}, ${result['ci_high']:.2f}]")
    """
    # Input validation
    if not values:
        raise ValueError("Values array cannot be empty")
    if len(values) < 2:
        raise ValueError("Need at least 2 values to compute confidence interval")
    if not 0 < alpha < 1:
        raise ValueError("Alpha must be between 0 and 1")

    # Convert to list if needed and validate numeric
    try:
        values = [float(v) for v in values]
    except (TypeError, ValueError):
        raise ValueError("All values must be numeric")

    # Compute mean and standard deviation
    mean = statistics.mean(values)
    n = len(values)

    if n == 1:
        # Single value, no variance
        return {"mean": mean, "ci_low": mean, "ci_high": mean}

    stdev = statistics.stdev(values)
    se = stdev / math.sqrt(n)

    # Critical value (z-score for large n, t-score would be more accurate for small n)
    z_crit = 1.96 if alpha == 0.05 else abs(_inverse_normal_cdf(alpha / 2))

    # Confidence interval
    ci_low = mean - z_crit * se
    ci_high = mean + z_crit * se

    return {
        "mean": mean,
        "ci_low": ci_low,
        "ci_high": ci_high,
    }


def guardrail_eval(
    baseline_value: float,
    treatment_value: float,
    rule: Dict[str, Any],
) -> Tuple[bool, str]:
    """
    Evaluate if treatment meets guardrail constraints.

    Compares baseline and treatment values against allowed deltas specified
    in the rule dictionary. Supports different rule types: max_drop_pp
    (percentage points), max_drop_pct (percent), max_increase_pp, max_increase_ms, etc.

    Args:
        baseline_value: Baseline (control) metric value
        treatment_value: Treatment metric value
        rule: Dictionary with constraint specifications, e.g.:
              {"max_drop_pp": 0.3} or {"max_drop_pct": 1.0}

    Returns:
        Tuple of (passed: bool, message: str)
        - passed: True if guardrail met, False if breached
        - message: Human-readable explanation

    Raises:
        ValueError: If rule format is invalid

    Example:
        >>> passed, msg = guardrail_eval(0.92, 0.91, {"max_drop_pp": 0.3})
        >>> print(f"Passed: {passed}, {msg}")
    """
    # Input validation
    if not rule or not isinstance(rule, dict):
        raise ValueError("Rule must be a non-empty dictionary")

    # Determine rule type and threshold
    rule_type = None
    threshold = None

    for key, value in rule.items():
        if key.startswith("max_drop_pp"):
            rule_type = "drop_pp"
            threshold = value
        elif key.startswith("max_drop_pct"):
            rule_type = "drop_pct"
            threshold = value
        elif key.startswith("max_increase_pp"):
            rule_type = "increase_pp"
            threshold = value
        elif key.startswith("max_increase_ms"):
            rule_type = "increase_ms"
            threshold = value
        elif key.startswith("max_increase_pct"):
            rule_type = "increase_pct"
            threshold = value

    if rule_type is None or threshold is None:
        raise ValueError(f"Unrecognized rule format: {rule}")

    # Compute delta based on rule type
    if rule_type == "drop_pp":
        # Absolute drop in percentage points
        delta = baseline_value - treatment_value
        passed = delta <= threshold
        msg = (
            f"Drop of {delta:.3f}pp (baseline: {baseline_value:.3f}, "
            f"treatment: {treatment_value:.3f}). "
            f"Threshold: {threshold}pp. {'PASS' if passed else 'FAIL'}"
        )

    elif rule_type == "drop_pct":
        # Relative drop as percentage
        if baseline_value == 0:
            return False, "Cannot compute percent drop with baseline = 0"
        delta_pct = ((baseline_value - treatment_value) / baseline_value) * 100
        passed = delta_pct <= threshold
        msg = (
            f"Drop of {delta_pct:.2f}% (baseline: {baseline_value:.2f}, "
            f"treatment: {treatment_value:.2f}). "
            f"Threshold: {threshold}%. {'PASS' if passed else 'FAIL'}"
        )

    elif rule_type == "increase_pp":
        # Absolute increase in percentage points
        delta = treatment_value - baseline_value
        passed = delta <= threshold
        msg = (
            f"Increase of {delta:.3f}pp (baseline: {baseline_value:.3f}, "
            f"treatment: {treatment_value:.3f}). "
            f"Threshold: {threshold}pp. {'PASS' if passed else 'FAIL'}"
        )

    elif rule_type == "increase_ms":
        # Absolute increase in milliseconds
        delta = treatment_value - baseline_value
        passed = delta <= threshold
        msg = (
            f"Increase of {delta:.1f}ms (baseline: {baseline_value:.1f}ms, "
            f"treatment: {treatment_value:.1f}ms). "
            f"Threshold: {threshold}ms. {'PASS' if passed else 'FAIL'}"
        )

    elif rule_type == "increase_pct":
        # Relative increase as percentage
        if baseline_value == 0:
            return False, "Cannot compute percent increase with baseline = 0"
        delta_pct = ((treatment_value - baseline_value) / baseline_value) * 100
        passed = delta_pct <= threshold
        msg = (
            f"Increase of {delta_pct:.2f}% (baseline: {baseline_value:.2f}, "
            f"treatment: {treatment_value:.2f}). "
            f"Threshold: {threshold}%. {'PASS' if passed else 'FAIL'}"
        )

    else:
        raise ValueError(f"Unsupported rule type: {rule_type}")

    return passed, msg


def pretty_round(value: float, decimal_places: int = None) -> float:
    """
    Round numeric value to human-friendly precision for reporting.

    Automatically chooses appropriate decimal places if not specified:
    - Large values (>100): 1 decimal
    - Medium values (1-100): 2 decimals
    - Small values (<1): 3 decimals
    - Very small values (<0.01): 4 decimals

    Args:
        value: Numeric value to round
        decimal_places: Optional fixed number of decimal places

    Returns:
        Rounded float value

    Example:
        >>> pretty_round(0.350123)
        0.35
        >>> pretty_round(1234.5678)
        1234.6
        >>> pretty_round(0.001234)
        0.0012
    """
    if decimal_places is not None:
        return round(value, decimal_places)

    abs_value = abs(value)

    if abs_value >= 100:
        return round(value, 1)
    elif abs_value >= 1:
        return round(value, 2)
    elif abs_value >= 0.01:
        return round(value, 3)
    else:
        return round(value, 4)


def _inverse_normal_cdf(p: float) -> float:
    """
    Approximate inverse normal CDF (probit function) for critical values.

    Uses a rational approximation for the inverse normal CDF. Accurate to
    about 4 decimal places for typical alpha values (0.01 to 0.10).

    Args:
        p: Probability (should be < 0.5 for left tail)

    Returns:
        z-score corresponding to probability p

    Note:
        This is an internal helper function. For production use, consider
        scipy.stats.norm.ppf for higher accuracy.
    """
    if p <= 0 or p >= 1:
        raise ValueError("Probability must be between 0 and 1 (exclusive)")

    # For common alpha values, use precomputed z-scores
    if abs(p - 0.025) < 1e-6:  # alpha = 0.05, two-tailed
        return -1.96
    if abs(p - 0.005) < 1e-6:  # alpha = 0.01, two-tailed
        return -2.576

    # Rational approximation (Abramowitz and Stegun, formula 26.2.23)
    # For general case, use a simple approximation
    if p > 0.5:
        return -_inverse_normal_cdf(1 - p)

    # Coefficients for approximation
    c0 = 2.515517
    c1 = 0.802853
    c2 = 0.010328
    d1 = 1.432788
    d2 = 0.189269
    d3 = 0.001308

    t = math.sqrt(-2 * math.log(p))
    z = t - (c0 + c1 * t + c2 * t * t) / (1 + d1 * t + d2 * t * t + d3 * t * t * t)

    return -z
