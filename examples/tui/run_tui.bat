@echo off
REM CyTube TUI Bot Launcher
REM Starts the terminal UI chat client with the specified config

cd /d "%~dp0..\.."
.venv\Scripts\python.exe examples\tui\bot.py examples\tui\config.yaml
pause
