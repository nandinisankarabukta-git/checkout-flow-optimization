#!/usr/bin/env python3
"""
Sensitivity Analysis for A/B Test Power
========================================
Sweep over users per day and uplift parameters to compute CCR detection rates.

Usage:
    python src/analysis/sensitivity.py \
        --start 2025-02-01 \
        --days 1 \
        --users "10000,20000" \
        --uplifts "0.0,0.02" \
        --repeats 10 \
        --seed 7
"""

import argparse
import csv
import json
import logging
import sys
import subprocess
import tempfile
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Tuple, Optional, Dict, Any
import shutil

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.analysis.metrics_runner import (
    connect_warehouse,
    get_variant_counts_for_ccr,
)
from src.analysis.stats_framework import two_proportion_test

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def parse_comma_separated_floats(value: str) -> List[float]:
    """Parse comma-separated float values."""
    try:
        return [float(v.strip()) for v in value.split(",")]
    except ValueError as e:
        raise argparse.ArgumentTypeError(f"Invalid float list: {value}") from e


def parse_comma_separated_ints(value: str) -> List[int]:
    """Parse comma-separated integer values."""
    try:
        return [int(v.strip()) for v in value.split(",")]
    except ValueError as e:
        raise argparse.ArgumentTypeError(f"Invalid integer list: {value}") from e


