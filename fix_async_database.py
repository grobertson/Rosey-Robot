#!/usr/bin/env python3
"""Script to convert BotDatabase methods to async/await style.

This script fixes the incomplete async conversion from Phase 1 by:
1. Converting method signatures from `def` to `async def`
2. Converting cursor creation from `cursor = self.conn.cursor()` to `cursor = await self.conn.cursor()`
3. Converting cursor operations from `cursor.execute()` to `await cursor.execute()`
4. Converting fetch operations from `cursor.fetchone()` to `await cursor.fetchone()`
5. Converting commit from `self.conn.commit()` to `await self.conn.commit()`
"""

import re

def fix_async_database(file_path='common/database.py'):
    """Fix database.py to use async/await properly."""
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Track changes
    changes = []
    
    # Methods to convert (after connect, close, _run_migrations which are already async)
    methods_to_convert = [
        'user_joined', 'user_left', 'user_chat_message', 'log_user_count',
        'update_high_water_mark', 'update_current_status', 'mark_outbound_sent',
        'get_unsent_outbound_messages', 'get_recent_chat', 'get_user_stats',
        'get_channel_stats', 'get_user_count', 'add_pm_action', 'queue_outbound_message',
        'get_and_clear_outbound_messages', 'increment_outbound_retry', 'delete_outbound_message',
        # Additional methods found in Phase 1 review:
        'log_user_action', 'get_high_water_mark', 'get_high_water_mark_connected',
        'get_top_chatters', 'get_total_users_seen', 'get_user_count_history',
        'cleanup_old_history', 'get_recent_chat_since', 'enqueue_outbound_message',
        'mark_outbound_failed', 'get_current_status', 'generate_api_token',
        'validate_api_token', 'revoke_api_token', 'list_api_tokens', 'perform_maintenance'
    ]
    
    # Convert method signatures: def method_name( to async def method_name(
    for method in methods_to_convert:
        # Match method definition with proper indentation
        pattern = rf'(    def {method}\()'
        replacement = rf'    async def {method}('
        if re.search(pattern, content):
            content = re.sub(pattern, replacement, content)
            changes.append(f'  - Converted {method}() to async def')
    
    # Convert cursor creation: cursor = self.conn.cursor() to cursor = await self.conn.cursor()
    pattern = r'(\s+)cursor = self\.conn\.cursor\(\)'
    replacement = r'\1cursor = await self.conn.cursor()'
    cursor_count = len(re.findall(pattern, content))
    content = re.sub(pattern, replacement, content)
    if cursor_count:
        changes.append(f'  - Converted {cursor_count} cursor() calls to await')
    
    # Convert cursor.execute(): cursor.execute( to await cursor.execute(
    pattern = r'(\s+)cursor\.execute\('
    replacement = r'\1await cursor.execute('
    execute_count = len(re.findall(pattern, content))
    content = re.sub(pattern, replacement, content)
    if execute_count:
        changes.append(f'  - Converted {execute_count} execute() calls to await')
    
    # Convert cursor.fetchone(): cursor.fetchone() to await cursor.fetchone()
    pattern = r'(\s+)([\w\s=]+)?cursor\.fetchone\(\)'
    replacement = r'\1\2await cursor.fetchone()'
    fetchone_count = len(re.findall(pattern, content))
    content = re.sub(pattern, replacement, content)
    if fetchone_count:
        changes.append(f'  - Converted {fetchone_count} fetchone() calls to await')
    
    # Convert cursor.fetchall(): cursor.fetchall() to await cursor.fetchall()
    pattern = r'(\s+)([\w\s=\[\]]+)?cursor\.fetchall\(\)'
    replacement = r'\1\2await cursor.fetchall()'
    fetchall_count = len(re.findall(pattern, content))
    content = re.sub(pattern, replacement, content)
    if fetchall_count:
        changes.append(f'  - Converted {fetchall_count} fetchall() calls to await')
    
    # Convert self.conn.commit(): self.conn.commit() to await self.conn.commit()
    pattern = r'(\s+)self\.conn\.commit\(\)'
    replacement = r'\1await self.conn.commit()'
    commit_count = len(re.findall(pattern, content))
    content = re.sub(pattern, replacement, content)
    if commit_count:
        changes.append(f'  - Converted {commit_count} commit() calls to await')
    
    # Write back
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    # Print summary
    print(f"Fixed {file_path}:")
    for change in changes:
        print(change)
    print(f"\nTotal changes: {len(changes)}")

if __name__ == '__main__':
    fix_async_database()
