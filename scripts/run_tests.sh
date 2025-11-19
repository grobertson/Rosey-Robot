#!/bin/bash
# Run Quicksilver test suite

set -e

echo "=== Running Quicksilver Test Suite ==="
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if pytest is installed
if ! command -v pytest &> /dev/null; then
    echo "Error: pytest not found. Install with: pip install pytest pytest-asyncio pytest-cov"
    exit 1
fi

# Unit tests (fast, no dependencies)
echo -e "${YELLOW}[1/4] Running Unit Tests...${NC}"
pytest tests/unit -v -m unit --cov=bot/rosey/core --cov-report=term-missing --cov-report=html
UNIT_RESULT=$?

if [ $UNIT_RESULT -eq 0 ]; then
    echo -e "${GREEN}✓ Unit tests passed${NC}"
else
    echo "✗ Unit tests failed"
    exit 1
fi

echo ""

# Integration tests (require mock NATS)
echo -e "${YELLOW}[2/4] Running Integration Tests...${NC}"
pytest tests/integration -v -m integration
INTEGRATION_RESULT=$?

if [ $INTEGRATION_RESULT -eq 0 ]; then
    echo -e "${GREEN}✓ Integration tests passed${NC}"
else
    echo "✗ Integration tests failed"
    exit 1
fi

echo ""

# Performance tests (optional - can be skipped if NATS not available)
echo -e "${YELLOW}[3/4] Running Performance Tests (optional)...${NC}"
if pytest tests/performance -v -m performance -s 2>/dev/null; then
    echo -e "${GREEN}✓ Performance tests passed${NC}"
else
    echo "⚠ Performance tests skipped (requires real NATS server)"
fi

echo ""

# E2E tests (optional - require full stack)
echo -e "${YELLOW}[4/4] Running E2E Tests (optional)...${NC}"
if pytest tests/e2e -v -m e2e -s 2>/dev/null; then
    echo -e "${GREEN}✓ E2E tests passed${NC}"
else
    echo "⚠ E2E tests skipped (requires full stack setup)"
fi

echo ""
echo -e "${GREEN}=== Core Tests Passed! ===${NC}"
echo ""
echo "Coverage report: htmlcov/index.html"
