#!/usr/bin/env python3
"""
Synthetic Checkout Funnel Event Generator

Generates realistic checkout funnel events that match the tracking plan schema,
with A/B test variants and treatment uplift effects. Writes partitioned Parquet files.
"""

import argparse
import hashlib
import logging
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple
from uuid import uuid4

import pyarrow as pa
import pyarrow.parquet as pq

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# Schema validation: Valid enum values from tracking plan
VALID_VARIANTS = {"control", "treatment"}
VALID_STEP_NAMES = {"address", "shipping", "payment", "review"}
VALID_PAYMENT_METHODS = {"card", "paypal"}
VALID_ERROR_CODES = {"invalid", "declined", "timeout"}

# Funnel configuration
CHECKOUT_STEPS = [("address", 0), ("shipping", 1), ("payment", 2), ("review", 3)]

# Field names for form errors per step
STEP_FIELDS = {
    "address": ["street", "city", "state", "zip", "country"],
    "shipping": ["method", "instructions"],
    "payment": ["card_number", "cvv", "expiry", "billing_zip"],
    "review": ["terms_acceptance", "newsletter_opt_in"],
}


def assign_variant(user_id: str, salt: str = "experiment_v1") -> str:
    """
    Assigns a user to a variant deterministically using hash-based assignment.

    Args:
        user_id: Unique user identifier
        salt: Salt string for hash consistency

    Returns:
        Variant name: 'control' or 'treatment'
    """
    hash_input = f"{user_id}:{salt}".encode("utf-8")
    hash_value = int(hashlib.md5(hash_input).hexdigest(), 16)
    return "treatment" if hash_value % 2 == 0 else "control"


def validate_enum(value: str, valid_values: set, field_name: str) -> None:
    """
    Validates that a value is in the allowed enum set.

    Args:
        value: Value to validate
        valid_values: Set of valid enum values
        field_name: Name of the field for error messages

    Raises:
        ValueError: If value is not in valid_values
    """
    if value not in valid_values:
        raise ValueError(
            f"Invalid {field_name}: '{value}'. Must be one of {valid_values}"
        )


def generate_timestamp(base_date: datetime, hour_offset: float) -> str:
    """
    Generates an ISO 8601 timestamp.

    Args:
        base_date: Base date for the event
        hour_offset: Hours to add to base date

    Returns:
        ISO 8601 formatted timestamp string
    """
    ts = base_date + timedelta(hours=hour_offset)
    return ts.isoformat() + "Z"


