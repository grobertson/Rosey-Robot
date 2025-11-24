#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generate Performance Benchmark Report from pytest JSON output

Sprint 10 Sortie 4 - Performance Validation

Usage:
    pytest tests/performance/test_nats_overhead.py -v -s --json-report --json-report-file=benchmark_results.json
    python tests/performance/generate_report.py benchmark_results.json

Outputs:
    tests/performance/BENCHMARK_RESULTS.md
"""

import json
import os
import re
import sys
import platform
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any


def load_benchmark_results(json_file: str) -> Dict[str, Any]:
    """Load pytest JSON report."""
    with open(json_file, 'r') as f:
        return json.load(f)


def parse_benchmark_output(stdout: str) -> Dict[str, float]:
    """Parse benchmark metrics from stdout.

    Looks for patterns like:
    - Mean: 2.5ms
    - P95: 4.2ms
    - Throughput: 120 events/sec
    - CPU Overhead: 3.5%
    """
    metrics = {}

    patterns = {
        'mean': r'Mean:\s+([\d.]+)ms',
        'median': r'Median:\s+([\d.]+)ms',
        'p95': r'P95:\s+([\d.]+)ms',
        'p99': r'P99:\s+([\d.]+)ms',
        'max': r'Max:\s+([\d.]+)ms',
        'throughput': r'Throughput:\s+([\d.]+)\s+events/sec',
        'cpu_overhead': r'CPU Overhead:\s+([\d.]+)%',
        'memory_increase': r'Memory Increase:\s+([\d.]+)%',
        'memory_baseline': r'Baseline:\s+([\d.]+)\s*MB',
        'memory_final': r'Final:\s+([\d.]+)\s*MB'
    }

    for key, pattern in patterns.items():
        match = re.search(pattern, stdout)
        if match:
            metrics[key] = float(match.group(1))

    return metrics


def parse_test_results(report: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract benchmark data from pytest report."""
    results = []

    for test in report.get('tests', []):
        # Parse test name and outcome
        test_name = test['nodeid']
        outcome = test['outcome']
        duration = test.get('call', {}).get('duration', 0)
        stdout = test.get('call', {}).get('stdout', '')

        # Parse metrics from stdout
        metrics = parse_benchmark_output(stdout)

        results.append({
            'name': test_name,
            'short_name': test_name.split('::')[-1],
            'outcome': outcome,
            'duration': duration,
            'stdout': stdout,
            'metrics': metrics
        })

    return results


