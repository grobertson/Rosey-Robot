#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Migrate configuration from v1 to v2 format.

Usage:
    python scripts/migrate_config.py bot/rosey/config.json
    python scripts/migrate_config.py --backup bot/rosey/config.json
    python scripts/migrate_config.py --output new_config.json bot/rosey/config.json
"""
import argparse
import json
import shutil
from pathlib import Path


def migrate_config_v1_to_v2(old_config: dict) -> dict:
    """Convert v1 config to v2 format.

    Args:
        old_config: Configuration in v1 format

    Returns:
        Configuration in v2 format
    """
    # Extract old values with defaults
    domain = old_config.get('domain', 'https://cytu.be')
    channel = old_config.get('channel', 'YourChannelName')
    user = old_config.get('user', ['YourUsername', 'YourPassword'])
    response_timeout = old_config.get('response_timeout', 1)
    restart_delay = old_config.get('restart_delay', 5)
    log_level = old_config.get('log_level', 'WARNING')
    chat_log_file = old_config.get('chat_log_file', 'chat.log')
    media_log_file = old_config.get('media_log_file', 'media.log')
    shell = old_config.get('shell', 'localhost:5555')
    db_path = old_config.get('db', 'bot_data.db')
    llm = old_config.get('llm', {})

    # Parse shell (old format: "host:port")
    if ':' in shell:
        shell_host, shell_port = shell.split(':', 1)
        shell_port = int(shell_port)
    else:
        shell_host = 'localhost'
        shell_port = 5555

    # Build v2 config
    new_config = {
        "version": "2.0",

        "nats": {
            "url": "nats://localhost:4222",
            "connection_timeout": 5,
            "max_reconnect_attempts": -1,
            "reconnect_delay": 2
        },

        "database": {
            "path": db_path,
            "run_as_service": True
        },

        "platforms": [
            {
                "type": "cytube",
                "name": "primary",
                "enabled": True,
                "domain": domain,
                "channel": channel,
                "user": user,
                "response_timeout": response_timeout,
                "restart_delay": restart_delay
            }
        ],

        "shell": {
            "enabled": True,
            "host": shell_host,
            "port": shell_port
        },

        "logging": {
            "level": log_level,
            "chat_log_file": chat_log_file,
            "media_log_file": media_log_file
        },

        "llm": llm,

        "plugins": {
            "enabled": True,
            "directory": "plugins/",
            "auto_reload": False
        }
    }

    return new_config


def main():
    parser = argparse.ArgumentParser(
        description='Migrate Rosey configuration from v1 to v2 format (Sprint 9)',
        epilog='See docs/sprints/active/9-The-Accountant/MIGRATION.md for details'
    )
    parser.add_argument('config_file', help='Path to config.json')
    parser.add_argument('--backup', action='store_true',
                       help='Backup original file to .json.bak')
    parser.add_argument('--output', help='Output file (default: overwrite input)')
    args = parser.parse_args()

    config_path = Path(args.config_file)

    if not config_path.exists():
        print(f"❌ Error: Config file not found: {config_path}")
        return 1

    # Load old config
    print(f"📂 Loading config: {config_path}")
    try:
        with open(config_path) as f:
            old_config = json.load(f)
    except json.JSONDecodeError as e:
        print(f"❌ Error: Invalid JSON in config file: {e}")
        return 1

    # Check if already v2
    if old_config.get('version') == '2.0':
        print("✅ Config is already v2 format. Nothing to do.")
        return 0

    # Backup if requested
    if args.backup:
        backup_path = config_path.with_suffix('.json.bak')
        print(f"💾 Backing up to: {backup_path}")
        shutil.copy2(config_path, backup_path)

    # Migrate
    print("🔄 Migrating config v1 → v2...")
    new_config = migrate_config_v1_to_v2(old_config)

    # Write output
    output_path = Path(args.output) if args.output else config_path
    print(f"💾 Writing new config: {output_path}")
    with open(output_path, 'w') as f:
        json.dump(new_config, f, indent=2)

    print("\n✅ Migration complete!")
    print("\n📋 Next steps:")
    print("1. Review the new config file and adjust settings as needed")
    print("2. Ensure NATS server is installed:")
    print("   - macOS: brew install nats-server")
    print("   - Linux: Download from https://github.com/nats-io/nats-server/releases")
    print("   - Windows: Download from https://github.com/nats-io/nats-server/releases")
    print("3. Start NATS server: nats-server")
    print("4. Start bot: python bot/rosey/rosey.py config.json")
    print("\n📖 For troubleshooting, see:")
    print("   docs/sprints/active/9-The-Accountant/MIGRATION.md")

    return 0


if __name__ == '__main__':
    exit(main())
