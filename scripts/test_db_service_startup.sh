#!/bin/bash
# Test script to verify database service startup
# This mimics what the CI does

set -x  # Print commands
set -e  # Exit on error

echo "=== Testing Database Service Startup ==="

# Start NATS if not running (CI has it as a service)
echo "Checking NATS..."
if ! nc -z localhost 4222 2>/dev/null; then
    echo "NATS not running on 4222"
    exit 1
fi

echo "NATS is accessible on port 4222"

# Start database service
echo "Starting database service..."
nohup python -m common.database_service --db-path test_bot_data.db --nats-url nats://localhost:4222 --log-level INFO > /tmp/db_service.log 2>&1 &
DB_PID=$!
echo $DB_PID > /tmp/db_service.pid
echo "Started with PID: $DB_PID"

# Wait and verify
echo "Waiting 10 seconds for startup..."
sleep 10

# Check if process is still running
if ! ps -p $DB_PID > /dev/null; then
    echo "❌ Database service is not running!"
    echo "Log output:"
    cat /tmp/db_service.log
    exit 1
fi

echo "✓ Database service is running"
echo "First 20 lines of log:"
head -n 20 /tmp/db_service.log

# Test NATS connectivity
echo "Testing NATS subscription count..."
curl -s http://localhost:8222/subsz | grep -o '"num_subscriptions":[0-9]*' || echo "Could not query NATS"

# Kill service
echo "Stopping service..."
kill $DB_PID
sleep 2

echo "=== Test Complete ==="