def categorize_tests(results: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """Group test results by category."""
    categories = {
        'Latency': [],
        'Throughput': [],
        'CPU': [],
        'Memory': [],
        'Concurrent': [],
        'Failure Recovery': []
    }

    for result in results:
        name = result['name'].lower()
        if 'latency' in name:
            categories['Latency'].append(result)
        elif 'throughput' in name:
            categories['Throughput'].append(result)
        elif 'cpu' in name:
            categories['CPU'].append(result)
        elif 'memory' in name:
            categories['Memory'].append(result)
        elif 'concurrent' in name:
            categories['Concurrent'].append(result)
        elif 'failure' in name or 'recovery' in name:
            categories['Failure Recovery'].append(result)

    return categories


def evaluate_metric(metric_name: str, value: float) -> str:
    """Evaluate if metric meets requirements.

    Returns:
        str: '✅ PASS', '⚠️ WARN', or '❌ FAIL'
    """
    # Sprint 9 requirements
    requirements = {
        'mean': (5.0, 'ms'),
        'median': (5.0, 'ms'),
        'p95': (8.0, 'ms'),  # Allow some headroom
        'p99': (10.0, 'ms'),
        'throughput': (100.0, 'events/sec', 'gte'),  # Greater than or equal
        'cpu_overhead': (5.0, '%'),
        'memory_increase': (10.0, '%')
    }

    if metric_name not in requirements:
        return ''

    req = requirements[metric_name]
    threshold = req[0]
    unit = req[1] if len(req) > 1 else ''
    comparison = req[2] if len(req) > 2 else 'lte'  # Less than or equal (default)

    if comparison == 'gte':
        # Higher is better (throughput)
        if value >= threshold:
            return f'✅ **PASS**: {value}{unit} ≥ {threshold}{unit} target'
        elif value >= threshold * 0.8:
            return f'⚠️ **WARN**: {value}{unit} near {threshold}{unit} target (optimization recommended)'
        else:
            return f'❌ **FAIL**: {value}{unit} < {threshold}{unit} target'
    else:
        # Lower is better (latency, overhead)
        if value <= threshold:
            return f'✅ **PASS**: {value}{unit} ≤ {threshold}{unit} target'
        elif value <= threshold * 1.2:
            return f'⚠️ **WARN**: {value}{unit} near {threshold}{unit} target (optimization recommended)'
        else:
            return f'❌ **FAIL**: {value}{unit} > {threshold}{unit} target'


def generate_markdown_report(results: List[Dict[str, Any]], output_file: str):
    """Generate markdown report from benchmark results."""

    categories = categorize_tests(results)

    with open(output_file, 'w', encoding='utf-8') as f:
        # Header
        f.write('# Performance Benchmark Results - Sprint 10\n\n')
        f.write(f'**Generated**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n\n')
        f.write('**Rosey Version**: v0.5.0 (Sprint 10 Sortie 4)\n\n')
        f.write(f'**Total Tests**: {len(results)}\n\n')

        passed = sum(1 for r in results if r['outcome'] == 'passed')
        failed = sum(1 for r in results if r['outcome'] == 'failed')
        f.write(f'**Status**: {passed} passed, {failed} failed\n\n')

        f.write('---\n\n')

        # Executive Summary
        f.write('## Executive Summary\n\n')
        f.write('Sprint 10 completes the NATS event-driven architecture validation. ')
        f.write('These benchmarks measure performance characteristics against Sprint 9 requirements.\n\n')

        # Write results by category
        for category, tests in categories.items():
            if not tests:
                continue

            f.write(f'## {category} Benchmarks\n\n')

            for test in tests:
                f.write(f'### {test["short_name"]}\n\n')
                f.write(f'**Status**: {test["outcome"].upper()}\n\n')
                f.write(f'**Duration**: {test["duration"]:.2f}s\n\n')

                if test['metrics']:
                    f.write('**Metrics**:\n\n')
                    f.write('| Metric | Value |\n')
                    f.write('|--------|-------|\n')

                    for key, value in test['metrics'].items():
                        formatted_key = key.replace('_', ' ').title()

                        # Determine unit
                        if 'ms' in formatted_key or key in ['mean', 'median', 'p95', 'p99', 'max']:
                            unit = 'ms'
                        elif 'throughput' in key:
                            unit = ' events/sec'
                        elif 'overhead' in key or 'increase' in key:
                            unit = '%'
                        elif 'memory' in key:
                            unit = ' MB'
                        else:
                            unit = ''

                        f.write(f'| {formatted_key} | {value}{unit} |\n')

                    f.write('\n')

                    # Evaluate against requirements
                    for metric_name in ['mean', 'median', 'p95', 'throughput', 'cpu_overhead', 'memory_increase']:
                        if metric_name in test['metrics']:
                            evaluation = evaluate_metric(metric_name, test['metrics'][metric_name])
                            if evaluation:
                                f.write(f'{evaluation}\n\n')
                                break  # Only show primary metric evaluation

                f.write('---\n\n')

        # Analysis
        f.write('## Analysis & Recommendations\n\n')

        f.write('### Performance Summary\n\n')

        all_passed = all(r['outcome'] == 'passed' for r in results)
        if all_passed:
            f.write('✅ All benchmarks passed. NATS architecture meets Sprint 9 requirements.\n\n')
        else:
            f.write('⚠️ Some benchmarks failed or warned. Review results above for details.\n\n')

        f.write('### Optimization Opportunities (Sprint 11+)\n\n')
        f.write('- [ ] Consider connection pooling for DatabaseService\n')
        f.write('- [ ] Evaluate batch processing for high-volume events\n')
        f.write('- [ ] Profile slow database queries\n')
        f.write('- [ ] Add caching for frequently accessed stats\n')
        f.write('- [ ] Monitor production performance with APM tools\n\n')

        f.write('### Baseline Metrics Established\n\n')
        f.write('These results provide baseline metrics for Sprint 11+ performance tracking. ')
        f.write('Future changes should be compared against these values to detect regressions.\n\n')

        # Test Environment
        f.write('---\n\n')
        f.write('## Appendix: Test Environment\n\n')
        f.write('```\n')
        f.write(f'OS: {platform.system()} {platform.release()}\n')
        f.write(f'Python: {platform.python_version()}\n')
        f.write(f'Architecture: {platform.machine()}\n')
        f.write(f'Processor: {platform.processor()}\n')
        f.write('```\n\n')

        # Sprint 9 Requirements Reference
        f.write('## Appendix: Sprint 9 Requirements\n\n')
        f.write('| Metric | Target | Priority |\n')
        f.write('|--------|--------|----------|\n')
        f.write('| NATS Latency | <5ms per event | P0 |\n')
        f.write('| Request/Reply Latency | <10ms round-trip | P0 |\n')
        f.write('| Throughput | 100+ events/second | P0 |\n')
        f.write('| CPU Overhead | <5% vs direct DB | P1 |\n')
        f.write('| Memory Overhead | <10% increase | P1 |\n')
        f.write('| Concurrent Events | 50+ simultaneous | P1 |\n')
        f.write('| Failure Recovery | <100ms service restart | P1 |\n')
        f.write('\n')

        # Add CI information if running in GitHub Actions
        if os.getenv('GITHUB_ACTIONS') == 'true':
            f.write('---\n\n')
            f.write('## CI Information\n\n')
            f.write(f"- **Run ID**: {os.getenv('GITHUB_RUN_ID', 'N/A')}\n")
            f.write(f"- **Commit**: {os.getenv('GITHUB_SHA', 'N/A')[:7]}\n")
            f.write(f"- **Branch**: {os.getenv('GITHUB_REF_NAME', 'N/A')}\n")
            f.write(f"- **Triggered by**: {os.getenv('GITHUB_EVENT_NAME', 'N/A')}\n")
            f.write('\n')


def main():
    if len(sys.argv) < 2:
        print('Usage: python generate_report.py <benchmark_results.json>')
        print('')
        print('First run benchmarks with JSON output:')
        print('  pytest tests/performance/test_nats_overhead.py -v -s --json-report --json-report-file=benchmark_results.json')
        sys.exit(1)

    json_file = sys.argv[1]
    output_file = 'tests/performance/BENCHMARK_RESULTS.md'

    if not Path(json_file).exists():
        print(f'❌ Error: File not found: {json_file}')
        sys.exit(1)

    print(f'📊 Loading results from {json_file}...')
    report = load_benchmark_results(json_file)

    print('🔍 Parsing test results...')
    results = parse_test_results(report)

    if not results:
        print('⚠️  Warning: No test results found in JSON report')
        print('Make sure to run performance tests with --json-report flag')
        sys.exit(1)

    print(f'📝 Generating report: {output_file}...')
    generate_markdown_report(results, output_file)

    print('✅ Report generated successfully!')
    print(f'📄 View results: {output_file}')


if __name__ == '__main__':
    main()
