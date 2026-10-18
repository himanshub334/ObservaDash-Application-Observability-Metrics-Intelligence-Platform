package main

import (
  "bytes"
  "encoding/json"
  "fmt"
  "io"
  "net/http"
  "os"
  "runtime"
  "strconv"
  "strings"
  "time"
)

type Metric struct { Name string `json:"name"`; Value float64 `json:"value"`; Unit string `json:"unit,omitempty"`; Timestamp time.Time `json:"timestamp"`; Attributes map[string]string `json:"attributes,omitempty"` }
type Envelope struct { Resource map[string]string `json:"resource"`; Scope map[string]string `json:"scope"`; Metrics []Metric `json:"metrics"` }

func procMem() (float64, bool) {
  b, err := os.ReadFile("/proc/meminfo"); if err != nil { return 0, false }
  var total, available float64
  for _, line := range strings.Split(string(b), "\n") {
    fields := strings.Fields(line); if len(fields) < 2 { continue }
    n, _ := strconv.ParseFloat(fields[1], 64)
    if fields[0] == "MemTotal:" { total = n }; if fields[0] == "MemAvailable:" { available = n }
  }
  if total == 0 { return 0, false }; return (total-available)/total*100, true
}

func collect() []Metric {
  now := time.Now().UTC(); metrics := []Metric{{Name:"process.runtime.goroutines", Value:float64(runtime.NumGoroutine()), Unit:"{goroutine}", Timestamp:now}}
  if mem, ok := procMem(); ok { metrics = append(metrics, Metric{Name:"system.memory.used_percent", Value:mem, Unit:"%", Timestamp:now}) }
  target := strings.TrimSpace(os.Getenv("SCRAPE_TARGET"))
  if target != "" {
    resp, err := http.Get(target); if err == nil {
      defer resp.Body.Close(); body, _ := io.ReadAll(io.LimitReader(resp.Body, 1<<20))
      // Basic Prometheus text scrape: numeric samples only; labels are intentionally not parsed yet.
      for _, line := range strings.Split(string(body), "\n") {
        line = strings.TrimSpace(line); if line == "" || strings.HasPrefix(line, "#") { continue }
        parts := strings.Fields(line); if len(parts) < 2 { continue }
        name := strings.Split(parts[0], "{")[0]; value, e := strconv.ParseFloat(parts[1], 64); if e != nil { continue }
        metrics = append(metrics, Metric{Name:"scrape."+name, Value:value, Timestamp:now, Attributes:map[string]string{"target":target}})
      }
    }
  }
  return metrics
}

func send(client *http.Client, api string, metrics []Metric) error {
  body, err := json.Marshal(Envelope{Resource:map[string]string{"service.name":"observadash-collector", "host.name":hostname()}, Scope:map[string]string{"name":"observadash.collector", "version":"1.0.0"}, Metrics:metrics}); if err != nil { return err }
  req, err := http.NewRequest(http.MethodPost, strings.TrimRight(api, "/")+"/ingest", bytes.NewReader(body)); if err != nil { return err }; req.Header.Set("Content-Type", "application/json")
  resp, err := client.Do(req); if err != nil { return err }; defer resp.Body.Close(); if resp.StatusCode >= 300 { return fmt.Errorf("ingest returned %s", resp.Status) }; return nil
}
func hostname() string { h, err := os.Hostname(); if err != nil { return "unknown" }; return h }
func main() {
  api := os.Getenv("API_URL"); if api == "" { api = "http://localhost:8000" }
  seconds := 10; if n, err := strconv.Atoi(os.Getenv("COLLECTOR_INTERVAL_SECONDS")); err == nil && n > 0 { seconds = n }
  client := &http.Client{Timeout:5*time.Second}; ticker := time.NewTicker(time.Duration(seconds)*time.Second); defer ticker.Stop()
  for { if err := send(client, api, collect()); err != nil { fmt.Fprintln(os.Stderr, "collector send failed:", err) }; <-ticker.C }
}
