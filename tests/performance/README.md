# Sprint 9 Performance Benchmarking Report

## Overview

This directory contains performance benchmarks for Sprint 9's NATS event bus architecture.

## Performance Requirements

From SPEC-Sortie-6:

| Metric | Requirement | Status |
|--------|-------------|--------|
| NATS Latency | <5ms per event | ⏳ Testing |
| CPU Overhead | <5% vs v1.x | ⏳ Testing |
| Memory Overhead | <10% increase | ⏳ Testing |
| Throughput | 100+ events/sec | ⏳ Testing |
| Stability | No leaks (1 hour) | ⏳ Testing |

## Running Benchmarks

### Prerequisites

1. Install performance testing dependencies:
```bash
pip install psutil
```

2. Start NATS server:
```bash
nats-server
```

### Run All Benchmarks

```bash
pytest tests/performance/test_nats_overhead.py -v -s
```

### Run Specific Test Categories

```bash
# Latency benchmarks
pytest tests/performance/test_nats_overhead.py::TestLatencyBenchmarks -v -s

# Throughput benchmarks
pytest tests/performance/test_nats_overhead.py::TestThroughputBenchmarks -v -s

# CPU overhead
pytest tests/performance/test_nats_overhead.py::TestCPUOverhead -v -s

# Memory overhead
pytest tests/performance/test_nats_overhead.py::TestMemoryOverhead -v -s

# Concurrent operations
pytest tests/performance/test_nats_overhead.py::TestConcurrentOperations -v -s

# Failure recovery
pytest tests/performance/test_nats_overhead.py::TestFailureRecovery -v -s
```

## Benchmark Categories

### 1. Latency Benchmarks (`TestLatencyBenchmarks`)

Measures end-to-end event latency through NATS:

- **Single Event Latency**: Publish-to-process latency for individual events
  - Metrics: Average, median, P95, P99, min, max, std dev
  - Target: <5ms average

- **Request/Reply Latency**: Round-trip time for request/reply pattern
  - Metrics: Average, min, max
  - Target: <10ms average

- **Concurrent Event Latency**: Latency with multiple simultaneous publishers
  - Metrics: Latency under concurrent load, throughput
  - Target: <10ms average with 10+ concurrent publishers

### 2. Throughput Benchmarks (`TestThroughputBenchmarks`)

Measures sustained event processing rates:

- **Sustained Throughput**: Event rate over 10 seconds
  - Metrics: Events/second, storage rate
  - Target: 100+ events/second sustained

- **Burst Throughput**: Handling of sudden event bursts
  - Metrics: Burst size, publish rate, storage rate
  - Target: 1000 events with 95%+ storage

### 3. CPU Overhead (`TestCPUOverhead`)

Compares CPU usage between NATS and direct DB writes:

- **NATS CPU Overhead**: CPU usage with event bus
  - Metrics: Baseline vs active CPU, overhead percentage
  - Target: <5% overhead

- **Direct Database CPU**: v1.x baseline measurement
  - Metrics: CPU usage for direct writes
  - Purpose: Comparison baseline

### 4. Memory Overhead (`TestMemoryOverhead`)

Tracks memory usage over time:

- **Memory Stability**: Long-running memory behavior
  - Metrics: RSS, VMS, growth rate
  - Target: <10% increase, <50 MB/hour growth
  - Duration: 60 seconds (scale to 3600 for full test)

### 5. Concurrent Operations (`TestConcurrentOperations`)

Tests multiple event types simultaneously:

- **Mixed Event Types**: Chat, media, user events together
  - Metrics: Per-type count, total throughput
  - Target: 100+ events/second mixed

### 6. Failure Recovery (`TestFailureRecovery`)

Measures resilience to service failures:

- **DatabaseService Restart**: Event handling during restart
  - Metrics: Pre/post restart events, recovery rate
  - Target: 75%+ recovery (fire-and-forget semantics)

## Interpreting Results

### Success Criteria

All benchmarks must pass their assertions:
- ✅ Average latency <5ms
- ✅ P95 latency <10ms
- ✅ CPU overhead <5%
- ✅ Memory growth <10%
- ✅ Throughput >100 events/sec
- ✅ No memory leaks detected

