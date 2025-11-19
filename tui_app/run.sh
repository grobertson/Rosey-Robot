#!/bin/bash
# CyTube TUI Chat Client - Linux/Mac Launcher
# Automatically uses virtual environment if available

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$SCRIPT_DIR/.."

cd "$PROJECT_ROOT"

# Check if virtual environment exists
if [ -f ".venv/bin/python" ]; then
    echo "Using virtual environment..."
    .venv/bin/python -m tui_app tui_app/configs/config.yaml
else
    echo "Using system Python..."
    python3 -m tui_app tui_app/configs/config.yaml
fi