def simulate_user_funnel(
    user_id: str,
    session_id: str,
    variant: str,
    base_date: datetime,
    uplift: float,
    rng: random.Random,
) -> Tuple[List[Dict], List[Dict], List[Dict], List[Dict], List[Dict], List[Dict]]:
    """
    Simulates a complete checkout funnel for a single user.

    Args:
        user_id: User identifier
        session_id: Session identifier
        variant: Experiment variant (control or treatment)
        base_date: Base date for events
        uplift: Treatment uplift factor for conversion rates
        rng: Random number generator

    Returns:
        Tuple of event lists: (add_to_cart, begin_checkout, checkout_step_view,
                               form_error, payment_attempt, order_completed)
    """
    validate_enum(variant, VALID_VARIANTS, "variant")

    # Apply uplift multiplier for treatment
    uplift_multiplier = (1.0 + uplift) if variant == "treatment" else 1.0

    # For A/A tests (uplift=0), treatment should behave identically to control
    # error_multiplier reduces errors for treatment when uplift > 0
    error_multiplier = (1.0 - uplift * 0.4) if variant == "treatment" else 1.0
    # abandon_multiplier reduces abandonment for treatment when uplift > 0
    abandon_multiplier = (1.0 - uplift * 0.3) if variant == "treatment" else 1.0

    # Event storage
    add_to_cart_events = []
    begin_checkout_events = []
    checkout_step_view_events = []
    form_error_events = []
    payment_attempt_events = []
    order_completed_events = []

    # Random hour within the day for user activity
    hour_offset = rng.uniform(0, 24)

    # Step 1: add_to_cart event
    cart_value = round(rng.uniform(20.0, 500.0), 2)
    items_count = rng.randint(1, 10)

    add_to_cart_events.append(
        {
            "user_id": user_id,
            "session_id": session_id,
            "timestamp": generate_timestamp(base_date, hour_offset),
            "cart_value": cart_value,
            "items_count": items_count,
            "variant": variant,
        }
    )

    # Step 2: Decide if user begins checkout (baseline ~65-70%)
    cart_to_checkout_rate = 0.67 * uplift_multiplier
    if rng.random() > cart_to_checkout_rate:
        return (
            add_to_cart_events,
            begin_checkout_events,
            checkout_step_view_events,
            form_error_events,
            payment_attempt_events,
            order_completed_events,
        )

    checkout_id = str(uuid4())
    hour_offset += rng.uniform(0.01, 0.1)  # Small time increment

    begin_checkout_events.append(
        {
            "user_id": user_id,
            "checkout_id": checkout_id,
            "timestamp": generate_timestamp(base_date, hour_offset),
            "variant": variant,
        }
    )

    # Step 3: Progress through checkout steps
    for step_name, step_index in CHECKOUT_STEPS:
        validate_enum(step_name, VALID_STEP_NAMES, "step_name")

        hour_offset += rng.uniform(0.005, 0.02)  # Small time between steps
        latency_ms = rng.randint(200, 2000)

        checkout_step_view_events.append(
            {
                "checkout_id": checkout_id,
                "step_name": step_name,
                "step_index": step_index,
                "timestamp": generate_timestamp(base_date, hour_offset),
                "variant": variant,
                "latency_ms": latency_ms,
            }
        )

        # Randomly generate form errors (5-15% chance per step, lower for treatment)
        error_rate = 0.10 * error_multiplier
        if rng.random() < error_rate:
            error_code = rng.choice(list(VALID_ERROR_CODES))
            validate_enum(error_code, VALID_ERROR_CODES, "error_code")

            field_name = rng.choice(STEP_FIELDS.get(step_name, ["unknown_field"]))
            hour_offset += rng.uniform(0.001, 0.005)

            form_error_events.append(
                {
                    "checkout_id": checkout_id,
                    "step_name": step_name,
                    "field_name": field_name,
                    "error_code": error_code,
                    "timestamp": generate_timestamp(base_date, hour_offset),
                    "variant": variant,
                }
            )

        # Step abandonment rates (decreasing as user progresses)
        abandonment_rates = {
            "address": 0.20,
            "shipping": 0.15,
            "payment": 0.10,
            "review": 0.05,
        }

        abandon_rate = abandonment_rates[step_name] * abandon_multiplier
        if rng.random() < abandon_rate:
            # User abandons at this step
            return (
                add_to_cart_events,
                begin_checkout_events,
                checkout_step_view_events,
                form_error_events,
                payment_attempt_events,
                order_completed_events,
            )

    # Step 4: Payment attempt
    hour_offset += rng.uniform(0.01, 0.03)
    payment_method = rng.choice(list(VALID_PAYMENT_METHODS))
    validate_enum(payment_method, VALID_PAYMENT_METHODS, "payment_method")

    # Payment authorization rate (higher for treatment)
    auth_rate = 0.92 * uplift_multiplier
    authorized = rng.random() < auth_rate

    payment_attempt_events.append(
        {
            "checkout_id": checkout_id,
            "payment_method": payment_method,
            "authorized": authorized,
            "timestamp": generate_timestamp(base_date, hour_offset),
            "variant": variant,
        }
    )

    # Step 5: Order completed (only if payment authorized)
    if authorized:
        order_id = f"ORD-{uuid4().hex[:12].upper()}"
        hour_offset += rng.uniform(0.001, 0.01)

        order_completed_events.append(
            {
                "order_id": order_id,
                "checkout_id": checkout_id,
                "user_id": user_id,
                "timestamp": generate_timestamp(base_date, hour_offset),
                "order_value": cart_value,
                "currency": "USD",
                "variant": variant,
            }
        )

    return (
        add_to_cart_events,
        begin_checkout_events,
        checkout_step_view_events,
        form_error_events,
        payment_attempt_events,
        order_completed_events,
    )


def write_parquet_partition(
    data: List[Dict], event_name: str, date_str: str, base_path: Path
) -> None:
    """
    Writes event data to a partitioned Parquet file.

    Args:
        data: List of event dictionaries
        event_name: Name of the event type
        date_str: Date string in YYYY-MM-DD format
        base_path: Base path for data files
    """
    if not data:
        return

    # Create partition directory
    partition_dir = base_path / event_name / f"date={date_str}"
    partition_dir.mkdir(parents=True, exist_ok=True)

    # Convert to PyArrow table with explicit schema
    table = pa.Table.from_pylist(data)

    # Write Parquet file
    output_file = partition_dir / "part-0001.parquet"
    pq.write_table(table, output_file, compression="snappy")

    logger.debug(f"Wrote {len(data)} rows to {output_file}")


