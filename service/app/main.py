from __future__ import annotations
import json, os, statistics, re
from datetime import datetime, timedelta, timezone
from typing import Any
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://observadash:observadash@localhost:5432/observadash")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
app = FastAPI(title="ObservaDash API", version="1.0.0")
_cache = None

class Metric(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    value: float
    unit: str | None = None
    timestamp: datetime | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)

class Envelope(BaseModel):
    resource: dict[str, Any] = Field(default_factory=dict)
    scope: dict[str, Any] = Field(default_factory=dict)
    metrics: list[Metric] = Field(min_length=1, max_length=1000)


def connect():
    import psycopg
    from psycopg.rows import dict_row
    return psycopg.connect(DATABASE_URL, row_factory=dict_row, connect_timeout=3)


def cache_client():
    global _cache
    if _cache is None:
        try:
            import redis
            _cache = redis.Redis.from_url(REDIS_URL, decode_responses=True, socket_connect_timeout=0.5)
            _cache.ping()
        except Exception:
            _cache = False
    return _cache if _cache is not False else None


def evaluate_alert(cur, service: str, metric: Metric, value: float):
    name = metric.name.lower()
    reason = None
    if "p99" in name and ("latency" in name or "duration" in name) and value > 500:
        reason = f"p99 latency exceeds 500 ms ({value:.2f})"
    elif "error_rate" in name and value > 2:
        reason = f"error rate exceeds 2% ({value:.2f})"
    if reason:
        cur.execute("INSERT INTO alert_event(service_name, metric_name, severity, message, observed_value) VALUES (%s,%s,%s,%s,%s)", (service, metric.name, "critical", reason, value))

def publish_cloudwatch(service: str, metric: Metric, value: float):
    if os.getenv("AWS_CLOUDWATCH_ENABLED", "false").lower() != "true":
        return
    try:
        import boto3
        name = re.sub(r"[^A-Za-z0-9_ -]", "_", metric.name)[:255] or "metric"
        client = boto3.client("cloudwatch", region_name=os.getenv("AWS_REGION", "us-east-1"))
        client.put_metric_data(
            Namespace=os.getenv("CLOUDWATCH_NAMESPACE", "ObservaDash"),
            MetricData=[{"MetricName": name, "Dimensions": [{"Name": "ServiceName", "Value": service[:255]}], "Value": value, "Unit": "None", "Timestamp": metric.timestamp or datetime.now(timezone.utc)}],
        )
    except Exception:
        # Ingestion should continue even if the optional AWS integration is unavailable.
        pass


def detect_zscore_alert(cur, service: str, metric: Metric, value: float):
    # Evaluate against prior samples from the last five minutes; avoid unstable tiny windows.
    cur.execute("SELECT metric_value FROM metric_sample WHERE service_name=%s AND metric_name=%s AND observed_at >= %s ORDER BY observed_at DESC LIMIT 300", (service, metric.name, datetime.now(timezone.utc)-timedelta(minutes=5)))
    prior = [float(row["metric_value"]) for row in cur.fetchall()]
    if len(prior) < 10:
        return
    mean = statistics.mean(prior)
    stddev = statistics.pstdev(prior)
    if stddev > 0 and abs(value - mean) / stddev >= 3:
        cur.execute("INSERT INTO alert_event(service_name, metric_name, severity, message, observed_value) VALUES (%s,%s,%s,%s,%s)", (service, metric.name, "warning", f"Possible anomaly: z-score >= 3 in rolling 5-minute window (value {value:.3f}, mean {mean:.3f})", value))

@app.get("/health")
def health():
    db_ok = False
    try:
        with connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT 1")
            db_ok = True
    except Exception:
        pass
    return {"status": "ok" if db_ok else "degraded", "database": db_ok, "cache": cache_client() is not None}

