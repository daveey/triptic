"""Pytest configuration and fixtures for triptic tests."""

import os
import socket
import subprocess
import time
from pathlib import Path

import pytest


def is_port_open(port: int, timeout: float = 0.5) -> bool:
    """Check if a port is open on localhost."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        result = sock.connect_ex(('localhost', port))
        return result == 0
    finally:
        sock.close()


@pytest.fixture(scope="session", autouse=True)
def test_server(request):
    """Start a test server on port 3001 for frontend tests.

    This fixture automatically starts before any tests run and stops after all tests complete.
    Uses port 3001 to avoid conflicts with the production server on port 3000.

    Only starts the server if playwright tests are being run.
    """
    # Check if we're running playwright tests
    # Skip server setup if no playwright tests in this session
    test_items = [item.nodeid for item in request.session.items]
    has_playwright_tests = any('playwright' in nodeid.lower() for nodeid in test_items)

    if not has_playwright_tests:
        print("\n[test] No playwright tests detected, skipping test server")
        yield
        return

    test_port = 3001

    # Check if server is already running on test port
    if is_port_open(test_port):
        # Server already running on test port, use it
        print(f"\n[test] Using existing server on port {test_port}")
        yield
        return

    # Start test server in background
    print(f"\n[test] Starting test server on port {test_port}...")

    # Use a test-specific database
    test_db = Path.home() / ".triptic" / "triptic_test.db"
    env = os.environ.copy()
    env['TRIPTIC_DB_PATH'] = str(test_db)
    # Remove auth vars so server runs without authentication
    env.pop('TRIPTIC_AUTH_USERNAME', None)
    env.pop('TRIPTIC_AUTH_PASSWORD', None)

    try:
        # For daemon mode, don't pipe stdout/stderr as it can cause blocking
        # when the parent process exits and child takes over
        process = subprocess.Popen(
            ["uv", "run", "triptic", "start", "--port", str(test_port), "--daemon"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=env
        )

        # Wait a moment for daemon to spawn
        time.sleep(2)

        # Wait for server to start accepting connections
        max_wait = 10  # seconds
        start_time = time.time()
        while time.time() - start_time < max_wait:
            if is_port_open(test_port):
                print(f"[test] Test server started successfully on port {test_port}")
                break
            time.sleep(0.5)
        else:
            raise RuntimeError(
                f"Test server failed to start on port {test_port} within {max_wait} seconds"
            )

        yield

    finally:
        # Stop test server
        print(f"\n[test] Stopping test server on port {test_port}...")
        try:
            result = subprocess.run(
                ["uv", "run", "triptic", "stop", "--port", str(test_port)],
                capture_output=True,
                timeout=5,
                env=env
            )
            if result.returncode == 0:
                print("[test] Test server stopped successfully")
            else:
                print(f"[test] Warning: stop command returned {result.returncode}")
        except subprocess.TimeoutExpired:
            print("[test] Warning: stop command timed out")
        except Exception as e:
            print(f"[test] Warning: error stopping test server: {e}")
