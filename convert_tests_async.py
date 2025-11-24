#!/usr/bin/env python3
"""
Automated test conversion script for Sprint 11 Sortie 2/3.

Converts synchronous database tests to async/ORM compatible tests.

Usage:
    python convert_tests_async.py tests/unit/test_database.py

Changes Applied:
1. Add @pytest.mark.asyncio decorator to all test methods
2. Convert `def test_` to `async def test_`
3. Add `await` to all database method calls
4. Remove direct .conn access (use ORM equivalents where possible)
5. Update fixture usage (remove old sync fixtures)
6. Fix schema introspection (use SQLAlchemy metadata)

WARNING: This script modifies files in-place. Review diffs before committing.
"""
import re
import sys
from pathlib import Path


def convert_test_file(filepath: Path) -> tuple[int, int]:
    """
    Convert a test file from sync to async.

    Args:
        filepath: Path to test file

    Returns:
        tuple: (num_methods_converted, num_awaits_added)
    """
    content = filepath.read_text()
    original_content = content

    methods_converted = 0
    awaits_added = 0

    # 1. Add @pytest.mark.asyncio decorator before test methods
    pattern = r'(\n    )(def test_)'
    replacement = r'\1@pytest.mark.asyncio\1async \2'
    content, count = re.subn(pattern, replacement, content)
    methods_converted += count

    # 2. Add await to database method calls (common patterns)
    db_methods = [
        'user_joined', 'user_left', 'user_chat_message', 'get_recent_messages',
        'log_chat', 'log_user_action', 'update_high_water_mark',
        'get_user_stats', 'get_high_water_mark', 'get_high_water_mark_connected',
        'get_top_chatters', 'get_total_users_seen',
        'log_user_count', 'get_user_count_history', 'cleanup_old_history',
        'get_recent_chat', 'get_recent_chat_since',
        'enqueue_outbound_message', 'get_unsent_outbound_messages',
        'mark_outbound_sent', 'mark_outbound_failed',
        'update_current_status', 'get_current_status',
        'generate_api_token', 'validate_api_token', 'revoke_api_token',
        'list_api_tokens', 'perform_maintenance',
        'connect', 'close'
    ]

    for method in db_methods:
        # Pattern: db.method( or db_var.method(
        pattern = rf'(\bdb\w*\.{method}\()'
        replacement = r'await \1'
        # Only add await if not already present
        content = re.sub(
            rf'(?<!await )(\bdb\w*\.{method}\()',
            replacement,
            content
        )
        awaits_added += content.count('await db') - original_content.count('await db')

    # 3. Remove old sync fixture usage patterns (if any)
    # Example: db.conn.execute() → will be handled manually as these need ORM equivalents

    # Write back if changed
    if content != original_content:
        filepath.write_text(content)
        print(f"✅ Converted {filepath}")
        print(f"   - {methods_converted} test methods converted to async")
        print(f"   - {awaits_added} await statements added")
        return methods_converted, awaits_added
    else:
        print(f"⏭️  No changes needed for {filepath}")
        return 0, 0


def main():
    if len(sys.argv) < 2:
        print("Usage: python convert_tests_async.py <test_file>")
        print("Example: python convert_tests_async.py tests/unit/test_database.py")
        sys.exit(1)

    filepath = Path(sys.argv[1])

    if not filepath.exists():
        print(f"❌ File not found: {filepath}")
        sys.exit(1)

    print(f"Converting {filepath} to async...")
    print("=" * 60)

    methods, awaits = convert_test_file(filepath)

    print("=" * 60)
    print("🎉 Conversion complete!")
    print(f"   - {methods} test methods converted")
    print(f"   - {awaits} await statements added")
    print()
    print("⚠️  Manual fixes still needed:")
    print("   - Remove db.conn.execute() calls (use ORM)")
    print("   - Update schema introspection queries")
    print("   - Fix any remaining sync patterns")
    print()
    print("Next steps:")
    print("   1. Review changes: git diff")
    print("   2. Run tests: pytest tests/unit/test_database.py -v")
    print("   3. Fix any remaining issues")


if __name__ == '__main__':
    main()
