-- =====================================================================
-- DuckDB Schema Definition for Checkout Flow Optimization
-- =====================================================================
-- Purpose: Register external views over Parquet-partitioned event data
-- Location: data/raw/<event>/date=*/part-*.parquet
-- Database: duckdb/warehouse.duckdb
-- =====================================================================

-- Attach or create the DuckDB warehouse database
-- This creates the database file if it doesn't exist
ATTACH IF NOT EXISTS 'duckdb/warehouse.duckdb' AS warehouse;
USE warehouse;

-- Create events schema to organize all event tables
-- IF NOT EXISTS makes this idempotent
CREATE SCHEMA IF NOT EXISTS events;

-- =====================================================================
-- Event Views: Register Parquet partitions as queryable views
-- =====================================================================
-- Pattern: data/raw/<event>/date=*/part-*.parquet
-- Views are created with OR REPLACE to allow re-running this script
-- Note: Views that reference missing files will fail on query, not creation
-- To ensure smooth operation, run data simulation before querying views
-- =====================================================================

-- add_to_cart: Tracks when users add items to their shopping cart
CREATE OR REPLACE VIEW events.add_to_cart AS
SELECT * FROM read_parquet(
    'data/raw/add_to_cart/date=*/part-*.parquet',
    hive_partitioning = true,
    union_by_name = true
);

-- begin_checkout: Tracks when users initiate the checkout process
CREATE OR REPLACE VIEW events.begin_checkout AS
SELECT * FROM read_parquet(
    'data/raw/begin_checkout/date=*/part-*.parquet',
    hive_partitioning = true,
    union_by_name = true
);

-- checkout_step_view: Tracks each checkout step page view
CREATE OR REPLACE VIEW events.checkout_step_view AS
SELECT * FROM read_parquet(
    'data/raw/checkout_step_view/date=*/part-*.parquet',
    hive_partitioning = true,
    union_by_name = true
);

-- form_error: Tracks form validation errors during checkout
CREATE OR REPLACE VIEW events.form_error AS
SELECT * FROM read_parquet(
    'data/raw/form_error/date=*/part-*.parquet',
    hive_partitioning = true,
    union_by_name = true
);

-- payment_attempt: Tracks payment authorization attempts
CREATE OR REPLACE VIEW events.payment_attempt AS
SELECT * FROM read_parquet(
    'data/raw/payment_attempt/date=*/part-*.parquet',
    hive_partitioning = true,
    union_by_name = true
);

-- order_completed: Tracks successfully completed orders
CREATE OR REPLACE VIEW events.order_completed AS
SELECT * FROM read_parquet(
    'data/raw/order_completed/date=*/part-*.parquet',
    hive_partitioning = true,
    union_by_name = true
);

-- =====================================================================
-- Schema Registration Complete
-- =====================================================================
-- All views are now available in the events schema
-- Query example: SELECT * FROM events.add_to_cart WHERE date = '2025-01-01';
-- =====================================================================
