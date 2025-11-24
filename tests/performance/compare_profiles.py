#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Compare NATS vs direct database profiles.

Sprint 10.5 Sortie 4 - CPU Overhead Investigation

Usage:
    # First run the profilers:
    python tests/performance/profile_nats.py
    python tests/performance/profile_direct.py

    # Then compare:
    python tests/performance/compare_profiles.py
"""
from pathlib import Path


def compare_profiles():
    """Compare and report differences between NATS and direct profiles."""
    nats_path = Path('tests/performance/nats_profile.txt')
    direct_path = Path('tests/performance/direct_profile.txt')

    # Check files exist
    if not nats_path.exists():
        print(f"❌ Error: {nats_path} not found")
        print("Run: python tests/performance/profile_nats.py")
        return

    if not direct_path.exists():
        print(f"❌ Error: {direct_path} not found")
        print("Run: python tests/performance/profile_direct.py")
        return

    print("\n" + "="*80)
    print("CPU Profile Comparison: NATS Architecture vs Direct Database")
    print("="*80)

    # Load profiles (use pstats.Stats on the profile data, not text files)
    # Note: Since we saved text files, we'll just display them
    # For real comparison, we'd need to save the profile objects

    print("\n" + "="*80)
    print("NATS Architecture Profile (Top 20 Functions)")
    print("="*80)
    with open(nats_path, 'r') as f:
        lines = f.readlines()
        # Print header and top 20 function lines
        print_count = 0
        for line in lines:
            print(line.rstrip())
            if print_count > 25:  # Header + 20 functions
                break
            if 'function calls' in line or 'ncalls' in line:
                print_count += 1
            if print_count > 0:
                print_count += 1

    print("\n" + "="*80)
    print("Direct Database Profile (Top 20 Functions)")
    print("="*80)
    with open(direct_path, 'r') as f:
        lines = f.readlines()
        print_count = 0
        for line in lines:
            print(line.rstrip())
            if print_count > 25:
                break
            if 'function calls' in line or 'ncalls' in line:
                print_count += 1
            if print_count > 0:
                print_count += 1

    print("\n" + "="*80)
    print("Analysis Summary")
    print("="*80)
    print("""
NATS overhead functions likely include:
- nats.aio.client.* (publish/subscribe operations)
- json.dumps/loads (event serialization/deserialization)
- asyncio event loop operations (context switching)
- asyncio.Queue operations (internal NATS buffering)

Direct database functions:
- aiosqlite.* (async SQLite operations)
- asyncio event loop overhead (minimal)
- Database I/O operations

📊 Expected Findings:
1. JSON serialization overhead (necessary for event-driven architecture)
2. NATS publish/subscribe overhead (network abstraction layer)
3. Additional asyncio context switching (service decoupling)

💡 Recommendation:
Compare total execution time between both approaches.
If NATS overhead is <10%, it's acceptable for the architectural benefits:
  • Clean service separation
  • Independent scaling
  • Real-time event streaming
  • Simplified testing

🎯 Next Steps:
1. Extract total time from both profiles
2. Calculate overhead percentage
3. Document top 3 hotspots in CPU_OVERHEAD_ANALYSIS.md
4. Decide: Accept overhead OR optimize in Sprint 11
""")
    print("="*80)


if __name__ == '__main__':
    compare_profiles()
