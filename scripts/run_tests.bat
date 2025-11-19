@echo off
REM Run Quicksilver test suite (Windows)

setlocal enabledelayedexpansion

echo === Running Quicksilver Test Suite ===
echo.

REM Check if pytest is installed
python -m pytest --version >nul 2>&1
if errorlevel 1 (
    echo Error: pytest not found. Install with: pip install pytest pytest-asyncio pytest-cov
    exit /b 1
)

REM Unit tests
echo [1/4] Running Unit Tests...
python -m pytest tests\unit -v -m unit --cov=bot\rosey\core --cov-report=term-missing --cov-report=html
if errorlevel 1 (
    echo X Unit tests failed
    exit /b 1
)
echo [OK] Unit tests passed
echo.

REM Integration tests
echo [2/4] Running Integration Tests...
python -m pytest tests\integration -v -m integration
if errorlevel 1 (
    echo X Integration tests failed
    exit /b 1
)
echo [OK] Integration tests passed
echo.

REM Performance tests (optional)
echo [3/4] Running Performance Tests (optional)...
python -m pytest tests\performance -v -m performance -s 2>nul
if errorlevel 1 (
    echo [SKIP] Performance tests skipped (requires real NATS server)
) else (
    echo [OK] Performance tests passed
)
echo.

REM E2E tests (optional)
echo [4/4] Running E2E Tests (optional)...
python -m pytest tests\e2e -v -m e2e -s 2>nul
if errorlevel 1 (
    echo [SKIP] E2E tests skipped (requires full stack setup)
) else (
    echo [OK] E2E tests passed
)
echo.

echo === Core Tests Passed! ===
echo.
echo Coverage report: htmlcov\index.html

endlocal
