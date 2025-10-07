-- =====================================================================
-- Fact Table: Checkout Steps
-- =====================================================================
-- Purpose: Track checkout step-level metrics including latency and errors
-- Grain: One row per checkout session per step
-- =====================================================================

-- Attach warehouse database
ATTACH IF NOT EXISTS 'duckdb/warehouse.duckdb' AS warehouse;
USE warehouse;

-- Create marts schema for analytical tables
CREATE SCHEMA IF NOT EXISTS marts;

-- Create or replace the checkout steps fact table
CREATE OR REPLACE TABLE marts.fct_checkout_steps AS
SELECT
    c.checkout_id,
    c.step_name,
    c.step_index,
    c.variant,
    -- First time this step was viewed in the checkout session
    MIN(c.timestamp) AS first_seen_at,
    -- Median page load latency for this step (using approximate quantile)
    CAST(APPROX_QUANTILE(c.latency_ms, 0.5) AS INTEGER) AS median_latency_ms,
    -- Count of form errors that occurred on this step
    COUNT(e.checkout_id) AS error_events
FROM events.checkout_step_view c
-- Left join to capture errors; not all steps will have errors
LEFT JOIN events.form_error e 
    ON c.checkout_id = e.checkout_id 
    AND c.step_name = e.step_name
GROUP BY 
    c.checkout_id, 
    c.step_name, 
    c.step_index, 
    c.variant;

-- =====================================================================
-- Table created: marts.fct_checkout_steps
-- Tracks step-level checkout metrics for funnel analysis
-- =====================================================================
