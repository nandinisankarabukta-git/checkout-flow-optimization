"""
Statistical Analysis Runner for A/B Testing

Runs statistical tests for the most recent date and prints a compact summary
for CCR (primary metric) and guardrails.
"""

import sys
from pathlib import Path
from typing import Dict, Any

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.analysis.metrics_runner import (
    get_variant_counts_for_ccr,
    get_guardrails,
    most_recent_date,
)
from src.analysis.stats_framework import (
    two_proportion_test,
    proportion_ci,
    mean_ci,
    guardrail_eval,
    pretty_round,
)


def load_experiment_config() -> Dict[str, Any]:
    """
    Load experiment configuration from YAML file.

    Returns:
        Dictionary with experiment config, or None if file not found
    """
    try:
        import yaml

        config_path = Path("configs/experiment.yml")
        if not config_path.exists():
            return None

        with open(config_path, "r") as f:
            config = yaml.safe_load(f)
            return config.get("experiment", {})
    except ImportError:
        # yaml not available, skip config loading
        return None
    except Exception as e:
        print(f"Warning: Could not load config: {e}")
        return None


def print_header(date: str):
    """Print report header."""
    print("=" * 80)
    print("A/B TEST STATISTICAL ANALYSIS")
    print("=" * 80)
    print(f"Analysis Date: {date}")
    print("=" * 80)
    print()


def print_ccr_analysis(variant_counts: Dict[str, Dict[str, int]], alpha: float = 0.05):
    """
    Print CCR analysis with statistical test results.

    Returns:
        Tuple of (ccr_control, ccr_treatment, test_result)
    """
    print("PRIMARY METRIC: Conditional Conversion Rate (CCR)")
    print("-" * 80)

    control = variant_counts["control"]
    treatment = variant_counts["treatment"]

    # Compute CCR per variant
    ccr_control = control["orders"] / control["adders"] if control["adders"] > 0 else 0
    ccr_treatment = (
        treatment["orders"] / treatment["adders"] if treatment["adders"] > 0 else 0
    )

    print(
        f"Control:   {control['orders']:,} orders / {control['adders']:,} adders = {ccr_control:.2%}"
    )
    print(
        f"Treatment: {treatment['orders']:,} orders / {treatment['adders']:,} adders = {ccr_treatment:.2%}"
    )
    print()

    # Run two-proportion test
    test_result = two_proportion_test(
        successes_a=control["orders"],
        total_a=control["adders"],
        successes_b=treatment["orders"],
        total_b=treatment["adders"],
        alpha=alpha,
    )

    # Print results
    effect_abs_pp = test_result["effect_abs"] * 100  # Convert to percentage points
    ci_low_pp = test_result["ci_low"] * 100
    ci_high_pp = test_result["ci_high"] * 100

    print(
        f"Effect (absolute): {effect_abs_pp:+.2f}pp ({test_result['effect_rel']:+.1%} relative)"
    )
    print(f"95% Confidence Interval: [{ci_low_pp:.2f}pp, {ci_high_pp:.2f}pp]")
    print(f"p-value: {test_result['p_value']:.4f}")
    print()

    # Significance check
    is_significant = test_result["p_value"] < alpha
    if is_significant:
        print(f"SIGNIFICANT at α={alpha} (p < {alpha})")
    else:
        print(f"NOT SIGNIFICANT at α={alpha} (p >= {alpha})")

    print()
    return ccr_control, ccr_treatment, test_result


