#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Performance Benchmark Runner and Report Generator
==================================================

Runs Sprint 9 NATS performance benchmarks and generates a comprehensive report.

Usage:
    python scripts/run_benchmarks.py [--quick] [--report-file REPORT.md]

Options:
    --quick         Run quick benchmarks (shorter duration)
    --report-file   Output file for report (default: BENCHMARK_RESULTS.md)
    --no-color      Disable colored output

Requirements:
    - NATS server running on localhost:4222
    - psutil package installed
"""

import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path


def check_nats_server():
    """Check if NATS server is running."""
    try:
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(('localhost', 4222))
        sock.close()
        return result == 0
    except Exception:
        return False


def install_dependencies():
    """Install required dependencies."""
    print("📦 Installing dependencies...")
    subprocess.run([
        sys.executable, "-m", "pip", "install", "psutil", "-q"
    ], check=False)


def run_benchmarks(quick=False):
    """Run performance benchmarks."""
    print("\n🔬 Running performance benchmarks...")
    print("=" * 70)

    # Build pytest command
    cmd = [
        sys.executable, "-m", "pytest",
        "tests/performance/test_nats_overhead.py",
        "-v", "-s",
        "--tb=short",
        "-m", "benchmark"
    ]

    if quick:
        print("⚡ Quick mode enabled (reduced iterations)")

    # Run benchmarks
    start_time = time.time()
    result = subprocess.run(cmd, capture_output=False, text=True)
    elapsed = time.time() - start_time

    print("=" * 70)
    print(f"\n✅ Benchmarks completed in {elapsed:.1f} seconds")

    return result.returncode == 0


def generate_report(output_file="BENCHMARK_RESULTS.md"):
    """Generate markdown report."""
    print(f"\n📊 Generating report: {output_file}")

    report = f"""# Sprint 9 Performance Benchmark Results

**Date**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  
**Branch**: nano-sprint/8-inception  
**Sprint**: 9 - The Accountant  

---

## Executive Summary

This report contains performance benchmark results for Sprint 9's NATS event bus architecture.

### Performance Requirements

| Metric | Requirement | Result | Status |
|--------|-------------|--------|--------|
| NATS Latency | <5ms average | TBD | ⏳ |
| P95 Latency | <10ms | TBD | ⏳ |
| CPU Overhead | <5% vs v1.x | TBD | ⏳ |
| Memory Overhead | <10% increase | TBD | ⏳ |
| Throughput | 100+ events/sec | TBD | ⏳ |
| Memory Stability | No leaks | TBD | ⏳ |

**Overall Status**: ⏳ **PENDING** - Review detailed results below

---

## Detailed Results

### 1. Latency Benchmarks

#### Single Event Latency
- **Average**: TBD ms
- **Median**: TBD ms
- **P95**: TBD ms
- **P99**: TBD ms
- **Status**: ⏳ PENDING

#### Request/Reply Latency
- **Average**: TBD ms
- **Status**: ⏳ PENDING

#### Concurrent Event Latency
- **Concurrent Publishers**: 10
- **Average Latency**: TBD ms
- **Throughput**: TBD events/sec
- **Status**: ⏳ PENDING

---

### 2. Throughput Benchmarks

#### Sustained Throughput (10 seconds)
- **Events Published**: TBD
- **Throughput**: TBD events/sec
- **Storage Rate**: TBD%
- **Status**: ⏳ PENDING

#### Burst Throughput
- **Burst Size**: 1000 events
- **Publish Rate**: TBD events/sec
- **Storage Rate**: TBD%
- **Status**: ⏳ PENDING

---

### 3. CPU Overhead

#### NATS Architecture (v2.x)
- **Baseline CPU**: TBD%
- **Active CPU**: TBD%
- **Overhead**: TBD%
- **Status**: ⏳ PENDING

#### Direct Database (v1.x Baseline)
- **Baseline CPU**: TBD%
- **Active CPU**: TBD%
- **Status**: ⏳ PENDING

**Comparison**: NATS overhead TBD% vs direct writes

---

### 4. Memory Overhead

#### Memory Stability Test
- **Duration**: 60 seconds
- **Initial RSS**: TBD MB
- **Final RSS**: TBD MB
- **Memory Increase**: TBD MB (TBD%)
- **Growth Rate**: TBD MB/hour
- **Status**: ⏳ PENDING

---

### 5. Concurrent Operations

#### Mixed Event Types
- **Chat Events**: TBD
- **Media Events**: TBD
- **User Events**: TBD
- **Total Throughput**: TBD events/sec
- **Status**: ⏳ PENDING

---

### 6. Failure Recovery

#### DatabaseService Restart
- **Pre-restart Events**: 50
- **Downtime Events**: 30
- **Post-restart Events**: 50
- **Recovery Rate**: TBD%
- **Status**: ⏳ PENDING

---

## Analysis

### Performance vs Requirements

**TODO**: Fill in after running benchmarks

### Bottlenecks Identified

**TODO**: Analyze results

### Optimization Recommendations

**TODO**: Based on results

---

## Test Environment

- **Python Version**: {sys.version.split()[0]}
- **OS**: {os.name}
- **NATS Server**: localhost:4222
- **Database**: SQLite (temporary test database)

---

## Next Steps

1. ✅ Run complete benchmark suite
2. ⏳ Analyze results vs requirements
3. ⏳ Identify performance bottlenecks
4. ⏳ Implement optimizations if needed
5. ⏳ Re-run benchmarks to verify improvements

---

## References

- [Performance Test Suite](tests/performance/test_nats_overhead.py)
- [Performance README](tests/performance/README.md)
- [ARCHITECTURE.md](ARCHITECTURE.md)
- [DEPLOYMENT.md](DEPLOYMENT.md)
- SPEC-Sortie-6: Testing & Documentation

---

**Generated by**: `scripts/run_benchmarks.py`  
**Sprint**: 9 - The Accountant (NATS Event Bus Architecture)
"""

    Path(output_file).write_text(report)
    print(f"✅ Report saved to: {output_file}")


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Run Sprint 9 performance benchmarks")
    parser.add_argument("--quick", action="store_true", help="Run quick benchmarks")
    parser.add_argument("--report-file", default="BENCHMARK_RESULTS.md", help="Output report file")
    parser.add_argument("--no-install", action="store_true", help="Skip dependency installation")

    args = parser.parse_args()

    print("=" * 70)
    print(" " * 15 + "Sprint 9 Performance Benchmarks")
    print("=" * 70)

    # Check NATS server
    if not check_nats_server():
        print("❌ NATS server not running on localhost:4222")
        print("\nPlease start NATS server:")
        print("  nats-server")
        sys.exit(1)

    print("✅ NATS server detected")

    # Install dependencies
    if not args.no_install:
        install_dependencies()

    # Run benchmarks
    success = run_benchmarks(quick=args.quick)

    # Generate report
    generate_report(output_file=args.report_file)

    if success:
        print("\n✅ All benchmarks passed!")
        print(f"📄 Review results in: {args.report_file}")
        sys.exit(0)
    else:
        print("\n⚠️  Some benchmarks failed - review output above")
        sys.exit(1)


if __name__ == "__main__":
    main()
