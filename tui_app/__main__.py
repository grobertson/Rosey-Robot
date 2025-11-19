#!/usr/bin/env python3
"""Entry point for running the CyTube TUI as a standalone application."""

import sys
import asyncio
from pathlib import Path

# Add parent directory to path to access lib and common
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from tui_app import TUIBot
from common import get_config


def main():
    """Main entry point for the TUI application."""
    # Check for config file argument
    if len(sys.argv) < 2:
        print("Usage: python -m tui_app <config.yaml|config.json>")
        print("")
        print("Example config location: tui_app/configs/config.yaml.example")
        sys.exit(1)
    
    config_file = sys.argv[1]
    
    # Load configuration
    try:
        config = get_config(config_file)
    except Exception as e:
        print(f"Error loading config: {e}")
        sys.exit(1)
    
    # Extract TUI-specific config
    tui_config = config.pop('tui', {})
    
    # Create and run bot
    bot = TUIBot(config_file, tui_config=tui_config, **config)
    
    try:
        asyncio.run(bot.run_tui())
    except KeyboardInterrupt:
        print("\nShutting down...")
    except Exception as e:
        print(f"\nFatal error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
