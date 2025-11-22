#!/bin/bash
# Run Performance Benchmarks and Generate Report
# Sprint 10 Sortie 4

set -e

echo "🚀 Running Performance Benchmarks..."
echo "=================================="
echo ""

# Ensure NATS is running
if ! nc -z localhost 4222 2>/dev/null; then
    echo "❌ ERROR: NATS server not running on localhost:4222"
    echo "Start NATS with: docker run -d -p 4222:4222 nats:2.10-alpine"
    exit 1
fi

echo "✅ NATS server detected"
echo ""

# Run benchmarks with JSON output
echo "📊 Executing benchmarks..."
pytest tests/performance/test_nats_overhead.py \
    -v -s \
    --json-report \
    --json-report-file=benchmark_results.json \
    --tb=short

echo ""
echo "📝 Generating report..."
python tests/performance/generate_report.py benchmark_results.json

echo ""
echo "✅ Benchmark complete!"
echo "📄 Report: tests/performance/BENCHMARK_RESULTS.md"
echo ""
echo "View results:"
echo "  cat tests/performance/BENCHMARK_RESULTS.md"
