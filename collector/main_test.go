package main
import "testing"
func TestCollectReturnsMetrics(t *testing.T) { got := collect(); if len(got) == 0 { t.Fatal("expected at least runtime metric") }; if got[0].Name != "process.runtime.goroutines" { t.Fatalf("unexpected first metric %q", got[0].Name) } }
