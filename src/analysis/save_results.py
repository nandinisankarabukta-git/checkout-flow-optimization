"""
Save Statistical Analysis Results

Exports A/B test results (CCR, guardrails, funnel metrics) to JSON and CSV files
for consumption by reports and dashboards.
"""

import json
import csv
import sys
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.analysis.metrics_runner import (
    get_variant_counts_for_ccr,
    get_guardrails,
    most_recent_date,
    connect_warehouse,
)
from src.analysis.stats_framework import (
    two_proportion_test,
    proportion_ci,
)


def get_git_commit_hash() -> Optional[str]:
    """
    Get the current git commit hash.

    Returns:
        Commit hash string or None if not available
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        )
        return result.stdout.strip()
    except (
        subprocess.CalledProcessError,
        FileNotFoundError,
        subprocess.TimeoutExpired,
    ):
        return None


def load_experiment_config() -> Optional[Dict[str, Any]]:
    """
    Load experiment configuration from YAML file.

    Returns:
        Dictionary with experiment config, or None if not available
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
        # yaml not available
        return None
    except Exception:
        return None


def detect_simulator_seed() -> Optional[int]:
    """
    Attempt to detect the simulator seed from Makefile.

    Returns:
        Seed value or None if not detectable
    """
    try:
        makefile_path = Path("Makefile")
        if not makefile_path.exists():
            return None

        with open(makefile_path, "r") as f:
            content = f.read()

        # Look for --seed argument in simulate target
        for line in content.split("\n"):
            if "--seed" in line and "simulate" in content[: content.find(line)]:
                # Extract seed value after --seed
                parts = line.split("--seed")
                if len(parts) > 1:
                    seed_part = parts[1].strip().split()[0]
                    try:
                        return int(seed_part)
                    except ValueError:
                        pass
        return None
    except Exception:
        return None


def create_run_metadata(date: str) -> Dict[str, Any]:
    """
    Create metadata about the current analysis run.

    Args:
        date: The most recent date analyzed

    Returns:
        Dictionary with run metadata
    """
    metadata = {
        "timestamp_utc": datetime.utcnow().isoformat() + "Z",
        "date_analyzed": date,
    }

    # Add git commit hash if available
    git_hash = get_git_commit_hash()
    if git_hash:
        metadata["git_commit"] = git_hash
    else:
        metadata["git_commit"] = None

    # Add experiment name from config if available
    config = load_experiment_config()
    if config and "name" in config:
        metadata["experiment_name"] = config["name"]
    else:
        metadata["experiment_name"] = None

    # Add simulator seed if detectable
    seed = detect_simulator_seed()
    if seed is not None:
        metadata["simulator_seed"] = seed
    else:
        metadata["simulator_seed"] = None

    return metadata


def compute_ccr_summary(
    variant_counts: Dict[str, Dict[str, int]], date: str
) -> Dict[str, Any]:
    """
    Compute CCR statistical test results.

    Args:
        variant_counts: Per-variant adders and orders
        date: Analysis date

    Returns:
        Dictionary with effect, CI, p-value, and per-variant details
    """
    control = variant_counts["control"]
    treatment = variant_counts["treatment"]

    # Run two-proportion test
    test_result = two_proportion_test(
        successes_a=control["orders"],
        total_a=control["adders"],
        successes_b=treatment["orders"],
        total_b=treatment["adders"],
        alpha=0.05,
    )

    # Compute per-variant CCRs
    ccr_control = control["orders"] / control["adders"] if control["adders"] > 0 else 0
    ccr_treatment = (
        treatment["orders"] / treatment["adders"] if treatment["adders"] > 0 else 0
    )

    return {
        "date": date,
        "effect_abs": test_result["effect_abs"],
        "effect_rel": test_result["effect_rel"],
        "ci_low": test_result["ci_low"],
        "ci_high": test_result["ci_high"],
        "p_value": test_result["p_value"],
        "significant": test_result["p_value"] < 0.05,
        "control": {
            "adders": control["adders"],
            "orders": control["orders"],
            "ccr": ccr_control,
        },
        "treatment": {
            "adders": treatment["adders"],
            "orders": treatment["orders"],
            "ccr": ccr_treatment,
        },
    }


