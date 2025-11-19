@echo off
REM CyTube TUI Chat Client - Windows Launcher
REM Automatically uses virtual environment if available

cd /d "%~dp0.."

REM Check if virtual environment exists
if exist ".venv\Scripts\python.exe" (
    echo Using virtual environment...
    .venv\Scripts\python.exe -m tui_app tui_app\configs\config.yaml
) else (
    echo Using system Python...
    python -m tui_app tui_app\configs\config.yaml
)

pause
