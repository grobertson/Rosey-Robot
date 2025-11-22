#!/usr/bin/env python3
"""
Helper script to track remaining database method migrations.

This script identifies which methods still need migration from aiosqlite to SQLAlchemy ORM.

Sprint 11 Sortie 2 - BotDatabase Migration Tracker
"""

methods_to_migrate = [
    # User Tracking (DONE)
    ("user_joined", "DONE"),
    ("user_left", "DONE"),
    ("user_chat_message", "DONE"),
    ("get_recent_messages", "DONE"),
    ("log_chat", "DONE"),
    
    # Audit (DONE)
    ("log_user_action", "DONE"),
    
    # Channel Stats (TODO)
    ("update_high_water_mark", "TODO - line 407"),
    ("get_user_stats", "TODO - line ~485"),
    ("get_high_water_mark", "TODO - line ~502"),
    ("get_high_water_mark_connected", "TODO - line ~522"),
    ("get_top_chatters", "TODO - line ~540"),
    ("get_total_users_seen", "TODO - line ~552"),
    
    # Historical Tracking (TODO)
    ("log_user_count", "TODO - line ~571"),
    ("get_user_count_history", "TODO - line ~589"),
    ("cleanup_old_history", "TODO - line ~617"),
    
    # Recent Chat (TODO)
    ("get_recent_chat", "TODO - line ~643"),
    ("get_recent_chat_since", "TODO - line ~664"),
    
    # Outbound Messages (TODO)
    ("enqueue_outbound_message", "TODO - line ~687"),
    ("get_unsent_outbound_messages", "TODO - line ~708"),
    ("mark_outbound_sent", "TODO - line ~728"),
    ("mark_outbound_failed", "TODO - line ~765"),
    
    # Status (TODO)
    ("update_current_status", "TODO - line ~797"),
    ("get_current_status", "TODO - line ~822"),
    
    # API Tokens (TODO)
    ("generate_api_token", "TODO - line ~848"),
    ("validate_api_token", "TODO - line ~880"),
    ("revoke_api_token", "TODO - line ~915"),
    ("list_api_tokens", "TODO - line ~952"),
    
    # Maintenance (TODO)
    ("perform_maintenance", "TODO - line ~990"),
]

print("Sprint 11 Sortie 2: Database Migration Status")
print("=" * 60)
print()

done = [m for m, status in methods_to_migrate if status == "DONE"]
todo = [m for m, status in methods_to_migrate if status.startswith("TODO")]

print(f"Progress: {len(done)}/{len(methods_to_migrate)} methods migrated")
print()
print(f"DONE ({len(done)}):")
for method in done:
    print(f"  ✓ {method}")
print()
print(f"TODO ({len(todo)}):")
for method, status in methods_to_migrate:
    if status.startswith("TODO"):
        print(f"  ☐ {method} - {status}")
print()
print("=" * 60)