def simulate_day(
    date: datetime, num_users: int, uplift: float, base_path: Path, rng: random.Random
) -> Dict[str, int]:
    """
    Simulates checkout funnel events for a single day.

    Args:
        date: Date to simulate
        num_users: Number of users to simulate
        uplift: Treatment uplift factor
        base_path: Base path for output files
        rng: Random number generator

    Returns:
        Dictionary with event counts by event type
    """
    date_str = date.strftime("%Y-%m-%d")
    logger.info(f"Simulating {num_users} users for {date_str}")

    # Aggregate events for the day
    all_events = {
        "add_to_cart": [],
        "begin_checkout": [],
        "checkout_step_view": [],
        "form_error": [],
        "payment_attempt": [],
        "order_completed": [],
    }

    variant_counts = {"control": 0, "treatment": 0}

    # Process users in batches to manage memory
    batch_size = 1000
    for batch_start in range(0, num_users, batch_size):
        batch_end = min(batch_start + batch_size, num_users)

        for i in range(batch_start, batch_end):
            user_id = f"user_{date_str}_{i:06d}"
            session_id = str(uuid4())
            variant = assign_variant(user_id)
            variant_counts[variant] += 1

            # Simulate funnel for this user
            events = simulate_user_funnel(
                user_id, session_id, variant, date, uplift, rng
            )

            # Unpack and collect events
            (add_cart, begin_check, step_view, form_err, pay_attempt, order_comp) = (
                events
            )
            all_events["add_to_cart"].extend(add_cart)
            all_events["begin_checkout"].extend(begin_check)
            all_events["checkout_step_view"].extend(step_view)
            all_events["form_error"].extend(form_err)
            all_events["payment_attempt"].extend(pay_attempt)
            all_events["order_completed"].extend(order_comp)

    # Write Parquet files for each event type
    for event_name, events in all_events.items():
        write_parquet_partition(events, event_name, date_str, base_path)

    # Log summary
    event_counts = {k: len(v) for k, v in all_events.items()}
    logger.info(f"Day {date_str} summary:")
    logger.info(
        f"  Variants: control={variant_counts['control']}, "
        f"treatment={variant_counts['treatment']} "
        f"({variant_counts['treatment'] / num_users * 100:.1f}% treatment)"
    )
    for event_name, count in event_counts.items():
        logger.info(f"  {event_name}: {count} events")

    return event_counts


def main() -> int:
    """
    Main entry point for the simulation script.

    Returns:
        Exit code: 0 for success, non-zero for errors
    """
    parser = argparse.ArgumentParser(
        description="Generate synthetic checkout funnel events",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--start", type=str, required=True, help="Start date in ISO format (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--days", type=int, default=1, help="Number of days to simulate (default: 1)"
    )
    parser.add_argument(
        "--users",
        type=int,
        default=1000,
        help="Number of users per day (default: 1000)",
    )
    parser.add_argument(
        "--uplift",
        type=float,
        default=0.02,
        help="Treatment uplift factor (default: 0.02 for 2%% improvement)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducibility (default: 42)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="data/raw",
        help="Output directory for Parquet files (default: data/raw)",
    )
    parser.add_argument(
        "--aa",
        action="store_true",
        help="Run A/A test (forces uplift to 0.0 for both variants)",
    )

    args = parser.parse_args()

    try:
        # Check for A/A test mode
        if args.aa:
            logger.info("=" * 60)
            logger.info("A/A TEST MODE: Forcing uplift to 0.0")
            logger.info("Both variants will have identical behavior")
            logger.info("=" * 60)
            args.uplift = 0.0

        # Parse start date
        start_date = datetime.fromisoformat(args.start)
        logger.info(f"Starting simulation from {start_date.date()}")
        logger.info(
            f"Parameters: days={args.days}, users/day={args.users}, "
            f"uplift={args.uplift:.2%}, seed={args.seed}"
        )

        # Initialize random number generator
        rng = random.Random(args.seed)

        # Set up output path
        base_path = Path(args.output)
        base_path.mkdir(parents=True, exist_ok=True)

        # Simulate each day
        total_counts = {}
        for day_offset in range(args.days):
            current_date = start_date + timedelta(days=day_offset)

            try:
                day_counts = simulate_day(
                    current_date, args.users, args.uplift, base_path, rng
                )

                # Aggregate totals
                for event_name, count in day_counts.items():
                    total_counts[event_name] = total_counts.get(event_name, 0) + count

            except ValueError as e:
                logger.error(f"Schema validation error: {e}")
                return 1
            except Exception as e:
                logger.error(f"Error simulating day {current_date.date()}: {e}")
                return 1

        # Final summary
        logger.info("=" * 60)
        logger.info("Simulation complete!")
        logger.info(f"Total events generated:")
        for event_name, count in sorted(total_counts.items()):
            logger.info(f"  {event_name}: {count:,}")

        # Validation check: at least 60% conversion from add_to_cart to begin_checkout
        if total_counts.get("add_to_cart", 0) > 0:
            conversion_rate = (
                total_counts.get("begin_checkout", 0) / total_counts["add_to_cart"]
            )
            logger.info(f"Cart-to-checkout rate: {conversion_rate:.1%}")

            if conversion_rate < 0.60:
                logger.warning("Cart-to-checkout rate is below 60%")

        logger.info(f"Output written to: {base_path.absolute()}")
        return 0

    except ValueError as e:
        logger.error(f"Invalid input: {e}")
        return 1
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
