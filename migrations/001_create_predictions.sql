-- Migration 001: predictions table.
--
-- Logs every /predict request/response: input features, model output, the model
-- version that produced it, serving latency, whether it was a cache hit, and the
-- timestamp. The (route, carrier) lookup index is intentionally added separately
-- in migration 002 so its effect can be measured with EXPLAIN ANALYZE.

CREATE TABLE IF NOT EXISTS predictions (
    id                BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    request_id        VARCHAR(32),

    -- Request features
    carrier           VARCHAR(8)  NOT NULL,
    origin            VARCHAR(8)  NOT NULL,
    destination       VARCHAR(8)  NOT NULL,
    route             VARCHAR(16) NOT NULL,   -- denormalised "ORIGIN-DEST"
    month             SMALLINT    NOT NULL,
    day_of_week       SMALLINT    NOT NULL,
    dep_hour          SMALLINT    NOT NULL,

    -- Response
    delay_probability DOUBLE PRECISION NOT NULL,
    will_be_delayed   BOOLEAN     NOT NULL,
    risk_level        VARCHAR(16) NOT NULL,
    model_version     VARCHAR(64) NOT NULL,

    -- Serving metadata
    latency_ms        DOUBLE PRECISION NOT NULL,
    cache_hit         BOOLEAN     NOT NULL DEFAULT FALSE
);

-- Time index supports the writes/sec window query and recency ordering.
CREATE INDEX IF NOT EXISTS idx_predictions_created_at ON predictions (created_at);
