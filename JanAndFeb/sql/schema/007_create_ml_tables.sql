-- ML forecasting tables.
--
-- Three tables support the forecasting module:
--   1. forecasts       - predicted VWAP per (symbol, forecast_for, model, version)
--   2. anomaly_scores  - per-window anomaly signals from any detector
--   3. model_registry  - lineage of every trained model (params + metrics + artifact URI)
--
-- The forecasts and anomaly_scores tables are TimescaleDB hypertables because
-- they grow unbounded. The model_registry is a plain table (low volume).

-- ---------------------------------------------------------------------------
-- forecasts: predicted values per model per target timestamp
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS forecasts (
    symbol           TEXT          NOT NULL,
    forecast_for     TIMESTAMPTZ   NOT NULL,
    generated_at     TIMESTAMPTZ   NOT NULL,
    horizon_minutes  INTEGER       NOT NULL,
    yhat             NUMERIC(18,8) NOT NULL,
    yhat_lower       NUMERIC(18,8),
    yhat_upper       NUMERIC(18,8),
    model_name       TEXT          NOT NULL,
    model_version    TEXT          NOT NULL,
    feature_hash     TEXT          NOT NULL,
    PRIMARY KEY (symbol, forecast_for, model_name, model_version)
);

SELECT create_hypertable('forecasts', 'forecast_for', if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS idx_forecasts_symbol_generated
    ON forecasts (symbol, generated_at DESC);

CREATE INDEX IF NOT EXISTS idx_forecasts_model_version
    ON forecasts (model_name, model_version);

-- ---------------------------------------------------------------------------
-- anomaly_scores: one row per (symbol, window, detector)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS anomaly_scores (
    symbol        TEXT              NOT NULL,
    window_start  TIMESTAMPTZ       NOT NULL,
    score         DOUBLE PRECISION  NOT NULL,
    is_anomaly    BOOLEAN           NOT NULL,
    detector_name TEXT              NOT NULL,
    PRIMARY KEY (symbol, window_start, detector_name)
);

SELECT create_hypertable('anomaly_scores', 'window_start', if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS idx_anomaly_scores_symbol
    ON anomaly_scores (symbol, window_start DESC);

-- ---------------------------------------------------------------------------
-- model_registry: lineage for every trained model
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS model_registry (
    model_name    TEXT         NOT NULL,
    model_version TEXT         NOT NULL,
    trained_at    TIMESTAMPTZ  NOT NULL,
    metrics       JSONB        NOT NULL,
    params        JSONB        NOT NULL,
    artifact_uri  TEXT         NOT NULL,
    PRIMARY KEY (model_name, model_version)
);

CREATE INDEX IF NOT EXISTS idx_registry_name_trained
    ON model_registry (model_name, trained_at DESC);