### Performance Degradation

If benchmarks fail:

1. **High Latency** (>5ms average):
   - Check system load: `htop`, `top`
   - Verify NATS server health: `curl http://localhost:8222/varz`
   - Check network latency: `ping localhost`

2. **High CPU Overhead** (>5%):
   - Profile DatabaseService: Add `cProfile` instrumentation
   - Check database size: `ls -lh bot/rosey/rosey.db`
   - Optimize database queries: Add indexes

3. **Memory Leaks** (>50 MB/hour):
   - Use memory profiler: `pip install memory_profiler`
   - Check for unclosed connections
   - Review event handler cleanup

4. **Low Throughput** (<100 events/sec):
   - Check NATS `max_pending` configuration
   - Verify database WAL mode: `PRAGMA journal_mode`
   - Consider batch writes in DatabaseService

## Optimization Tips

### NATS Configuration

```text
# /etc/nats/nats.conf
max_payload: 2097152        # 2MB
max_connections: 1000
max_subscriptions: 10000
max_pending: 67108864       # 64MB
```

### Python Optimization

```bash
# Install uvloop for better async performance
pip install uvloop
```

Add to bot code:
```python
import uvloop
uvloop.install()
```

### Database Optimization

```python
# Enable WAL mode for better concurrency
await db.execute("PRAGMA journal_mode=WAL")
await db.execute("PRAGMA synchronous=NORMAL")
```

## CI/CD Integration

Add to GitHub Actions workflow:

```yaml
- name: Run Performance Benchmarks
  run: |
    nats-server &
    sleep 2
    pytest tests/performance/test_nats_overhead.py -v
```

Set failure thresholds in CI environment variables:
```bash
export BENCHMARK_LATENCY_MAX=5.0
export BENCHMARK_CPU_MAX=5.0
export BENCHMARK_MEMORY_MAX=10.0
export BENCHMARK_THROUGHPUT_MIN=100
```

## Profiling Tools

For deeper analysis:

### CPU Profiling
```bash
python -m cProfile -o profile.stats bot/rosey/rosey.py config.json
python -m pstats profile.stats
```

### Memory Profiling
```bash
pip install memory_profiler
python -m memory_profiler bot/rosey/rosey.py config.json
```

### NATS Monitoring
```bash
# Connection stats
curl http://localhost:8222/connz

# Subscription stats  
curl http://localhost:8222/subsz

# Server stats
curl http://localhost:8222/varz
```

## Historical Results

Track benchmark results over time to detect regressions.

### Example Results Format

```
Sprint 9 Benchmarks - 2025-11-21
================================
Latency:      2.3ms avg (P95: 4.1ms) ✅
CPU Overhead: 2.1% ✅
Memory:       +4.3% (+12 MB) ✅
Throughput:   157 events/sec ✅
Stability:    No leaks detected ✅
```

## Troubleshooting

### NATS Server Not Running
```
ERROR: Could not connect to NATS at localhost:4222
```
**Solution**: Start NATS server: `nats-server`

### Database Lock Errors
```
sqlite3.OperationalError: database is locked
```
**Solution**: Ensure no other processes using database

### High Variance in Results
```
WARNING: High standard deviation in latency measurements
```
**Solution**: 
- Close other applications
- Run on dedicated test hardware
- Increase number of iterations

## Related Documentation

- [ARCHITECTURE.md](../../ARCHITECTURE.md) - Sprint 9 architecture
- [DEPLOYMENT.md](../../DEPLOYMENT.md) - Deployment guide
- [TESTING.md](../../TESTING.md) - General testing guide
- SPEC-Sortie-6 - Detailed benchmark specifications

## Continuous Monitoring

For production deployments, integrate with monitoring tools:

- **Prometheus**: Collect NATS metrics
- **Grafana**: Visualize performance trends
- **Alerting**: Set thresholds for latency spikes

See [DEPLOYMENT.md](../../DEPLOYMENT.md) for monitoring setup.