def compute_guardrails_summary(
    guardrails: Dict[str, Dict[str, Any]], date: str
) -> Dict[str, Any]:
    """
    Compute guardrail metrics with confidence intervals.

    Args:
        guardrails: Per-variant guardrail data
        date: Analysis date

    Returns:
        Dictionary with authorization rate and AOV per variant with CIs
    """
    control_gr = guardrails["control"]
    treatment_gr = guardrails["treatment"]

    # Payment authorization CIs
    control_auth_ci = proportion_ci(
        successes=control_gr["payment_auth"]["authorized"],
        total=control_gr["payment_auth"]["total_attempts"],
        alpha=0.05,
    )
    treatment_auth_ci = proportion_ci(
        successes=treatment_gr["payment_auth"]["authorized"],
        total=treatment_gr["payment_auth"]["total_attempts"],
        alpha=0.05,
    )

    return {
        "date": date,
        "payment_authorization": {
            "control": {
                "rate": control_auth_ci["rate"],
                "ci_low": control_auth_ci["ci_low"],
                "ci_high": control_auth_ci["ci_high"],
                "authorized": control_gr["payment_auth"]["authorized"],
                "total_attempts": control_gr["payment_auth"]["total_attempts"],
            },
            "treatment": {
                "rate": treatment_auth_ci["rate"],
                "ci_low": treatment_auth_ci["ci_low"],
                "ci_high": treatment_auth_ci["ci_high"],
                "authorized": treatment_gr["payment_auth"]["authorized"],
                "total_attempts": treatment_gr["payment_auth"]["total_attempts"],
            },
        },
        "average_order_value": {
            "control": {
                "mean": control_gr["aov"]["mean"],
                "count": control_gr["aov"]["count"],
            },
            "treatment": {
                "mean": treatment_gr["aov"]["mean"],
                "count": treatment_gr["aov"]["count"],
            },
        },
    }


def get_funnel_data(date: str, conn=None) -> Dict[str, Dict[str, int]]:
    """
    Get funnel metrics per variant for CSV export.

    Args:
        date: Analysis date
        conn: Optional DuckDB connection

    Returns:
        Dictionary with funnel metrics per variant
    """
    close_conn = False
    if conn is None:
        conn = connect_warehouse()
        close_conn = True

    try:
        result = conn.execute(
            f"""
            WITH most_recent_date AS (
                SELECT '{date}'::DATE as max_date
            )
            SELECT 
                variant,
                COUNT(DISTINCT user_id) as adders,
                (SELECT COUNT(DISTINCT checkout_id) 
                 FROM events.begin_checkout, most_recent_date 
                 WHERE DATE(timestamp) = max_date 
                 AND begin_checkout.variant = a.variant) as begin_checkout,
                (SELECT COUNT(*) 
                 FROM events.payment_attempt, most_recent_date 
                 WHERE DATE(timestamp) = max_date 
                 AND payment_attempt.variant = a.variant) as payment_attempts,
                (SELECT COUNT(*) 
                 FROM events.order_completed, most_recent_date 
                 WHERE DATE(timestamp) = max_date 
                 AND order_completed.variant = a.variant) as orders
            FROM events.add_to_cart a, most_recent_date
            WHERE DATE(a.timestamp) = most_recent_date.max_date
            GROUP BY variant
            ORDER BY variant
        """
        ).fetchall()

        funnel = {}
        for row in result:
            variant, adders, begin_checkout, payment_attempts, orders = row
            funnel[variant] = {
                "variant": variant,
                "adders": int(adders),
                "begin_checkout": int(begin_checkout),
                "payment_attempts": int(payment_attempts),
                "orders": int(orders),
            }

        return funnel

    finally:
        if close_conn:
            conn.close()


def save_results(output_dir: str = "reports/results") -> int:
    """
    Save statistical analysis results to JSON and CSV files.

    Args:
        output_dir: Output directory path

    Returns:
        Exit code: 0 on success, 1 on failure
    """
    try:
        # Create output directory
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # Get most recent date
        date = most_recent_date()
        print(f"Analyzing data for: {date}")

        # Get data
        variant_counts = get_variant_counts_for_ccr()
        guardrails_data = get_guardrails()
        funnel_data = get_funnel_data(date)

        # Compute summaries
        ccr_summary = compute_ccr_summary(variant_counts, date)
        guardrails_summary = compute_guardrails_summary(guardrails_data, date)

        # 1. Create and save run metadata
        run_metadata = create_run_metadata(date)
        metadata_json_path = output_path / "_run_meta.json"
        with open(metadata_json_path, "w") as f:
            json.dump(run_metadata, f, indent=2)
        print(f"Saved run metadata: {metadata_json_path.resolve()}")

        # 2. Save CCR summary to JSON
        ccr_json_path = output_path / "ccr_summary.json"
        with open(ccr_json_path, "w") as f:
            json.dump(ccr_summary, f, indent=2)
        print(f"Saved CCR summary: {ccr_json_path.resolve()}")

        # 3. Save guardrails summary to JSON
        guardrails_json_path = output_path / "guardrails_summary.json"
        with open(guardrails_json_path, "w") as f:
            json.dump(guardrails_summary, f, indent=2)
        print(f"Saved guardrails summary: {guardrails_json_path.resolve()}")

        # 4. Save funnel data to CSV
        funnel_csv_path = output_path / "variant_funnel.csv"
        with open(funnel_csv_path, "w", newline="") as f:
            fieldnames = [
                "variant",
                "adders",
                "begin_checkout",
                "payment_attempts",
                "orders",
            ]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for variant_data in funnel_data.values():
                writer.writerow(variant_data)
        print(f"Saved variant funnel: {funnel_csv_path.resolve()}")

        print()
        print("All results saved successfully!")
        return 0

    except Exception as e:
        print(f"\nERROR: Failed to save results: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        return 1


def main() -> int:
    """Main entry point."""
    return save_results()


if __name__ == "__main__":
    sys.exit(main())
