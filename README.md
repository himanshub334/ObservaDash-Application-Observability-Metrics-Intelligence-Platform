# ObservaDash — Application Observability & Metrics Intelligence Platform

A runnable starter implementation of a small observability stack: Go sidecar collector, FastAPI ingestion/aggregation API, PostgreSQL/TimescaleDB storage, Redis cache, React/TypeScript dashboard, Docker Compose, and GitHub Actions CI.

## Features included
- Go collector scrapes an optional application `/metrics` endpoint and collects basic Linux `/proc` CPU/memory signals; sends batches to the API.
- FastAPI endpoints for ingesting metrics, querying recent series, listing alerts, and health checks.
- PostgreSQL schema using a TimescaleDB hypertable when the TimescaleDB extension is available; standard PostgreSQL fallback is documented.
- Rolling z-score anomaly detection for numeric samples and threshold alerts for p99 latency > 500 ms or error rate > 2% (when those metric names are sent).
- Redis cache for recent metric query responses.
- React/TypeScript dashboard with latency summaries, metric series, and alert history.
- Docker Compose and CI workflows for Python tests, Go tests, and frontend build.

## Quick start
Requirements: Docker Desktop with Compose.

```bash
docker compose up --build
```

Open:
- Dashboard: http://localhost:5173
- API docs: http://localhost:8000/docs
- API health: http://localhost:8000/health

The collector sends host metrics when running on Linux. Docker Desktop on Windows/macOS may not expose host `/proc` in the same way; use the optional scrape target for app metrics or run the collector on a Linux host.

## Local development

Python service:
```bash
cd service
python -m venv .venv
# Windows: .venv\Scripts\activate ; macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Go collector:
```bash
cd collector
go test ./...
go run .
```

Frontend:
```bash
cd frontend
npm install
npm run dev
```

## Configuration
See `.env.example`. Never commit credentials. CloudWatch publishing is optional and only runs when `AWS_CLOUDWATCH_ENABLED=true` and AWS credentials/region are configured. It has not been tested against a real AWS account.

## Metric payload
The API accepts a pragmatic OTLP-inspired envelope:
```json
{
  "resource": {"service.name": "checkout"},
  "scope": {"name": "observadash.collector"},
  "metrics": [
    {"name": "http.server.duration.p99_ms", "value": 420.0, "unit": "ms", "timestamp": "2025-01-01T00:00:00Z", "attributes": {"route": "/checkout"}}
  ]
}
```
This is **not a complete OTLP protobuf/HTTP implementation**. It is an OTLP-inspired JSON format intended for the demo; use the official OpenTelemetry SDK/exporter and OTLP receiver for production interoperability.

## Important limitations
- Demo-quality starter, not production-ready or security-hardened.
- No authentication/authorization, TLS termination, tenant isolation, retention policy, or rate limiting is configured.
- The dashboard has a useful empty state; it does not fabricate production measurements.
- CloudWatch alarm creation is not implemented; the optional publisher emits metric data points only. Configure actual alarms in AWS separately.
- A Confluence ADR cannot be created from this repository; a sample ADR is in `docs/adr-observability.md`.
- No performance benchmark or specific coverage percentage is claimed. CI runs the tests that are present.

### Alerting and CloudWatch notes
The API evaluates threshold alerts and a simple z-score rule against up to 300 previous samples from a five-minute window (minimum 10 prior samples, population standard deviation, threshold |z| >= 3). This is a starter heuristic, not a statistically validated production detector. If enabled, the optional CloudWatch publisher sends metric data points; it does **not** create CloudWatch alarm resources. Alarm thresholds/composite conditions and minimum-request-count guards must be configured separately in AWS.
# ObservaDash-Application-Observability-Metrics-Intelligence-Platform
