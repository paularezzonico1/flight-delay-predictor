-- Migration 002: composite index on (route, carrier).
--
-- Accelerates the prediction-lookup query used by GET /predictions/recent and
-- SqlPredictionRepository.find_recent():
--
--   SELECT ... FROM predictions
--   WHERE route = $1 AND carrier = $2 AND dep_hour = $3
--   ORDER BY created_at DESC LIMIT 1;
--
-- Applied separately from migration 001 so the before/after impact can be
-- measured with EXPLAIN ANALYZE (see METRICS.md). Leading the index with
-- (route, carrier) matches the equality predicates on the hot path.

CREATE INDEX IF NOT EXISTS idx_predictions_route_carrier
    ON predictions (route, carrier);
