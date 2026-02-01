-- Migration: Add LMP (Location Marginal Pricing) columns to trade_aggregates
--
-- LMP = Energy + Congestion + Loss
-- This is the standard pricing mechanism in US energy markets (PJM, NYISO, etc.)
-- For European markets, this provides additional pricing transparency.

-- Add LMP columns (nullable for backward compatibility)
ALTER TABLE trade_aggregates
ADD COLUMN IF NOT EXISTS lmp NUMERIC(18, 8),
ADD COLUMN IF NOT EXISTS lmp_energy NUMERIC(18, 8),
ADD COLUMN IF NOT EXISTS lmp_congestion NUMERIC(18, 8),
ADD COLUMN IF NOT EXISTS lmp_loss NUMERIC(18, 8);

-- Add comments for documentation
COMMENT ON COLUMN trade_aggregates.lmp IS 'Location Marginal Price (total) = energy + congestion + loss';
COMMENT ON COLUMN trade_aggregates.lmp_energy IS 'Energy component of LMP (system marginal price)';
COMMENT ON COLUMN trade_aggregates.lmp_congestion IS 'Congestion component of LMP (transmission constraint cost)';
COMMENT ON COLUMN trade_aggregates.lmp_loss IS 'Loss component of LMP (electrical loss cost)';

-- Create index for LMP queries (partial index on non-null values)
CREATE INDEX IF NOT EXISTS idx_trade_aggregates_lmp
ON trade_aggregates (symbol, window_start, lmp)
WHERE lmp IS NOT NULL;

-- Create index for congestion analysis
CREATE INDEX IF NOT EXISTS idx_trade_aggregates_congestion
ON trade_aggregates (symbol, lmp_congestion DESC)
WHERE lmp_congestion IS NOT NULL AND lmp_congestion > 0;
