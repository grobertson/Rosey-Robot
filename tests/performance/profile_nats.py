#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Profile NATS operations to identify CPU hotspots.

Sprint 10.5 Sortie 4 - CPU Overhead Investigation

Usage:
    python tests/performance/profile_nats.py

Outputs:
    nats_profile.txt - cProfile results
"""
import asyncio
import cProfile
import pstats
import json
import time
from io import StringIO
from pathlib import Path

try:
    from nats.aio.client import Client as NATS
except ImportError:
    print("Error: nats-py not installed. Run: pip install nats-py")
    exit(1)

from common.database_service import DatabaseService


async def profile_nats_operations():
    """Profile 1000 NATS publish operations."""
    print("\n" + "="*80)
    print("NATS Architecture CPU Profiling")
    print("="*80)
    print("Profiling 1000 chat events through NATS...\n")

    # Connect to NATS
    nc = NATS()
    try:
        await nc.connect(servers=["nats://localhost:4222"])
        print("✅ Connected to NATS")
    except Exception as e:
        print(f"❌ Failed to connect to NATS: {e}")
        print("Make sure NATS server is running: nats-server")
        return

    # Create database service with temp database
    db_path = ':memory:'
    db_service = DatabaseService(nats_client=nc, db_path=db_path)
    await db_service.start()
    print("✅ Database service started")

    # Prepare test data
    data = json.dumps({
        'username': 'TestUser',
        'message': 'Test message for profiling',
        'timestamp': int(time.time())
    }).encode()

    print("\n⏱️  Profiling NATS publish operations...")
    start = time.time()

    # Profile 1000 chat events
    for i in range(1000):
        await nc.publish('rosey.db.message.log', data)

    # Wait for processing
    await asyncio.sleep(0.5)

    elapsed = time.time() - start
    print(f"✅ Completed 1000 events in {elapsed:.3f}s ({1000/elapsed:.1f} events/sec)")

    # Cleanup
    await db_service.stop()
    await nc.close()
    print("✅ Cleanup complete\n")


if __name__ == '__main__':
    # Run with profiling
    print("Starting cProfile...")
    profiler = cProfile.Profile()
    profiler.enable()

    asyncio.run(profile_nats_operations())

    profiler.disable()

    # Generate report
    stream = StringIO()
    stats = pstats.Stats(profiler, stream=stream)
    stats.strip_dirs()
    stats.sort_stats('cumulative')
    stats.print_stats(50)  # Top 50 functions

    # Save to file
    output_path = Path('tests/performance/nats_profile.txt')
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w') as f:
        f.write(stream.getvalue())

    print(f"✅ Profile saved to {output_path}\n")
    print("="*80)
    print("Top 10 CPU-intensive functions:")
    print("="*80)
    stats.print_stats(10)
