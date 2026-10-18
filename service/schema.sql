CREATE TABLE IF NOT EXISTS metric_sample (
  id BIGSERIAL NOT NULL,
  observed_at TIMESTAMPTZ NOT NULL,
  service_name TEXT NOT NULL,
  metric_name TEXT NOT NULL,
  metric_value DOUBLE PRECISION NOT NULL,
  unit TEXT,
  attributes JSONB NOT NULL DEFAULT '{}'::jsonb,
  PRIMARY KEY (observed_at, id)
);
CREATE INDEX IF NOT EXISTS idx_metric_sample_service_metric_time ON metric_sample(service_name, metric_name, observed_at DESC);
CREATE TABLE IF NOT EXISTS alert_event (
  id BIGSERIAL PRIMARY KEY,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  service_name TEXT NOT NULL,
  metric_name TEXT NOT NULL,
  severity TEXT NOT NULL,
  message TEXT NOT NULL,
  observed_value DOUBLE PRECISION NOT NULL,
  resolved BOOLEAN NOT NULL DEFAULT FALSE
);
CREATE INDEX IF NOT EXISTS idx_alert_event_created ON alert_event(created_at DESC);
DO $$ BEGIN
  CREATE EXTENSION IF NOT EXISTS timescaledb;
  PERFORM create_hypertable('metric_sample', 'observed_at', if_not_exists => TRUE);
EXCEPTION WHEN OTHERS THEN
  RAISE NOTICE 'TimescaleDB hypertable setup skipped: %', SQLERRM;
END $$;