def load_preset(preset_name: str) -> dict:
    """
    Load preset configuration from YAML file.

    Args:
        preset_name: Name of the preset to load

    Returns:
        Dictionary with preset configuration

    Raises:
        FileNotFoundError: If preset file doesn't exist
        KeyError: If preset name not found
        ValueError: If YAML is invalid
    """
    preset_path = Path("configs/sensitivity_presets.yml")

    if not preset_path.exists():
        raise FileNotFoundError(
            f"Preset file not found: {preset_path}. "
            "Create configs/sensitivity_presets.yml with preset definitions."
        )

    try:
        import yaml

        with open(preset_path, "r") as f:
            config = yaml.safe_load(f)

        if "presets" not in config:
            raise ValueError("Invalid preset file: missing 'presets' key")

        if preset_name not in config["presets"]:
            available = ", ".join(config["presets"].keys())
            raise KeyError(
                f"Preset '{preset_name}' not found. Available presets: {available}"
            )

        return config["presets"][preset_name]

    except ImportError:
        raise ImportError(
            "PyYAML is required for preset support. Install with: pip install pyyaml"
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


def create_metadata(
    users_list: List[int],
    uplifts_list: List[float],
    repeats: int,
    alpha: float,
    power_target: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Create metadata dictionary for sensitivity analysis run.

    Args:
        users_list: List of users per day tested
        uplifts_list: List of uplifts tested
        repeats: Number of repeats per grid point
        alpha: Significance level
        power_target: Optional target statistical power (e.g., 0.80 for 80%)

    Returns:
        Dictionary with run metadata
    """
    metadata = {
        "generated_at_utc": datetime.utcnow().isoformat() + "Z",
        "alpha": alpha,
        "grid_specification": {
            "users_per_day": sorted(users_list),
            "uplifts": sorted(uplifts_list),
            "grid_size": len(users_list) * len(uplifts_list),
        },
        "repeats": repeats,
        "total_simulations": len(users_list) * len(uplifts_list) * repeats,
    }

    # Add power target if specified
    if power_target is not None:
        metadata["power_target"] = power_target

    # Add git commit hash if available
    git_hash = get_git_commit_hash()
    if git_hash:
        metadata["git_commit"] = git_hash
    else:
        metadata["git_commit"] = None

    return metadata


def run_simulation(
    date: str,
    days: int,
    users: int,
    uplift: float,
    seed: int,
    output_dir: Path,
) -> bool:
    """
    Run data simulation for given parameters.

    Args:
        date: Start date in ISO format
        days: Number of days to simulate
        users: Users per day
        uplift: Treatment uplift
        seed: Random seed
        output_dir: Output directory for data

    Returns:
        True if successful, False otherwise
    """
    try:
        cmd = [
            "python",
            "src/data/simulate.py",
            "--start",
            date,
            "--days",
            str(days),
            "--users",
            str(users),
            "--uplift",
            str(uplift),
            "--seed",
            str(seed),
            "--output",
            str(output_dir),
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
            check=True,
        )
        return True

    except subprocess.TimeoutExpired:
        logger.error(f"Simulation timed out for users={users}, uplift={uplift}")
        return False
    except subprocess.CalledProcessError as e:
        logger.error(
            f"Simulation failed for users={users}, uplift={uplift}: {e.stderr}"
        )
        return False
    except Exception as e:
        logger.error(f"Unexpected error in simulation: {e}")
        return False


def build_warehouse(data_dir: Path, db_path: Path) -> bool:
    """
    Build DuckDB warehouse from parquet files.

    Args:
        data_dir: Directory containing raw parquet files
        db_path: Path to DuckDB database file

    Returns:
        True if successful, False otherwise
    """
    try:
        import duckdb

        # Create database and register views
        conn = duckdb.connect(str(db_path))

        # Create events schema
        conn.execute("CREATE SCHEMA IF NOT EXISTS events")

        # Register event views pointing to temp data directory
        event_types = [
            "add_to_cart",
            "begin_checkout",
            "checkout_step_view",
            "form_error",
            "payment_attempt",
            "order_completed",
        ]

        for event_type in event_types:
            event_path = data_dir / event_type / "date=*" / "part-*.parquet"
            conn.execute(
                f"""
                CREATE OR REPLACE VIEW events.{event_type} AS
                SELECT * FROM read_parquet(
                    '{event_path}',
                    hive_partitioning = true,
                    union_by_name = true
                )
                """
            )

        # Create marts schema
        conn.execute("CREATE SCHEMA IF NOT EXISTS marts")

        # Build marts
        marts_dir = Path("sql/marts")
        for mart_file in [
            "fct_experiments.sql",
            "fct_checkout_steps.sql",
            "fct_orders.sql",
        ]:
            mart_sql = (marts_dir / mart_file).read_text()
            # Remove ATTACH and USE statements since we're already connected
            lines = []
            for line in mart_sql.split("\n"):
                stripped = line.strip()
                if stripped.startswith("ATTACH") or stripped.startswith("USE"):
                    continue
                lines.append(line)
            mart_sql = "\n".join(lines)
            conn.execute(mart_sql)

        conn.close()
        return True

    except Exception as e:
        logger.error(f"Failed to build warehouse: {e}")
        return False


def run_ccr_test(db_path: Path, date: str, alpha: float = 0.05) -> Tuple[bool, float]:
    """
    Run CCR test and return detection status and p-value.

    Args:
        db_path: Path to DuckDB database
        date: Date to analyze
        alpha: Significance level

    Returns:
        Tuple of (detected, p_value)
    """
    try:
        import duckdb

        conn = duckdb.connect(str(db_path))

        # Query variant counts
        result = conn.execute(
            f"""
            WITH adders AS (
                SELECT
                    variant,
                    COUNT(DISTINCT user_id) as adders
                FROM marts.fct_experiments
                WHERE DATE(first_exposed_at) = '{date}'
                GROUP BY variant
            ),
            orders AS (
                SELECT
                    variant,
                    COUNT(DISTINCT user_id) as orderers
                FROM marts.fct_orders
                WHERE DATE(ordered_at) = '{date}'
                GROUP BY variant
            )
            SELECT
                a.variant,
                a.adders,
                COALESCE(o.orderers, 0) as orderers
            FROM adders a
            LEFT JOIN orders o ON a.variant = o.variant
            ORDER BY a.variant
        """
        ).fetchall()

        conn.close()

        if len(result) < 2:
            logger.warning(f"Expected 2 variants, got {len(result)}")
            return False, 1.0

        # Extract control and treatment data
        control_data = [r for r in result if r[0] == "control"][0]
        treatment_data = [r for r in result if r[0] == "treatment"][0]

        control_adders = control_data[1]
        control_orders = control_data[2]
        treatment_adders = treatment_data[1]
        treatment_orders = treatment_data[2]

        # Run statistical test
        test_result = two_proportion_test(
            successes_a=control_orders,
            total_a=control_adders,
            successes_b=treatment_orders,
            total_b=treatment_adders,
            alpha=alpha,
        )

        p_value = test_result["p_value"]
        detected = p_value < alpha

        return detected, p_value

    except Exception as e:
        logger.error(f"CCR test failed: {e}")
        return False, 1.0


def run_sensitivity_grid(
    start_date: str,
    days: int,
    users_list: List[int],
    uplifts_list: List[float],
    repeats: int,
    seed: int,
    alpha: float = 0.05,
) -> List[dict]:
    """
    Run sensitivity analysis over parameter grid.

    Args:
        start_date: Base start date
        days: Days per simulation
        users_list: List of users per day to test
        uplifts_list: List of uplifts to test
        repeats: Number of repeats per grid point
        seed: Base random seed
        alpha: Significance level

    Returns:
        List of result dictionaries
    """
    results = []
    base_date = datetime.fromisoformat(start_date)

    # Create temporary directory for simulations
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        grid_points = [(u, upl) for u in users_list for upl in uplifts_list]
        total_runs = len(grid_points) * repeats

        logger.info(f"Starting sensitivity analysis:")
        logger.info(f"  Grid points: {len(grid_points)}")
        logger.info(f"  Repeats per point: {repeats}")
        logger.info(f"  Total runs: {total_runs}")
        logger.info(f"  Alpha: {alpha}")

        run_count = 0

        for users, uplift in grid_points:
            logger.info(
                f"\nGrid point: users={users}, uplift={uplift:.3f} ({repeats} repeats)"
            )

            detections = 0

            for rep in range(repeats):
                run_count += 1

                # Use unique date offset for each repeat
                date_offset = run_count
                sim_date = base_date + timedelta(days=date_offset)
                sim_date_str = sim_date.strftime("%Y-%m-%d")

                # Create unique directories for this run
                data_dir = temp_path / f"data_{run_count}"
                data_dir.mkdir(parents=True, exist_ok=True)

                db_path = temp_path / f"warehouse_{run_count}.duckdb"

                # Unique seed for this run
                run_seed = seed + run_count

                # Run simulation
                success = run_simulation(
                    sim_date_str, days, users, uplift, run_seed, data_dir
                )

                if not success:
                    logger.warning(f"  Repeat {rep + 1}/{repeats}: simulation failed")
                    continue

                # Build warehouse
                success = build_warehouse(data_dir, db_path)

                if not success:
                    logger.warning(
                        f"  Repeat {rep + 1}/{repeats}: warehouse build failed"
                    )
                    continue

                # Run CCR test
                detected, p_value = run_ccr_test(db_path, sim_date_str, alpha)

                if detected:
                    detections += 1

                logger.debug(
                    f"  Repeat {rep + 1}/{repeats}: p={p_value:.4f}, detected={detected}"
                )

            # Calculate detection rate
            detection_rate = detections / repeats if repeats > 0 else 0.0

            result = {
                "users_per_day": users,
                "uplift": uplift,
                "repeats": repeats,
                "detections": detections,
                "detection_rate": detection_rate,
                "alpha": alpha,
            }

            results.append(result)

            logger.info(
                f"  Result: {detections}/{repeats} detections "
                f"(rate={detection_rate:.1%})"
            )

    return results


def write_results(results: List[dict], output_path: Path) -> None:
    """Write results to CSV file."""
    if not results:
        logger.warning("No results to write")
        return

    output_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "users_per_day",
        "uplift",
        "repeats",
        "detections",
        "detection_rate",
        "alpha",
    ]

    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    logger.info(f"\nResults written to: {output_path.resolve()}")


def print_summary(results: List[dict]) -> None:
    """Print summary of results."""
    if not results:
        logger.warning("No results to summarize")
        return

    print("\n" + "=" * 80)
    print("SENSITIVITY ANALYSIS SUMMARY")
    print("=" * 80)
    print(
        f"{'Users/Day':<12} {'Uplift':<10} {'Repeats':<10} "
        f"{'Detections':<12} {'Rate':<10}"
    )
    print("-" * 80)

    for r in results:
        print(
            f"{r['users_per_day']:<12} {r['uplift']:<10.3f} {r['repeats']:<10} "
            f"{r['detections']:<12} {r['detection_rate']:<10.1%}"
        )

    print("=" * 80)
    print()


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Run sensitivity analysis for A/B test power",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--preset",
        type=str,
        help="Preset name from configs/sensitivity_presets.yml (e.g., 'quick_smoke', 'full_demo')",
    )
    parser.add_argument(
        "--start",
        type=str,
        help="Start date in ISO format (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--days",
        type=int,
        help="Number of days per simulation",
    )
    parser.add_argument(
        "--users",
        type=parse_comma_separated_ints,
        help='Comma-separated list of users per day, e.g., "10000,20000"',
    )
    parser.add_argument(
        "--uplifts",
        type=parse_comma_separated_floats,
        help='Comma-separated list of uplifts, e.g., "0.0,0.02"',
    )
    parser.add_argument(
        "--repeats",
        type=int,
        help="Number of repeats per grid point",
    )
    parser.add_argument(
        "--seed",
        type=int,
        help="Base random seed",
    )
    parser.add_argument(
        "--alpha",
        type=float,
        help="Significance level",
    )
    parser.add_argument(
        "--power-target",
        type=float,
        help="Target statistical power (e.g., 0.80 for 80%%)",
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Output CSV path",
    )

    args = parser.parse_args()

    # Load preset if specified
    preset_config = {}
    if args.preset:
        try:
            preset_config = load_preset(args.preset)
            logger.info(f"Using preset: {args.preset}")
            if "description" in preset_config:
                logger.info(f"  Description: {preset_config['description']}")
        except Exception as e:
            logger.error(f"Failed to load preset '{args.preset}': {e}")
            return 1

    # Apply preset defaults, allow CLI args to override
    start_date = args.start if args.start is not None else None
    days = args.days if args.days is not None else preset_config.get("days", 1)
    users_list = (
        args.users if args.users is not None else preset_config.get("users_per_day")
    )
    uplifts_list = (
        args.uplifts if args.uplifts is not None else preset_config.get("uplifts")
    )
    repeats = (
        args.repeats if args.repeats is not None else preset_config.get("repeats", 10)
    )
    seed = args.seed if args.seed is not None else preset_config.get("seed", 7)
    alpha = args.alpha if args.alpha is not None else preset_config.get("alpha", 0.05)
    power_target = (
        args.power_target
        if args.power_target is not None
        else preset_config.get("power_target")
    )
    output = (
        args.output
        if args.output is not None
        else "reports/results/sensitivity_summary.csv"
    )

    # Validate required parameters
    if start_date is None:
        logger.error("--start is required (either directly or via preset)")
        return 1

    # Validate inputs
    if repeats < 1:
        logger.error("Repeats must be at least 1")
        return 1

    if not users_list:
        logger.error("Users list cannot be empty (specify --users or use a preset)")
        return 1

    if not uplifts_list:
        logger.error("Uplifts list cannot be empty (specify --uplifts or use a preset)")
        return 1

    try:
        # Run sensitivity analysis
        results = run_sensitivity_grid(
            start_date=start_date,
            days=days,
            users_list=users_list,
            uplifts_list=uplifts_list,
            repeats=repeats,
            seed=seed,
            alpha=alpha,
        )

        if not results:
            logger.error("No results generated - all simulations failed")
            return 1

        # Write results
        output_path = Path(output)
        write_results(results, output_path)

        # Write metadata
        metadata = create_metadata(
            users_list=users_list,
            uplifts_list=uplifts_list,
            repeats=repeats,
            alpha=alpha,
            power_target=power_target,
        )
        metadata_path = output_path.parent / "sensitivity_meta.json"
        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=2)
        logger.info(f"Metadata written to: {metadata_path.resolve()}")

        # Print summary
        print_summary(results)

        return 0

    except KeyboardInterrupt:
        logger.info("\nInterrupted by user")
        return 130
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
