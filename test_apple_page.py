"""
Test loading apple asset group page to see what breaks.
"""

from playwright.sync_api import sync_playwright
from pathlib import Path
import os
import time


def load_env_file():
    """Load environment variables from .env file."""
    env_file = Path.cwd() / '.env'
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    if '=' in line:
                        key, value = line.split('=', 1)
                        os.environ[key] = value


def test_apple_page():
    """Test apple asset group page."""

    load_env_file()

    username = os.environ.get('TRIPTIC_AUTH_USERNAME')
    password = os.environ.get('TRIPTIC_AUTH_PASSWORD')

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            http_credentials={
                "username": username,
                "password": password
            }
        )
        page = context.new_page()

        # Capture console messages and errors
        console_messages = []
        page.on("console", lambda msg: console_messages.append({
            'type': msg.type,
            'text': msg.text
        }))

        errors = []
        page.on("pageerror", lambda err: errors.append(str(err)))

        print("=" * 80)
        print("TESTING APPLE ASSET GROUP PAGE")
        print("=" * 80)

        print("\nLoading http://localhost:3000/asset_group.html?id=apple...")

        try:
            page.goto('http://localhost:3000/asset_group.html?id=apple', timeout=10000)
            page.wait_for_load_state('networkidle', timeout=10000)
            print("✓ Page loaded successfully")
        except Exception as e:
            print(f"✗ Page failed to load: {e}")

        # Wait a bit to let any JS errors surface
        time.sleep(2)

        # Check for errors
        print("\n--- Page Errors ---")
        if errors:
            for err in errors:
                print(f"ERROR: {err}")
        else:
            print("No page errors")

        print("\n--- Console Messages ---")
        error_logs = [msg for msg in console_messages if msg['type'] == 'error']
        if error_logs:
            for msg in error_logs:
                print(f"CONSOLE ERROR: {msg['text']}")
        else:
            print("No console errors")

        # Take screenshot
        page.screenshot(path='/tmp/apple_page.png', full_page=True)
        print(f"\nScreenshot saved: /tmp/apple_page.png")

        print("\n" + "=" * 80)

        time.sleep(2)
        browser.close()


if __name__ == '__main__':
    test_apple_page()