def print_guardrails_analysis(
    guardrails: Dict[str, Dict[str, Any]], config: Dict[str, Any] = None
):
    """
    Print guardrail metrics with confidence intervals and PASS/FAIL evaluation.

    Returns:
        Boolean indicating if all guardrails passed
    """
    print("GUARDRAIL METRICS")
    print("-" * 80)

    control_gr = guardrails["control"]
    treatment_gr = guardrails["treatment"]

    all_passed = True

    # 1. Payment Authorization Rate
    print("1. Payment Authorization Rate")
    print()

    control_auth = control_gr["payment_auth"]
    treatment_auth = treatment_gr["payment_auth"]

    # Compute CIs for each variant
    control_ci = proportion_ci(
        successes=control_auth["authorized"],
        total=control_auth["total_attempts"],
    )
    treatment_ci = proportion_ci(
        successes=treatment_auth["authorized"],
        total=treatment_auth["total_attempts"],
    )

    print(
        f"   Control:   {control_ci['rate']:.1%} (95% CI: [{control_ci['ci_low']:.1%}, {control_ci['ci_high']:.1%}])"
    )
    print(
        f"   Treatment: {treatment_ci['rate']:.1%} (95% CI: [{treatment_ci['ci_low']:.1%}, {treatment_ci['ci_high']:.1%}])"
    )
    print()

    # Evaluate guardrail if threshold available
    if config and "metrics" in config and "guardrails" in config["metrics"]:
        threshold_key = "payment_auth_min_drop_pp"
        if threshold_key in config["metrics"]["guardrails"]:
            threshold = config["metrics"]["guardrails"][threshold_key]
            passed, msg = guardrail_eval(
                baseline_value=control_ci["rate"],
                treatment_value=treatment_ci["rate"],
                rule={"max_drop_pp": threshold},
            )
            print(f"   Guardrail: {msg}")
            if not passed:
                all_passed = False
        else:
            print("   Guardrail: No threshold configured")
    else:
        print("   Guardrail: No threshold configured")

    print()

    # 2. Average Order Value (AOV)
    print("2. Average Order Value (AOV)")
    print()

    control_aov = control_gr["aov"]
    treatment_aov = treatment_gr["aov"]

    print(f"   Control:   ${control_aov['mean']:.2f} (n={control_aov['count']:,})")
    print(f"   Treatment: ${treatment_aov['mean']:.2f} (n={treatment_aov['count']:,})")
    print()

    # Evaluate guardrail if threshold available
    if config and "metrics" in config and "guardrails" in config["metrics"]:
        threshold_key = "aov_min_drop_pct"
        if threshold_key in config["metrics"]["guardrails"]:
            threshold = config["metrics"]["guardrails"][threshold_key]
            passed, msg = guardrail_eval(
                baseline_value=control_aov["mean"],
                treatment_value=treatment_aov["mean"],
                rule={"max_drop_pct": threshold},
            )
            print(f"   Guardrail: {msg}")
            if not passed:
                all_passed = False
        else:
            print("   Guardrail: No threshold configured")
    else:
        print("   Guardrail: No threshold configured")

    print()
    return all_passed


def print_decision(is_significant: bool, guardrails_passed: bool, mde: float = None):
    """Print final ship/no-ship decision."""
    print("DECISION")
    print("-" * 80)

    if is_significant and guardrails_passed:
        print("PRIMARY METRIC: Statistically significant")
        print("GUARDRAILS: All passed")
        print()
        print("RECOMMENDATION: SHIP")
        if mde:
            print(f"(Note: Check that effect meets MDE of {mde * 100:.2f}pp)")
    elif not is_significant:
        print("PRIMARY METRIC: Not statistically significant")
        if guardrails_passed:
            print("GUARDRAILS: All passed")
        else:
            print("GUARDRAILS: One or more failed")
        print()
        print("RECOMMENDATION: DO NOT SHIP")
    else:  # significant but guardrails failed
        print("PRIMARY METRIC: Statistically significant")
        print("GUARDRAILS: One or more failed")
        print()
        print("RECOMMENDATION: DO NOT SHIP")

    print("=" * 80)


def main() -> int:
    """
    Main entry point for statistical analysis.

    Returns:
        Exit code: 0 if significant and guardrails pass, 1 otherwise
    """
    try:
        # Load configuration
        config = load_experiment_config()
        alpha = 0.05
        mde = None

        if config:
            if "alpha" in config:
                alpha = config["alpha"]
            if "mde_abs" in config:
                mde = config["mde_abs"]

        # Get most recent date
        date = most_recent_date()

        # Print header
        print_header(date)

        # Get data
        variant_counts = get_variant_counts_for_ccr()
        guardrails_data = get_guardrails()

        # Run CCR analysis
        ccr_control, ccr_treatment, test_result = print_ccr_analysis(
            variant_counts, alpha
        )
        is_significant = test_result["p_value"] < alpha

        # Run guardrails analysis
        guardrails_passed = print_guardrails_analysis(guardrails_data, config)

        # Print decision
        print_decision(is_significant, guardrails_passed, mde)

        # Exit code
        if is_significant and guardrails_passed:
            return 0
        else:
            return 1

    except Exception as e:
        print(f"\nERROR: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        return 2


if __name__ == "__main__":
    sys.exit(main())
