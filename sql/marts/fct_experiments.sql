-- =====================================================================
-- Fact Table: Experiments
-- =====================================================================
-- Purpose: Track user-level experiment assignments and first exposure
-- Grain: One row per user with their stable variant assignment
-- =====================================================================

-- Attach warehouse database
ATTACH IF NOT EXISTS 'duckdb/warehouse.duckdb' AS warehouse;
USE warehouse;

-- Create marts schema for analytical tables
CREATE SCHEMA IF NOT EXISTS marts;

-- Create or replace the experiments fact table
CREATE OR REPLACE TABLE marts.fct_experiments AS
SELECT
    user_id,
    -- Variant assignment is stable per user (deterministic hash-based)
    MIN(variant) AS variant,
    -- Timestamp of first exposure to experiment (first add_to_cart event)
    MIN(timestamp) AS first_exposed_at
FROM events.add_to_cart
GROUP BY user_id;

-- =====================================================================
-- Table created: marts.fct_experiments
-- Tracks user experiment assignments and exposure timing
-- =====================================================================
