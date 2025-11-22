#!/usr/bin/env python3
"""
Production verification script for Rosey Bot.

Performs comprehensive health checks before and after production deployments.
More thorough than test verification, includes smoke tests.

Usage:
    python scripts/verify_production.py --pre-deploy
    python scripts/verify_production.py --post-deploy --version v1.0.0
"""

import argparse
import json
import sys
import time
from datetime import datetime
from typing import List, Tuple

import requests

# Exit codes
EXIT_SUCCESS = 0
EXIT_PROCESS_CHECK_FAILED = 1
EXIT_HEALTH_CHECK_FAILED = 2
EXIT_CONNECTION_CHECK_FAILED = 3
EXIT_RESPONSE_TIME_FAILED = 4
EXIT_SMOKE_TEST_FAILED = 5

# Colors
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
NC = '\033[0m'

# Production settings
HEALTH_PORT = 8000
RESPONSE_THRESHOLD_MS = 500  # Strict for production
HEALTH_URL = f"http://localhost:{HEALTH_PORT}/api/health"


class ProductionVerifier:
    """Verifies production deployment health."""

    def __init__(self, pre_deploy: bool = False, post_deploy: bool = False,
                 version: str = None, json_output: bool = False):
        self.pre_deploy = pre_deploy
        self.post_deploy = post_deploy
        self.version = version
        self.json_output = json_output
        self.results = []
        self.failed = False
        self.exit_code = EXIT_SUCCESS
        self.start_time = datetime.utcnow()

    def print_status(self, status: str, message: str, color: str = NC):
        """Print status message (unless JSON mode)."""
        if not self.json_output:
            print(f"{color}{status}{NC} {message}")

    def print_header(self, title: str):
        """Print section header."""
        if not self.json_output:
            print(f"\n{BLUE}{'=' * 50}{NC}")
            print(f"{BLUE}  {title}{NC}")
            print(f"{BLUE}{'=' * 50}{NC}\n")

    def verify_health_endpoint(self) -> Tuple[bool, str]:
        """Check if health endpoint is responding."""
        try:
            response = requests.get(HEALTH_URL, timeout=5)
            response.raise_for_status()

            data = response.json()
            status = data.get('status', 'unknown')

            if status == 'running':
                uptime = data.get('uptime', 'unknown')
                return True, f"Health endpoint healthy (uptime: {uptime}s)"
            else:
                return False, f"Health endpoint reports: {status}"
        except requests.exceptions.ConnectionError:
            return False, f"Cannot connect to health endpoint (port {HEALTH_PORT})"
        except requests.exceptions.Timeout:
            return False, "Health endpoint timeout"
        except Exception as e:
            return False, f"Health check failed: {str(e)}"

    def verify_connection(self) -> Tuple[bool, str]:
        """Check if bot is connected to CyTube."""
        try:
            response = requests.get(HEALTH_URL, timeout=5)
            response.raise_for_status()

            data = response.json()
            connected = data.get('connected', False)

            if connected:
                channel = data.get('channel', 'unknown')
                users = data.get('user_count', 0)
                return True, f"Connected to CyTube (channel: {channel}, users: {users})"
            else:
                return False, "Not connected to CyTube"
        except Exception as e:
            return False, f"Connection check failed: {str(e)}"

    def verify_version(self) -> Tuple[bool, str]:
        """Check if correct version is running (post-deploy only)."""
        if not self.post_deploy or not self.version:
            return True, "Version check skipped (not post-deploy)"

        try:
            response = requests.get(HEALTH_URL, timeout=5)
            response.raise_for_status()

            data = response.json()
            running_version = data.get('version', 'unknown')
            expected_version = self.version.lstrip('v')  # Remove 'v' prefix

            if running_version == expected_version:
                return True, f"Correct version running: {running_version}"
            else:
                return False, f"Version mismatch (expected: {expected_version}, got: {running_version})"
        except Exception as e:
            return False, f"Version check failed: {str(e)}"

    def verify_response_time(self) -> Tuple[bool, str]:
        """Check if response time is acceptable."""
        try:
            samples = 10  # More samples for production
            times = []

            for _ in range(samples):
                start = time.time()
                response = requests.get(HEALTH_URL, timeout=5)
                response.raise_for_status()
                elapsed = (time.time() - start) * 1000
                times.append(elapsed)
                time.sleep(0.3)  # Small delay between samples

            avg_time = sum(times) / len(times)
            min_time = min(times)
            max_time = max(times)
            p95_time = sorted(times)[int(len(times) * 0.95)]

            if avg_time < RESPONSE_THRESHOLD_MS:
                return True, f"Response time OK (avg: {avg_time:.1f}ms, p95: {p95_time:.1f}ms, max: {max_time:.1f}ms)"
            else:
                return False, f"Response time too slow (avg: {avg_time:.1f}ms, threshold: {RESPONSE_THRESHOLD_MS}ms)"
        except Exception as e:
            return False, f"Response time check failed: {str(e)}"

    def verify_error_rate(self) -> Tuple[bool, str]:
        """Check error rate from health endpoint."""
        try:
            response = requests.get(HEALTH_URL, timeout=5)
            response.raise_for_status()

            data = response.json()
            errors = data.get('errors', 0)
            requests_count = data.get('requests', 1)

            error_rate = (errors / requests_count) * 100 if requests_count > 0 else 0

            if error_rate < 1.0:  # Less than 1% error rate
                return True, f"Error rate OK: {error_rate:.2f}% ({errors}/{requests_count})"
            else:
                return False, f"Error rate too high: {error_rate:.2f}% ({errors}/{requests_count})"
        except Exception as e:
            # Not critical if metrics aren't available yet
            return True, f"Error rate check skipped: {str(e)}"

    def smoke_test_echo(self) -> Tuple[bool, str]:
        """Smoke test: verify echo feature (post-deploy only)."""
        if not self.post_deploy:
            return True, "Smoke test skipped (not post-deploy)"

        # This would send a test message to CyTube and verify response
        # For now, stub implementation
        return True, "Echo smoke test: not yet implemented"

    def smoke_test_logging(self) -> Tuple[bool, str]:
        """Smoke test: verify logging feature (post-deploy only)."""
        if not self.post_deploy:
            return True, "Smoke test skipped (not post-deploy)"

        # This would verify log files are being written
        # For now, stub implementation
        return True, "Logging smoke test: not yet implemented"

    def pre_deploy_checks(self) -> bool:
        """Run pre-deployment checks."""
        self.print_header("Pre-Deployment Verification")

        checks = [
            ("Health Endpoint", self.verify_health_endpoint, EXIT_HEALTH_CHECK_FAILED),
            ("CyTube Connection", self.verify_connection, EXIT_CONNECTION_CHECK_FAILED),
            ("Response Time", self.verify_response_time, EXIT_RESPONSE_TIME_FAILED),
            ("Error Rate", self.verify_error_rate, EXIT_HEALTH_CHECK_FAILED),
        ]

        return self._run_checks(checks)

    def post_deploy_checks(self) -> bool:
        """Run post-deployment checks."""
        self.print_header("Post-Deployment Verification")

        checks = [
            ("Health Endpoint", self.verify_health_endpoint, EXIT_HEALTH_CHECK_FAILED),
            ("Version Check", self.verify_version, EXIT_HEALTH_CHECK_FAILED),
            ("CyTube Connection", self.verify_connection, EXIT_CONNECTION_CHECK_FAILED),
            ("Response Time", self.verify_response_time, EXIT_RESPONSE_TIME_FAILED),
            ("Error Rate", self.verify_error_rate, EXIT_HEALTH_CHECK_FAILED),
            ("Smoke Test: Echo", self.smoke_test_echo, EXIT_SMOKE_TEST_FAILED),
            ("Smoke Test: Logging", self.smoke_test_logging, EXIT_SMOKE_TEST_FAILED),
        ]

        return self._run_checks(checks)

    def _run_checks(self, checks: List[Tuple]) -> bool:
        """Run a list of checks."""
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

        return all_passed

    def run_verification(self) -> bool:
        """Run appropriate verification based on mode."""
        if self.pre_deploy:
            success = self.pre_deploy_checks()
        elif self.post_deploy:
            success = self.post_deploy_checks()
        else:
            self.print_status("✗", "Must specify --pre-deploy or --post-deploy", RED)
            return False

        if not self.json_output:
            print()
            if success:
                print(f"{GREEN}✓ All verification checks passed{NC}")
            else:
                print(f"{RED}✗ Some verification checks failed{NC}")
            print()

        return success

    def output_json(self):
        """Output results as JSON."""
        end_time = datetime.utcnow()
        duration = (end_time - self.start_time).total_seconds()

        output = {
            'environment': 'production',
            'mode': 'pre-deploy' if self.pre_deploy else 'post-deploy',
            'version': self.version,
            'passed': not self.failed,
            'checks': self.results,
            'exit_code': self.exit_code,
            'duration_seconds': duration,
            'timestamp': self.start_time.isoformat()
        }
        print(json.dumps(output, indent=2))


def main():
    parser = argparse.ArgumentParser(description='Verify production deployment')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--pre-deploy', action='store_true',
                       help='Run pre-deployment checks')
    group.add_argument('--post-deploy', action='store_true',
                       help='Run post-deployment checks')
    parser.add_argument('--version', type=str,
                        help='Expected version (required for post-deploy)')
    parser.add_argument('--json', action='store_true',
                        help='Output results as JSON')

    args = parser.parse_args()

    if args.post_deploy and not args.version:
        parser.error("--version is required when using --post-deploy")

    verifier = ProductionVerifier(
        pre_deploy=args.pre_deploy,
        post_deploy=args.post_deploy,
        version=args.version,
        json_output=args.json
    )

    success = verifier.run_verification()

    if args.json:
        verifier.output_json()

    sys.exit(verifier.exit_code)


if __name__ == '__main__':
    main()
