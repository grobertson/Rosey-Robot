"""
Performance Baseline Loader for Test Suite.

This module provides utilities to load calibrated performance baselines
for the test suite, ensuring consistent and realistic performance expectations
across different CI environments.

The baseline system:
1. Loads performance targets from baseline.json
2. Provides minimum acceptable thresholds with tolerance
3. Logs actual performance for monitoring
4. Allows easy recalibration for different environments

Usage:
    from tests.performance.baseline_loader import get_min_acceptable, log_performance
    
    min_acceptable = get_min_acceptable("simple_select_validation")
    # ... run benchmark ...
    log_performance("simple_select_validation", actual_ops, 300, "ops/sec")
    assert actual_ops > min_acceptable
"""

import json
from pathlib import Path
from typing import Dict, Any, Literal

# Cache to avoid repeated file reads
_baseline_cache: Dict[str, Any] | None = None


def load_baseline() -> Dict[str, Any]:
    """
    Load performance baseline configuration from baseline.json.
    
    The baseline file contains calibrated performance targets for
    all performance tests, including tolerance margins for system variation.
    
    Returns:
        Dict containing:
            - version: Baseline format version
            - environment: Target environment (ci, development)
            - calibration_date: When baselines were last calibrated
            - tolerance_percent: Default tolerance for variation
            - baselines: Dict of test_name -> baseline config
    
    Raises:
        FileNotFoundError: If baseline.json doesn't exist
        json.JSONDecodeError: If baseline.json is invalid JSON
    
    Example:
        >>> baseline = load_baseline()
        >>> baseline["baselines"]["simple_select_validation"]["ops_per_sec"]
        300
    """
    global _baseline_cache
    
    # Return cached version if available
    if _baseline_cache is not None:
        return _baseline_cache
    
    # Find baseline.json in same directory as this module
    baseline_path = Path(__file__).parent / "baseline.json"
    
    if not baseline_path.exists():
        raise FileNotFoundError(
            f"Baseline file not found: {baseline_path}\n"
            f"Run tests/performance/calibrate.py to generate baselines."
        )
    
    # Load and cache baseline configuration
    with open(baseline_path, 'r', encoding='utf-8') as f:
        _baseline_cache = json.load(f)
    
    return _baseline_cache


def get_min_acceptable(
    test_name: str, 
    metric: Literal["ops_per_sec", "avg_time_ms"] = "ops_per_sec"
) -> float:
    """
    Get minimum acceptable performance value for a test.
    
    For throughput metrics (ops_per_sec), returns the minimum acceptable
    rate below which the test should fail.
    
    For latency metrics (avg_time_ms), returns the maximum acceptable
    time above which the test should fail.
    
    Args:
        test_name: Name of the test (matches key in baseline.json)
        metric: Type of metric - "ops_per_sec" or "avg_time_ms"
    
    Returns:
        Minimum acceptable value (for ops_per_sec) or
        Maximum acceptable value (for avg_time_ms)
    
    Raises:
        KeyError: If test_name not found in baselines
        ValueError: If metric type is unknown
    
    Example:
        >>> min_ops = get_min_acceptable("simple_select_validation")
        >>> assert actual_ops > min_ops  # Should be > 240
        
        >>> max_time = get_min_acceptable("full_pipeline", "avg_time_ms")
        >>> assert actual_time < max_time  # Should be < 6.0ms
    """
    baseline = load_baseline()
    test_baseline = baseline["baselines"].get(test_name)
    
    if not test_baseline:
        available = ", ".join(baseline["baselines"].keys())
        raise KeyError(
            f"No baseline found for test: {test_name}\n"
            f"Available tests: {available}"
        )
    
    # For throughput metrics, return min_acceptable
    if metric == "ops_per_sec":
        return test_baseline["min_acceptable"]
    # For latency metrics, return max_acceptable
    elif metric == "avg_time_ms":
        return test_baseline["max_acceptable"]
    else:
        raise ValueError(
            f"Unknown metric: {metric}\n"
            f"Supported metrics: 'ops_per_sec', 'avg_time_ms'"
        )


def get_baseline_value(
    test_name: str,
    metric: Literal["ops_per_sec", "avg_time_ms"] = "ops_per_sec"
) -> float:
    """
    Get the baseline (expected) performance value for a test.
    
    This is the target value, not the minimum acceptable.
    Use for logging and comparison purposes.
    
    Args:
        test_name: Name of the test
        metric: Type of metric
    
    Returns:
        Baseline target value
    
    Example:
        >>> baseline = get_baseline_value("simple_select_validation")
        >>> log_performance("test", actual, baseline, "ops/sec")
    """
    baseline = load_baseline()
    test_baseline = baseline["baselines"].get(test_name)
    
    if not test_baseline:
        raise KeyError(f"No baseline found for test: {test_name}")
    
    return test_baseline[metric]


def log_performance(
    test_name: str, 
    actual: float, 
    expected: float, 
    metric: str
) -> None:
    """
    Log performance metrics for monitoring and debugging.
    
    Prints a formatted performance summary showing:
    - Actual performance achieved
    - Percentage of baseline target
    - Clear formatting for easy reading
    
    Args:
        test_name: Name of the test being run
        actual: Actual performance value measured
        expected: Expected baseline value
        metric: Unit of measurement (e.g., "ops/sec", "ms")
    
    Example:
        >>> log_performance("simple_select_validation", 325.5, 300, "ops/sec")
        Performance [simple_select_validation]: 325.5 ops/sec (108.5% of baseline)
    """
    if expected > 0:
        percent = (actual / expected) * 100
        print(f"  Performance [{test_name}]: {actual:.1f} {metric} ({percent:.1f}% of baseline)")
    else:
        print(f"  Performance [{test_name}]: {actual:.1f} {metric} (baseline: {expected:.1f})")
