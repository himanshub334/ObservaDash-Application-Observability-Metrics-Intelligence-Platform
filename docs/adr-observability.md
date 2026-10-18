# ADR-001: Metrics collection and transport

- Status: Accepted for this demo; revisit before production.
- Context: The platform needs to ingest service and host metrics while remaining compatible with common observability tools.
- Options considered:
  - Prometheus pull: straightforward scrape semantics, but requires reachable scrape endpoints and polling ownership.
  - OpenTelemetry push/export: vendor-neutral model and ecosystem support; requires an exporter/collector and careful batching/retry configuration.
  - CloudWatch Agent: convenient in AWS environments, but couples collection and some operational assumptions to AWS.
- Decision: Use a small Go sidecar to collect and batch samples into a central API, with an OTLP-inspired JSON envelope in this starter. Production implementation should use the official OpenTelemetry SDK/exporter and OTLP protocol rather than treating this demo envelope as OTLP compliant.
- Consequences: Central aggregation supports common storage and dashboard queries; reliability concerns such as retry queues, backpressure, authentication, cardinality controls, and retention must be addressed before production.
