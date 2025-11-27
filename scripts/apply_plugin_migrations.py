#!/usr/bin/env python3
"""
Apply plugin migrations via NATS for CI testing.

This script connects to NATS and applies migrations for specified plugins.
Used in CI to ensure database schema is up-to-date before running tests.
"""
import asyncio
import json
import sys

import nats


async def apply_migrations(namespace: str, nats_url: str = "nats://localhost:4222") -> bool:
    """
    Apply migrations for a plugin namespace.

    Args:
        namespace: Plugin namespace (e.g., "quote-db")
        nats_url: NATS server URL

    Returns:
        True if migrations applied successfully, False otherwise
    """
    try:
        # Connect to NATS
        nc = await nats.connect(nats_url, connect_timeout=10.0)
        print(f"✓ Connected to NATS at {nats_url}")

        # Apply migrations
        subject = f"rosey.db.migrate.{namespace}.apply"
        request_data = json.dumps({"target_version": "latest"}).encode()

        print(f"Requesting migration apply for '{namespace}'...")
        print(f"  Subject: {subject}")
        print(f"  Request: {request_data.decode()}")

        response = await nc.request(subject, request_data, timeout=30.0)
        result = json.loads(response.data.decode())

        print(f"✓ Migration response: {json.dumps(result, indent=2)}")

        if result.get("success"):
            applied = result.get("applied_migrations", [])
            if applied:
                print(f"✓ Applied {len(applied)} migrations:")
                for migration in applied:
                    print(f"  - v{migration['version']}: {migration['name']}")
            else:
                print("✓ No new migrations to apply (already up-to-date)")

            current = result.get("current_version", 0)
            print(f"✓ Current schema version: {current}")
            await nc.close()
            return True
        else:
            error = result.get("error", {})
            error_code = error.get("code", "unknown") if isinstance(error, dict) else str(error)
            error_msg = error.get("message", "unknown error") if isinstance(error, dict) else str(error)
            print(f"✗ Migration failed: {error_msg}", file=sys.stderr)
            print(f"  Error code: {error_code}", file=sys.stderr)
            print(f"  Full error response: {json.dumps(result, indent=2)}", file=sys.stderr)
            await nc.close()
            return False

    except asyncio.TimeoutError:
        print("✗ Timeout waiting for response from database service", file=sys.stderr)
        print(f"  Make sure the database service is running and responding to {subject}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"✗ Error applying migrations: {e}", file=sys.stderr)
        return False


async def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python apply_plugin_migrations.py <namespace> [nats_url]")
        print("Example: python apply_plugin_migrations.py quote-db nats://localhost:4222")
        sys.exit(1)

    namespace = sys.argv[1]
    nats_url = sys.argv[2] if len(sys.argv) > 2 else "nats://localhost:4222"

    print(f"Applying migrations for plugin: {namespace}")
    success = await apply_migrations(namespace, nats_url)

    if success:
        print(f"\n✓ Migrations applied successfully for '{namespace}'")
        sys.exit(0)
    else:
        print(f"\n✗ Failed to apply migrations for '{namespace}'", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
