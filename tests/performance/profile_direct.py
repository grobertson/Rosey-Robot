#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Profile direct database operations (no NATS) for comparison.

Sprint 10.5 Sortie 4 - CPU Overhead Investigation

Usage:
    python tests/performance/profile_direct.py

Outputs:
    direct_profile.txt - cProfile results
"""
import asyncio
import cProfile
import pstats
import time
from io import StringIO
from pathlib import Path

from common.database import BotDatabase


async def profile_direct_operations():
    """Profile 1000 direct database writes."""
    print("\n" + "="*80)
    print("Direct Database CPU Profiling")
    print("="*80)
    print("Profiling 1000 direct database writes...\n")

    # Connect to database
    db = BotDatabase(':memory:')
    await db.connect()
    print("✅ Database connected")

    print("\n⏱️  Profiling direct database operations...")
    start = time.time()

    # Profile 1000 chat logs
    for i in range(1000):
        await db.log_chat('TestUser', f'Test message {i}', int(time.time()))

    elapsed = time.time() - start
    print(f"✅ Completed 1000 writes in {elapsed:.3f}s ({1000/elapsed:.1f} writes/sec)")

    # Cleanup
    await db.close()
    print("✅ Database closed\n")


if __name__ == '__main__':
    # Run with profiling
    print("Starting cProfile...")
    profiler = cProfile.Profile()
    profiler.enable()

    asyncio.run(profile_direct_operations())

    profiler.disable()

    # Generate report
    stream = StringIO()
    stats = pstats.Stats(profiler, stream=stream)
    stats.strip_dirs()
    stats.sort_stats('cumulative')
    stats.print_stats(50)

    # Save to file
    output_path = Path('tests/performance/direct_profile.txt')
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w') as f:
        f.write(stream.getvalue())

    print(f"✅ Profile saved to {output_path}\n")
    print("="*80)
    print("Top 10 CPU-intensive functions:")
    print("="*80)
    stats.print_stats(10)
