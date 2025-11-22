#!/usr/bin/env python3
"""
Example demonstrating SQLiteStorage adapter usage.

This script shows how to use the SQLiteStorage implementation
of the StorageAdapter interface for bot data persistence.
"""

import asyncio
import time
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.storage import SQLiteStorage


async def main():
    """Demonstrate SQLiteStorage functionality."""
    
    # Create and connect to storage
    print("Creating SQLiteStorage...")
    storage = SQLiteStorage('example_bot.db')
    
    print("Connecting to database...")
    await storage.connect()
    print(f"Connected: {storage.is_connected}")
    
    # Simulate user joining
    print("\n--- User Session ---")
    now = int(time.time())
    await storage.save_user_stats(
        "alice",
        first_seen=now,
        last_seen=now,
        session_start=now
    )
    await storage.log_user_action("alice", "join", "from 192.168.1.1")
    print("User 'alice' joined")
    
    # Simulate chat messages
    print("\n--- Chat Messages ---")
    await storage.save_user_stats("alice", chat_lines=1, last_seen=now + 10)
    await storage.save_message("alice", "Hello everyone!", timestamp=now + 10)
    
    await storage.save_user_stats("alice", chat_lines=1, last_seen=now + 20)
    await storage.save_message("alice", "How's everyone doing?", timestamp=now + 20)
    
    print("Saved 2 chat messages")
    
    # Retrieve user stats
    print("\n--- User Stats ---")
    stats = await storage.get_user_stats("alice")
    print(f"Username: {stats['username']}")
    print(f"First seen: {stats['first_seen']}")
    print(f"Total chat lines: {stats['total_chat_lines']}")
    print(f"Session active: {stats['current_session_start'] is not None}")
    
    # Retrieve recent messages
    print("\n--- Recent Messages ---")
    messages = await storage.get_recent_messages(limit=10)
    for msg in messages:
        print(f"[{msg['timestamp']}] {msg['username']}: {msg['message']}")
    
    # Update channel stats
    print("\n--- Channel Stats ---")
    await storage.update_channel_stats(max_users=5, max_connected=8, timestamp=now)
    await storage.log_user_count(5, 8, timestamp=now)
    
    channel_stats = await storage.get_channel_stats()
    print(f"Max users: {channel_stats['max_users']}")
    print(f"Max connected: {channel_stats['max_connected']}")
    
    # Get user actions
    print("\n--- User Actions ---")
    actions = await storage.get_user_actions(username="alice")
    for action in actions:
        print(f"[{action['timestamp']}] {action['username']} - {action['action_type']}")
    
    # Cleanup
    print("\n--- Closing Connection ---")
    await storage.close()
    print(f"Connected: {storage.is_connected}")
    print("\nExample complete!")


if __name__ == '__main__':
    asyncio.run(main())
