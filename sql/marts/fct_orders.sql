-- =====================================================================
-- Fact Table: Orders
-- =====================================================================
-- Purpose: Track completed orders with order value and metadata
-- Grain: One row per completed order
-- =====================================================================

-- Attach warehouse database
ATTACH IF NOT EXISTS 'duckdb/warehouse.duckdb' AS warehouse;
USE warehouse;

-- Create marts schema for analytical tables
CREATE SCHEMA IF NOT EXISTS marts;

-- Create or replace the orders fact table
CREATE OR REPLACE TABLE marts.fct_orders AS
SELECT
    order_id,
    checkout_id,
    user_id,
    order_value,
    currency,
    variant,
    -- Timestamp when order was completed
    timestamp AS ordered_at
FROM events.order_completed;

-- =====================================================================
-- Table created: marts.fct_orders
-- Tracks all successfully completed orders for revenue and conversion analysis
-- =====================================================================