@app.post("/ingest")
def ingest(payload: Envelope):
    service = str(payload.resource.get("service.name", "unknown-service"))[:200]
    inserted = 0
    try:
        with connect() as conn, conn.cursor() as cur:
            for metric in payload.metrics:
                observed = metric.timestamp or datetime.now(timezone.utc)
                detect_zscore_alert(cur, service, metric, metric.value)
                cur.execute("INSERT INTO metric_sample(observed_at, service_name, metric_name, metric_value, unit, attributes) VALUES (%s,%s,%s,%s,%s,%s)", (observed, service, metric.name, metric.value, metric.unit, json.dumps(metric.attributes)))
                evaluate_alert(cur, service, metric, metric.value)
                inserted += 1
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"metric persistence failed: {type(exc).__name__}") from exc
    for metric in payload.metrics:
        publish_cloudwatch(service, metric, metric.value)
    c = cache_client()
    if c:
        try: c.delete("metrics:summary")
        except Exception: pass
    return {"accepted": inserted, "service": service}

@app.get("/metrics")
def metrics(service: str | None = None, since_minutes: int = Query(60, ge=1, le=10080), limit: int = Query(500, ge=1, le=5000)):
    cache_key = f"metrics:{service or '*'}:{since_minutes}:{limit}"
    c = cache_client()
    if c:
        try:
            cached = c.get(cache_key)
            if cached: return json.loads(cached)
        except Exception: pass
    try:
        with connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT id, observed_at, service_name, metric_name, metric_value, unit, attributes FROM metric_sample WHERE observed_at >= %s AND (%s IS NULL OR service_name=%s) ORDER BY observed_at DESC LIMIT %s", (datetime.now(timezone.utc)-timedelta(minutes=since_minutes), service, service, limit))
            rows = cur.fetchall()
    except Exception as exc:
        raise HTTPException(status_code=503, detail="metric query failed; check database availability") from exc
    result = [{**r, "observed_at": r["observed_at"].isoformat(), "attributes": r["attributes"]} for r in rows]
    if c:
        try: c.setex(cache_key, 10, json.dumps(result, default=str))
        except Exception: pass
    return result

@app.get("/summary")
def summary():
    try:
        with connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT metric_name, percentile_cont(0.50) WITHIN GROUP (ORDER BY metric_value) AS p50, percentile_cont(0.95) WITHIN GROUP (ORDER BY metric_value) AS p95, percentile_cont(0.99) WITHIN GROUP (ORDER BY metric_value) AS p99, count(*) AS samples FROM metric_sample WHERE observed_at >= %s AND (metric_name ILIKE '%latency%' OR metric_name ILIKE '%duration%') GROUP BY metric_name ORDER BY metric_name", (datetime.now(timezone.utc)-timedelta(minutes=60),))
            latency = cur.fetchall()
            cur.execute("SELECT count(*) AS total, count(*) FILTER (WHERE resolved=false) AS active FROM alert_event WHERE created_at >= %s", (datetime.now(timezone.utc)-timedelta(hours=24),))
            alerts = cur.fetchone()
            cur.execute("SELECT count(DISTINCT service_name) AS services FROM metric_sample WHERE observed_at >= %s", (datetime.now(timezone.utc)-timedelta(hours=1),))
            services = cur.fetchone()["services"]
        return {"latency": latency, "alerts_24h": alerts["total"], "active_alerts": alerts["active"], "services": services}
    except Exception as exc:
        raise HTTPException(status_code=503, detail="summary unavailable; check database availability") from exc

@app.get("/alerts")
def alerts(limit: int = Query(100, ge=1, le=1000)):
    try:
        with connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT id, created_at, service_name, metric_name, severity, message, observed_value, resolved FROM alert_event ORDER BY created_at DESC LIMIT %s", (limit,))
            rows = cur.fetchall()
        return [{**r, "created_at": r["created_at"].isoformat()} for r in rows]
    except Exception as exc:
        raise HTTPException(status_code=503, detail="alerts unavailable; check database availability") from exc
