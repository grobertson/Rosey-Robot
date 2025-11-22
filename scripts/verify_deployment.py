#!/usr/bin/env python3
"""
Deployment verification script for Rosey Bot.

Verifies that a deployment is healthy and ready to serve traffic.
Runs a series of checks against the deployed bot instance.

Usage:
    python scripts/verify_deployment.py --env test
    python scripts/verify_deployment.py --env prod --json
"""

import argparse
import json
import subprocess
import sys
import time
from typing import Tuple

import requests

# Exit codes
EXIT_SUCCESS = 0
EXIT_PROCESS_CHECK_FAILED = 1
EXIT_CONNECTION_CHECK_FAILED = 2
EXIT_DATABASE_CHECK_FAILED = 3
EXIT_HEALTH_ENDPOINT_FAILED = 6
EXIT_RESPONSE_TIME_FAILED = 5

# Colors for terminal output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
NC = '\033[0m'  # No Color


class DeploymentVerifier:
    """Verifies deployment health across multiple checks."""

    def __init__(self, environment: str, json_output: bool = False):
        self.environment = environment
        self.json_output = json_output
        self.results = []
        self.failed = False
        self.exit_code = EXIT_SUCCESS

        # Environment-specific settings
        if environment == 'prod':
            self.health_port = 8000
            self.response_threshold_ms = 1000  # Stricter for prod
        else:
            self.health_port = 8001
            self.response_threshold_ms = 2000

    def print_status(self, status: str, message: str, color: str = NC):
        """Print status message (unless JSON mode)."""
        if not self.json_output:
            print(f"{color}{status}{NC} {message}")

    def verify_process(self) -> Tuple[bool, str]:
        """Check if bot process is running."""
        try:
            result = subprocess.run(
                ['pgrep', '-f', 'python.*bot.py'],
                capture_output=True,
                text=True
            )

            if result.returncode == 0:
                pid = result.stdout.strip()
                return True, f"Bot process running (PID: {pid})"
            else:
                return False, "Bot process not found"
        except Exception as e:
            return False, f"Process check failed: {str(e)}"

    def verify_health_endpoint(self) -> Tuple[bool, str]:
        """Check if health endpoint is responding."""
        try:
            url = f"http://localhost:{self.health_port}/api/health"
            response = requests.get(url, timeout=5)
            response.raise_for_status()

            data = response.json()
            status = data.get('status', 'unknown')

            if status == 'running':
                return True, f"Health endpoint healthy (status: {status})"
            else:
                return False, f"Health endpoint reports: {status}"
        except requests.exceptions.ConnectionError:
            return False, f"Cannot connect to health endpoint (port {self.health_port})"
        except requests.exceptions.Timeout:
            return False, "Health endpoint timeout"
        except Exception as e:
            return False, f"Health check failed: {str(e)}"

    def verify_connection(self) -> Tuple[bool, str]:
        """Check if bot is connected to CyTube."""
        try:
            url = f"http://localhost:{self.health_port}/api/health"
            response = requests.get(url, timeout=5)
            response.raise_for_status()

            data = response.json()
            connected = data.get('connected', False)

            if connected:
                channel = data.get('channel', 'unknown')
                return True, f"Connected to CyTube (channel: {channel})"
            else:
                return False, "Not connected to CyTube"
        except Exception as e:
            return False, f"Connection check failed: {str(e)}"

    def verify_database(self) -> Tuple[bool, str]:
        """Check if database is accessible (placeholder)."""
        # For now, assume no database or always pass
        # Will be implemented when database is added
        return True, "Database check skipped (not implemented)"

    def verify_response_time(self) -> Tuple[bool, str]:
        """Check if response time is acceptable."""
        try:
            url = f"http://localhost:{self.health_port}/api/health"

            total_time = 0
            samples = 5

            for _ in range(samples):
                start = time.time()
                response = requests.get(url, timeout=5)
                response.raise_for_status()
                elapsed = (time.time() - start) * 1000  # Convert to ms
                total_time += elapsed
                time.sleep(0.5)  # Small delay between samples

            avg_time = total_time / samples

            if avg_time < self.response_threshold_ms:
                return True, f"Response time OK ({avg_time:.1f}ms avg, threshold: {self.response_threshold_ms}ms)"
            else:
                return False, f"Response time too slow ({avg_time:.1f}ms avg, threshold: {self.response_threshold_ms}ms)"
        except Exception as e:
            return False, f"Response time check failed: {str(e)}"

    def run_all_verifications(self) -> bool:
        """Run all verification checks."""
        checks = [
            ("Process Check", self.verify_process, EXIT_PROCESS_CHECK_FAILED),
            ("Database Check", self.verify_database, EXIT_DATABASE_CHECK_FAILED),
            ("Health Endpoint", self.verify_health_endpoint, EXIT_HEALTH_ENDPOINT_FAILED),
            ("CyTube Connection", self.verify_connection, EXIT_CONNECTION_CHECK_FAILED),
            ("Response Time", self.verify_response_time, EXIT_RESPONSE_TIME_FAILED),
        ]

        if not self.json_output:
            print(f"\n{BLUE}════════════════════════════════════════════{NC}")
            print(f"{BLUE}  Deployment Verification - {self.environment.upper()}{NC}")
            print(f"{BLUE}════════════════════════════════════════════{NC}\n")

        all_passed = True

        for check_name, check_func, exit_code in checks:
            success, message = check_func()

            self.results.append({
                'check': check_name,
                'passed': success,
                'message': message
            })

            if success:
                self.print_status("✓", f"{check_name}: {message}", GREEN)
            else:
                self.print_status("✗", f"{check_name}: {message}", RED)
                all_passed = False
                self.failed = True
                if self.exit_code == EXIT_SUCCESS:
                    self.exit_code = exit_code

        if not self.json_output:
            print()
            if all_passed:
                print(f"{GREEN}✓ All verification checks passed{NC}")
            else:
                print(f"{RED}✗ Some verification checks failed{NC}")
            print()

        return all_passed

    def get_exit_code(self) -> int:
        """Get the exit code based on verification results."""
        return self.exit_code

    def output_json(self):
        """Output results as JSON."""
        output = {
            'environment': self.environment,
            'passed': not self.failed,
            'checks': self.results,
            'exit_code': self.exit_code
        }
        print(json.dumps(output, indent=2))


def main():
    parser = argparse.ArgumentParser(description='Verify bot deployment')
    parser.add_argument('--env', required=True, choices=['test', 'prod'],
                        help='Environment to verify')
    parser.add_argument('--json', action='store_true',
                        help='Output results as JSON')

    args = parser.parse_args()

    verifier = DeploymentVerifier(args.env, json_output=args.json)

    verifier.run_all_verifications()

    if args.json:
        verifier.output_json()

    sys.exit(verifier.get_exit_code())


if __name__ == '__main__':
    main()
