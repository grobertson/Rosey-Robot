@echo off
REM Run Performance Benchmarks and Generate Report
REM Sprint 10 Sortie 4

echo Running Performance Benchmarks...
echo ==================================
echo.

REM Check for NATS
powershell -Command "if (!(Test-NetConnection -ComputerName localhost -Port 4222 -InformationLevel Quiet)) { Write-Host 'ERROR: NATS server not running'; exit 1 }"
if %ERRORLEVEL% NEQ 0 (
    echo Start NATS with: docker run -d -p 4222:4222 nats:2.10-alpine
    exit /b 1
)

echo NATS server detected
echo.

echo Executing benchmarks...
pytest tests/performance/test_nats_overhead.py -v -s --json-report --json-report-file=benchmark_results.json --tb=short

if %ERRORLEVEL% NEQ 0 (
    echo Benchmark execution failed
    exit /b 1
)

echo.
echo Generating report...
python tests/performance/generate_report.py benchmark_results.json

echo.
echo Benchmark complete!
echo Report: tests\performance\BENCHMARK_RESULTS.md
echo.
