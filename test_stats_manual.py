"""Manual test for stats command NATS integration.

This script tests the stats functionality by:
1. Creating an in-memory database with test data
2. Starting DatabaseService with NATS
3. Sending stats query requests
4. Validating responses

Run with: python test_stats_manual.py
"""

import asyncio
import json
import time
from pathlib import Path

# Add project root to path
import sys
sys.path.insert(0, str(Path(__file__).parent))

from nats.aio.client import Client as NATS
from common.database_service import DatabaseService


async def main():
    """Run manual stats test."""
    print("=" * 80)
    print("STATS COMMAND MANUAL TEST")
    print("=" * 80)
    
    # Connect to NATS
    print("\n[1] Connecting to NATS...")
    nats = NATS()
    await nats.connect("nats://localhost:4222")
    print("✓ NATS connected")
    
    # Create test database path
    import tempfile
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    
    print(f"\n[2] Creating test database: {db_path}")
    
    # Start DatabaseService (creates and connects database)
    service = DatabaseService(nats, db_path)
    await service.start()
    print("✓ DatabaseService started")
    
    # Add test data directly to database
    print("\n[3] Adding test data...")
    now = int(time.time())
    cursor = await service.db.conn.cursor()
    
    # Add users
    await cursor.execute('''
        INSERT INTO user_stats 
        (username, first_seen, last_seen, total_chat_lines, total_time_connected)
        VALUES 
        ('Alice', ?, ?, 1234, 3600),
        ('Bob', ?, ?, 987, 7200),
        ('Charlie', ?, ?, 654, 1800)
    ''', (now - 86400, now, now - 86400, now, now - 86400, now))
    
    # Update channel stats
    await cursor.execute('''
        UPDATE channel_stats
        SET max_users = 42,
            max_users_timestamp = ?,
            max_connected = 58,
            max_connected_timestamp = ?
    ''', (now - 3600, now - 1800))
    
    await service.db.conn.commit()
    print("✓ Test data created (3 users, channel stats)")
    
    try:
        # Test 1: Channel stats query
        print("\n[4] Testing channel stats query...")
        print("   Sending request to: rosey.db.query.channel_stats")
        
        response = await nats.request(
            'rosey.db.query.channel_stats',
            b'{}',
            timeout=1.0
        )
        
        stats = json.loads(response.data.decode())
        print(f"   Response: {json.dumps(stats, indent=2)}")
        
        # Validate response
        assert stats['success'] is True, "Expected success=true"
        assert 'high_water_mark' in stats, "Missing high_water_mark"
        assert stats['high_water_mark']['users'] == 42, f"Expected 42 users, got {stats['high_water_mark']['users']}"
        assert 'high_water_connected' in stats, "Missing high_water_connected"
        assert stats['high_water_connected']['users'] == 58, f"Expected 58 connected, got {stats['high_water_connected']['users']}"
        assert 'top_chatters' in stats, "Missing top_chatters"
        assert len(stats['top_chatters']) == 3, f"Expected 3 chatters, got {len(stats['top_chatters'])}"
        assert stats['top_chatters'][0]['username'] == 'Alice', "Expected Alice first"
        assert stats['top_chatters'][0]['chat_lines'] == 1234, "Expected 1234 chat lines"
        print("   ✓ Channel stats validation PASSED")
        
        # Test 2: User stats query (found)
        print("\n[5] Testing user stats query (Alice)...")
        print("   Sending request to: rosey.db.query.user_stats")
        
        request_data = json.dumps({'username': 'Alice'}).encode()
        response = await nats.request(
            'rosey.db.query.user_stats',
            request_data,
            timeout=1.0
        )
        
        user_stats = json.loads(response.data.decode())
        print(f"   Response: {json.dumps(user_stats, indent=2)}")
        
        # Validate response
        assert user_stats['success'] is True, "Expected success=true"
        assert user_stats['found'] is True, "Expected found=true"
        assert user_stats['username'] == 'Alice', "Expected username=Alice"
        assert user_stats['total_chat_lines'] == 1234, "Expected 1234 chat lines"
        assert user_stats['total_time_connected'] == 3600, "Expected 3600 seconds"
        print("   ✓ User stats validation PASSED")
        
        # Test 3: User stats query (not found)
        print("\n[6] Testing user stats query (NotFound)...")
        
        request_data = json.dumps({'username': 'NotFound'}).encode()
        response = await nats.request(
            'rosey.db.query.user_stats',
            request_data,
            timeout=1.0
        )
        
        user_stats = json.loads(response.data.decode())
        print(f"   Response: {json.dumps(user_stats, indent=2)}")
        
        # Validate response
        assert user_stats['success'] is True, "Expected success=true"
        assert user_stats['found'] is False, "Expected found=false"
        print("   ✓ User not found validation PASSED")
        
        print("\n" + "=" * 80)
        print("ALL TESTS PASSED ✓")
        print("=" * 80)
        
    finally:
        # Cleanup
        print("\n[7] Cleaning up...")
        await service.stop()
        await nats.close()
        
        # Remove temp database file
        try:
            Path(db_path).unlink(missing_ok=True)
        except Exception as e:
            print(f"Warning: Could not remove temp database: {e}")
        
        print("✓ Cleanup complete")


if __name__ == '__main__':
    asyncio.run(main())
